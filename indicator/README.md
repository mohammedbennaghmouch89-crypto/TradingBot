# Phase 1 — Indicator (Pine Script / TradingView)

This directory holds the custom **Pine Script v5** indicator used inside
TradingView.

> **Status: skeleton.** The indicator idea and behavior will be provided by the
> project owner. No indicator logic is implemented yet (see `AGENTS.md`).

## Conventions

- Target Pine Script **v5** (`//@version=5`).
- Keep the source in this directory as `*.pine` files.
- **Performance matters**: minimize per-bar work, avoid unnecessary
  `request.security` calls and repaints, and prefer built-in series ops.
- Each indicator file starts with a header comment describing inputs, outputs,
  and the signal logic so the Phase 2 Python port can mirror it exactly.

## Layout (planned)

```
indicator/
├── README.md          # this file
└── <name>.pine        # the indicator source (added once specified)
```
