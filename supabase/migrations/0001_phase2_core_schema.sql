-- ============================================================================
-- Phase 2 core schema: TradingView webhook -> signals -> orders -> positions
-- Broker-agnostic. All tables RLS-enabled with NO policies => only the
-- service_role (used by the Edge Function) can read/write. anon/authenticated
-- are denied by default.
-- ============================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
create type signal_action  as enum ('buy', 'sell', 'close');
create type signal_status  as enum ('received', 'accepted', 'rejected', 'executed', 'error');
create type order_side     as enum ('buy', 'sell');
create type order_type     as enum ('market', 'limit', 'stop', 'stop_limit');
create type order_status    as enum ('pending', 'submitted', 'filled', 'partial', 'cancelled', 'rejected', 'error');
create type position_status as enum ('open', 'closed');

-- ---------------------------------------------------------------------------
-- bot_config : single-row control panel (kill switch + risk limits)
-- ---------------------------------------------------------------------------
create table bot_config (
  id                  int primary key default 1 check (id = 1),
  enabled             boolean      not null default false,   -- master kill switch
  broker              text         not null default 'paper', -- 'paper' | 'tradovate' | 'ibkr' | ...
  symbol              text         not null default 'MNQ1!',
  contracts_per_trade int          not null default 1 check (contracts_per_trade > 0),
  max_trades_per_day  int          not null default 5  check (max_trades_per_day  > 0),
  max_daily_loss_usd  numeric(12,2) not null default 500 check (max_daily_loss_usd > 0),
  allow_pyramiding    boolean      not null default false,   -- false => one position at a time
  trading_start_utc   time         not null default '13:30', -- e.g. NY killzone window
  trading_end_utc     time         not null default '20:00',
  enforce_hours       boolean      not null default false,
  allowed_setups      text[]       not null default '{}',    -- empty => all setups allowed
  updated_at          timestamptz  not null default now()
);
insert into bot_config (id) values (1);

-- ---------------------------------------------------------------------------
-- signals : every inbound webhook from TradingView (audit trail)
-- ---------------------------------------------------------------------------
create table signals (
  id            uuid primary key default gen_random_uuid(),
  received_at   timestamptz   not null default now(),
  strategy      text,
  action        signal_action not null,
  price         numeric(14,4),
  stop          numeric(14,4),
  tp1           numeric(14,4),
  tp2           numeric(14,4),
  setup         text,
  raw_payload   jsonb         not null,
  source_ip     text,
  status        signal_status not null default 'received',
  reject_reason text
);
create index signals_received_at_idx on signals (received_at desc);
create index signals_status_idx      on signals (status);

-- ---------------------------------------------------------------------------
-- orders : orders sent to the broker (one signal may create several)
-- ---------------------------------------------------------------------------
create table orders (
  id              uuid primary key default gen_random_uuid(),
  signal_id       uuid references signals (id) on delete set null,
  created_at      timestamptz  not null default now(),
  broker          text         not null default 'paper',
  broker_order_id text,
  symbol          text         not null,
  side            order_side   not null,
  qty             int          not null check (qty > 0),
  order_type      order_type   not null default 'market',
  limit_price     numeric(14,4),
  stop_price      numeric(14,4),
  status          order_status not null default 'pending',
  submitted_at    timestamptz,
  filled_at       timestamptz,
  filled_qty      int          not null default 0,
  filled_price    numeric(14,4),
  raw_response    jsonb,
  error_message   text
);
create index orders_signal_id_idx on orders (signal_id);
create index orders_status_idx    on orders (status);

-- ---------------------------------------------------------------------------
-- positions : net position lifecycle + realized P&L
-- ---------------------------------------------------------------------------
create table positions (
  id            uuid primary key default gen_random_uuid(),
  signal_id     uuid references signals (id) on delete set null,
  symbol        text            not null,
  side          order_side      not null,
  qty           int             not null check (qty > 0),
  avg_entry     numeric(14,4)   not null,
  stop          numeric(14,4),
  tp1           numeric(14,4),
  tp2           numeric(14,4),
  status        position_status not null default 'open',
  opened_at     timestamptz     not null default now(),
  closed_at     timestamptz,
  exit_price    numeric(14,4),
  realized_pnl  numeric(14,2),
  setup         text
);
create index positions_status_idx on positions (status);
create unique index positions_one_open_per_symbol on positions (symbol) where status = 'open';

-- ---------------------------------------------------------------------------
-- pnl_daily : per-day aggregate (drives max_daily_loss check)
-- ---------------------------------------------------------------------------
create table pnl_daily (
  trade_date    date primary key default (now() at time zone 'utc')::date,
  trades        int           not null default 0,
  realized_pnl  numeric(14,2) not null default 0,
  updated_at    timestamptz   not null default now()
);

-- ---------------------------------------------------------------------------
-- RLS: enable on all tables; create NO policies => service_role only.
-- ---------------------------------------------------------------------------
alter table bot_config enable row level security;
alter table signals    enable row level security;
alter table orders     enable row level security;
alter table positions  enable row level security;
alter table pnl_daily  enable row level security;
