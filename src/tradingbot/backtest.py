"""Portfolio backtest for Strategy V1 on MNQ (1 micro contract).

Turns the round-trip trades from ``strategy.vp_ict_v1`` into a dollar P&L curve
on a simulated account, using the Micro E-mini Nasdaq-100 contract economics:

* **Point value:** $2.00 per index point (1 tick = 0.25 pt = $0.50).
* **Size:** always 1 contract (project rule).
* **Commission:** configurable round-trip per contract (default $1.00).

Reports the final balance, net/gross P&L, win rate, max drawdown and the equity
curve. Pure arithmetic over the trade list — deterministic and testable.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tradingbot.strategy.vp_ict_v1 import Trade

MNQ_POINT_VALUE = 2.0  # USD per index point for MNQ
MNQ_TICK = 0.25


@dataclass
class BacktestResult:
    """Outcome of a portfolio backtest."""

    starting_balance: float
    final_balance: float
    trades: list[Trade]
    equity_curve: pd.Series  # indexed by exit time
    point_value: float
    commission_rt: float

    @property
    def net_pnl(self) -> float:
        return self.final_balance - self.starting_balance

    @property
    def gross_pnl(self) -> float:
        return sum(t.points for t in self.closed) * self.point_value

    @property
    def total_commission(self) -> float:
        return len(self.closed) * self.commission_rt

    @property
    def closed(self) -> list[Trade]:
        return [t for t in self.trades if t.exit_price is not None]

    @property
    def num_trades(self) -> int:
        return len(self.closed)

    @property
    def wins(self) -> list[Trade]:
        return [t for t in self.closed if t.points * self.point_value > self.commission_rt]

    @property
    def win_rate(self) -> float:
        return len(self.wins) / self.num_trades if self.num_trades else 0.0

    @property
    def max_drawdown(self) -> float:
        """Largest peak-to-trough drop of the equity curve, in dollars."""
        if self.equity_curve.empty:
            return 0.0
        running_max = self.equity_curve.cummax()
        return float((self.equity_curve - running_max).min())

    def trade_risk(self, trade: Trade) -> float:
        """Dollar risk of a trade = |entry - stop| x point value (1 contract).

        The amount that would be lost if the protective stop were hit — the
        denominator of the trade's R-multiple.
        """
        return abs(trade.entry_price - trade.stop) * self.point_value

    @property
    def avg_risk(self) -> float:
        """Average dollar risk across closed trades."""
        if not self.closed:
            return 0.0
        return sum(self.trade_risk(t) for t in self.closed) / len(self.closed)

    def trade_log(self) -> pd.DataFrame:
        """Per-trade table with a Risk $ column and the realized R-multiple.

        R-multiple = net P&L / risk, the trade's result expressed in units of the
        risk taken (so a +2R win made twice what it risked).
        """
        rows = []
        for t in self.closed:
            risk = self.trade_risk(t)
            pnl = t.points * self.point_value - self.commission_rt
            rows.append(
                {
                    "entry_time": t.entry_time,
                    "dir": "long" if t.direction == 1 else "short",
                    "setup": t.setup,
                    "entry": round(t.entry_price, 2),
                    "stop": round(t.stop, 2),
                    "risk_$": round(risk, 2),
                    "exit": round(t.exit_price, 2) if t.exit_price is not None else None,
                    "reason": t.exit_reason,
                    "points": round(t.points, 2),
                    "pnl_$": round(pnl, 2),
                    "R": round(pnl / risk, 2) if risk > 0 else float("nan"),
                }
            )
        return pd.DataFrame(rows)

    def summary(self) -> str:
        """Human-readable one-block summary."""
        return (
            f"Starting balance : ${self.starting_balance:,.2f}\n"
            f"Final balance    : ${self.final_balance:,.2f}\n"
            f"Net P&L          : ${self.net_pnl:,.2f}\n"
            f"Gross P&L        : ${self.gross_pnl:,.2f}\n"
            f"Commissions      : ${self.total_commission:,.2f}\n"
            f"Trades           : {self.num_trades}\n"
            f"Win rate         : {self.win_rate:.1%}\n"
            f"Avg risk / trade : ${self.avg_risk:,.2f}\n"
            f"Max drawdown     : ${self.max_drawdown:,.2f}"
        )


def run_portfolio(
    trades: list[Trade],
    starting_balance: float = 25_000.0,
    point_value: float = MNQ_POINT_VALUE,
    commission_rt: float = 1.0,
) -> BacktestResult:
    """Apply the trade list to a simulated account and build the equity curve.

    Each closed trade moves the balance by ``points * point_value - commission``.
    The equity curve is sampled at each trade's exit time (plus the starting
    point), which is what we plot.
    """
    closed = [t for t in trades if t.exit_price is not None and t.exit_time is not None]
    closed.sort(key=lambda t: t.exit_time)  # type: ignore[arg-type,return-value]

    balance = starting_balance
    times: list[pd.Timestamp] = []
    equity: list[float] = []
    for t in closed:
        balance += t.points * point_value - commission_rt
        times.append(t.exit_time)
        equity.append(balance)

    curve = pd.Series(equity, index=pd.DatetimeIndex(times), name="equity")
    return BacktestResult(
        starting_balance=starting_balance,
        final_balance=balance,
        trades=trades,
        equity_curve=curve,
        point_value=point_value,
        commission_rt=commission_rt,
    )
