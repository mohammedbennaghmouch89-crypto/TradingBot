"""Strategy V1 in Python — Volume-Profile setup (5m) + ICT entry (1m).

This is the executable port of ``indicator/vp_ict_strategy_v1.pine`` used by the
backtester. It reuses the vectorized Volume Profile core
(``tradingbot.indicators.volume_profile``) for the 5m context and reproduces the
two state machines documented in ``docs/INDICATOR.md``:

* **Setup (5m):** a session Volume Profile arms a directional bias when price
  reaches VAL (long), VAH (short) or a naked POC (toward it).
* **Entry (1m):** within the setup window, an ICT liquidity sweep -> market
  structure shift (close break) -> displacement/FVG -> retrace-into-FVG entry in
  the bias direction, with a stop beyond the swept extreme and targets at POC and
  the opposite value-area edge.

It walks 1m bars and, for each, reads the *most recently completed* 5m session
profile — never future data — so signals are causal (backtest-safe). Pivots use
the same confirm-lag convention as Pine (a pivot is known ``pivot_len`` bars
later).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tradingbot.indicators.volume_profile import Profile, compute_profile

# New York session for RTH; the profile and bias use this window.
RTH_TZ = "America/New_York"
RTH_START = (9, 30)
RTH_END = (16, 0)


@dataclass(frozen=True)
class Params:
    """Tunable Strategy V1 parameters (defaults match the Pine inputs)."""

    rows: int = 24
    va_percent: float = 0.70
    tol_atr_mult: float = 0.75
    setup_bars: int = 120
    pivot_len: int = 4
    use_close_break: bool = True
    ote_max: float = 0.5
    stop_buf_atr: float = 0.1
    atr_len: int = 14
    # How many 1m bars after a liquidity sweep we keep looking for the MSS+FVG,
    # and how many bars after arming the FVG we keep waiting for the retrace
    # entry. A sweep -> displacement -> retrace sequence can take ~30-60 min on
    # 1m, so these are generous by default; tighten them to trade more selectively.
    sweep_window: int = 60
    entry_window: int = 60
    # Minimum distance (in ATR) from the POC to the value-area edge being traded.
    # If the value area is compressed (POC sits right next to VAH/VAL) the edge
    # trade has almost no room to its POC target, so skip it. 0 disables. Kept
    # gentle (1.25): on this small sample, win rate improves up to ~1.25 ATR but
    # larger values overfit (one dropped setup re-routes the sequence badly).
    min_poc_edge_atr: float = 1.25
    # --- Trade-selection filters (ICT/VP confluence; see docs/STRATEGY_V1.md) ---
    # VWAP premium/discount gate: take longs only at/below VWAP (discount) and
    # shorts only at/above VWAP (premium) — VWAP as the equilibrium/fair value.
    # On the test window this ~doubled net P&L and lowered drawdown while keeping
    # a usable trade count, so it is on by default.
    use_vwap_pd: bool = True
    # Killzone: only enter inside the high-probability NY-AM window (minutes from
    # NY midnight). 09:30-11:30 ET captures the NY open + the 10-11 Silver Bullet.
    # Off by default: it lifts win rate sharply but cuts the 3-week sample to a
    # handful of trades (overfit risk). Enable once more data is available.
    use_killzone: bool = False
    killzone_start_min: int = 9 * 60 + 30
    killzone_end_min: int = 11 * 60 + 30
    # Exit target: "poc" (nearer, higher win rate) or "opposite_edge" (TP2,
    # further, bigger winners). POC default keeps the higher win rate.
    target_mode: str = "poc"
    # Trade management: once price reaches this fraction of the entry->target
    # distance, move the stop to breakeven (entry). Protects open profit on trades
    # that run in favour then reverse. 0 disables. 0.5 = halfway to target.
    breakeven_at: float = 0.5


@dataclass
class Trade:
    """One round-trip trade produced by the strategy."""

    direction: int  # +1 long, -1 short
    setup: str
    entry_time: pd.Timestamp
    entry_price: float
    stop: float
    tp1: float
    tp2: float
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str = ""
    points: float = 0.0
    be_armed: bool = False  # stop has been moved to breakeven
    initial_stop: float = field(init=False)  # entry-time stop (for risk reporting)

    def __post_init__(self) -> None:
        # Capture the original stop before any breakeven move mutates ``stop``.
        self.initial_stop = self.stop


@dataclass
class _SessionProfile:
    """Cached profile + ATR for a completed RTH session."""

    profile: Profile
    naked_poc: float | None
    atr5: float


def _rth_mask(index: pd.DatetimeIndex) -> np.ndarray:
    """Boolean mask of bars inside the RTH window (NY time)."""
    local = index.tz_convert(RTH_TZ)
    minutes = local.hour * 60 + local.minute
    start = RTH_START[0] * 60 + RTH_START[1]
    end = RTH_END[0] * 60 + RTH_END[1]
    weekday = local.weekday < 5  # Mon-Fri
    return np.asarray((minutes >= start) & (minutes < end) & weekday)


def _session_id(index: pd.DatetimeIndex) -> np.ndarray:
    """Integer id per RTH calendar day (NY), for grouping a session's bars."""
    local = index.tz_convert(RTH_TZ)
    return np.asarray(local.normalize().asi8)


