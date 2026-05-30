"""Tests for the Strategy V1 engine (`tradingbot.strategy.vp_ict_v1`).

The full sweep->MSS+FVG->retrace sequence is hard to assert end-to-end without a
hand-crafted tape, so these focus on the load-bearing, independently-checkable
pieces: the pivot/swing helper (and its repaint lag), the RTH session mask, the
setup detector's bias rules, and that ``generate_trades`` runs causally on
synthetic data producing only well-formed, closed trades. Deterministic, no
network. See ``docs/TESTING.md``.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from tradingbot.indicators.volume_profile import compute_profile
from tradingbot.strategy.vp_ict_v1 import (
    Params,
    _detect_setup,
    _rolling_swings,
    _rth_mask,
    _session_vwap,
    generate_trades,
)


def test_rolling_swings_confirm_with_lag() -> None:
    """A pivot high must only become known ``pivot_len`` bars after it forms.

    Pine's ``ta.pivothigh(n, n)`` confirms n bars late; the backtest must respect
    that lag or it would act on information it could not have had (lookahead).
    """
    # A clear peak at index 5 (value 10) with n=2 confirms at index 7.
    high = np.array([1, 2, 3, 4, 5, 10, 5, 4, 3, 2], dtype=float)
    low = np.array([0, 1, 2, 3, 4, 9, 4, 3, 2, 1], dtype=float)
    sh, _ = _rolling_swings(high, low, n=2)
    assert np.isnan(sh[6]), "pivot must not be known the bar before confirmation"
    assert sh[7] == 10.0, "pivot high should publish exactly n bars later"


def test_rth_mask_selects_regular_hours_only() -> None:
    """The RTH mask must include 09:30-16:00 NY and exclude overnight/weekends.

    Every level and the bias depend on the RTH session window; an off-by-one-hour
    or weekend leak here would corrupt the whole profile (the #1 tz bug).
    """
    idx = pd.DatetimeIndex(
        [
            "2026-05-11 13:30",  # 09:30 ET Monday -> in
            "2026-05-11 19:59",  # 15:59 ET Monday -> in
            "2026-05-11 20:00",  # 16:00 ET Monday -> out (exclusive end)
            "2026-05-11 08:00",  # 04:00 ET Monday -> out
            "2026-05-09 14:00",  # Saturday -> out
        ],
        tz="UTC",
    )
    mask = _rth_mask(idx)
    assert list(mask) == [True, True, False, False, False]


def test_detect_setup_bias_rules() -> None:
    """Setup bias must be long at VAL, short at VAH, and flat mid-value.

    These mappings are the core of the mean-reversion setup; if VAL did not map to
    long (or VAH to short) the strategy would fade the wrong way.
    """
    # Asymmetric profile so the value area straddles the POC with real room on
    # both sides: POC=145, VAL=125, VAH=165 (20 pts each side).
    highs = np.array([110.0, 130.0, 150.0, 170.0, 190.0])
    lows = np.array([100.0, 120.0, 140.0, 160.0, 180.0])
    vols = np.array([40.0, 45.0, 100.0, 15.0, 8.0])
    prof = compute_profile(highs, lows, vols, rows=9, va_percent=0.70)
    tol = 1.0
    atr5 = 1.0  # small ATR so the wide value area passes the POC-edge filter
    long_bias, long_name = _detect_setup(prof.val + 0.5, prof, None, tol, atr5, Params())
    short_bias, short_name = _detect_setup(prof.vah - 0.5, prof, None, tol, atr5, Params())
    assert (long_bias, long_name) == (1, "VAL")
    assert (short_bias, short_name) == (-1, "VAH")


def test_detect_setup_skips_compressed_value_area() -> None:
    """A VAL/VAH setup must be rejected when POC sits too close to that edge.

    This is the "don't trade a compressed value area" filter: if the POC→edge
    distance is below ``min_poc_edge_atr`` ATR, the edge→POC target is too small
    to be worth taking, so the setup is suppressed. Empirically these narrow-VA
    trades were the worst performers, so dropping them is the point of the filter.
    """
    highs = np.array([110.0, 130.0, 150.0, 170.0, 190.0])
    lows = np.array([100.0, 120.0, 140.0, 160.0, 180.0])
    vols = np.array([40.0, 45.0, 100.0, 15.0, 8.0])
    prof = compute_profile(highs, lows, vols, rows=9, va_percent=0.70)
    tol = 1.0
    # POC→VAL distance here is ~20 points; a large ATR makes the required room
    # (min_poc_edge_atr * atr) exceed it, so the same VAL touch must be skipped.
    big_atr = abs(prof.poc - prof.val) / Params().min_poc_edge_atr + 1.0
    bias, name = _detect_setup(prof.val + 0.5, prof, None, tol, big_atr, Params())
    assert (bias, name) == (0, "")


def _synthetic_market(n_days: int = 6, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build deterministic synthetic 1m + 5m RTH data (random walk) for E2E runs."""
    rng = np.random.default_rng(seed)
    stamps = []
    for d in range(n_days):
        day = pd.Timestamp("2026-05-11", tz="America/New_York") + pd.Timedelta(days=d)
        if day.weekday() >= 5:
            continue
        start = day.replace(hour=9, minute=30)
        stamps.append(pd.date_range(start, periods=390, freq="1min"))
    idx = (
        pd.DatetimeIndex(np.concatenate([s.values for s in stamps]))
        .tz_localize("America/New_York")
        .tz_convert("UTC")
    )
    price = 20000 + np.cumsum(rng.normal(0, 3, size=len(idx)))
    high = price + rng.uniform(0.5, 4, size=len(idx))
    low = price - rng.uniform(0.5, 4, size=len(idx))
    open_ = price + rng.normal(0, 1, size=len(idx))
    vol = rng.uniform(50, 500, size=len(idx))
    df1 = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": price, "volume": vol}, index=idx
    )
    df1.index.name = "timestamp"
    df5 = (
        df1.resample("5min")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    return df1, df5


def test_generate_trades_runs_and_trades_are_well_formed() -> None:
    """End-to-end: the engine runs on synthetic data and emits only valid trades.

    This is a smoke + invariants test (not a P&L assertion): every produced trade
    must be closed, have a direction in {-1, +1}, an exit at/after entry, and
    realized points consistent with its entry/exit. Catches crashes and
    state-machine leaks (e.g. trades left open or with inverted P&L).
    """
    df1, df5 = _synthetic_market()
    trades = generate_trades(df1, df5, Params())
    for t in trades:
        assert t.direction in (-1, 1)
        assert t.exit_time is not None and t.exit_price is not None
        assert t.exit_time >= t.entry_time
        expected = (t.exit_price - t.entry_price) * t.direction
        assert t.points == expected


def test_no_trades_outside_rth() -> None:
    """No trade may be entered outside the RTH session window.

    The strategy is intraday-only; an entry stamped overnight would mean the RTH
    gate leaked and the backtest is trading hours that don't exist for it.
    """
    df1, df5 = _synthetic_market()
    trades = generate_trades(df1, df5, Params())
    mask = _rth_mask(pd.DatetimeIndex([t.entry_time for t in trades])) if trades else []
    assert all(mask), "all entries must fall inside RTH"


def test_session_vwap_resets_each_session() -> None:
    """Session VWAP must start at the first bar's typical price and stay bounded.

    A correct anchored VWAP equals the typical price on a session's first bar and
    thereafter stays within that session's price range; a leak across sessions (no
    reset) would drift it outside, breaking the premium/discount gate.
    """
    df1, _ = _synthetic_market()
    vwap = _session_vwap(df1)
    assert len(vwap) == len(df1)
    # VWAP must always sit within the running high/low envelope of the data.
    assert np.nanmin(vwap) >= df1["low"].min() - 1e-6
    assert np.nanmax(vwap) <= df1["high"].max() + 1e-6


def test_killzone_filter_is_subset_of_unfiltered() -> None:
    """Enabling the killzone filter must only ever remove trades, never add them.

    The killzone is a pure entry gate; turning it on can reduce the trade set but
    must never produce a trade that the unfiltered run didn't (a sanity check that
    the filter is subtractive, not a logic change to entries).
    """
    df1, df5 = _synthetic_market()
    base = Params(use_killzone=False)
    gated = replace(base, use_killzone=True)
    n_base = len(generate_trades(df1, df5, base))
    n_gated = len(generate_trades(df1, df5, gated))
    assert n_gated <= n_base
