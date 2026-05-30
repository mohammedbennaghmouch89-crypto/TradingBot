# ICT Reference — Market Structure & Liquidity

Algorithmic, OHLC-based definitions for the structure & liquidity cluster.
"Close break" = the candle **body close** crosses a level; "wick break" = only
the high/low penetrates it. See `../SKILL.md` for the cross-cutting conventions.

---

## 1. Swing highs / swing lows (the fractal foundation)

**Definition.** A swing high (pivot high) is a candle whose high exceeds the highs
of N candles on each side; a swing low is the mirror. The ICT-canonical form is the
**3-candle** pattern (N=1); the Bill Williams **fractal** uses N=2 (5 candles).

**Detection.**
- 3-bar swing high: `high[i] > high[i-1] AND high[i] > high[i+1]`; swing low mirrors with lows.
- 5-bar swing high: `high[i]` strictly greater than `high[i±1]` and `high[i±2]`.
- Generalize to a `pivotLeft / pivotRight` length. The widely used LuxAlgo SMC
  indicator uses **two tiers**: an "internal" lookback 5–49 (default 5) and a
  "swing" lookback 50–100 (default 50).
- A pivot is only confirmable `pivotRight` bars after it forms → do **not** paint
  it earlier or it repaints. Detection uses raw **wick extremes**, not closes.

**ICT pivot hierarchy** (basis of internal vs external structure): Short-Term
High/Low (STH/STL) = any swing. Intermediate-Term High (ITH) = a swing high with a
**lower** swing high on each side. Long-Term High (LTH) = an ITH with a lower ITH
on each side. Mirror for lows (ITL = swing low with a **higher** swing low on each
side).

**Pitfalls.** N=1 is noisy, N≥2 cleaner but lags. Decide `>` vs `>=` for equal
adjacent highs (most use strict `>`). Right-side confirmation lag is the #1 cause
of "the indicator changed its mind."

---

## 2. Market structure: bullish vs bearish

**Definition.** Bullish = higher highs (HH) + higher lows (HL); bearish = lower
highs (LH) + lower lows (LL); otherwise ranging.

**Detection.** Track the last confirmed swing high and low; on each new confirmed
swing compare to its predecessor (HH/LH, HL/LL). State machine: `bullish` while
HH+HL, `bearish` while LH+LL, with an explicit `ranging` state for the ambiguous
mix (HH with LL). All comparisons use swing-point wick extremes.

**Pitfalls.** Consolidation yields ambiguous structure; pivot-lookback choice
changes the entire read.

---

## 3. Break of Structure (BOS)

**Definition.** A swing break **in the trend direction** → **continuation**.
Bullish BOS = take out the prior swing high in an uptrend (new HH); bearish BOS =
take out the prior swing low in a downtrend (new LL).

**Detection.** Bullish: `close > lastSwingHigh` while bullish; bearish:
`close < lastSwingLow` while bearish. **Dominant convention requires a candle
CLOSE** beyond the level; a wick alone is a sweep, not a BOS. (LuxAlgo SMC offers a
wick/close toggle, so expose `useCloseForBreak`, default close.) The broken swing
plus the most recent opposite swing become the next structure references.

**Pitfalls.** Close-based misses fast moves; wick-based gives false signals. Define
*which* swing is the BOS reference (most recent confirmed major swing), else you
get a BOS on every candle.

---

## 4. Change of Character (CHoCH)

**Definition.** The **first** swing break **against** the trend — an early reversal
*warning*. In an uptrend, breaking the most recent **higher low** (making a LL) =
bearish CHoCH; in a downtrend, breaking the most recent **lower high** (making a HH)
= bullish CHoCH.

**Detection.** Bullish CHoCH: structure bearish AND `close > lastLowerHigh`;
bearish CHoCH: structure bullish AND `close < lastHigherLow`. Same close-vs-wick
rule as BOS. After it fires, flip the trend state; later with-trend breaks become
BOS.

**BOS vs CHoCH.** Same crossover test; differ by which swing (with-trend vs
counter-trend) breaks and the current state. BOS = continuation; CHoCH =
first counter-trend break = potential reversal.

**Pitfalls.** "First" is state-dependent → needs a robust state machine. LuxAlgo's
**CHoCH+** adds a *failed swing* precondition; sources disagree whether that's
required.

---

## 5. Market Structure Shift (MSS) / Break (MSB)

**Definition.** MSS = a **CHoCH plus displacement** — a counter-trend break carried
by a strong, expansive (usually FVG-creating) candle; treated as a *confirmed*
reversal. "MSB" is used by many authors as a synonym for BOS or CHoCH — terminology
is inconsistent, so define your own terms.

