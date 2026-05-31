-- ============================================================================
-- Phase 2 paper-trading engine upgrade:
--   * realistic fills (slippage + commission)
--   * automatic SL/TP exits driven by 'mark' price webhooks
--   * partial take-profit (tp1 scale-out + move-to-breakeven) when qty > 1
--   * unrealized P&L + equity tracking
-- ============================================================================

-- Fill realism + account config ---------------------------------------------
alter table bot_config
  add column slippage_ticks         numeric(6,2)  not null default 1    check (slippage_ticks >= 0),
  add column tick_size              numeric(10,4) not null default 0.25 check (tick_size > 0),     -- MNQ tick = 0.25 pt
  add column commission_per_side_usd numeric(8,2) not null default 0.37 check (commission_per_side_usd >= 0),
  add column starting_equity_usd    numeric(14,2) not null default 10000 check (starting_equity_usd >= 0);

comment on column bot_config.slippage_ticks          is 'Adverse ticks applied to market/stop fills (per side)';
comment on column bot_config.tick_size               is 'Instrument tick size in price points (MNQ=0.25)';
comment on column bot_config.commission_per_side_usd is 'Commission per contract per side; round-turn = 2x';

-- Position mark-to-market + partial-TP state --------------------------------
alter table positions
  add column last_price     numeric(14,4),
  add column unrealized_pnl numeric(14,2) not null default 0,
  add column tp1_filled     boolean       not null default false;

-- Latest price per symbol (updated by 'mark' webhooks) ----------------------
create table market (
  symbol     text primary key,
  last_price numeric(14,4),
  high       numeric(14,4),
  low        numeric(14,4),
  updated_at timestamptz not null default now()
);
alter table market enable row level security;

-- Account / equity views (security_invoker => respect RLS, service-role only)
create view v_account with (security_invoker = on) as
select
  (select starting_equity_usd from bot_config where id = 1)                              as starting_equity,
  coalesce((select sum(realized_pnl)   from pnl_daily), 0)                               as realized_pnl,
  coalesce((select sum(unrealized_pnl) from positions where status = 'open'), 0)         as open_unrealized_pnl,
  (select starting_equity_usd from bot_config where id = 1)
    + coalesce((select sum(realized_pnl)   from pnl_daily), 0)
    + coalesce((select sum(unrealized_pnl) from positions where status = 'open'), 0)     as equity;

create view v_open_positions with (security_invoker = on) as
select id, symbol, side, qty, avg_entry, stop, tp1, tp2, tp1_filled,
       last_price, unrealized_pnl, setup, opened_at
from positions
where status = 'open';
