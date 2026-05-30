# Architecture

> Skeleton document — expanded as the project grows.

## Two phases

### Phase 1 — Indicator (Pine Script)

The signal logic is first authored as a **Pine Script v6** indicator in
`indicator/`, validated visually inside TradingView. This is the source of
truth for the trading logic.

### Phase 2 — Bot (Python)

The bot in `src/tradingbot/` re-implements the indicator logic in Python and
trades on it daily. It is split into focused modules:

```
data/        OHLCV fetching/caching via ccxt
indicators/  vectorized (NumPy/pandas) port of the Pine Script indicator
strategy/    turns indicator output into trade signals + sizing
execution/   places/*simulates* orders (respects dry_run) via ccxt
config.py    typed settings loaded from env
cli.py       entry point / run loop
```

### Data flow (planned)

```
exchange ──data──▶ indicators ──signals──▶ strategy ──orders──▶ execution ──▶ exchange
                                                  ▲
                                              config (env)
```

## Performance principles

- The indicator hot path is treated as latency-critical: vectorized math, no
  per-bar Python loops, minimal allocations (see `AGENTS.md`).
- Parity between the Pine Script indicator and the Python port is verified by
  tests against known values.

## Branch & release model

`feature/* → (PR, CI green) → develop → (PR) → main`. `main` and `develop`
accept changes only through pull requests.
