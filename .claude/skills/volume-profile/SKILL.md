---
name: volume-profile
description: >-
  Expert knowledge of Volume Profile and Market Profile trading (Auction Market
  Theory): how a volume-at-price histogram is built (rows/bins), POC, Value Area
  (VAH/VAL) and the exact 70% value-area algorithm, HVN/LVN nodes, profile shapes
  (D/P/b/B/trend), naked/virgin POC, developing-VA migration, excess & poor
  highs/lows; profile types (VPVR, FRVP, session/periodic, composite); Initial
  Balance, Dalton day types & open types; VWAP with standard-deviation bands; and
  trading strategies (value-area rejection & the 80% rule, breakout/acceptance,
  POC & naked-POC plays, LVN/HVN trades, day-type playbooks, VWAP & ICT
  confluence). Use this skill whenever designing, implementing, reviewing, or
  discussing the Phase 1 Pine Script indicator or the Phase 2 bot, or answering
  any Volume/Market Profile question. It gives precise, calculable rules plus the
  configuration decisions ("forks") that materially change an implementation.
---

# Volume Profile & Market Profile

This skill makes the agent an expert in **Volume Profile** (a histogram of
**volume traded at each price**) and its parent **Market Profile / TPO** (time
spent at each price), both grounded in **Auction Market Theory (AMT)**: the market
is a two-way auction whose purpose is to *facilitate trade*; price rises to shut
off buying and falls to shut off selling, constantly searching for the price where
the most business occurs (**fair value / the POC**). The tooling quantifies *where*
value is, *whether* the market is in balance or imbalance, and *whether* a level is
being accepted or rejected.

It pairs with the [`ict`](../ict/SKILL.md) skill: VP marks the same institutional
zones from a volume angle (see the **VP ↔ ICT mapping** below).

## How to use this skill

1. Read here for the **mental model, the value-area algorithm, and the
   implementation conventions** (the section that prevents most bugs).
2. Open the matching **reference file** for precise per-concept detection logic
   (definition → calculation/detection → usage → pitfalls):

| Reference file | Covers |
| --- | --- |
| [`reference/foundations-and-calculation.md`](reference/foundations-and-calculation.md) | Auction Market Theory, Volume vs Market Profile/TPO, building the histogram (rows/bins/ticks-per-row), up/down/delta per row, POC, Value Area/VAH/VAL, **the standard 70% value-area algorithm**, why 70%≈1σ, the Pine data-approximation problem, resolution vs performance |
| [`reference/structure-nodes-and-shapes.md`](reference/structure-nodes-and-shapes.md) | HVN/LVN detection, single prints, profile shapes (D/P/b/B-double/trend), naked & virgin POC, developing POC/VA & migration, excess (buying/selling tails), poor highs/lows, balance vs imbalance, value-area width, composite ledges |
| [`reference/profile-types-sessions-and-vwap.md`](reference/profile-types-sessions-and-vwap.md) | VPVR, FRVP, session/periodic & composite profiles, session boundaries (RTH vs ETH, `America/New_York`), Initial Balance, range extension, Dalton day types & open types, VWAP formula, σ-bands, anchored VWAP, σ-bands vs value area |
| [`reference/strategies.md`](reference/strategies.md) | acceptance vs rejection (defined), value-area rejection fade, the 80% rule, breakout/acceptance, POC S/R & magnet, naked-POC trades, LVN/HVN trades, trend-day vs range-day playbooks, open-type strategies, VWAP confluence, VP+ICT confluence, risk management, multi-timeframe use |

## Core levels (the vocabulary)

- **POC (Point of Control):** the single price row with the most traded volume (or
  most TPO letters) — the modal "fairest" price; a magnet and S/R.
- **Value Area (VA) / VAH / VAL:** the contiguous band around the POC holding a
  target % (default ~70%) of volume; VAH/VAL are its high/low — the "fair value" range.
- **HVN (High Volume Node):** a local volume peak — acceptance/consolidation; strong
  S/R; price sticks.
- **LVN (Low Volume Node):** a local volume valley — rejection / "frictionless"; price
  traverses fast; breakout & stop-placement zone.
- **Naked / Virgin POC:** a prior period's POC never revisited since — an untested magnet.

