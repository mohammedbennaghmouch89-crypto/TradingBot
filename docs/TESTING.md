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
  Exchange interactions are mocked/stubbed; the MNQ backtest tests use synthetic
  or hand-built data, never the live `yfinance` feed (the `backtest` extra is not
  required to run the suite).
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

### `tests/test_backtest.py`

Arithmetic tests for the **MNQ portfolio backtest** (`src/tradingbot/backtest.py`)
— the contract economics that turn Strategy V1 trades into a dollar P&L. See
`docs/BACKTEST.md`. Stdlib + pandas/numpy only (no network).

| Test | What it verifies | Why |
| --- | --- | --- |
| `test_point_value_and_balance_long_win` | A +20-pt long adds 20×$2 − commission. | Pins the $2/point MNQ economics and fee deduction behind every reported balance. |
| `test_short_trade_pnl_sign` | A short closing lower is a profit. | Guards the direction sign so shorts aren't inverted. |
| `test_win_rate_and_counts` | Win rate counts only trades that beat commission. | Fixes the headline metric's definition (net of fees). |
| `test_max_drawdown_is_peak_to_trough` | Drawdown tracks the running peak. | The key risk number must be peak-to-trough, not start-to-end. |
| `test_empty_trades_returns_starting_balance` | No trades leaves balance/​drawdown untouched. | A no-signal period must not crash or invent P&L. |

### `tests/test_vp_ict_strategy.py`

Tests for the **Strategy V1 engine** (`src/tradingbot/strategy/vp_ict_v1.py`):
the swing/pivot lag, the RTH session mask, setup-bias rules, and an end-to-end
run on deterministic synthetic data. See `docs/STRATEGY_V1.md`. No network.

| Test | What it verifies | Why |
| --- | --- | --- |
| `test_rolling_swings_confirm_with_lag` | A pivot publishes exactly `pivot_len` bars late. | Enforces the no-lookahead repaint lag shared with Pine. |
| `test_rth_mask_selects_regular_hours_only` | 09:30–16:00 NY in; overnight/weekend out. | Catches the #1 timezone bug that would corrupt every level. |
| `test_detect_setup_bias_rules` | VAL→long, VAH→short. | The core mean-reversion mapping; wrong sign fades the wrong way. |
| `test_generate_trades_runs_and_trades_are_well_formed` | E2E run yields only closed, sign-consistent trades. | Smoke + invariants; catches crashes and state-machine leaks. |
| `test_no_trades_outside_rth` | No entry falls outside RTH. | Confirms the intraday gate doesn't leak into hours the strategy can't trade. |

### `tests/test_volume_profile.py`

Correctness tests for the **Volume Profile core**
(`src/tradingbot/indicators/volume_profile.py`) — the parity-critical math shared
by the Phase 1 Pine indicator (`indicator/vp_ict_strategy_v1.pine`) and the
Phase 2 bot. See `docs/STRATEGY_V1.md` / `docs/INDICATOR.md`.

| Test | What it verifies | Why |
| --- | --- | --- |
| `test_poc_is_highest_volume_row` | POC lands on the heaviest-volume row. | POC anchors VAH/VAL and all trade targets; a wrong POC breaks the whole strategy. |
| `test_bins_conserve_total_volume` | The histogram redistributes volume without creating/destroying it. | Conservation catches off-by-one row-span bugs in the OHLCV approximation. |
| `test_value_area_simple_known_case` | Value area matches a hand-computed expansion. | Pins the canonical two-rows-per-side 70% algorithm to a known result. |
| `test_value_area_tie_breaks_upward` | An exact above/below tie expands upward. | Locks the TradingView upper-row tie-break for reproducible levels. |
| `test_value_area_spans_everything_at_100_percent` | A 100% target includes every row. | Guards loop termination (no early stop, no infinite loop). |
| `test_degenerate_single_price_session` | Zero price range collapses to row 0, no divide-by-zero. | Real edge case for halted/illiquid bars. |
| `test_empty_input_returns_zero_bins` | No bars yields an all-zero histogram. | Lets callers treat "no levels yet" uniformly before a session has data. |
| `test_mismatched_lengths_raise` | Unequal OHLCV lengths raise. | Fails fast instead of silently misaligning bars into a corrupt profile. |
| `test_build_bins_matches_naive_loop_reference` | Vectorized binning equals a scalar per-bar reference. | Ensures the AGENTS-mandated vectorization can't drift from correctness. |

### `tests/test_ict_skill.py`

Structural-integrity tests for the **ICT skill** (`.claude/skills/ict/`). The skill
is documentation, so these guard that it stays a valid, navigable Claude Code skill
rather than testing trading behavior. Stdlib-only, so they pass in CI even when
third-party packages can't be installed.

| Test | What it verifies | Why |
| --- | --- | --- |
| `test_skill_md_exists` | `SKILL.md` exists. | Without it the folder isn't a loadable skill. |
| `test_frontmatter_has_name_and_description` | Frontmatter declares `name` and `description`. | These drive skill discovery; a missing key silently breaks loading. |
| `test_skill_name_is_ict` | `name` is exactly `ict`. | An accidental rename would detach anything referencing the skill. |
| `test_required_reference_files_exist` | All four `reference/*.md` files are present. | SKILL.md delegates detail to them; a missing one is a dead end. |
| `test_skill_md_relative_links_resolve` | Every relative link in SKILL.md points to a real file. | Catches typos/renames that break navigation (http/anchor links skipped). |
| `test_reference_files_are_nonempty_and_cite_sources` | Each reference file is substantial and has a `## Sources` section. | Keeps ICT claims auditable and flags botched writes. |
| `test_key_conventions_documented` | SKILL.md keeps the key conventions (`America/New_York`, `useCloseForBreak`, `0.705`). | These are the rules most likely to cause indicator/chart mismatches if dropped. |

### `tests/test_volume_profile_skill.py`

Structural-integrity tests for the **Volume Profile skill**
(`.claude/skills/volume-profile/`), mirroring the ICT skill tests. Stdlib-only.

| Test | What it verifies | Why |
| --- | --- | --- |
| `test_skill_md_exists` | `SKILL.md` exists. | Without it the folder isn't a loadable skill. |
| `test_frontmatter_has_name_and_description` | Frontmatter declares `name` and `description`. | These drive skill discovery; a missing key silently breaks loading. |
| `test_skill_name_is_volume_profile` | `name` is exactly `volume-profile`. | An accidental rename would detach anything referencing the skill. |
| `test_required_reference_files_exist` | All four `reference/*.md` files are present. | SKILL.md delegates detail to them; a missing one is a dead end. |
| `test_skill_md_relative_links_resolve` | Every relative link in SKILL.md resolves (incl. the cross-link to the `ict` skill). | Catches typos/renames that break navigation. |
| `test_reference_files_are_nonempty_and_cite_sources` | Each reference file is substantial and has a `## Sources` section. | Keeps Volume Profile claims auditable and flags botched writes. |
| `test_key_conventions_documented` | SKILL.md keeps the key conventions (value-area algorithm, `America/New_York`, `footprint`). | These are the rules most likely to cause profile mismatches/wrong levels if dropped. |

## Adding tests for a new change

1. Get the change validated by the owner (see `AGENTS.md`).
2. Add tests under `tests/`, each with a docstring explaining it.
3. Add a row to the relevant table above.
4. Run `pytest` until green, then commit.
