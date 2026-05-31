// ===========================================================================
// tv-webhook : TradingView -> Supabase paper-trading engine for VP+ICT V1.
//
// Actions (JSON body, plus shared-secret `token`):
//   buy  / sell  -> open (or reverse) a position; applies entry slippage
//   close        -> flatten the open position (market, adverse slippage)
//   mark         -> price heartbeat: mark-to-market + auto SL/TP exits
//                   body: {"action":"mark","price":18010,"high":18012,"low":18007}
//
// Fill realism comes from bot_config: slippage_ticks * tick_size on
// market/stop fills, and commission_per_side_usd (round-turn = 2x) booked at
// exit. Take-profit fills are treated as limits (no adverse slippage).
//
// Auth: token via ?token=... (query) or {"token":"..."} (body), compared to
// bot_config.webhook_token. verify_jwt is disabled (custom token auth).
// ===========================================================================
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const todayUTC = () => new Date().toISOString().slice(0, 10);
const nowISO = () => new Date().toISOString();
const num = (v: unknown) => (v === undefined || v === null ? null : Number(v));

type Cfg = Record<string, any>;
type Pos = Record<string, any>;

Deno.serve(async (req) => {
  if (req.method === "GET") return json(200, { ok: true, service: "tv-webhook" });
  if (req.method !== "POST") return json(405, { error: "method_not_allowed" });

  let payload: Record<string, unknown>;
  const rawText = await req.text();
  try { payload = JSON.parse(rawText); }
  catch { return json(400, { error: "invalid_json", raw: rawText.slice(0, 500) }); }

  const { data: cfg, error: cfgErr } = await supabase.from("bot_config").select("*").eq("id", 1).single();
  if (cfgErr || !cfg) return json(500, { error: "config_unavailable" });

  // ---- Auth -------------------------------------------------------------
  const url = new URL(req.url);
  const token = url.searchParams.get("token") ?? (payload.token as string | undefined);
  if (!token || token !== cfg.webhook_token) return json(401, { error: "unauthorized" });

  const action = String(payload.action ?? "").toLowerCase();
  const symbol = cfg.symbol as string;

  // ---- mark: price heartbeat -> mark-to-market + auto SL/TP --------------
  // Not logged as a signal (would be too noisy) and bypasses the kill switch
  // so risk management keeps running even when new entries are disabled.
  if (action === "mark") {
    const price = num(payload.price);
    if (price === null) return json(400, { error: "missing_price" });
    const high = num(payload.high) ?? price;
    const low = num(payload.low) ?? price;
    await supabase.from("market").upsert({ symbol, last_price: price, high, low, updated_at: nowISO() });
    const result = await manageOpenPosition(cfg, symbol, price, high, low);
    return json(200, { ok: true, action: "mark", ...result });
  }

  if (!(["buy", "sell", "close"].includes(action))) {
    return json(400, { error: "invalid_action", action: payload.action });
  }

  const setup = (payload.setup as string | undefined) ?? null;

  // ---- Log the signal (audit trail) ------------------------------------
  const { data: sig, error: sigErr } = await supabase.from("signals").insert({
    strategy: payload.strategy ?? null, action, price: num(payload.price), stop: num(payload.stop),
    tp1: num(payload.tp1), tp2: num(payload.tp2), setup, raw_payload: payload,
    source_ip: req.headers.get("x-forwarded-for"), status: "received",
  }).select().single();
  if (sigErr || !sig) return json(500, { error: "signal_insert_failed", detail: sigErr?.message });

  const reject = async (reason: string) => {
    await supabase.from("signals").update({ status: "rejected", reject_reason: reason }).eq("id", sig.id);
    return json(200, { ok: true, signal_id: sig.id, status: "rejected", reason });
  };

  // ---- Risk checks ------------------------------------------------------
  if (!cfg.enabled) return await reject("bot_disabled");

  if (cfg.enforce_hours) {
    const hhmm = nowISO().slice(11, 16);
    if (hhmm < String(cfg.trading_start_utc).slice(0, 5) || hhmm > String(cfg.trading_end_utc).slice(0, 5)) {
      return await reject(`outside_hours:${hhmm}`);
    }
  }

  const allowed = (cfg.allowed_setups as string[]) ?? [];
  if (allowed.length > 0 && setup && !allowed.includes(setup)) return await reject(`setup_not_allowed:${setup}`);

  const day = todayUTC();
  await supabase.from("pnl_daily").upsert({ trade_date: day }, { onConflict: "trade_date", ignoreDuplicates: true });
  const { data: pnl } = await supabase.from("pnl_daily").select("*").eq("trade_date", day).single();
  if (pnl) {
    if (action !== "close" && pnl.trades >= cfg.max_trades_per_day) return await reject("max_trades_per_day");
    if (Number(pnl.realized_pnl) <= -Number(cfg.max_daily_loss_usd)) return await reject("max_daily_loss");
  }

  const { data: openPos } = await supabase
    .from("positions").select("*").eq("symbol", symbol).eq("status", "open").maybeSingle();

  // ---- Routing ----------------------------------------------------------
  try {
    // CLOSE or reversal: flatten first (market exit, adverse slippage).
    const isReversal = openPos && action !== "close" && openPos.side !== action;
    if (action === "close" || isReversal) {
      if (!openPos) {
        if (action === "close") return await reject("no_open_position");
      } else {
        const exitRaw = num(payload.price) ?? Number(openPos.avg_entry);
        const realized = await closePosition(cfg, openPos, exitRaw, action === "close" ? "manual_close" : "reversal", "adverse");
        if (action === "close") {
          await supabase.from("signals").update({ status: "executed" }).eq("id", sig.id);
          return json(200, { ok: true, signal_id: sig.id, status: "executed", closed: openPos.id, realized_pnl: realized });
        }
      }
    }

    if (openPos && action !== "close" && openPos.side === action && !cfg.allow_pyramiding) {
      return await reject("position_already_open");
    }

    // OPEN (buy/sell) with entry slippage.
    const entryRaw = num(payload.price);
    if (entryRaw === null) return await reject("missing_entry_price");
    const fill = applySlippage(cfg, action as "buy" | "sell", entryRaw); // entry: buy fills higher, sell lower
    const order = await insertOrder(cfg.broker, sig.id, symbol, action as "buy" | "sell", cfg.contracts_per_trade, fill, { reason: "entry" });
    const { data: pos } = await supabase.from("positions").insert({
      signal_id: sig.id, symbol, side: action, qty: cfg.contracts_per_trade, avg_entry: order.filled_price,
      stop: num(payload.stop), tp1: num(payload.tp1), tp2: num(payload.tp2), setup, status: "open",
      last_price: order.filled_price, unrealized_pnl: 0,
    }).select().single();
    await bumpPnl(day, 1, 0);
    await supabase.from("signals").update({ status: "executed" }).eq("id", sig.id);
    return json(200, { ok: true, signal_id: sig.id, status: "executed", order_id: order.id, position_id: pos?.id, fill });
  } catch (e) {
    await supabase.from("signals").update({ status: "error", reject_reason: String(e) }).eq("id", sig.id);
    return json(500, { error: "execution_failed", detail: String(e) });
  }
});

