"""Smoke tests for the skeleton.

These tests do **not** test trading logic (none exists yet). They only verify
that the package is importable, configurable and runnable, so CI has something
meaningful to gate pull requests on from day one. See ``docs/TESTING.md``.
"""

from __future__ import annotations

import tradingbot
from tradingbot.cli import build_parser, main
from tradingbot.config import Settings, get_settings


def test_package_exposes_version() -> None:
    """The package must import cleanly and expose a string version.

    Guards against import-time errors and a missing/oddly-typed ``__version__``,
    which would break packaging and the ``--version`` CLI flag.
    """
    assert isinstance(tradingbot.__version__, str)
    assert tradingbot.__version__  # non-empty


def test_get_settings_returns_documented_defaults() -> None:
    """``get_settings()`` returns a ``Settings`` with the documented defaults.

    Confirms configuration loads without requiring any environment variables
    and that defaults match ``.env.example`` (safe ``dry_run=True`` by default).
    """
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.exchange_id == "binance"
    assert settings.trading_symbol == "BTC/USDT"
    assert settings.trading_timeframe == "1d"
    assert settings.dry_run is True


def test_settings_read_from_environment(monkeypatch) -> None:
    """Settings must be overridable via environment variables.

    Verifies the pydantic-settings wiring actually reads the environment, so
    real deployments can be configured without code changes.
    """
    monkeypatch.setenv("TRADING_SYMBOL", "ETH/USDT")
    monkeypatch.setenv("DRY_RUN", "false")
    settings = Settings()
    assert settings.trading_symbol == "ETH/USDT"
    assert settings.dry_run is False


def test_cli_version_flag_exits_zero() -> None:
    """``tradingbot --version`` prints the version and exits with code 0.

    ``argparse`` raises ``SystemExit`` for ``--version``; a non-zero code would
    signal a broken entry point.
    """
    parser = build_parser()
    try:
        parser.parse_args(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    else:  # pragma: no cover - parse_args must exit on --version
        raise AssertionError("--version did not trigger SystemExit")


def test_cli_main_runs_without_args() -> None:
    """``main([])`` runs the skeleton entry point and returns exit code 0.

    Ensures the default invocation path is wired up and side-effect free while
    no trading logic exists yet.
    """
    assert main([]) == 0
