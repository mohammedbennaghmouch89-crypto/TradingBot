---
name: ict
description: >-
  Expert knowledge of the ICT (Inner Circle Trader, by Michael J. Huddleston)
  smart-money trading methodology: market structure (BOS/CHoCH/MSS), liquidity
  (sweeps/raids, BSL/SSL, inducement, draw on liquidity), PD arrays (order
  blocks, FVGs, breakers, mitigation/rejection/propulsion blocks, NWOG/NDOG),
  premium/discount & Optimal Trade Entry, time-based concepts (killzones,
  macros, Silver Bullet, Power of 3, daily bias), and entry models (2022 model,
  Silver Bullet, Turtle Soup, Unicorn, SMT divergence). Use this skill whenever
  designing, implementing, reviewing, or discussing the Phase 1 Pine Script
  indicator or the Phase 2 trading bot, or answering any ICT question. It gives
  precise, algorithmic OHLC detection rules plus the configuration decisions
  ("forks") that materially change an implementation.
---

# ICT (Inner Circle Trader) Methodology

This skill makes the agent an ICT expert for building the project's indicator
(Phase 1, Pine Script) and bot (Phase 2, Python). ICT explains price as the
output of an **algorithm** (the "Interbank Price Delivery Algorithm") whose two
jobs are: **(1) take liquidity** where stop orders rest, and **(2) rebalance
inefficiencies** (price gaps) it created. Everything below serves those two
ideas. ICT is discretionary by origin, so this skill deliberately reduces each
concept to **codeable OHLC rules** and flags where the community disagrees.

## How to use this skill

1. Start here for the **mental model, the concept map, and the implementation
   conventions** (the section that prevents most bugs).
2. Open the matching **reference file** for the precise per-concept detection
   logic (definition → detection rule → trader usage → pitfalls):

| Reference file | Covers |
| --- | --- |
| [`reference/market-structure-and-liquidity.md`](reference/market-structure-and-liquidity.md) | Swings, market structure, BOS / CHoCH / MSS, internal vs external (IRL/ERL), BSL/SSL, liquidity pools, EQH/EQL, sweeps/raids/SFP, inducement, draw on liquidity, trendline liquidity, session/day/week highs & lows |
| [`reference/pd-arrays.md`](reference/pd-arrays.md) | Premium/discount & equilibrium, order blocks, breaker/mitigation/rejection/propulsion blocks, FVG, inversion FVG, balanced price range, liquidity void, volume imbalance, opening gaps (NWOG/NDOG), the PD-array matrix |
| [`reference/time-and-price.md`](reference/time-and-price.md) | Dealing range/equilibrium, premium/discount, OTE & Fibonacci, standard-deviation projections, CBDR/Asian range, killzones, Silver Bullet windows, macros, Judas swing, Power of 3 (AMD), session opens, daily bias, daily/weekly profiles, quarterly theory |
| [`reference/entry-models-and-theory.md`](reference/entry-models-and-theory.md) | Displacement, SMT divergence, Turtle Soup, Unicorn, the 2022 model, Silver Bullet sequence, OTE model, IPDA, liquidity runs, risk management, top-down workflow, the A+ confluence checklist |

## The universal ICT trade backbone

Every ICT entry model is a variation of one sequence. Internalize this; the
named models (2022 model, Silver Bullet, Turtle Soup, Unicorn) differ only by
time-gating, an extra overlap requirement, or confirmation strictness.

```
HTF bias                    where price wants to go (draw on liquidity)
   │                        established top-down, before any entry
   ▼
Liquidity sweep             price raids a pool (wick beyond a high/low) then rejects
   │                        — this is the "manipulation" / Judas move
   ▼
MSS + displacement          counter-trend structure break by a strong candle
   │                        that leaves an FVG (the "shift")
   ▼
Retrace into PD array       entry at the FVG / order block / breaker the
   │                        displacement left behind (often its 50%)
   ▼
Target opposing liquidity   exit into the next pool; stop beyond the swept extreme
```

Mandatory gates for a valid setup: **bias + completed sweep + MSS-with-displacement
+ entry array on the correct side of equilibrium**. Boosters: killzone timing,
OTE overlap, SMT divergence, stacked arrays (OB with an FVG inside).

## Critical implementation conventions (read before coding)

These cross-cutting decisions recur in every concept and are the main source of
"the indicator disagrees with my chart." Make each a documented, configurable
input with the **default** shown. Per the project's `AGENTS.md`, the indicator
hot path must stay fast (vectorized, no per-bar loops), so prefer
O(bars) single-pass detection.

1. **Timezone — always `America/New_York`.** ICT defines all session/killzone/
   macro times in New York local wall-clock; the UTC offset shifts with US DST.
   Never hardcode a UTC offset — anchor to the `"America/New_York"` zone and let
   the platform resolve EST/EDT. (Also: US and EU DST transitions are misaligned
   for ~3 weeks each spring/fall.)

2. **Structure break = candle CLOSE, sweep = WICK.** Dominant ICT convention:
   BOS/CHoCH/MSS require a **body close** beyond the swing level; a **wick alone**
   beyond a level that **closes back inside** is a *liquidity sweep* (reversal),
   not a break (continuation). This wick-vs-close test is the cleanest
   discriminator between a sweep and a break. Expose `useCloseForBreak`
   (**default: close**) because the popular LuxAlgo SMC indicator allows wick.

