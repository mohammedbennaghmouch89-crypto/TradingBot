# Phase 2 — Live(ish) Execution: TradingView → Supabase → Broker

Phase 2 turns the Phase 1 VP+ICT V1 indicator's `alert()` JSON into actual
(paper) orders. It is **broker-agnostic**: a built-in **paper broker** is wired
up today so the whole pipeline can be tested end-to-end, and a real futures
broker (Tradovate / IBKR) drops in later behind the same interface.

```
TradingView (Premium webhook alert)
        │  POST JSON  { action, price, stop, tp1, tp2, setup, token }
        ▼
Supabase Edge Function  tv-webhook        ← validates token, runs risk checks
        │
        ▼
Postgres:  signals → orders → positions → pnl_daily
        ▲
   bot_config  (kill switch + risk limits + webhook token)
```

## Supabase project

| Item | Value |
|------|-------|
| Project name | `tradingbot-phase2` |
| Project ref  | `ebmzjzjvtemecwckhdgo` |
| Region       | `eu-west-1` |
| API URL      | `https://ebmzjzjvtemecwckhdgo.supabase.co` |
| Webhook URL  | `https://ebmzjzjvtemecwckhdgo.supabase.co/functions/v1/tv-webhook` |

Everything is on the **free tier** ($0/month).

## Database schema

| Table | Purpose |
|-------|---------|
| `bot_config` | Single-row control panel: **`enabled`** kill switch, broker, symbol, `contracts_per_trade`, `max_trades_per_day`, `max_daily_loss_usd`, trading-hours window, `allowed_setups`, `webhook_token`, `point_value_usd`. |
| `signals`   | Every inbound webhook (full audit trail, even rejected ones). |
| `orders`    | Orders sent to the broker, with fill price + raw broker response. |
| `positions` | Position lifecycle; one open position per symbol (enforced by a partial unique index) unless pyramiding is enabled. |
| `pnl_daily` | Per-day trade count + realized P&L — drives the daily caps. |

**Security:** RLS is enabled on every table with **no policies**, so only the
Edge Function (service role) can touch them. Public/anon clients are blocked.

## Risk controls (all in `bot_config`)

Checked in order, before any order is placed:

1. `enabled` — master kill switch (currently **OFF**).
2. `enforce_hours` + `trading_start_utc`/`trading_end_utc` — optional session window.
3. `allowed_setups` — if non-empty, only those setup names execute.
4. `max_trades_per_day` — caps new entries per UTC day.
5. `max_daily_loss_usd` — once realized loss hits this, new entries are rejected.
6. `allow_pyramiding` — when false, a same-side signal while in a position is
   rejected; an opposite-side signal flattens and reverses.

## How a signal is handled

- **buy / sell** → opens a position (or reverses an opposite one).
- **close** → flattens the open position and books realized P&L
  `(exit − entry) × dir × qty × point_value_usd` (MNQ point value = $2).
- Duplicate same-side entry → `rejected: position_already_open`.
- Bad/missing token → `401 unauthorized`.

## TradingView alert setup (Premium)

1. Add the VP+ICT V1 indicator to your **MNQ1!** chart.
2. Create an alert on the indicator, condition **"Any alert() function call"**.
3. **Webhook URL** (Notifications tab):
   `https://ebmzjzjvtemecwckhdgo.supabase.co/functions/v1/tv-webhook?token=<YOUR_TOKEN>`
4. The Pine `alert()` already emits the JSON body. To send the token in the
   body instead of the URL, append `,"token":"<YOUR_TOKEN>"` inside the payload.

Retrieve / rotate the token (never commit it):
```sql
select webhook_token from bot_config where id = 1;             -- read
update bot_config set webhook_token = encode(gen_random_bytes(24),'hex') where id = 1;  -- rotate
```

## Going live (paper)

```sql
update bot_config set enabled = true where id = 1;   -- arm the bot
-- ... watch signals / positions / pnl_daily ...
update bot_config set enabled = false where id = 1;  -- disarm
```

## Broker roadmap

The paper broker lives in `executeFill()` in `supabase/functions/tv-webhook/index.ts`.
To go to a real futures paper account, add a `case` there and set
`bot_config.broker`:

- **Tradovate** — REST/WebSocket API, free demo, webhook-friendly *(recommended)*.
- **Interactive Brokers** — free paper account via TWS/Gateway API (heavier setup).

Both need their demo API credentials stored as **Edge Function secrets** (never
in code or the DB).

## Source of truth

- `supabase/migrations/0001_phase2_core_schema.sql`
- `supabase/migrations/0002_phase2_webhook_auth_and_pointvalue.sql`
- `supabase/functions/tv-webhook/index.ts`

These mirror what is deployed to the live project.
