// ===========================================================================
// tv-webhook : TradingView -> Supabase webhook receiver for VP+ICT V1 bot.
//
// Flow:  validate token -> log signal -> risk checks (kill switch, hours,
//        allowed setups, daily trade cap, daily loss cap, pyramiding) ->
//        execute via broker (built-in PAPER broker simulates fills) ->
//        record order + position + daily P&L.
//
// Auth:  TradingView cannot send custom headers, so the shared secret is
//        accepted as ?token=... (query) OR {"token":"..."} in the JSON body,
//        compared against bot_config.webhook_token. verify_jwt is disabled
//        because this endpoint implements its own token auth.
//
// Expected body (from the Pine `alert()`):
//   {"strategy":"vp_ict_v1","action":"buy","price":18000.25,
//    "stop":17985,"tp1":18020,"tp2":18050,"setup":"...","token":"..."}
// ===========================================================================
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const todayUTC = () => new Date().toISOString().slice(0, 10); // YYYY-MM-DD

type Action = "buy" | "sell" | "close";

Deno.serve(async (req) => {
  // Health check.
  if (req.method === "GET") return json(200, { ok: true, service: "tv-webhook" });
  if (req.method !== "POST") return json(405, { error: "method_not_allowed" });

  // ---- Parse body -------------------------------------------------------
  let payload: Record<string, unknown>;
  const rawText = await req.text();
  try {
    payload = JSON.parse(rawText);
  } catch {
    return json(400, { error: "invalid_json", raw: rawText.slice(0, 500) });
  }

  // ---- Load config (single row) ----------------------------------------
  const { data: cfg, error: cfgErr } = await supabase
    .from("bot_config").select("*").eq("id", 1).single();
  if (cfgErr || !cfg) return json(500, { error: "config_unavailable" });

  // ---- Auth -------------------------------------------------------------
  const url = new URL(req.url);
  const token = url.searchParams.get("token") ?? (payload.token as string | undefined);
  if (!token || token !== cfg.webhook_token) {
    return json(401, { error: "unauthorized" });
  }

  // ---- Normalize signal -------------------------------------------------
  const action = String(payload.action ?? "").toLowerCase() as Action;
  if (!(["buy", "sell", "close"] as string[]).includes(action)) {
    return json(400, { error: "invalid_action", action: payload.action });
  }
  const num = (v: unknown) => (v === undefined || v === null ? null : Number(v));
  const setup = (payload.setup as string | undefined) ?? null;
  const symbol = cfg.symbol as string;
  const sourceIp = req.headers.get("x-forwarded-for");

  // ---- Log the signal (audit trail) ------------------------------------
  const { data: sig, error: sigErr } = await supabase.from("signals").insert({
    strategy: payload.strategy ?? null,
    action,
    price: num(payload.price),
    stop: num(payload.stop),
    tp1: num(payload.tp1),
    tp2: num(payload.tp2),
    setup,
    raw_payload: payload,
    source_ip: sourceIp,
    status: "received",
  }).select().single();
  if (sigErr || !sig) return json(500, { error: "signal_insert_failed", detail: sigErr?.message });

  const reject = async (reason: string) => {
    await supabase.from("signals").update({ status: "rejected", reject_reason: reason }).eq("id", sig.id);
    return json(200, { ok: true, signal_id: sig.id, status: "rejected", reason });
  };

  // ---- Risk checks ------------------------------------------------------
  if (!cfg.enabled) return await reject("bot_disabled");

  if (cfg.enforce_hours) {
    const now = new Date();
    const hhmm = now.toISOString().slice(11, 16); // HH:MM UTC
    const start = String(cfg.trading_start_utc).slice(0, 5);
    const end = String(cfg.trading_end_utc).slice(0, 5);
    if (hhmm < start || hhmm > end) return await reject(`outside_hours:${hhmm}`);
  }

  const allowed = (cfg.allowed_setups as string[]) ?? [];
  if (allowed.length > 0 && setup && !allowed.includes(setup)) {
    return await reject(`setup_not_allowed:${setup}`);
  }

  // Daily caps (ensure today's row exists).
  const day = todayUTC();
  await supabase.from("pnl_daily").upsert({ trade_date: day }, { onConflict: "trade_date", ignoreDuplicates: true });
  const { data: pnl } = await supabase.from("pnl_daily").select("*").eq("trade_date", day).single();
  if (pnl) {
    if (action !== "close" && pnl.trades >= cfg.max_trades_per_day) return await reject("max_trades_per_day");
    if (Number(pnl.realized_pnl) <= -Number(cfg.max_daily_loss_usd)) return await reject("max_daily_loss");
  }

  // Existing open position?
  const { data: openPos } = await supabase
    .from("positions").select("*").eq("symbol", symbol).eq("status", "open").maybeSingle();

  // ---- Routing ----------------------------------------------------------
  try {
    const pointValue = Number(cfg.point_value_usd);
    const qty = cfg.contracts_per_trade as number;

    // CLOSE (explicit) or reversal: flatten the open position first.
    const isReversal = openPos && action !== "close" && openPos.side !== action;
    if (action === "close" || isReversal) {
      if (!openPos) {
        if (action === "close") return await reject("no_open_position");
      } else {
        const exit = num(payload.price) ?? Number(openPos.avg_entry);
        const dir = openPos.side === "buy" ? 1 : -1;
        const realized = (exit - Number(openPos.avg_entry)) * dir * Number(openPos.qty) * pointValue;
        await executeFill(cfg.broker, { signal_id: sig.id, symbol, side: openPos.side === "buy" ? "sell" : "buy", qty: openPos.qty, price: exit });
        await supabase.from("positions").update({
          status: "closed", closed_at: new Date().toISOString(), exit_price: exit, realized_pnl: realized,
        }).eq("id", openPos.id);
        await bumpPnl(day, 0, realized);
        if (action === "close") {
          await supabase.from("signals").update({ status: "executed" }).eq("id", sig.id);
          return json(200, { ok: true, signal_id: sig.id, status: "executed", closed: openPos.id, realized_pnl: realized });
        }
      }
    }

    // Same-side duplicate without pyramiding -> reject.
    if (openPos && action !== "close" && openPos.side === action && !cfg.allow_pyramiding) {
      return await reject("position_already_open");
    }

    // OPEN a new position (buy/sell).
    const entry = num(payload.price);
    if (entry === null) return await reject("missing_entry_price");
    const order = await executeFill(cfg.broker, { signal_id: sig.id, symbol, side: action as "buy" | "sell", qty, price: entry });
    const { data: pos } = await supabase.from("positions").insert({
      signal_id: sig.id, symbol, side: action, qty, avg_entry: order.filled_price,
      stop: num(payload.stop), tp1: num(payload.tp1), tp2: num(payload.tp2), setup, status: "open",
    }).select().single();
    await bumpPnl(day, 1, 0);
    await supabase.from("signals").update({ status: "executed" }).eq("id", sig.id);
    return json(200, { ok: true, signal_id: sig.id, status: "executed", order_id: order.id, position_id: pos?.id });
  } catch (e) {
    await supabase.from("signals").update({ status: "error", reject_reason: String(e) }).eq("id", sig.id);
    return json(500, { error: "execution_failed", detail: String(e) });
  }
});

