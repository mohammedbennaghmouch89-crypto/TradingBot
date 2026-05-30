# ICT Reference — PD Arrays (zones & imbalances)

The zones price is drawn to and reacts from. Each has an OHLC detection rule.
Conventions: C1 (oldest), C2 (middle), C3 (newest) for 3-candle patterns;
"up candle" = `close > open`; "body top/bottom" = `max/min(open, close)`.
See `../SKILL.md` for the global zone-basis / violation-basis / displacement forks.

---

## 0. Premium / discount & equilibrium (prerequisite)

Almost every array trade is gated on premium vs discount.

- **Definition.** Within a swing range, **equilibrium (EQ)** = 50%. Above EQ =
  **premium** (sell zone); below = **discount** (buy zone).
- **Detection.** `eq = (rangeLow + rangeHigh)/2`; `p` is premium if `p > eq`, discount
  if `p < eq`. Range = most recent confirmed dealing range / swing pivots.
- **Use.** Buy only discount arrays, sell only premium arrays.
- **Pitfall.** Entirely dependent on *which* range you measure; let the user pick the
  swing source (pivot lookback).

---

## 1. Order Block (OB)

**Definition.** Bullish OB = the **last down-close candle before an up displacement**
that breaks structure / leaves an imbalance; bearish OB = the **last up-close candle
before a down displacement**. Acts as support (bullish) / resistance (bearish) on
return.

**Detection.**
- Bullish OB: candle `i` with `close[i] < open[i]` such that the subsequent move is
  strong up — confirm by any/combination (exposed as settings): next 1–3 candles close
  progressively higher and take out `high[i]` (ideally a swing high → BOS); and/or a
  bullish FVG forms within 3 candles. Take the **last** down candle before the up run.
- Bearish OB: mirror (last up candle before a down displacement taking out `low[i]` /
  leaving a bearish FVG).
- **Zone boundaries — SOURCES DISAGREE (expose setting):** full-range `low..high`
  (most tutorials, default); body-only `min(o,c)..max(o,c)` (LuxAlgo "candle bodies");
  or asymmetric open-based (bullish = open→low, bearish = open→high).
- Optional stricter variant: require the displacement candle to fully **engulf** the OB
  candle body-to-body and wick-to-wick.
- **Mitigation / "filled":** price returns into the zone; canonical entry = the **50%
  mean threshold** `(high+low)/2`. **Invalidated** on a **body close through the far
  side** (bullish OB: close below OB low; bearish OB: close above OB high).

**Pitfalls.** Body vs full-range vs open is the biggest fork. Displacement has no
universal number (use FVG-present / ATR-multiple / swing break). Define a tie-break
for doji (`close==open`). With several stacked candles, the immediately-preceding rule
picks exactly one.

---

## 2. Breaker Block

**Definition.** A **failed order block** that price has broken through; the zone flips
side (support↔resistance). Forms on a swing that **sweeps liquidity then reverses
through the OB**, confirming a BOS/MSS.

**Detection.**
- Bullish breaker (from a failed bearish OB): (1) low → higher high → a lower low that
  **sweeps the prior swing low**; (2) price reverses up and **closes above** the down-leg
  high / prior bearish OB (BOS up); (3) breaker zone = the **last up-close candle before
  that final swing high** (range, with the same body-vs-range setting).
- Bearish breaker: mirror (sweep a prior swing high, **close below** a prior swing low;
  breaker = last down-close candle before the final swing low).
- Skeleton: detect (a) a 3-pivot structure, (b) a liquidity sweep of the outer pivot,
  (c) a body close through the opposing structural level → tag the defining candle.
- Mitigation/invalidation: same body-close-through-far-edge rule as OB.

**Pitfalls.** Heavy dependence on pivot lookback. Sources differ on *which* candle is
"the breaker" — pin one definition. Requires numeric sweep (wick beyond + close back)
and BOS (body close beyond) definitions.

---

## 3. Mitigation Block

**Definition.** A reversal zone from a **failure swing** — price reaches an
institutional reference and **fails to make a new HH/LL**, then breaks structure the
other way. **Key difference vs breaker:** a breaker forms after price **sweeps** the
prior extreme; a mitigation block forms when it does **NOT** sweep it before reversing.

**Detection.**
- Bullish mitigation block: downtrend → low → lower high → a **higher low (prior low NOT
  taken)** → **close above** the intervening swing high (BOS up). Block = last down-close
  candle before the up-move; distinguishing boolean = `currentLow > priorLow` (not swept).
- Bearish: mirror (lower high that fails to exceed prior high → close below intervening
  swing low).
- Implement identically to a breaker, then branch on `sweptPriorExtreme`: true = breaker,
  false = mitigation block.

**Pitfalls.** The distinction hinges on the "was the prior extreme swept?" boolean —
sensitive to wick vs body. Some sources define the zone as the area between the broken
swing high and the new higher low (a *range*, not a candle) — expose as setting. Retail
SMC often uses "mitigation block" loosely for any retested OB; ICT's strict meaning is
narrower.

---

