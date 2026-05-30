"""Vectorized Volume Profile core — the Python parity port of the Pine indicator.

This mirrors the Volume-Profile math in
``indicator/vp_ict_strategy_v1.pine`` (functions ``f_buildProfile`` and
``f_valueArea``) so the Phase 2 bot and the Phase 1 indicator agree on POC / VAH
/ VAL. It is the portable, testable heart of "Strategy V1" (see
``docs/STRATEGY_V1.md`` and ``docs/INDICATOR.md``).

Conventions (kept identical to the Pine source and the ``volume-profile`` skill):

* **Volume-at-price is approximated from OHLCV** by distributing each bar's
  volume uniformly across the rows its high-low range spans — chart bars carry
  no intrabar tick detail. This is a model, not a tick reconstruction.
* **Value Area** uses the canonical algorithm: from the POC, compare the two
  rows above against the two rows below, add the larger pair, repeat until the
  cumulative volume reaches ``va_percent`` (default 0.70). Ties expand
  **upward** (TradingView's upper-row convention).
* Row count is the dominant parameter: ``row_height = (high - low) / rows`` and
  ``row_index = floor((price - low) / row_height)`` clamped to ``[0, rows-1]``.

Per ``AGENTS.md`` the histogram build is vectorized (no per-bar Python loop); the
value-area expansion is an O(rows) loop over the (small) bin array, which is the
algorithm's irreducible shape.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Profile:
    """Result of a Volume Profile computation.

    Attributes:
        bins: per-row volume, index 0 = lowest price row.
        bottom: price at the bottom edge of row 0.
        row_height: price height of one row.
        poc_index, val_index, vah_index: row indices of POC / value-area low /
            value-area high.
        poc, val, vah: the corresponding prices (row midpoints).
    """

    bins: FloatArray
    bottom: float
    row_height: float
    poc_index: int
    val_index: int
    vah_index: int

    @property
    def poc(self) -> float:
        return self._price_at(self.poc_index)

    @property
    def val(self) -> float:
        return self._price_at(self.val_index)

    @property
    def vah(self) -> float:
        return self._price_at(self.vah_index)

    def _price_at(self, index: int) -> float:
        """Price at the midpoint of ``index`` (matches the Pine ``+ 0.5`` row mid)."""
        return self.bottom + (index + 0.5) * self.row_height


def build_bins(
    highs: FloatArray,
    lows: FloatArray,
    volumes: FloatArray,
    rows: int,
) -> tuple[FloatArray, float, float]:
    """Bin OHLCV bars into a volume-at-price histogram (vectorized).

    Each bar's volume is spread uniformly across the rows its ``[low, high]``
    range covers, identical to the Pine ``f_buildProfile`` loop but computed with
    NumPy. Returns ``(bins, bottom, row_height)``. If the session has no range
    (all bars at one price) ``row_height`` is ``0.0`` and all volume lands in
    row 0.

    Args:
        highs, lows, volumes: equal-length per-bar arrays.
        rows: number of histogram rows (bins).
    """
    if not (len(highs) == len(lows) == len(volumes)):
        raise ValueError("highs, lows and volumes must have equal length")
    if rows < 1:
        raise ValueError("rows must be >= 1")
    if len(highs) == 0:
        return np.zeros(rows, dtype=np.float64), float("nan"), float("nan")

    bottom = float(np.min(lows))
    top = float(np.max(highs))
    rng = top - bottom
    bins = np.zeros(rows, dtype=np.float64)

    if rng <= 0:
        # Degenerate: every bar at the same price -> all volume in row 0.
        bins[0] = float(np.sum(volumes))
        return bins, bottom, 0.0

    row_height = rng / rows
    lo_idx = np.clip(((lows - bottom) / row_height).astype(np.int64), 0, rows - 1)
    hi_idx = np.clip(((highs - bottom) / row_height).astype(np.int64), 0, rows - 1)
    span = hi_idx - lo_idx + 1
    per = volumes / span

    # Spread each bar's per-row share across [lo_idx, hi_idx]. Vectorized via a
    # difference array: +per at lo_idx, -per just past hi_idx, then cumulative sum.
    delta = np.zeros(rows + 1, dtype=np.float64)
    np.add.at(delta, lo_idx, per)
    np.add.at(delta, hi_idx + 1, -per)
    bins = np.cumsum(delta)[:rows]
    return bins, bottom, row_height


def value_area(bins: FloatArray, poc_index: int, va_percent: float) -> tuple[int, int]:
    """Compute the value-area low/high row indices (canonical algorithm).

    Mirrors Pine ``f_valueArea``: grow out from the POC two rows at a time, always
    taking the heavier pair, until cumulative volume reaches ``va_percent`` of the
    total. Ties expand **upward**. Returns ``(val_index, vah_index)``.

    Args:
        bins: per-row volume.
        poc_index: index of the point of control (highest-volume row).
        va_percent: fraction of total volume the value area must contain.
    """
    n = len(bins)
    total = float(np.sum(bins))
    if total <= 0:
        return poc_index, poc_index
    target = total * va_percent
    acc = float(bins[poc_index])
    up = poc_index
    dn = poc_index
    while acc < target:
        a1 = bins[up + 1] if up + 1 <= n - 1 else 0.0
        a2 = bins[up + 2] if up + 2 <= n - 1 else 0.0
        b1 = bins[dn - 1] if dn - 1 >= 0 else 0.0
        b2 = bins[dn - 2] if dn - 2 >= 0 else 0.0
        above = float(a1) + float(a2)
        below = float(b1) + float(b2)
        if above == 0 and below == 0:
            break
        if above >= below:  # tie -> expand up (upper-row convention)
            acc += above
            up = min(up + 2, n - 1)
        else:
            acc += below
            dn = max(dn - 2, 0)
    return dn, up


def compute_profile(
    highs: FloatArray,
    lows: FloatArray,
    volumes: FloatArray,
    rows: int = 24,
    va_percent: float = 0.70,
) -> Profile:
    """Build the full Volume Profile (bins + POC + value area) from OHLCV bars.

    This is the one-call entry point the bot uses; defaults match the Pine
    indicator (``rows=24``, ``va_percent=0.70``).
    """
    bins, bottom, row_height = build_bins(highs, lows, volumes, rows)
    poc_index = int(np.argmax(bins))
    val_index, vah_index = value_area(bins, poc_index, va_percent)
    return Profile(
        bins=bins,
        bottom=bottom,
        row_height=row_height,
        poc_index=poc_index,
        val_index=val_index,
        vah_index=vah_index,
    )