// ---------------------------------------------------------------------------
// Broker abstraction. Today only the PAPER broker is implemented (fills at the
// requested price). Add `case "tradovate":` / `case "ibkr":` here later.
// ---------------------------------------------------------------------------
async function executeFill(
  broker: string,
  o: { signal_id: string; symbol: string; side: "buy" | "sell"; qty: number; price: number },
) {
  let status = "filled";
  let filledPrice: number | null = o.price;
  let raw: Record<string, unknown> = { broker };

  switch (broker) {
    case "paper":
      raw = { broker: "paper", simulated: true };
      break;
    // case "tradovate": ... place real order, set status/filledPrice/raw ...
    default:
      status = "error";
      filledPrice = null;
      raw = { broker, error: "broker_not_implemented" };
  }

  const { data: order, error } = await supabase.from("orders").insert({
    signal_id: o.signal_id, broker, symbol: o.symbol, side: o.side, qty: o.qty,
    order_type: "market", status, submitted_at: new Date().toISOString(),
    filled_at: status === "filled" ? new Date().toISOString() : null,
    filled_qty: status === "filled" ? o.qty : 0, filled_price: filledPrice, raw_response: raw,
  }).select().single();
  if (error || !order) throw new Error(`order_insert_failed: ${error?.message}`);
  if (status !== "filled") throw new Error(`broker_not_implemented: ${broker}`);
  return order;
}

async function bumpPnl(day: string, addTrades: number, addPnl: number) {
  const { data: row } = await supabase.from("pnl_daily").select("*").eq("trade_date", day).single();
  await supabase.from("pnl_daily").update({
    trades: Number(row?.trades ?? 0) + addTrades,
    realized_pnl: Number(row?.realized_pnl ?? 0) + addPnl,
    updated_at: new Date().toISOString(),
  }).eq("trade_date", day);
}
