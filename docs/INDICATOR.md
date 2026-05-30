# Indicator — `vp_ict_strategy_v1.pine` (logic & internals)

> Status: **draft for owner validation.** Companion to
> [`docs/STRATEGY_V1.md`](STRATEGY_V1.md) (the *trading* logic). This file
> documents *how the code works* so the Phase 2 Python port can mirror it.

- **File:** [`indicator/vp_ict_strategy_v1.pine`](../indicator/vp_ict_strategy_v1.pine)
- **Pine version:** v6.
- **Type:** `indicator(overlay=true)` — decision support, not a `strategy()`.
- **Apply it twice:** once on the **3-minute** chart (read the setup/levels), once
  on the **1-minute** chart (take the entry). Same script, same inputs.

## 1. Why one script on both timeframes

The Volume Profile is anchored to a **session window** (not to the visible
range). Because both the 3m and 1m charts cover the *same* session bars, they
bin the *same* traded volume and produce **aligned POC/VAH/VAL** — so the levels
you see on the 3m are the levels the 1m entry logic uses. This avoids a
cross-timeframe `request.security` call for levels (a performance + repaint risk
flagged in `indicator/README.md`).

## 2. Data structures & lifecycle

```
arrays sH[], sL[], sV[]   ← this session's bar highs / lows / volumes
   │  cleared on newSession (first bar inside the session window)
   │  appended on every confirmed in-session bar
   ▼
f_buildProfile()          ← bins[] histogram over [sessionLow, sessionHigh]
   │  POC = argmax(bins);  VA via f_valueArea()
   ▼
poc / vah / val / bins / profBot / profRowH
```

- **Session detection:** `time(timeframe.period, vpSession, vpTz)` is `na`
  outside the window; `newSession` = first in-session bar after a gap.
- **Confirmed bars only:** data is pushed on `barstate.isconfirmed` so the
  profile is built from closed bars (avoids intrabar flicker).
- **Cost:** RTH is ~78 bars (5m) / ~390 bars (1m). The `O(bars × rows)` rebuild
  on a ~24-row profile is small and runs once per confirmed bar, keeping the hot
  path light per `AGENTS.md`.

## 3. The functions

### `f_valueArea(bins, poc, target)` — canonical Value Area

Implements the standard algorithm from the volume-profile skill verbatim:

- Start at the POC row; repeatedly compare the **two rows above** vs the **two
  rows below**, add the **larger pair**, until cumulative volume ≥ `target ×
  total` (default 70%).
