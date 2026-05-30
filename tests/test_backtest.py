"""Tests for the MNQ portfolio backtest (`tradingbot.backtest`).

These verify the account arithmetic that turns Strategy V1 trades into a dollar
P&L on a 1-contract MNQ portfolio: contract economics ($2/point), commissions,
final balance, win rate and max drawdown. Deterministic, no network — trades are
constructed by hand so the expected numbers are obvious. See ``docs/TESTING.md``.
"""

from __future__ import annotations

import pandas as pd

from tradingbot.backtest import MNQ_POINT_VALUE, run_portfolio
from tradingbot.strategy.vp_ict_v1 import Trade


def _closed_trade(direction: int, entry: float, exit_px: float, t: str) -> Trade:
    """Build a fully-closed Trade with realized points, for arithmetic tests."""
    tr = Trade(
        direction=direction,
        setup="VAL",
        entry_time=pd.Timestamp(t, tz="UTC"),
        entry_price=entry,
        stop=entry - 10 * direction,
        tp1=entry + 5 * direction,
        tp2=entry + 10 * direction,
    )
    tr.exit_time = pd.Timestamp(t, tz="UTC") + pd.Timedelta(minutes=5)
    tr.exit_price = exit_px
    tr.points = (exit_px - entry) * direction
    return tr


def test_point_value_and_balance_long_win() -> None:
    """A +20-point MNQ long must add 20*$2 minus commission to the balance.

    Pins the core contract economics ($2/point) and the commission deduction —
    the numbers that decide whether the reported final balance is meaningful.
    """
    trades = [_closed_trade(1, 20000.0, 20020.0, "2026-05-11 14:00")]
    r = run_portfolio(trades, starting_balance=25_000.0, commission_rt=1.0)
    assert MNQ_POINT_VALUE == 2.0
    assert r.gross_pnl == 40.0  # 20 points * $2
    assert r.final_balance == 25_000.0 + 40.0 - 1.0
    assert r.net_pnl == 39.0


def test_short_trade_pnl_sign() -> None:
    """A short that closes lower than entry must be a profit.

    Guards the direction handling: for shorts, ``points = (exit-entry)*-1``, so a
    fall in price is a gain. A sign bug here would invert every short's P&L.
    """
    trades = [_closed_trade(-1, 20000.0, 19980.0, "2026-05-11 15:00")]
    r = run_portfolio(trades, starting_balance=25_000.0, commission_rt=0.0)
    assert r.gross_pnl == 40.0
    assert r.final_balance == 25_040.0


def test_win_rate_and_counts() -> None:
    """Win rate counts only trades whose P&L beats commission, over all closed.

    Win rate is the headline metric; this fixes its definition (net of fees) so a
    barely-positive gross trade that loses to commission is not counted a win.
    """
    trades = [
        _closed_trade(1, 100.0, 110.0, "2026-05-11 14:00"),  # +10 pts win
        _closed_trade(1, 100.0, 95.0, "2026-05-11 15:00"),  # -5 pts loss
        _closed_trade(-1, 100.0, 90.0, "2026-05-11 16:00"),  # +10 pts win
    ]
    r = run_portfolio(trades, starting_balance=25_000.0, commission_rt=1.0)
    assert r.num_trades == 3
    assert r.win_rate == 2 / 3


def test_max_drawdown_is_peak_to_trough() -> None:
    """Max drawdown must be the largest peak-to-trough equity drop, in dollars.

    Drawdown is the key risk number; this checks it tracks the running peak
    rather than just start-to-end, using a win-then-loss sequence.
    """
    trades = [
        _closed_trade(1, 100.0, 150.0, "2026-05-11 14:00"),  # +50 pts -> +$100
        _closed_trade(1, 100.0, 60.0, "2026-05-11 15:00"),  # -40 pts -> -$80
    ]
    r = run_portfolio(trades, starting_balance=25_000.0, commission_rt=0.0)
    # Peak 25_100 after trade 1, trough 25_020 after trade 2 -> drawdown -$80.
    assert r.max_drawdown == -80.0


def test_empty_trades_returns_starting_balance() -> None:
    """No trades must leave the balance untouched and drawdown at zero.

    A period that produces no signals (very possible for a selective strategy)
    must not crash the portfolio math or invent P&L.
    """
    r = run_portfolio([], starting_balance=25_000.0)
    assert r.final_balance == 25_000.0
    assert r.num_trades == 0
    assert r.max_drawdown == 0.0
    assert r.win_rate == 0.0