// ---------------------------------------------------------------------------
// Position management on a price 'mark': SL/TP auto-exits + partial TP.
// Stop is checked first (conservative when a bar hits both stop and target).
// ---------------------------------------------------------------------------
async function manageOpenPosition(cfg: Cfg, symbol: string, price: number, high: number, low: number) {
  const { data: pos } = await supabase
    .from("positions").select("*").eq("symbol", symbol).eq("status", "open").maybeSingle();
  if (!pos) return { managed: false, open_positions: 0 };

  const pv = Number(cfg.point_value_usd);
  const dir = pos.side === "buy" ? 1 : -1;
  const long = pos.side === "buy";
  const stop = num(pos.stop), tp1 = num(pos.tp1), tp2 = num(pos.tp2);

  // 1) Stop loss (stop order -> adverse slippage).
  if (stop !== null && ((long && low <= stop) || (!long && high >= stop))) {
    const realized = await closePosition(cfg, pos, stop, pos.tp1_filled ? "stop_runner" : "stop", "adverse");
    return { managed: true, event: "stop", realized_pnl: realized };
  }

  // 2) Take profit (limit -> no adverse slippage).
  const tp1Hit = tp1 !== null && ((long && high >= tp1) || (!long && low <= tp1));
  const tp2Hit = tp2 !== null && ((long && high >= tp2) || (!long && low <= tp2));

  if (!pos.tp1_filled && tp1Hit) {
    if (Number(pos.qty) > 1 && tp2 !== null) {
      // Scale out half at tp1, move stop to breakeven, let the runner go.
      const closeQty = Math.floor(Number(pos.qty) / 2);
      const realized = await partialClose(cfg, pos, closeQty, tp1, "tp1_partial");
      return { managed: true, event: "tp1_partial", closed_qty: closeQty, realized_pnl: realized };
    }
    const realized = await closePosition(cfg, pos, tp1, "tp1", "none");
    return { managed: true, event: "tp1", realized_pnl: realized };
  }

  if (tp2Hit) {
    const realized = await closePosition(cfg, pos, tp2!, "tp2", "none");
    return { managed: true, event: "tp2", realized_pnl: realized };
  }

  // 3) No exit -> just mark to market.
  const unrealized = round2((price - Number(pos.avg_entry)) * dir * Number(pos.qty) * pv);
  await supabase.from("positions").update({ last_price: price, unrealized_pnl: unrealized }).eq("id", pos.id);
  return { managed: true, event: "marked", unrealized_pnl: unrealized };
}