3. **Two-tier pivots.** Use two swing-detection lookbacks: **internal** (short
   term, default ~5 bars/side) and **swing** (major, default ~50). This single
   choice powers internal-vs-external structure, IRL-vs-ERL, inducement, and the
   dealing range. Pivots **confirm only `pivotRight` bars later** → state this
   repaint/lag explicitly; never act on an unconfirmed pivot.

4. **Zone basis — body vs full range.** For order/breaker/mitigation/propulsion
   blocks, the zone is either the candle **body** (`min(open,close)..max(open,close)`)
   or the **full range** (`low..high`). Sources split. Provide a global setting
   (**default: full range**) with per-type overrides. The **50% / mean threshold**
   (`(top+bottom)/2`, "consequent encroachment") is the canonical entry inside any
   array.

5. **Violation basis — wick-touch vs body-close.** "Filled / mitigated /
   invalidated / inverted" can trigger on a wick touch or a body close through the
   far edge. Provide a global setting (**default: body close** for
   invalidation/inversion; wick touch for "tagged/mitigated").

6. **Displacement has no official number.** The only near-universal, non-arbitrary
   criterion is **"the move left an FVG."** Use that as the anchor; offer optional
   tunable confirmations: body/range ratio ≥ ~0.6–0.7, and range ≥ k×ATR (k≈1.5–2)
   or k×average body over N bars. Displacement is timeframe-relative.

7. **Fibonacci / OTE.** Compute levels explicitly, not via a drawing tool:
   for longs `level = low + (high-low)*r`; mirror for shorts. Retracement set
   `r ∈ {0.50, 0.62, 0.705, 0.79}` (OTE zone = 0.62–0.79, **0.705** is the focal
   level and is *not* a standard Fibonacci ratio). Profit-target extensions past
   the origin: `r ∈ {-0.27, -0.62}` (universal), optionally `{-1.0, -2.0, -2.5, -4.0}`.

8. **"Standard deviation" = range × N**, not statistical σ. SD projections are
   `boundary ± N*(rangeHigh - rangeLow)`, N = 1..3(4), off a reference range
   (CBDR / Asian / Flout).

9. **"Equal" tolerance (EQH/EQL, trendline).** No standard value. Prefer
   **ATR-based** (`tol = m*ATR`, m≈0.1) for cross-instrument robustness; also
   bound by `maxBarsBetween`. Make it a parameter.

10. **Premium/discount gating.** Only buy discount arrays / sell premium arrays.
    Equilibrium = 50% of the chosen dealing range; the result depends entirely on
    *which* range you measure, so make the range source explicit.

11. **Acronym hazard: "IFVG."** Most sources = **Inversion** FVG (a failed FVG
    that flips polarity). Some ICT pages = **Implied** FVG (wick-midpoint gap when
    bodies overlap). Name them distinctly in code/UI.

12. **True-day-open anchor is forked:** **00:00 ET (midnight, most common)** vs
    **18:00 ET (CME futures day)**. Expose a toggle (default midnight). NDOG/NWOG
    and Power-of-3 anchors depend on this.

## Acronym glossary

| Term | Meaning |
| --- | --- |
| BOS | Break of Structure (continuation, with-trend swing break) |
| CHoCH | Change of Character (first counter-trend swing break; reversal warning) |
| MSS / MSB | Market Structure Shift / Break (CHoCH **with displacement**; confirmed reversal) |
| BSL / SSL | Buy-Side / Sell-Side Liquidity (stops above highs / below lows) |
| IRL / ERL | Internal / External Range Liquidity |
| EQH / EQL | Equal Highs / Equal Lows (relative-equal liquidity pool) |
| SFP | Swing Failure Pattern (wick beyond a level, close back inside = sweep) |
| IDM | Inducement (engineered minor liquidity that traps before the real level) |
| DOL | Draw On Liquidity (the pool price is targeting) |
| OB | Order Block | 
| FVG | Fair Value Gap (3-candle imbalance) |
| IFVG | Inversion FVG (failed FVG, polarity flipped) — *not* Implied FVG |
| BPR | Balanced Price Range (overlap of a bullish and bearish FVG) |
| NWOG / NDOG | New Week / New Day Opening Gap |
| OTE | Optimal Trade Entry (0.62–0.79 fib zone, 0.705 focal) |
| PD array | Premium/Discount array (any institutional reference zone) |
| AMD / PO3 | Accumulation–Manipulation–Distribution / Power of 3 |
| SMT | Smart Money Technique (divergence between correlated assets) |
| IPDA | Interbank Price Delivery Algorithm (the "price is algorithmic" premise; 20/40/60-day ranges) |
| CBDR | Central Bank Dealing Range (14:00–20:00 ET) |
| EQ | Equilibrium (50% of a range) |

## Provenance & caveats

- ICT is taught discretionarily; many numeric thresholds (displacement size,
  "equal" tolerance, macro minute-lists, killzone bounds) are **community
  interpretations, not official constants** — they are flagged per concept and
  must be configurable.
- **Quarterly Theory** and some macro lists are ICT-*adjacent* extensions (e.g.
  Daye/TTrades), not core ICT — labeled as such in the reference.
- Reference files end with the **source URLs** used during research so claims can
  be re-verified.
