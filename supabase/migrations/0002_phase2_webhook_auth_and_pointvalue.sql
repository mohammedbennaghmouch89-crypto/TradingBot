-- Shared-secret token for the TradingView webhook + instrument point value.
-- Token lives only in bot_config (service_role-only via RLS). Rotate by
-- updating this column.
alter table bot_config
  add column webhook_token   text          not null default encode(gen_random_bytes(24), 'hex'),
  add column point_value_usd numeric(10,2) not null default 2.00;  -- MNQ = $2 / point

comment on column bot_config.webhook_token   is 'Shared secret; TradingView must send it as ?token= or body {"token":...}';
comment on column bot_config.point_value_usd is 'USD per 1.0 price point per contract (MNQ=2, MES=5, ES=50, NQ=20)';