**Detection.** Start from a CHoCH (counter-trend break by close), then add a
**displacement filter**: break candle range/body ≥ k×ATR (k≈1.5–2) or ≥ X×average
body; and/or the break leg **leaves an FVG**. "A closed displacement candle" must
print — wicks through the swing without one don't qualify. MSS ⊂ CHoCH (a CHoCH
that also passes the displacement test).

**Pitfalls.** "Displacement" is unstandardized — your numeric choice changes signals
materially. MSB/MSS/BOS naming overlaps across sources.

---

## 6. Internal vs external structure; IRL vs ERL

**Definition.** **External structure** = the major swing high/low bounding the
current **dealing range** (built from large pivots). **Internal structure** = minor
swings inside it (small pivots). **External Range Liquidity (ERL)** = liquidity at
the range boundaries (above range high / below range low). **Internal Range
Liquidity (IRL)** = liquidity inside the range (minor equal highs/lows, FVGs).

**Detection.** Dealing range = most recent confirmed major swing high & low (large
lookback, e.g. ≥50). ERL = range high (BSL) and range low (SSL). IRL = levels
between equilibrium and the boundaries (minor pivots, small lookback ~5).
Equilibrium = 50%; above = premium, below = discount. Typical sequence: price
sweeps **IRL first**, then expands to **ERL**; BOS occurs at the boundary, CHoCH
forms inside.

**Pitfalls.** Internal/external depends entirely on the two lookbacks; re-anchor the
range whenever a major swing is taken out (it is dynamic).

---

## 7. Buy-side (BSL) & sell-side (SSL) liquidity

**Definition.** **BSL** = buy stops resting **above** price (above swing/equal highs,
prior day/session highs). **SSL** = sell stops resting **below** price. (BSL above,
SSL below — these are where breakout buys and trapped-position stops live.)

**Detection.** BSL level = each confirmed swing high / equal-high cluster /
prior-session-day-week high; SSL = mirror with lows. Draw a horizontal line until
price trades through it. "Taken/swept" = the high (BSL) or low (SSL) exceeds the
level (a **wick is enough to take** liquidity). Tag each level by tier (minor = IRL,
major/PDH/PWH = ERL).

**Pitfalls.** Prune/expire swept levels or the chart floods; deduplicate
coincident levels (a swing high that is also the PDH).

---

## 8. Liquidity pools; equal highs (EQH) & equal lows (EQL)

**Definition.** A pool = concentrated resting orders, clearest at **equal
highs/lows** (a flat top/bottom of two or more swings at ~the same price). Because
exact ticks rarely match, the practical term is **relative-equal**.

**Detection.** Detect swings, then two swing highs are **EQH** if
`abs(high_a - high_b) ≤ tolerance`. Tolerance options: **ATR-based** (recommended,
~`0.1*ATR`), percentage (`≤ p%*price`), or fixed points/pips. Require the pivots
within a `maxBarsBetween` window. EQL mirrors with lows. Draw a line/box joining
the equal points.

**Pitfalls.** **Tolerance is the whole ballgame** — no agreed value; ATR-based is
most portable. Decide minimum touches (2 vs 3+) and whether intervening price must
stay below the EQH (clean double-top vs deep dip).

---

## 9. Liquidity sweep / raid / grab / stop hunt (SFP)

**Definition.** Price **pushes beyond** a known level, triggers the resting stops,
then **reverses**. Community grades: **sweep** = trades through an obvious high/low;
**raid/run** = the penetration that triggers stops; **grab** = sweep + fast
rejection back inside (the tradeable reversal). "Stop hunt" is the narrative term.
This is the **Swing Failure Pattern (SFP)**.

**Detection (key reversal signal).**
- Wick exceeds a level: `high[i] > level` (high sweep) or `low[i] < level` (low sweep).
- AND closes back inside within M bars: `close < level` (high sweep) / `close > level`
  (low sweep). Wick-beyond **+** close-back-inside is the 2-part SFP.
- Strength filters: subsequent **displacement**, a break of minor internal structure
  in the reversal direction, retrace into a PD array. A bare wick without a following
  shift often fails.
- **vs BOS:** BOS = **close** beyond the level (continuation); sweep = **wick**
  beyond + **close back inside** (reversal). This is the cleanest discriminator.

**Pitfalls.** Choice of reversal window M changes results. A "sweep" that closes
beyond is actually a BOS — order of evaluation matters. Needs a real level to sweep.
Consider a small tolerance on the wick-beyond test for spread/volatility.

---

## 10. Inducement (IDM)

