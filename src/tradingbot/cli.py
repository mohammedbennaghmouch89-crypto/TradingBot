"""Command-line entry point for the trading bot (skeleton).

The real run loop is intentionally not implemented yet — see AGENTS.md. For now
this only exposes a ``--version`` flag so the package is runnable and testable.
"""

from __future__ import annotations

import argparse

from tradingbot import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="tradingbot", description="TradingBot CLI")
    parser.add_argument(
        "--version",
        action="version",
        version=f"tradingbot {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    parser.parse_args(argv)
    # Skeleton: no run loop yet. Indicator/strategy wiring comes later.
    print("TradingBot skeleton — no trading logic implemented yet. See AGENTS.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