## The standard Value Area algorithm (codeable)

The canonical "from POC, compare two rows above vs two below, add the larger pair,
repeat to ~70%." Identical for volume (`rows[i]` = volume) or TPO (`rows[i]` = letter
count). Cache the cumulative sums; it is O(rows) per recompute (keep it off the
per-bar hot path where possible).

```
INPUT:  rows[]        # per-row volume, index 0 = lowest price
        vaPercent     # default 0.70
total  = sum(rows)
target = total * vaPercent
poc    = argmax(rows)
acc    = rows[poc];  upIdx = poc;  dnIdx = poc
while acc < target:
    aboveSum = (rows[upIdx+1] or 0) + (rows[upIdx+2] or 0)   # two rows above
    belowSum = (rows[dnIdx-1] or 0) + (rows[dnIdx-2] or 0)   # two rows below
    if aboveSum == 0 and belowSum == 0: break                # exhausted
    if   aboveSum >  belowSum: acc += aboveSum; upIdx += 2
    elif belowSum >  aboveSum: acc += belowSum; dnIdx -= 2
    else:                      acc += aboveSum; upIdx += 2    # tie -> see convention 6
VAL = price_at(dnIdx);  VAH = price_at(upIdx);  POC = price_at(poc)
```

## Critical implementation conventions (read before coding)

These cross-cutting decisions recur everywhere and are the main source of "my
profile doesn't match the platform." Make each a documented, configurable input with
the **default** shown. Per `AGENTS.md`, keep the indicator fast: precompute bins,
cache cumulative sums, and recompute the profile only when the range/params change —
not on every tick.

1. **Volume-at-price is approximated from OHLCV — the core gotcha.** A *true* profile
   needs tick/intrabar data; chart bars give one volume per bar with no price detail.
   Approximate by **lower-timeframe sampling** (`request.security_lower_tf`, e.g. 1-min
   sub-bars) and/or distributing a bar's volume across its range. Prefer Pine's
   `request.footprint()` where available, and in the **Python bot bin real trade ticks
   at their execution price** (exact — sidesteps the whole problem). Always disclose
   that an OHLCV profile is a model, not a reconstruction.

2. **Row size / bin height is the single most outcome-changing parameter.** It moves
   POC, VA, and every node/shape. Two inverse inputs: **Number of Rows** or **Ticks Per
   Row**, with `rowHeight = ticksPerRow * tickSize`, `rowIndex = floor((p-Bottom)/rowHeight)`
   (clamp at the top edge). For Pine↔Python parity, fix the **same `rowHeight` in price
   terms**, not just the same row count. Mind Pine's box/line object limits (~500 default).

3. **Value-area percent: 70% (convention) vs 68% (true 1σ).** Same idea (≈1 standard
   deviation); Steidlmayer rounded to 70%. Default **0.70**, expose it (some use 0.68 or
   0.80 for the 80%-rule context).

4. **VA expansion granularity: two rows per side (standard) vs one.** The classic
   CBOT/TradingView method adds **two rows at a time**; some platforms add one. They can
   differ by a row. Default **two**, document it.

