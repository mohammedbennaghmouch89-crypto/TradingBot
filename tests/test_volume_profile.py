"""Tests for the Volume Profile core (`tradingbot.indicators.volume_profile`).

These verify the parity-critical math that both the Phase 1 Pine indicator and
the Phase 2 bot rely on: the OHLCV->histogram binning, the POC, and the
canonical 70%/two-rows-per-side/tie-break-upward value-area algorithm. Each test
states *what* it checks and *why* it matters. Deterministic, no network. See
``docs/TESTING.md``.
"""

from __future__ import annotations

import numpy as np
import pytest

from tradingbot.indicators.volume_profile import (
    build_bins,
    compute_profile,
    value_area,
)


def test_poc_is_highest_volume_row() -> None:
    """POC must land on the price row that accumulates the most volume.

    The POC ("fair value") anchors every downstream level and the strategy's
    targets; if it is wrong, VAH/VAL and the trade management are all wrong.
    """
    # Three bars all spanning one row each, with a clear heaviest row in the middle.
    highs = np.array([10.5, 11.5, 12.5], dtype=np.float64)
    lows = np.array([10.0, 11.0, 12.0], dtype=np.float64)
    volumes = np.array([5.0, 100.0, 5.0], dtype=np.float64)
    prof = compute_profile(highs, lows, volumes, rows=3, va_percent=0.70)
    assert prof.poc_index == 1
    # POC price is the midpoint of the middle row.
    assert prof.poc == pytest.approx(prof.bottom + 1.5 * prof.row_height)


def test_bins_conserve_total_volume() -> None:
    """The histogram must redistribute volume, never create or destroy it.

    Distributing a bar's volume across the rows it spans is an approximation, but
    it must still sum to the original total — a conservation check that catches
    off-by-one row-span bugs.
    """
    rng = np.random.default_rng(42)
    lows = rng.uniform(100, 200, size=50)
    highs = lows + rng.uniform(0.1, 5.0, size=50)
    volumes = rng.uniform(1, 1000, size=50)
    bins, _, _ = build_bins(highs, lows, volumes, rows=30)
    assert float(np.sum(bins)) == pytest.approx(float(np.sum(volumes)))


def test_value_area_simple_known_case() -> None:
    """Value area must match a hand-computed expansion on a known histogram.

    Bins ``[1, 2, 10, 3, 1]`` (total 17, POC at index 2). With a 70% target
    (11.9) the algorithm compares the two-above pair (3+1=4) vs the two-below
    pair (2+1=3); 4 >= 3 so it expands up to index 4 (acc=14 >= 11.9). VAL stays
    at the POC row 2, VAH at row 4. Pins the canonical two-rows-per-side rule.
    """
    bins = np.array([1, 2, 10, 3, 1], dtype=np.float64)
    val_index, vah_index = value_area(bins, poc_index=2, va_percent=0.70)
    assert (val_index, vah_index) == (2, 4)


def test_value_area_tie_breaks_upward() -> None:
    """On an exact above/below tie, the value area must expand upward.

    This is the TradingView upper-row convention encoded as ``above >= below``.
    Symmetric bins ``[2, 5, 2]`` around the POC give a 2-vs-2 tie at the first
    step. With a 70% target (6.3) the algorithm reaches the target on that single
    tie step, which must consume the **upper** row (acc 5 -> 7): VAH lands above
    the POC and VAL stays on it. Reproducibility depends on this fixed tie-break.
    """
    bins = np.array([2.0, 5.0, 2.0], dtype=np.float64)
    val_index, vah_index = value_area(bins, poc_index=1, va_percent=0.70)
    assert vah_index == 2, "tie should have expanded upward"
    assert val_index == 1, "lower row should not have been taken on the tie"


def test_value_area_spans_everything_at_100_percent() -> None:
    """A value-area target of 100% must include every non-empty row.

    Guards the loop's termination: with the target equal to the total it must
    keep expanding to both ends rather than stopping early or looping forever.
    """
    bins = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=np.float64)
    val_index, vah_index = value_area(bins, poc_index=2, va_percent=1.0)
    assert (val_index, vah_index) == (0, 4)


def test_degenerate_single_price_session() -> None:
    """A session with no price range must not divide by zero.

    When every bar trades at one price (range 0) the build collapses all volume
    into row 0 with ``row_height == 0`` instead of raising — a real edge case for
    illiquid or halted instruments.
    """
    highs = np.array([50.0, 50.0], dtype=np.float64)
    lows = np.array([50.0, 50.0], dtype=np.float64)
    volumes = np.array([10.0, 20.0], dtype=np.float64)
    bins, bottom, row_height = build_bins(highs, lows, volumes, rows=10)
    assert row_height == 0.0
    assert bins[0] == pytest.approx(30.0)
    assert bottom == pytest.approx(50.0)


def test_empty_input_returns_zero_bins() -> None:
    """No bars must yield an all-zero histogram, not an error.

    Before a session has any bars the profile must be defined (empty) so callers
    can treat "no levels yet" uniformly.
    """
    empty = np.array([], dtype=np.float64)
    bins, _, _ = build_bins(empty, empty, empty, rows=8)
    assert bins.shape == (8,)
    assert float(np.sum(bins)) == 0.0


def test_mismatched_lengths_raise() -> None:
    """Unequal input lengths must raise rather than silently misalign bars.

    A length mismatch means OHLCV columns are out of sync; failing fast prevents
    a corrupted profile from feeding the strategy.
    """
    with pytest.raises(ValueError, match="equal length"):
        build_bins(
            np.array([1.0, 2.0]),
            np.array([1.0]),
            np.array([1.0, 2.0]),
            rows=4,
        )


def test_build_bins_matches_naive_loop_reference() -> None:
    """The vectorized binning must equal a plain per-bar reference loop.

    AGENTS.md requires the hot path be vectorized (no Python per-bar loop). This
    test keeps an obviously-correct scalar reference and asserts the fast
    NumPy implementation reproduces it exactly, so optim/perf cannot drift from
    correctness.
    """
    rng = np.random.default_rng(7)
    lows = rng.uniform(100, 110, size=40)
    highs = lows + rng.uniform(0.05, 3.0, size=40)
    volumes = rng.uniform(1, 500, size=40)
    rows = 16

    fast, bottom, row_height = build_bins(highs, lows, volumes, rows)

    # Naive, unmistakable reference (the algorithm spelled out bar by bar).
    ref = np.zeros(rows, dtype=np.float64)
    for h, low, v in zip(highs, lows, volumes, strict=True):
        lo_idx = min(max(int((low - bottom) / row_height), 0), rows - 1)
        hi_idx = min(max(int((h - bottom) / row_height), 0), rows - 1)
        share = v / (hi_idx - lo_idx + 1)
        for r in range(lo_idx, hi_idx + 1):
            ref[r] += share

    np.testing.assert_allclose(fast, ref, rtol=1e-9, atol=1e-9)