def _atr(df: pd.DataFrame, length: int) -> pd.Series:
    """Wilder-style ATR (RMA of true range)."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(
        axis=1
    )
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def _session_vwap(df: pd.DataFrame) -> np.ndarray:
    """Session-anchored VWAP, reset each RTH day (NY).

    VWAP = cumulative(typical_price x volume) / cumulative(volume) within the
    session. Used as the equilibrium / fair-value reference for the ICT
    premium-discount entry gate (VP↔ICT mapping: VWAP ↔ equilibrium).
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    sid = pd.Series(_session_id(df.index), index=df.index)
    pv = (typical * df["volume"]).groupby(sid).cumsum()
    vol = df["volume"].groupby(sid).cumsum().replace(0, np.nan)
    return np.asarray((pv / vol).to_numpy(dtype=float))


def _ny_minutes(index: pd.DatetimeIndex) -> np.ndarray:
    """Minutes since NY midnight for each bar (for the killzone window)."""
    local = index.tz_convert(RTH_TZ)
    return np.asarray(local.hour * 60 + local.minute)


def _build_session_profiles(df5: pd.DataFrame, p: Params) -> dict[int, _SessionProfile]:
    """Compute one Volume Profile per completed RTH session on the 5m data.

    The profile for session *S* is only used by 1m bars that occur *after* S
    closes (or, for the live session, from its accumulated-so-far bars). To keep
    the backtest causal and simple we key by session id and, when trading inside a
    session, the engine uses the *prior* completed session's profile as context —
    matching how a trader reads "yesterday/earlier value" on the 5m.
    """
    rth = df5[_rth_mask(df5.index)].copy()
    rth["sid"] = _session_id(rth.index)
    atr5 = _atr(df5, p.atr_len)

    profiles: dict[int, _SessionProfile] = {}
    prev_poc: float | None = None
    for sid, grp in rth.groupby("sid"):
        prof = compute_profile(
            grp["high"].to_numpy(dtype=float),
            grp["low"].to_numpy(dtype=float),
            grp["volume"].to_numpy(dtype=float),
            rows=p.rows,
            va_percent=p.va_percent,
        )
        atr_val = float(atr5.loc[: grp.index[-1]].iloc[-1])
        profiles[int(sid)] = _SessionProfile(profile=prof, naked_poc=prev_poc, atr5=atr_val)
        prev_poc = prof.poc
    return profiles


@dataclass
class _EntryState:
    """Sequential ICT entry machine: sweep -> MSS+FVG -> retrace.

    ICT describes the entry as an *ordered sequence*, not three things on one
    candle: liquidity is swept first, then a displacement breaks structure and
    leaves an FVG over the following candles, then price retraces into that FVG.
    ``stage`` tracks where we are; ``bars_in_stage`` ages out a stalled setup.
    """

    stage: str = "idle"  # idle -> swept -> armed
    direction: int = 0
    bars_in_stage: int = 0
    swept_ext: float = 0.0  # the extreme the sweep raided (stop reference)
    fvg_top: float = 0.0
    fvg_bot: float = 0.0

    def reset(self) -> None:
        self.stage = "idle"
        self.direction = 0
        self.bars_in_stage = 0