## 4. Rejection Block

**Definition.** Built from **wicks** (not bodies): a candle/cluster spikes into liquidity
beyond an old high/low, gets rejected, and closes back inside. The **wick** is the zone.

**Detection.**
- Bullish (at a swing low): candle(s) sweep **below** a prior low but **close back above**
  it. Zone = `low` (wick extreme) → `min(open,close)` (body bottom).
- Bearish (at a swing high): sweep **above** a prior high but **close back below** it.
  Zone = `max(open,close)` (body top) → `high` (wick extreme).
- Often a small cluster: take the extreme wick and the highest/lowest body close among them.

**Pitfalls.** OB = where a move *starts* (body, before displacement); rejection block =
where a move is *rejected* after a sweep (wick, at the extreme). Single-candle vs cluster
varies. Needs a prior high/low reference (pivot sensitivity).

---

## 5. Propulsion Block

**Definition.** A **single candle that traded into an existing order block and then
propelled price away**. Zone = typically that candle's **body** (open→close). Essentially
a refined OB nested on a prior OB.

**Detection.**
- Bullish: a candle whose **low penetrates an existing bullish OB**, followed by strong
  bullish continuation. Zone = open→close body (some use full range). Requires a valid
  bullish OB to exist.
- Bearish: mirror (high penetrates a bearish OB).
- Algorithm: for each existing OB, find a later candle whose wick re-enters the OB and is
  immediately followed by displacement away → tag its body.

**Pitfalls.** Inherits all OB ambiguities (it depends on a pre-existing OB). Body vs
full-range unspecified (most say body). "Propelled away" needs a displacement proxy.

---

## 6. Fair Value Gap (FVG) / imbalance

**Definition.** A 3-candle imbalance where the **wicks of C1 and C3 do not overlap**,
leaving an un-traded gap; the middle candle (C2) is the displacement. (Well-agreed
formula.)

**Detection.**
- **Bullish FVG:** `low[C3] > high[C1]`. Zone bottom = `high[C1]`, top = `low[C3]`.
- **Bearish FVG:** `high[C3] < low[C1]`. Zone top = `low[C1]`, bottom = `high[C3]`.
- Optional filters: require C2 in the gap direction; minimum gap size (ATR multiple).
- **Fill / mitigation:** partial when price re-enters; **50% (consequent encroachment)**
  `(top+bottom)/2` is most reactive. **Invalidation:** bullish FVG invalid when price
  **closes below** the gap bottom (`high[C1]`); bearish when it **closes above** the gap
  top (`low[C1]`). Sources split on wick-touch vs body-close for "filled" — expose setting.

**Pitfalls.** "Filled" by wick vs body is the biggest setting. Whether C2 must be
impulsive / a min gap size varies. Beware the **Implied FVG** vs **Inversion FVG** acronym
collision (see §7).

---

## 7. Inversion Fair Value Gap (IFVG)

**Definition.** An FVG that has been **violated** and therefore **flips polarity**: a
failed bullish FVG becomes bearish resistance; a failed bearish FVG becomes bullish
support.

**Detection.** Start from a detected FVG. **Inversion trigger — SOURCES DISAGREE:** strict
(ICT-faithful) = a candle **body close** through the far side (bullish FVG → IFVG when a
candle **closes below** `high[C1]`; bearish FVG → IFVG when a candle **closes above**
`low[C1]`); loose = a wick penetration. Default body-close. New zone = the **same price
band**, opposite direction. Invalidated when price closes back through it the other way.

**Pitfalls.** Wick-vs-body trigger is the key fork. **Naming collision:** "IFVG" =
*Inversion* FVG here, but ICT also teaches *Implied* FVG (a wick-midpoint gap when bodies
overlap) — use distinct names.

---

## 8. Balanced Price Range (BPR)

**Definition.** The band where a **bullish FVG and a bearish FVG overlap** (one from an
up-leg, one from a down-leg) — a double-imbalance zone of heightened reaction.

**Detection.** Given a bullish FVG `[bull_bottom, bull_top]` and a bearish FVG
`[bear_bottom, bear_top]` formed close in time, overlap exists if
`bull_top >= bear_bottom AND bear_top >= bull_bottom`. **BPR = the intersection:**
`BPR_bottom = max(bull_bottom, bear_bottom)`, `BPR_top = min(bull_top, bear_top)`.
A bullish BPR sits in discount (longs); bearish in premium (shorts).

**Pitfalls.** Need a time-window rule for how far apart the two FVGs may form. Bullish vs
bearish labeling is convention-dependent (often by the later FVG / premium-discount
location). Consider a minimum-overlap-size filter.

---

## 9. Liquidity Void

**Definition.** A **larger** zone of one-sided rapid delivery — several consecutive
large-body, small-wick candles with little retracement; often contains FVGs.
Distinguished from FVG by **scale** (FVG = a single 3-candle gap; void = a stacked run).

**Detection (qualitative in sources; workable proxy).** A run of **N≥3 consecutive**
same-direction candles where each has a high **body/range ratio**
(`abs(close-open)/(high-low) > k`, k≈0.6–0.7). Zone = full extent of the run
(`void_bottom = lowest low`, `void_top = highest high`). Optionally require ≥1 FVG inside.

