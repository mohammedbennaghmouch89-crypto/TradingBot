"""Run the Strategy V1 backtest on MNQ and produce the visuals.

Usage:
    python scripts/backtest_mnq.py [--refresh] [--days N] [--balance 25000]

Fetches (and caches) MNQ 1m data, derives the 3m context by resampling, runs
Strategy V1, simulates a 1-contract $25k portfolio, prints the performance
summary, and writes three PNGs to ``reports/``:

* ``mnq_context_setups.png`` — 3m candles with the session POC/VAH/VAL.
* ``mnq_1m_trades.png``       — 1m candles with trade entries/exits.
* ``mnq_equity.png``          — the account equity curve.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from tradingbot.backtest import run_portfolio  # noqa: E402
from tradingbot.data import mnq  # noqa: E402
from tradingbot.strategy.vp_ict_v1 import (  # noqa: E402
    Params,
    Trade,
    _build_session_profiles,
    _rth_mask,
    _session_id,
    generate_trades,
)

REPORTS = Path(__file__).resolve().parents[1] / "reports"


def _candles(ax: plt.Axes, df: pd.DataFrame, width: float) -> None:
    """Minimal OHLC candlestick render (no extra deps)."""
    t = mdates.date2num(df.index.to_pydatetime())
    for x, (_, row) in zip(t, df.iterrows(), strict=True):
        up = row["close"] >= row["open"]
        color = "#26a69a" if up else "#ef5350"
        ax.plot([x, x], [row["low"], row["high"]], color=color, linewidth=0.5, zorder=1)
        ax.add_patch(
            plt.Rectangle(
                (x - width / 2, min(row["open"], row["close"])),
                width,
                max(abs(row["close"] - row["open"]), 1e-9),
                color=color,
                zorder=2,
            )
        )
    ax.xaxis_date()


def plot_context(df_ctx: pd.DataFrame, params: Params, minutes: int, path: Path) -> None:
    """Context-timeframe candles with the (prior-session) POC/VAH/VAL levels."""
    profiles = _build_session_profiles(df_ctx, params)
    fig, ax = plt.subplots(figsize=(16, 8))
    _candles(ax, df_ctx, width=(minutes / (24 * 60)) * 0.7)
    # Overlay each session's POC/VAH/VAL across that session's time span.
    sub = df_ctx[_rth_mask(df_ctx.index)]
    sids = _session_id(sub.index)
    for sid in sorted(set(sids)):
        if sid not in profiles:
            continue
        span = sub.index[sids == sid]
        x0, x1 = mdates.date2num(span[0]), mdates.date2num(span[-1])
        prof = profiles[sid].profile
        for level, color in [
            (prof.poc, "#ff9800"),
            (prof.vah, "#2196f3"),
            (prof.val, "#2196f3"),
        ]:
            ax.hlines(level, x0, x1, color=color, linewidth=1.2, alpha=0.8)
    ax.set_title(f"MNQ {minutes}-minute — session Volume Profile levels (POC orange, VA blue)")
    ax.set_ylabel("Price")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_1m(df1: pd.DataFrame, trades: list[Trade], path: Path) -> None:
    """1m close line with entry/exit markers for every trade."""
    fig, ax = plt.subplots(figsize=(16, 8))
    ax.plot(df1.index, df1["close"], color="#455a64", linewidth=0.6, zorder=1)
    for tr in trades:
        if tr.exit_time is None:
            continue
        ec = "#26a69a" if tr.direction == 1 else "#ef5350"
        ax.scatter(
            tr.entry_time,
            tr.entry_price,
            marker="^" if tr.direction == 1 else "v",
            color=ec,
            s=60,
            zorder=3,
            edgecolor="black",
            linewidth=0.3,
        )
        ax.scatter(tr.exit_time, tr.exit_price, marker="x", color="black", s=40, zorder=3)
        ax.plot(
            [tr.entry_time, tr.exit_time],
            [tr.entry_price, tr.exit_price],
            color=ec,
            linewidth=0.8,
            alpha=0.6,
            zorder=2,
        )
    ax.set_title("MNQ 1-minute — Strategy V1 trades (▲ long, ▼ short, ✕ exit)")
    ax.set_ylabel("Price")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_equity(curve: pd.Series, starting: float, path: Path) -> None:
    """Account equity curve over time, with the starting-balance baseline."""
    fig, ax = plt.subplots(figsize=(14, 6))
    if not curve.empty:
        full = pd.concat([pd.Series([starting], index=[curve.index[0]]), curve])
        # Step plot: the balance changes only at each trade's exit, not between.
        ax.step(full.index, full.values, where="post", color="#1e88e5", linewidth=1.6)
        ax.scatter(curve.index, curve.values, color="#1e88e5", s=18, zorder=3)
    ax.axhline(starting, color="gray", linestyle="--", linewidth=1)
    ax.set_title(f"Strategy V1 equity curve — MNQ 1 contract (start ${starting:,.0f})")
    ax.set_ylabel("Account balance ($)")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Strategy V1 MNQ backtest")
    ap.add_argument("--refresh", action="store_true", help="re-fetch data (else use cache)")
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--context-min", type=int, default=3, help="setup timeframe in minutes")
    ap.add_argument("--balance", type=float, default=25_000.0)
    ap.add_argument("--commission", type=float, default=1.0)
    args = ap.parse_args()

    REPORTS.mkdir(exist_ok=True)
    print("Loading MNQ data...")
    df1, df_ctx = mnq.load(
        days=args.days, context_rule=f"{args.context_min}min", refresh=args.refresh
    )
    print(f"  1m bars : {len(df1)}  ({df1.index.min()} .. {df1.index.max()})")
    print(
        f"  {args.context_min}m bars : {len(df_ctx)}  "
        f"({df_ctx.index.min()} .. {df_ctx.index.max()})"
    )

    params = Params()
    print("Running Strategy V1...")
    trades = generate_trades(df1, df_ctx, params)
    result = run_portfolio(trades, starting_balance=args.balance, commission_rt=args.commission)

    print("\n" + "=" * 48)
    print(result.summary())
    print("=" * 48 + "\n")

    print("Rendering charts...")
    plot_context(df_ctx, params, args.context_min, REPORTS / "mnq_context_setups.png")
    plot_1m(df1, trades, REPORTS / "mnq_1m_trades.png")
    plot_equity(result.equity_curve, args.balance, REPORTS / "mnq_equity.png")
    print(f"  wrote charts to {REPORTS}/")


if __name__ == "__main__":
    main()
