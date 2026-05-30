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