**Definition.** An **engineered minor liquidity level** (typically the first
pullback / minor swing before a major level or order block) whose purpose is to
**trap** traders and gather liquidity before price reaches the real level. Formally:
price takes out an **internal** swing while the **major** structure stays intact.

**Detection.** After a BOS/CHoCH leg, the **most recent minor opposing swing** within
the retracement (the deepest counter-leg pivot) = the IDM level. LuxAlgo-style:
track directional legs, monitor the deepest retracement extreme against the active
move, promote it to an active IDM when the trend resumes. The IDM sits **between**
current price and the valid OB/major swing; the OB is only "valid" once the IDM is
swept first. Types: **internal** IDM (break of a candle high/low within a range)
and **external** IDM (false breakout of a key S/R boundary).

**Pitfalls.** "Minor" vs "major" is entirely lookback-dependent; algorithmically it's
"the last internal pivot before the structural level." Subjective in manual practice;
false IDMs proliferate in chop.

---

## 11. Draw on liquidity (DOL)

**Definition.** The liquidity level price is most likely magnetizing toward next —
the directional **target/objective** (not a signal itself). E.g. relative equal
highs above as a bullish DOL.

**Detection.** A *selection* among detected levels: pick the nearest significant
**opposing** ERL/IRL in the bias direction. Candidate hierarchy: relative equal
highs/lows (30m–1H) → prior session/day/week highs/lows → major swing extremes (ERL).
A "grey pool" = an unconfirmed relative-equal level (a target, not a standalone
signal). Sequence: IRL consumed first → expansion to ERL.

**Pitfalls.** Interpretive — surface ranked candidate targets (by proximity /
significance) rather than asserting a single definitive DOL.

---

## 12. Trendline liquidity

**Definition.** Liquidity along a **diagonal** line of multiple aligned swing highs
(or lows); stops/breakout orders cluster along/beyond it, so the line itself becomes
a pool that gets raided ("trendline break").

**Detection.** Find a set of swing highs/lows (default ~3) whose extremes lie on/near
a straight line: fit a line through 2 anchor pivots, then require subsequent
qualifying pivots within a tolerance band (a sloped analog of EQH/EQL tolerance).
The liquidity sits just **beyond** the line; sweep = price wicks through the projected
line value then reverses.

**Pitfalls.** Line-fitting is fuzzy (anchors, slope tolerance, min touches). Harder
to make deterministic than horizontal EQH/EQL; many implementations approximate it as
"3+ ascending lows / descending highs within tolerance."

---

## 13. Old / session / daily / weekly highs & lows

**Definition.** Calendar-anchored liquidity: Previous Day High/Low (PDH/PDL),
Previous Week High/Low (PWH/PWL), and **session** highs/lows (Asia, London, NY).
High-probability targets because stops cluster at these obvious levels; the Asian
high/low are classic London/NY sweep targets.

**Detection.** PDH/PDL = max-high/min-low of the prior daily bar (HTF
`request.security` or roll over at the daily boundary in exchange time); PWH/PWL =
same weekly. Session high/low = running max/min within a NY-time session window,
frozen at session close. ERL-class; "taken" on a wick through.

**Pitfalls.** **Timezone is critical** — define sessions in a consistent
NY/exchange offset with DST; daily/weekly rollover depends on the instrument's
session. Make each level toggleable to avoid clutter.

---

## Sources

- https://tradingstrategyguides.com/day-3-smc-ict-market-structure-explained-bos-choch-swing-points-2026/
- https://tradingstrategyguides.com/liquidity-ict-smc-trading-explained/
- https://tradingfinder.com/education/forex/bos-vs-choch/
- https://fxopen.com/blog/en/market-structure-shift-meaning-and-use-in-ict-trading/
- https://liquidity-provider.com/articles/internal-vs-external-range-liquidity-in-ict-trading/
- https://thesimpleict.com/dealing-range-ict-guide/
- https://tradingfinder.com/education/forex/ict-swing-high/
- https://arongroups.co/technical-analyze/liquidity-in-ict/
- https://arongroups.co/technical-analyze/ict-swing-failure-pattern-sfp-trading-failed-highs-lows-forex/
- https://tradingfinder.com/education/forex/inducement/
- https://www.litefinance.org/blog/for-beginners/what-is-inducement-in-trading/
- https://www.luxalgo.com/library/indicator/eqh-eql-liquidity-zones/
- https://docs.luxalgo.com/docs/algos/price-action-concepts/market-structures
- https://www.tradingview.com/script/CnB3fSph-Smart-Money-Concepts-SMC-LuxAlgo/
- https://www.mql5.com/en/blogs/post/762665
- https://liquidityfinder.com/news/stop-hunting-101-how-swing-highs-and-lows-become-liquidity-traps-b599c