**Pitfalls.** No agreed numeric definition (N, k, wick handling are choices). Overlaps
heavily with "displacement" and stacked FVGs — avoid double-counting.

---

## 10. Volume Imbalance

**Definition.** A **single-bar, body-to-body gap** between consecutive candles (a gap
between one candle's **close** and the next candle's **open**) where wicks may overlap but
**bodies don't**.

**Detection.**
- Bullish: `open[next] > close[prev]`. Zone bottom = `close[prev]`, top = `open[next]`.
- Bearish: `open[next] < close[prev]`. Zone top = `close[prev]`, bottom = `open[next]`.
- vs FVG: FVG = 3-candle wick-to-wick gap; volume imbalance = 2-candle body-to-body gap,
  usually small. vs true gap: in a volume imbalance the **wicks still overlap**.

**Pitfalls.** Some sources require wick overlap (else it's a true/opening gap). Very common
and small → needs a min-size filter.

---

## 11. Opening gaps: NDOG & NWOG

**Definition.** A gap between a session **close** and the next session **open**, treated as
a fair-value magnet.
- **NDOG (New Day Opening Gap):** prior day's close at **17:00 NY** → new day's open at
  **18:00 NY** (the CME 1-hour halt), Mon–Thu.
- **NWOG (New Week Opening Gap):** **Friday close (~16:59–17:00 ET)** → **Sunday reopen
  (18:00 ET)** across the weekend.

**Detection.** At the first bar at/after **18:00 America/New_York**, record
`gap = [prevClose@17:00, open@18:00]` (order them); **consequent encroachment = 50% =
midpoint**. NWOG keyed off the Sunday 18:00 ET reopen vs Friday close; ICT often keeps the
**last 5 NWOGs** drawn. **Timezone is critical** — NY session boundaries with DST, never
fixed UTC.

**Pitfalls.** Only meaningful where there's a real close/reopen (CME futures, indices); FX/
crypto are ~24h (only the weekend NWOG applies to FX). DST shifts 17:00/18:00 ET vs UTC.
Exact Friday close minute varies (4:59 vs 5:00). These gaps are themselves "real FVGs" —
avoid double-drawing.

---

## 12. PD Array Matrix (premium vs discount hierarchy)

**Definition.** A **ranked checklist** of institutional reference points split into a
**premium column** (sell arrays, above EQ) and **discount column** (buy arrays, below EQ),
ordered strongest→weakest draw.

**Composition (ordering varies between teachers — treat as configurable weights):**
- **Premium (SELL, above EQ):** Old High → Rejection Block → Bearish OB → Bearish
  Mitigation Block → Bearish Breaker → Bearish FVG → Liquidity Void / Volume Imbalance.
- **Discount (BUY, below EQ):** Old Low → Rejection Block → Bullish OB → Bullish Mitigation
  Block → Bullish Breaker → Bullish FVG → Liquidity Void / Volume Imbalance.
- Full element set: Old High/Low, OB, Breaker, Mitigation, Rejection, FVG, Inversion FVG,
  Volume Imbalance, Liquidity Void, NWOG, NDOG, and the "Unicorn" (Breaker + FVG overlap).

**Encoding.** Compute EQ of the working range; tag each detected array premium/discount;
enable buy-arrays only in discount, sell-arrays only in premium; assign each type a
priority weight to rank confluence.

**Pitfalls.** Exact rank order is **not standardized** → configurable weights. "Old
High/Low" are liquidity (see the structure reference), not zones — cross-reference rather
than re-detect. Premium/discount tagging depends on the chosen range.

---

## Sources

- https://innercircletrader.net/tutorials/ict-order-block/
- https://www.fluxcharts.com/articles/order-blocks-ob-explained
- https://www.fluxcharts.com/articles/fair-value-gaps-fvg-explained
- https://www.fluxcharts.com/articles/inversion-fair-value-gaps-ifvg-explained
- https://www.fluxcharts.com/articles/balanced-price-range-bpr-explained-how-to-identify-and-trade-it
- https://www.luxalgo.com/blog/ict-trader-concepts-order-blocks-unpacked/
- https://blog.opofinance.com/en/ict-breaker-block-vs-mitigation-block/
- https://www.xs.com/en/blog/rejection-block/
- https://www.writofinance.com/ict-propulsion-block-in-forex/
- https://www.writofinance.com/ict-volume-imbalance/
- https://tradingfinder.com/education/forex/ict-liquidity-void/
- https://tradingfinder.com/education/forex/ict-new-day-opening-gap/
- https://blog.opofinance.com/en/ict-opening-range-gap/
- https://innercircletrader.net/tutorials/ict-pd-array-key-to-trade-execution/
- https://ictflow.com/blog/ict-pd-array-matrix-explained
- https://grandalgo.com/blog/ict-pd-array-matrix-explained
- https://www.tradezella.com/learning-items/key-ict-concepts