def generate_trades(df1: pd.DataFrame, df5: pd.DataFrame, p: Params) -> list[Trade]:
    """Run Strategy V1 over aligned 1m/5m data and return the round-trip trades.

    One position at a time (flat-to-flat); a position exits on stop, TP2, or the
    end of its RTH session (no overnight risk for an intraday micro strategy).
    """
    profiles = _build_session_profiles(df5, p)
    session_ids = sorted(profiles)

    df1 = df1.copy()
    in_rth = _rth_mask(df1.index)
    df1_sid = _session_id(df1.index)
    atr1 = _atr(df1, p.atr_len).to_numpy()
    vwap1 = _session_vwap(df1)
    ny_min = _ny_minutes(df1.index)

    high = df1["high"].to_numpy(dtype=float)
    low = df1["low"].to_numpy(dtype=float)
    close = df1["close"].to_numpy(dtype=float)
    times = df1.index

    # Confirmed pivots (known pivot_len bars later) -> last swing high/low series.
    last_sh, last_sl = _rolling_swings(high, low, p.pivot_len)

    trades: list[Trade] = []
    open_trade: Trade | None = None
    entry = _EntryState()

    # Setup state (from the 5m context, refreshed as price nears a level).
    setup_bias = 0
    setup_name = ""
    setup_age = 0

    for i in range(len(df1)):
        if not in_rth[i]:
            _force_exit(open_trade, times[i], close[i], "session_end")
            open_trade = None
            setup_bias = 0
            entry.reset()
            continue

        sid = df1_sid[i]
        ctx = _context_profile(profiles, session_ids, sid)
        if ctx is None:
            continue
        prof, atr5, naked = ctx.profile, ctx.atr5, ctx.naked_poc
        tol = atr5 * p.tol_atr_mult

        # ---- manage an open position first ----
        if open_trade is not None:
            if _check_exit(open_trade, high[i], low[i], times[i], p):
                open_trade = None
            else:
                continue  # one position at a time

        # ---- setup detection (Volume Profile bias) ----
        c = close[i]
        new_bias, new_name = _detect_setup(c, prof, naked, tol, atr5, p)
        if new_bias != 0:
            setup_bias, setup_name, setup_age = new_bias, new_name, 0
        elif setup_bias != 0:
            setup_age += 1
            if setup_age > p.setup_bars:
                setup_bias = 0
                entry.reset()

        if setup_bias == 0:
            continue

        # ---- sequential ICT entry machine on 1m ----
        if i < 2:
            continue
        sh, sl = last_sh[i], last_sl[i]
        a = atr1[i] if not np.isnan(atr1[i]) else 0.0
        kz_ok = (not p.use_killzone) or (p.killzone_start_min <= ny_min[i] < p.killzone_end_min)
        vwap = vwap1[i]
        open_trade = _step_entry(
            entry,
            setup_bias,
            setup_name,
            i,
            high,
            low,
            close,
            times,
            sh,
            sl,
            prof,
            a,
            kz_ok,
            vwap,
            p,
        )
        if open_trade is not None:
            trades.append(open_trade)
            entry.reset()

    # Close any still-open trade at the last bar.
    _force_exit(open_trade, times[-1], close[-1], "data_end")
    return trades


def _context_profile(
    profiles: dict[int, _SessionProfile], session_ids: list[int], sid: int
) -> _SessionProfile | None:
    """Return the profile context for a 1m bar: the prior completed session.

    Using the previous session's value area as context for the current session is
    the causal, no-lookahead choice (today trades against yesterday's value).
    """
    if sid in profiles:
        idx = session_ids.index(sid)
        if idx == 0:
            return None
        return profiles[session_ids[idx - 1]]
    # 1m bar with no matching 5m session -> use the latest completed one before it.
    earlier = [s for s in session_ids if s < sid]
    return profiles[earlier[-1]] if earlier else None