5. **Timezone & session: `America/New_York`, RTH vs ETH.** Session/IB/VWAP anchors must
   use NY time with DST handled by a tz/calendar library — never hardcode a UTC offset
   (feed UTC→ET conversion errors are the #1 off-by-one-hour bug). **RTH vs ETH is a
   first-class flag** that changes every level (RTH ≈ 09:30–16:00 ET and ~70% of ES
   volume; ETH = Sun 18:00→Fri 17:00 ET with a 17:00–18:00 break). Index-futures RTH close
   is **16:00 vs 16:15 ET** depending on source — make it configurable. Use an exchange
   calendar for holidays/half-days.

6. **VA tie-break:** prefer the row **closer to POC**; if equidistant, prefer the **upper**
   row (TradingView convention) — fix it for reproducibility.

7. **Up/down volume = `close >= open` proxy.** Per-row up/down/delta from OHLCV tags a
   whole bar one direction (`close >= open` → up, ties count up) — a *coarse* proxy; true
   bid/ask delta needs tick/footprint data. `rowDelta[i] = rowUp[i] - rowDown[i]`.

8. **Acceptance vs rejection has no universal threshold — define it as config.**
   *Acceptance* = sustained two-way trade beyond a level: **≥2 thirty-min TPO periods
   (~1h)** or **≥1–2 closes** beyond, ideally on volume ≥ average. *Rejection* = quick
   move through that fails to accept and returns, leaving a wick (≥~50% of range). Model
   as `APPROACH → TOUCH → {ACCEPT | REJECT}`. This gate drives nearly every strategy.

9. **VPVR is non-deterministic** (depends on viewport zoom/width) — **do not emulate it in
   the bot**; use an explicit rolling lookback ("last N bars/days") or FRVP (fixed anchors)
   for reproducibility.

10. **Normalize Value-Area Width (VAW = VAH−VAL)** before using it as a regime signal —
    divide by ATR / price / total range; raw VAW is instrument- and bin-dependent. Narrow
    VAW ⇒ conviction/trend or compression (pre-breakout); wide VAW ⇒ balance.

11. **TPO-native vs volume.** POC/VA/HVN/LVN/shapes work on either; **excess, poor
    highs/lows, single prints need the TPO letter matrix**, so volume-only code must
    approximate them.

## Strategy backbone & regime gate

Day type decides which strategy family is valid — classify it early (first 30–60 min)
and gate accordingly:

- **Range / rotational day** (balanced D-profile, open-auction): **mean-reversion** — fade
  VAH/VAL back to POC / opposite edge; the **80% rule**; POC bounce. *Disable breakouts.*
- **Trend day** (thin/elongated profile, Open-Drive, IB breakout that holds): **continuation**
  — VA/LVN breakout with acceptance, pullback-to-POC/VWAP entries. *Disable edge fades.*

Shared sub-states reused everywhere: `APPROACH → TOUCH → {ACCEPT → trade with | REJECT →
trade against}`. Stops go where *acceptance would prove you wrong* (beyond VAH/VAL/POC/LVN);
targets are POC → opposite VA edge → next HVN → naked POC.

## VP ↔ ICT mapping (confluence with the `ict` skill)

VP (volume) and ICT (price action) often mark the **same** institutional zones — real
confluence is when both *independently* agree. Do **not** double-count one level as two.

| Volume Profile | ICT analogue |
| --- | --- |
| HVN / POC (acceptance, heavy trade) | Order Block |
| LVN / single-print (inefficiency, fast move) | Fair Value Gap (FVG) / imbalance |
| VA edges (VAH/VAL), naked POC, prior highs/lows | Liquidity pools / draw on liquidity |
| VWAP / POC (fair value) | Equilibrium / dealing-range midpoint |

High-conviction play: an ICT **liquidity sweep at/near a POC or VA edge** → displacement/FVG
back toward value → enter targeting POC then the opposite VA edge.

## Acronym glossary

| Term | Meaning |
| --- | --- |
| POC / VPOC | Point of Control (highest-volume price row) |
| VA / VAH / VAL | Value Area / its High / its Low (~70% of volume) |
| HVN / LVN | High / Low Volume Node |
| TPO | Time Price Opportunity (one letter = price traded in a time bracket) |
| nPOC / vPOC | Naked / Virgin POC (untested prior POC) |
| VPVR / VRVP | Volume Profile Visible Range |
| FRVP | Fixed Range Volume Profile |
| SVP | Session Volume Profile |
| IB | Initial Balance (first hour / two 30-min periods) |
| VAW | Value Area Width (VAH−VAL) |
| RTH / ETH | Regular / Electronic Trading Hours |
| VWAP / AVWAP | Volume-Weighted Average Price / Anchored VWAP |
| AMT | Auction Market Theory |
| OD/OTD/ORR/OA | Open-Drive / -Test-Drive / -Rejection-Reverse / -Auction |

## Provenance & caveats

- Many thresholds (HVN/LVN window & multiplier, "acceptance" periods, breakout volume
  multiple, the "80%/85%/75%" win-rates) are **conventions or marketing heuristics, not
  validated constants** — they are flagged per concept and must be configurable & backtested.
- Letter-shape naming (P vs b) conflicts across sources due to draw orientation; this skill
  uses **physical shape** (P = volume at top, b = volume at bottom).
- Reference files end with the **source URLs** used during research.