- **Tie-break:** expand **upward** (TradingView's upper-row convention) — encoded
  as `aboveSum >= belowSum`.
- Returns `[valIdx, vahIdx]` (the low/high row indices of the value area).

### `f_buildProfile()` — OHLCV → histogram → levels

1. Find session `hi`/`lo` from `sH[]`/`sL[]`; `rowH = (hi-lo)/vpRows`.
2. **Volume-at-price approximation:** for each bar, find the row span it covers
   (`loIdx..hiIdx`) and add `volume / span` to each spanned row (uniform
   distribution — the documented OHLCV model; chart bars have no tick detail).
3. `POC` = highest-volume row. Convert row indices to prices at the row **mid**
   (`lo + (idx + 0.5) × rowH`).
4. Returns POC/VAH/VAL prices plus `bins`, `profBot`, `profRowH` for drawing.

## 4. Naked POC carry-forward

`nakedPoc` holds the **previous** session's POC. On `newSession` it is promoted
from `thisSessionPoc[1]` and marked active; it is cleared the first time a bar's
range straddles it (`high >= nakedPoc and low <= nakedPoc`) — i.e. once tested.

## 5. Setup state machine (Volume Profile)

```
f_near(level) = |close - level| <= ATR×tolAtrMult

price near VAL  & close>=VAL  → bias=+1 (long),  level=VAL,  name="VAL"
price near VAH  & close<=VAH  → bias=-1 (short), level=VAH,  name="VAH"
price near nPOC (active)      → bias toward it,  name="nPOC"
price near POC                → name="POC" (context only, bias unchanged)

setupAge++ each bar; bias cleared when setupAge > setupBars
setupActive = bias != 0
```

## 6. Entry state machine (ICT) — sequential

ICT is an **ordered** move (sweep → *then* displacement/MSS+FVG → *then*
retrace), not three conditions on one candle. Both the Pine indicator (`stage`
0/1/2) and the Python port (`_EntryState`) walk these stages with timeouts, so
the two agree.

```
pivots:  ph = ta.pivothigh(pivotLen,pivotLen);  pl = ta.pivotlow(...)   [lag = pivotLen]
sweep:   sweptLow  = low<lastSwingLow  & close>lastSwingLow             (wick raid, closes back in)
         sweptHigh = high>lastSwingHigh & close<lastSwingHigh
MSS:     breakUp   = close>lastSwingHigh   (or wick if useCloseForBreak=off)
         breakDown = close<lastSwingLow
FVG:     bullFvg = low>high[2];   bearFvg = high<low[2]                 (3-candle gap)

stage 0 idle  → 1 swept:   setupActive & bias-aligned sweep   → record sweptExt
stage 1 swept → 2 armed:   within sweepWindow, MSS & FVG      → store fvgTop/fvgBot, draw box
                           (abandon if stageAge>sweepWindow or bias flips)
stage 2 armed → ENTRY:     within entryWindow, retrace into FVG to oteMax
   long:  low  <= fvgBot + (fvgTop-fvgBot)*oteMax
   short: high >= fvgTop - (fvgTop-fvgBot)*oteMax
   → entry=retrace level; stop=sweptExt ∓ ATR×stopBuffAtr; tp1=POC; tp2=opposite VA edge

INVALIDATE: close beyond sweptExt before fill, stage times out, or setup expires → stage:=0
```

The staged sweep→arm→trigger flow is what makes the entry **retrace-based** and
**sequential**: you do not enter on the displacement candle itself, you wait for
the pullback into the gap, and each stage has its own timeout.

## 7. Inputs reference

See the `INPUTS` block in the `.pine` file; grouped as **Volume Profile**,
**Setup**, **Entry (ICT)**, and **Visuals**. Every numeric threshold is an input
because (per both skills) these are conventions to be tuned and backtested, not
fixed constants. Notable defaults: `vpRows=24`, `vaPercent=0.70`,
`tolAtrMult=0.75`, `setupBars=120`, `pivotLen=4`, `useCloseForBreak=true`,
`oteMax=0.5`, `stopBuffAtr=0.1`, `sweepWindow=60`, `entryWindow=60`.

## 8. Outputs

- **Plots/shapes:** POC/VAH/VAL lines + labels, dashed naked-POC line, histogram
  boxes, HVN/LVN tags, setup diamonds, ENTRY triangles, and a trade label with
  entry/stop/targets.
- **Alerts:** `alertcondition()` for "setup formed", "long entry", "short entry",
  plus a combined `alert()` emitting a **JSON payload**
  (`{strategy, action, price, stop, tp1, tp2, setup}`) ready for the Phase 2
  webhook described in `docs/phase2-workflow.png`.

## 9. Repaint & correctness notes

- **Pivots confirm `pivotLen` bars late** — entries are detected with that lag;
  the script never uses an unconfirmed pivot.
- **Levels/histogram are (re)drawn on `barstate.islast`** to keep history clean
  and respect Pine's ~500-object limits.
- **Profile uses confirmed bars only**, so POC/VA do not flicker intrabar.
- The OHLCV volume-at-price is an **approximation** — disclosed in the header and
  in `docs/STRATEGY_V1.md §7`.

## 10. Conventions honoured (from the skills)

| Convention | Where |
| --- | --- |
| 70% / two-rows-per-side / tie-break-upper Value Area | `f_valueArea` |
| Row size = primary VP parameter, exposed | `vpRows` |
| OHLCV volume-at-price is approximate, disclosed | `f_buildProfile`, header |
| `America/New_York`, RTH session as a first-class flag | `vpSession`, `vpTz` |
| Structure break = close; sweep = wick | `breakUp/Down`, `sweptHigh/Low` |
| Displacement anchored to "left an FVG" | `bullFvg/bearFvg` |
| OTE / consequent-encroachment 50% entry | `oteMax` |
| ATR-based tolerances (cross-instrument) | `tol`, `stopBuffAtr` |
| Two-tier pivots / repaint lag stated | `pivotLen`, §9 |
