# TradingBot

A two-phase project:

1. **Phase 1 — Indicator (Pine Script / TradingView):** a custom indicator
   written in Pine Script for use inside TradingView. See [`indicator/`](indicator/).
2. **Phase 2 — Trading bot:** a Python bot that reuses the Phase 1 indicator
   logic to perform daily trading. See [`src/tradingbot/`](src/tradingbot/).

> ⚠️ This repository is currently a **skeleton**. No indicator or trading logic
> is implemented yet — the structure, tooling, CI and conventions are in place
> and waiting for the indicator specification.

## Tech stack

| Area | Choice | Why |
| --- | --- | --- |
| Indicator | **Pine Script v6** | Native TradingView language. |
| Bot language | **Python 3.11+** | Best ecosystem for market data, indicators and exchange APIs. |
| Market data / exchange | **ccxt** | Unified API across many crypto exchanges. |
| Numerics | **NumPy + pandas** | Fast, vectorized indicator math (performance requirement). |
| Config | **pydantic-settings** | Typed, validated configuration from env. |
| Tests | **pytest + pytest-cov** | Standard, fast test runner with coverage. |
| Lint / format | **ruff** | Single fast tool for linting and formatting. |
| Types | **mypy** | Static type checking. |

## Repository layout

```
.
├── AGENTS.md                 # Working agreement / mandatory rules
├── pyproject.toml            # Python project + tooling config
├── .github/workflows/ci.yml  # CI: lint + type-check + tests on every PR
├── indicator/                # Phase 1 — Pine Script indicator
├── src/tradingbot/           # Phase 2 — bot package (skeleton)
│   ├── config.py             # Typed settings
│   ├── data/                 # Market-data access
│   ├── indicators/           # Python port of the indicator (vectorized)
│   ├── strategy/             # Trading strategy built on the indicator
│   ├── execution/            # Order execution / exchange glue
│   └── cli.py                # Entry point
├── tests/                    # Test suite
└── docs/                     # Architecture + testing docs
```

## Getting started (Phase 2 / bot)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # install package + dev tools
cp .env.example .env         # configure (never commit real secrets)

ruff check .                 # lint
ruff format --check .        # format check
mypy src                     # type check
pytest                       # run tests
```

## Contributing

Read [`AGENTS.md`](AGENTS.md) first. In short: changes are validated by the
owner before commit, every change ships with documented tests, and `main` /
`develop` are updated **only through pull requests** that pass CI.