// ---------------------------------------------------------------------------
// Fill helpers
// ---------------------------------------------------------------------------
function slipAmount(cfg: Cfg) { return Number(cfg.slippage_ticks) * Number(cfg.tick_size); }

// Entry slippage: buy fills higher, sell fills lower (adverse).
function applySlippage(cfg: Cfg, side: "buy" | "sell", price: number) {
  const s = slipAmount(cfg);
  return round4(side === "buy" ? price + s : price - s);
}

async function insertOrder(
  broker: string, signalId: string | null, symbol: string,
  side: "buy" | "sell", qty: number, fill: number, raw: Record<string, unknown>,
) {
  if (broker !== "paper") throw new Error(`broker_not_implemented: ${broker}`);
  const { data: order, error } = await supabase.from("orders").insert({
    signal_id: signalId, broker, symbol, side, qty, order_type: "market",
    status: "filled", submitted_at: nowISO(), filled_at: nowISO(),
    filled_qty: qty, filled_price: fill, raw_response: { broker: "paper", simulated: true, ...raw },
  }).select().single();
  if (error || !order) throw new Error(`order_insert_failed: ${error?.message}`);
  return order;
}

// Full close. slipMode 'adverse' for market/stop fills, 'none' for TP limits.
async function closePosition(cfg: Cfg, pos: Pos, exitRaw: number, reason: string, slipMode: "adverse" | "none") {
  const closeSide = pos.side === "buy" ? "sell" : "buy";
  const exitFill = slipMode === "adverse" ? applySlippage(cfg, closeSide, exitRaw) : round4(exitRaw);
  const realized = pnlFor(cfg, pos, exitFill, Number(pos.qty));
  await insertOrder(cfg.broker, pos.signal_id, pos.symbol, closeSide, Number(pos.qty), exitFill, { reason });
  await supabase.from("positions").update({
    status: "closed", closed_at: nowISO(), exit_price: exitFill, realized_pnl: realized, unrealized_pnl: 0, last_price: exitFill,
  }).eq("id", pos.id);
  await bumpPnl(todayUTC(), 0, realized);
  return realized;
}

// Partial close: book closeQty, shrink the position, move stop to breakeven.
async function partialClose(cfg: Cfg, pos: Pos, closeQty: number, exitRaw: number, reason: string) {
  const closeSide = pos.side === "buy" ? "sell" : "buy";
  const exitFill = round4(exitRaw); // tp limit, no adverse slippage
  const realized = pnlFor(cfg, pos, exitFill, closeQty);
  await insertOrder(cfg.broker, pos.signal_id, pos.symbol, closeSide, closeQty, exitFill, { reason });
  await supabase.from("positions").update({
    qty: Number(pos.qty) - closeQty, tp1_filled: true, stop: Number(pos.avg_entry), // breakeven stop on the runner
  }).eq("id", pos.id);
  await bumpPnl(todayUTC(), 0, realized);
  return realized;
}

// Realized P&L for `qty` contracts, net of round-turn commission.
function pnlFor(cfg: Cfg, pos: Pos, exitFill: number, qty: number) {
  const dir = pos.side === "buy" ? 1 : -1;
  const gross = (exitFill - Number(pos.avg_entry)) * dir * qty * Number(cfg.point_value_usd);
  const commission = 2 * Number(cfg.commission_per_side_usd) * qty; // round turn
  return round2(gross - commission);
}

async function bumpPnl(day: string, addTrades: number, addPnl: number) {
  await supabase.from("pnl_daily").upsert({ trade_date: day }, { onConflict: "trade_date", ignoreDuplicates: true });
  const { data: row } = await supabase.from("pnl_daily").select("*").eq("trade_date", day).single();
  await supabase.from("pnl_daily").update({
    trades: Number(row?.trades ?? 0) + addTrades,
    realized_pnl: round2(Number(row?.realized_pnl ?? 0) + addPnl),
    updated_at: nowISO(),
  }).eq("trade_date", day);
}

const round2 = (n: number) => Math.round(n * 100) / 100;
const round4 = (n: number) => Math.round(n * 10000) / 10000;
