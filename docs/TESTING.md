# Testing guide

This project follows the rule in `AGENTS.md`: **every change ships with tests,
and every test is documented and explained.** This file is the human-readable
index of the suite — keep it in sync whenever tests are added or changed.

## How to run

```bash
pip install -e ".[dev]"
pytest                                   # run everything
pytest --cov=tradingbot --cov-report=term-missing   # with coverage (as in CI)
```

CI runs the exact same suite on Python 3.11 and 3.12 for every pull request
targeting `develop` or `main`. A PR is mergeable only when CI is green.

## Conventions

- Tests live in `tests/`, named `test_*.py`.
- **Every test has a docstring** stating *what* it verifies and *why* it
  matters.
- Tests must be deterministic and must not hit the network or a real exchange.
  Exchange interactions are mocked/stubbed.
- Indicator tests (added in Phase 1/2) must also include at least one
  correctness check against known values and, where relevant, a guard that the
  computation stays vectorized/fast.

## Current tests

### `tests/test_smoke.py`

Skeleton-level tests that give CI something meaningful to gate on before any
trading logic exists.

| Test | What it verifies | Why |
| --- | --- | --- |
| `test_package_exposes_version` | The package imports and `__version__` is a non-empty string. | Catches import-time errors and protects packaging + `--version`. |
| `test_get_settings_returns_documented_defaults` | `get_settings()` returns a `Settings` with the documented defaults (incl. `dry_run=True`). | Config must load with zero env vars and default to safe (no live trading). |
| `test_settings_read_from_environment` | Env vars override settings (`TRADING_SYMBOL`, `DRY_RUN`). | Confirms pydantic-settings wiring so deployments configure via env. |
| `test_cli_version_flag_exits_zero` | `--version` triggers `SystemExit(0)`. | A broken entry point would exit non-zero. |
| `test_cli_main_runs_without_args` | `main([])` returns exit code 0. | Ensures the default run path is wired and side-effect free. |

## Adding tests for a new change

1. Get the change validated by the owner (see `AGENTS.md`).
2. Add tests under `tests/`, each with a docstring explaining it.
3. Add a row to the relevant table above.
4. Run `pytest` until green, then commit.
