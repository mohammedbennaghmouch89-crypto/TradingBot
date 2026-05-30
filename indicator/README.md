# Phase 1 — Indicator (Pine Script / TradingView)

This directory holds the custom **Pine Script v6** indicator used inside
TradingView.

> **Status: Strategy V1 in review.** First indicator implemented:
> [`vp_ict_strategy_v1.pine`](vp_ict_strategy_v1.pine) — a Volume-Profile setup
> (5m) → ICT entry (1m) tool. See [`docs/STRATEGY_V1.md`](../docs/STRATEGY_V1.md)
> for the trading logic and [`docs/INDICATOR.md`](../docs/INDICATOR.md) for the
> code internals.

## Conventions

- Target Pine Script **v6** (`//@version=6`).
- Keep the source in this directory as `*.pine` files.
- **Performance matters**: minimize per-bar work, avoid unnecessary
  `request.security` calls and repaints, and prefer built-in series ops.
- Each indicator file starts with a header comment describing inputs, outputs,
  and the signal logic so the Phase 2 Python port can mirror it exactly.

## Layout (planned)

```
indicator/
├── README.md                  # this file
└── vp_ict_strategy_v1.pine    # Strategy V1: VP setup (5m) → ICT entry (1m)
```
