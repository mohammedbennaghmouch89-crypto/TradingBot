# Backtesting Strategy V1 on MNQ (Micro Nasdaq)

> Status: **draft for owner validation.** Documents the local backtest harness
> for [`docs/STRATEGY_V1.md`](STRATEGY_V1.md). This is offline analysis, not the
> live Phase 2 bot.

## What it does

Pulls historical MNQ (Micro E-mini Nasdaq-100) data at **1-minute** resolution,
derives the **3-minute** context timeframe by resampling it, runs the Python port
of Strategy V1, simulates a **$25,000 account trading 1 micro contract**, and
produces a performance summary plus three charts.

```
data/mnq.py  ──1m + 3m──▶  strategy/vp_ict_v1.py  ──trades──▶  backtest.py  ──▶  $ summary
   (yfinance 1m,             (VP setup 3m +                     (1 MNQ contract,      + charts
    cached; 3m resampled)     ICT entry 1m)                      $2/pt, commission)
```

## How to run

```bash
pip install -e ".[dev,backtest]"          # adds yfinance + matplotlib
python scripts/backtest_mnq.py --refresh  # fetch fresh data, run, render charts
python scripts/backtest_mnq.py            # re-run from cached data (offline)
```

Options: `--days N` (history to fetch, default 21), `--balance` (default 25000),
`--commission` (round-trip per contract, default 1.0). Charts are written to
`reports/` (git-ignored); cached data to `data_cache/` (git-ignored).

## Contract economics (MNQ)

| Item | Value |
| --- | --- |
| Point value | **$2.00 per index point** |
| Tick | 0.25 pt = **$0.50** |
| Position size | **1 contract** (project rule) |
| Starting balance | **$25,000** |
| Commission | **~$1.00 round-trip** (configurable) |

P&L per trade = `points × $2 − commission`. One position at a time; positions
exit on stop, the `target_mode` target (default POC / fair value), or the RTH
session close (no overnight risk). Once price reaches `breakeven_at` (default
50%) of the target, the stop is moved to entry (breakeven). Entries are gated by
the VWAP premium/discount filter (on) and an optional NY-AM killzone filter
(off). The per-trade log (`reports/mnq_trades.csv`) reports each trade's
**risk_$** (entry-time |entry−stop|×$2) and **R-multiple**.

## Data source & its limits (important)

Data is the free Yahoo feed (`MNQ=F`). Empirically discovered caps:

- **1-minute:** max **8 days per request** and only the **last ~30 days** are
  retained. The loader fetches 1m in ≤7-day chunks and concatenates, yielding
  the most recent **~3 weeks**.
- **3-minute context:** Yahoo has no native 3m interval, so it is **resampled
  from the 1m data** (`mnq.resample`). Both series therefore share one source and
  align exactly — and the context timeframe is configurable (`--context-min`).

Because the strategy is bounded by 1m availability, the backtest window is
**~3 weeks, not a full calendar month**. A true clean month at 1m needs a paid
feed (Databento / Polygon / IBKR) — a later upgrade; the loader is structured so
only `data/mnq.py` would change.

## Outputs

Printed summary: starting/final balance, net & gross P&L, commissions, trade
count, win rate, max drawdown. Plus `reports/`:

- `mnq_context_setups.png` — 3m candles with each session's POC (orange) / VAH-VAL (blue).
- `mnq_1m_trades.png` — 1m price with entry (▲/▼) and exit (✕) markers per trade.
- `mnq_equity.png` — the account equity curve as a **step** plot (balance changes
  only at trade exits).

## Honest reading of the results

- **Small sample.** ~3 weeks of a selective intraday strategy produces only a
  handful of trades. Treat any P&L / win-rate as **anecdotal, not statistically
  significant** — it is a *wiring and behaviour* check, not an edge claim.
- **Selectivity is by design.** The full ICT sequence (sweep → MSS+displacement
  /FVG → retrace) at a Volume-Profile edge is rare; the funnel typically goes
  dozens of sweeps → a few armed setups → one or two entries per week. The
  `sweep_window` / `entry_window` / `setup_bars` params control how much room the
  sequence is given and materially change trade frequency (see `Params`).
- **Approximations.** Volume-at-price is modelled from OHLCV (no ticks); fills
  assume the entry/stop/target prices are reached intrabar; if a bar straddles
  both stop and target the **stop is assumed first** (conservative).
- **No lookahead.** Each 1m bar uses the *prior completed* 3m session's profile,
  and pivots confirm `pivot_len` bars late — matching the Pine indicator.
- **Yahoo futures data** is continuous-contract and can differ from a specific
  CME front-month and from your broker's prints; good enough for behaviour
  validation, not for P&L to the dollar.

## Where the code lives

| Piece | File |
| --- | --- |
| Data loader (chunked, cached) | `src/tradingbot/data/mnq.py` |
| Strategy V1 (setup + ICT entry machine) | `src/tradingbot/strategy/vp_ict_v1.py` |
| Volume Profile core (shared with the indicator) | `src/tradingbot/indicators/volume_profile.py` |
| Portfolio / P&L | `src/tradingbot/backtest.py` |
| Runner + charts | `scripts/backtest_mnq.py` |
| Tests | `tests/test_backtest.py`, `tests/test_vp_ict_strategy.py`, `tests/test_volume_profile.py` |