def _detect_setup(
    c: float, prof: Profile, naked: float | None, tol: float, atr5: float, p: Params
) -> tuple[int, str]:
    """Return (bias, name) if price is within ``tol`` of a key level, else (0,'').

    Value-area-edge setups (VAL/VAH) are skipped when the value area is too
    compressed — i.e. the POC sits closer than ``min_poc_edge_atr`` ATR to the
    edge being traded — because the edge→POC profit target would then be tiny.
    Naked-POC setups have no value-area-edge geometry, so the filter ignores them.
    """
    min_room = p.min_poc_edge_atr * atr5
    at_val = abs(c - prof.val) <= tol and c >= prof.val
    at_vah = abs(c - prof.vah) <= tol and c <= prof.vah
    if at_val and abs(prof.poc - prof.val) >= min_room:
        return 1, "VAL"
    if at_vah and abs(prof.vah - prof.poc) >= min_room:
        return -1, "VAH"
    if naked is not None and abs(c - naked) <= tol:
        return (1 if c < naked else -1), "nPOC"
    return 0, ""


def _rolling_swings(high: np.ndarray, low: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Last confirmed swing-high / swing-low at each bar (pivot confirms n bars late).

    A bar j is a pivot high if its high is the strict max of [j-n, j+n]; it only
    becomes *known* at bar j+n, so we publish it from j+n onward (matching Pine's
    ``ta.pivothigh(n, n)`` repaint lag).
    """
    size = len(high)
    sh = np.full(size, np.nan)
    sl = np.full(size, np.nan)
    cur_h = np.nan
    cur_l = np.nan
    for j in range(size):
        piv = j - n  # the bar that could now be confirmed
        if piv - n >= 0:
            window_h = high[piv - n : piv + n + 1]
            window_l = low[piv - n : piv + n + 1]
            if high[piv] == window_h.max() and (window_h == high[piv]).sum() == 1:
                cur_h = high[piv]
            if low[piv] == window_l.min() and (window_l == low[piv]).sum() == 1:
                cur_l = low[piv]
        sh[j] = cur_h
        sl[j] = cur_l
    return sh, sl


def _step_entry(
    e: _EntryState,
    bias: int,
    name: str,
    i: int,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    times: pd.DatetimeIndex,
    sh: float,
    sl: float,
    prof: Profile,
    atr1: float,
    kz_ok: bool,
    vwap: float,
    p: Params,
) -> Trade | None:
    """Advance the sequential ICT entry machine by one 1m bar.

    Stages, all in the setup's bias direction:

    * **idle -> swept:** a liquidity sweep (wick beyond the relevant swing that
      closes back inside) starts the sequence and records the swept extreme.
    * **swept -> armed:** within ``sweep_window`` bars, a displacement that both
      breaks structure (close beyond the opposing swing) **and** leaves a 3-candle
      FVG arms that FVG as the entry zone.
    * **armed -> entry:** within ``entry_window`` bars, price retracing into the
      FVG to the ``ote_max`` level fires the trade; stop sits beyond the swept
      extreme, targets at POC and the opposite value-area edge.

    Each stage ages out (``bars_in_stage``) so a stalled sequence is abandoned.
    """
    e.bars_in_stage += 1

    if e.stage == "idle":
        if bias == 1 and not np.isnan(sl) and low[i] < sl and close[i] > sl:
            e.stage, e.direction, e.bars_in_stage, e.swept_ext = "swept", 1, 0, low[i]
        elif bias == -1 and not np.isnan(sh) and high[i] > sh and close[i] < sh:
            e.stage, e.direction, e.bars_in_stage, e.swept_ext = "swept", -1, 0, high[i]
        return None

    if e.stage == "swept":
        if e.bars_in_stage > p.sweep_window or e.direction != bias:
            e.reset()
            return None
        if e.direction == 1:
            brk = (close[i] > sh) if p.use_close_break else (high[i] > sh)
            brk = bool(brk) and not np.isnan(sh)
            fvg = low[i] > high[i - 2]
            if brk and fvg:
                e.stage, e.bars_in_stage = "armed", 0
                e.fvg_top, e.fvg_bot = low[i], high[i - 2]
        else:
            brk = (close[i] < sl) if p.use_close_break else (low[i] < sl)
            brk = bool(brk) and not np.isnan(sl)
            fvg = high[i] < low[i - 2]
            if brk and fvg:
                e.stage, e.bars_in_stage = "armed", 0
                e.fvg_top, e.fvg_bot = low[i - 2], high[i]
        return None

    # e.stage == "armed": wait for the retrace into the FVG.
    if e.bars_in_stage > p.entry_window:
        e.reset()
        return None
    if e.direction == 1:
        level = e.fvg_bot + (e.fvg_top - e.fvg_bot) * p.ote_max
        if low[i] <= level:
            # Selection gates: NY killzone + discount to VWAP (long).
            pd_ok = (not p.use_vwap_pd) or np.isnan(vwap) or level <= vwap
            if kz_ok and pd_ok:
                stop = e.swept_ext - atr1 * p.stop_buf_atr
                return Trade(1, name, times[i], level, stop, prof.poc, prof.vah)
            e.reset()  # arrived at the zone but failed a gate -> drop the setup
        elif close[i] < e.swept_ext:  # invalidated: closed back beyond the sweep
            e.reset()
    else:
        level = e.fvg_top - (e.fvg_top - e.fvg_bot) * p.ote_max
        if high[i] >= level:
            pd_ok = (not p.use_vwap_pd) or np.isnan(vwap) or level >= vwap
            if kz_ok and pd_ok:
                stop = e.swept_ext + atr1 * p.stop_buf_atr
                return Trade(-1, name, times[i], level, stop, prof.poc, prof.val)
            e.reset()
        elif close[i] > e.swept_ext:
            e.reset()
    return None


def _check_exit(trade: Trade, hi: float, lo: float, t: pd.Timestamp, p: Params) -> bool:
    """Stop/target check for the open trade. Returns True if it exited this bar.

    With a single MNQ contract there is no scaling out, so the position takes a
    single target chosen by ``p.target_mode``: ``"poc"`` (TP1 — nearer, highest
    win rate) or ``"opposite_edge"`` (TP2 — the full value-area rotation, bigger
    winners). With the selection filters raising trade quality, running to TP2 is
    viable and lifts profit.

    Trade management: once price reaches ``p.breakeven_at`` of the entry→target
    distance, the stop is moved to breakeven (entry). The move is applied at the
    end of a bar — *after* that bar's stop/target checks — so it never uses
    intrabar look-ahead; it protects subsequent bars. A breakeven exit is tagged
    ``"be"``. Conservative tie-break: if a bar straddles both stop and target,
    assume the **stop** is hit first so the backtest never flatters itself.
    """
    target = trade.tp1 if p.target_mode == "poc" else trade.tp2
    reason = "tp1" if p.target_mode == "poc" else "tp2"
    if trade.direction == 1:
        if lo <= trade.stop:
            _close(trade, t, trade.stop, "be" if trade.be_armed else "stop")
            return True
        if hi >= target:
            _close(trade, t, target, reason)
            return True
        # Move stop to breakeven once price reaches `breakeven_at` of the target.
        if p.breakeven_at > 0 and not trade.be_armed:
            trigger = trade.entry_price + (target - trade.entry_price) * p.breakeven_at
            if hi >= trigger:
                trade.stop = trade.entry_price
                trade.be_armed = True
    else:
        if hi >= trade.stop:
            _close(trade, t, trade.stop, "be" if trade.be_armed else "stop")
            return True
        if lo <= target:
            _close(trade, t, target, reason)
            return True
        if p.breakeven_at > 0 and not trade.be_armed:
            trigger = trade.entry_price - (trade.entry_price - target) * p.breakeven_at
            if lo <= trigger:
                trade.stop = trade.entry_price
                trade.be_armed = True
    return False


def _force_exit(trade: Trade | None, t: pd.Timestamp, px: float, reason: str) -> None:
    """Flatten an open trade at ``px`` (session/data end), in place."""
    if trade is not None and trade.exit_time is None:
        _close(trade, t, px, reason)


def _close(trade: Trade, t: pd.Timestamp, px: float, reason: str) -> None:
    """Record the exit and realized points on a trade."""
    trade.exit_time = t
    trade.exit_price = px
    trade.exit_reason = reason
    trade.points = (px - trade.entry_price) * trade.direction
