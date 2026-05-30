# AGENTS.md — Working Agreement for AI Agents & Contributors

This file defines the **mandatory rules** that any AI agent (Claude Code, etc.)
or human contributor must follow when working in this repository.

## Project overview

This repository is built in **two phases**:

- **Phase 1 — Indicator (Pine Script / TradingView).** A custom indicator
  written in Pine Script, used directly inside TradingView.
- **Phase 2 — Trading bot.** A bot that consumes the Phase 1 indicator logic
  and performs daily trading.

> The concrete indicator idea and behavior will be specified by the project
> owner. **Do not implement indicator or strategy logic until it is explained
> and explicitly requested.**

## Golden rules (non-negotiable)

1. **Code should always be optimal.** Prefer clear, efficient, well-structured
   code. No dead code, no needless abstractions, no premature complexity.
2. **Respect performance — the indicator must be fast.** Indicator
   computations must be vectorized and allocation-light. Avoid per-bar Python
   loops; use NumPy/pandas vectorization. Treat the indicator hot path as
   latency-critical and benchmark anything that could regress it.
3. **Never commit until the owner validates all the changes.** Build the
   changes, present them for review, and **wait** for explicit validation
   before creating any commit.
4. **After validation: write tests, run them, then commit.** Once the change is
   validated, create tests for it, run the full test suite, and only commit
   **after all tests pass**.
5. **Document all tests and explain each test.** Every test must have a
   docstring/comment explaining *what* it verifies and *why*. Keep
   `docs/TESTING.md` in sync.

## Workflow rules

- **`main` and `develop` are protected.** Code reaches them **only via pull
  request** — never via a direct push.
- Active development happens on feature branches that target **`develop`**.
- The CI workflow runs the test suite on every pull request. A PR may be merged
  into `develop` **only after CI is green**.
- `develop` is promoted to `main` via pull request once a milestone is stable.

## Branch model

```
main      ← stable, release-ready (PR only)
  ▲
develop   ← integration branch for ongoing work (PR only)
  ▲
feature/* ← day-to-day development; opens PR into develop
```

## Definition of done for a change

- [ ] Owner has validated the change.
- [ ] Tests exist for the change and each test is documented.
- [ ] `docs/TESTING.md` updated.
- [ ] Full test suite passes locally and in CI.
- [ ] Performance of the indicator hot path is not regressed.
- [ ] Merged through a pull request (never a direct push to `main`/`develop`).
