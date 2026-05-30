# Volume Profile Reference — Structure, Nodes & Shapes

Detection logic on the **per-row volume array** `V[i]` (index 0 = lowest price, fixed
tick height). For TPO substitute `TPO[i]` (letter count). See `../SKILL.md` for the
POC/VA algorithm and conventions.

> **Naming note.** Sources conflict on letter-shapes because some draw the histogram
> mirrored. This file uses **physical shape**: **P = volume at top, b = volume at bottom.**

---

## 1. Core reference levels (recap)

- **POC** = `argmax(V)`; tie-break = row closest to center / upper of equidistant ties.
  With ticks, merge rows within 1–2 ticks before argmax to avoid jumpiness.
- **Value Area / VAH / VAL** = the 70% two-row expansion from POC (see foundations §7).
  Two competing standards (1-row vs 2-row per side) can shift VAH/VAL by a row — pick one.

---

## 2. High Volume Node (HVN)

**Definition.** A price row/cluster holding a locally large share of volume — a profile peak;
prolonged trading / acceptance.

**Detection (implement both; flag rows satisfying either/both).**
- **Local-maximum (peak):** `V[i] > V[i±k]` for all `k` in `1..N` (window `N` per side).
- **Threshold:** `V[i] >= T_high`, e.g. `mean(V) + c*std(V)` (c≈1.0), or `>= 0.7*V[POC]`, or top X%.
- Merge adjacent qualifying rows into a single HVN **zone** (band), not many one-tick nodes.

**Use.** Consolidation zones, magnets, strong S/R; price slows/stalls/reverses inside; the POC is
the dominant HVN.

**Pitfalls.** `N` controls sensitivity (typ. 2–5); threshold `c`/% is arbitrary (calibrate per
instrument/bin); optional 3-row smoothing cuts spurious peaks but shifts locations; pure global
thresholds miss secondary peaks in trending profiles.

---

## 3. Low Volume Node (LVN) & single prints

**Definition.** A row/band of local-minimum / unusually low volume — a valley where price moved
fast. TPO analogue at extremes = **single print** (one letter); internal LVNs split a profile.

**Detection.**
- **Local-minimum (trough):** `V[i] < V[i±k]` for all `k` in `1..N`.
- **Threshold:** `V[i] <= T_low`, e.g. `c2*mean(V)` (c2≈0.2–0.5), or `<= 0.1–0.2*V[POC]`, or bottom X%.
- **Single print (TPO):** `TPO[i] == 1` with `TPO[i±1] > 1`.
- **Internal LVN / split:** a below-threshold row with HVNs on **both** sides → divides into two
  distributions (B-shape, §4).

**Use.** Rejection / fast-move / breakout zones; price accelerates through and doesn't linger.
Boundaries between value areas; precise stop-placement and breakout-trigger levels.

**Pitfalls.** Exclude profile tails (top/bottom rows are trivially low — handle as excess, §7).
Decide a rule for zero-volume gap rows. Same `N`/threshold sensitivity as HVN. Volume profile has no
exact "single print" — use the relative-trough definition.

---

## 4. Profile shapes

Let `POC_pos = (price[POC] − low) / (high − low) ∈ [0,1]`, `range_mid` = midpoint.

- **D-shape (balanced / normal).** Symmetric bell, POC central. Detect: `POC_pos ≈ 0.4–0.6`,
  `|vol_above_POC − vol_below_POC|/total` small (<~0.15), single dominant peak, relatively wide VA.
  → range/rotation: fade extremes, revert to POC; neutral bias.
- **P-shape (short covering / bullish-then-balance).** Fat at **top**, thin (often single-print)
  at **bottom**. Detect: `POC_pos > ~0.6`, mass above mid, thin lower tail. → bullish/short-covering
  in a downtrend (possible bottom) or healthy pause in an uptrend; thin lower zone is an LVN
  boundary. *Context-dependent* (a P atop an extended rally can mark exhaustion).
- **b-shape (long liquidation / bearish-then-balance).** Mirror of P: fat at **bottom**, thin top.
  Detect: `POC_pos < ~0.4`, mass below mid, thin upper tail. → bearish / long-liquidation; bias flips
  with prior-trend context.
- **B-shape (double distribution).** Two HVN clusters / two POCs separated by an internal **LVN**
  neck. Detect: ≥2 prominent peaks with a separating trough `V[trough] < 0.3*min(peak1,peak2)`. Report
  the secondary POC; the dividing LVN is the pivot (acceptance above = bullish, below = bearish).
  Needs a *prominence* test, not just "two bumps."
- **Thin / trend-day.** Elongated, no dominant peak, many small equal nodes along the move. Detect:
  `V[POC]/mean(V)` small, VA narrow vs total range (e.g. <0.35), volume spread across many rows
  (low kurtosis). → trend/continuation: trade *with* direction, use minor-node pullbacks; do not fade.

**Pitfalls.** Same physical shape can imply opposite things by prior trend (P/b) — always use trend
context. Distinguishing a finished shape from a developing mid-session profile is hard early.

---

## 5. Naked / Virgin POC (nPOC / vPOC)

**Definition.** A prior period's POC price never traded back to since — untested "unfinished
business." NPOC and vPOC are synonyms.

**Detection.** Maintain `{(date, poc_price)}` of prior (e.g. daily) POCs. A prior POC at price `p` is
**naked** while **no later bar** has `low <= p <= high`. On each new bar, mark any naked POC whose
`[low,high]` brackets `p` as **tested** → it becomes an ordinary HVN.

**Use.** Magnets / targets; the first re-test tends to produce a reaction. High-quality objective
level lists for plotting and bot targets.

**Pitfalls.** Define "touched" precisely (most use any intrabar touch). Choose period granularity
(session vs weekly). Volume-POC vs TPO-POC differ — pick which defines the level. Compare `p` at full
tick resolution, not the current profile's coarse row.

---

## 6. Developing POC / VA & migration

**Definition.** Intra-session, POC and VA are recomputed continuously as volume accumulates
("developing"). **Migration** = the directional drift of POC/VA over time — a primary trend signal.

**Detection.** Recompute POC/VA each bar from the running `V[i]`; store `POC_t, VAH_t, VAL_t`.
Migration: `POC_today > POC_yesterday` over consecutive sessions → bullish; reverse → bearish; flat/
oscillating after ~45 min → balance. VA migration: both VAH and VAL rising (shifted up vs prior day) →
uptrend acceptance; both falling → downtrend; stationary overlapping VAs → balance.

**Use.** Steady migration = strongest trend confirmation (institutional accumulation/distribution);
"trading against VA migration is low-probability." Stable developing POC = mean-reversion regime.

**Pitfalls.** Early-session POC is noisy/jumpy (wait ~30–45 min). Define the day-over-day overlap
metric precisely (% overlap of `[VAL,VAH]`). Cache cumulative sums (recompute is O(rows)).

---

## 7. Excess (tails), poor highs/lows, single prints

TPO-native; volume-only versions are approximations.

- **Excess (buying/selling tail).** A run of single-print TPOs at an extreme from price auctioning
  too far and being sharply rejected. Buying tail = single prints at the **bottom**; selling tail =
  at the **top**. Marks a **finished** auction. Detect (TPO): contiguous `TPO==1` run of length ≥2 at
  the extreme, terminating into multi-TPO rows. Volume proxy: a run of very-low-volume rows at an
  extreme next to a fast move that reverses. The tail's start price is key S/R and a likely revisit.
- **Poor high / poor low (unfinished).** A flat, blunt extreme with **multiple equal TPOs / no
  excess tail** (≥2 periods printed the same extreme). Detect (TPO): top/bottom rows have `TPO>=2`
  with no single-print beyond. → weak "magnet" extreme that price tends to **return to and repair**
  (take out) later.
- **Single prints (recap).** `count==1` rows isolated by multi-count neighbors — excess at extremes,
  LVN splits internally.

**Pitfalls.** These need the TPO **letter matrix**, not the collapsed `V[i]`. Define minimum
single-print run length (1–3) and require ≥2 equal periods for a genuine poor high/low.

---

## 8. Balance vs imbalance; Value Area width

**Definition.** Balanced = wide, symmetric (D) VA, central POC, equal volume above/below (agreement).
Imbalanced/trend = thin, skewed, elongated (disagreement, searching for value).

**Detection.** Balance: symmetry small **and** wide VA/range **and** single dominant peak. Imbalance:
skew and/or narrow VA-to-range and/or no dominant peak. **Value Area Width** `VAW = VAH − VAL`; as a
regime signal use **`VAW / total_range`** or VAW normalized vs its recent average / ATR. Wide VAW →
acceptance/balance/range-trade; narrow VAW → conviction/trend, and often **precedes expansion**
(compression → breakout).

**Pitfalls.** **Always normalize** VAW (vs ATR/price/range) — raw VAW is instrument- and bin-
dependent. Narrow VAW is ambiguous (dead-quiet vs trending hard) — disambiguate with developing-POC
migration (§6).

---

## 9. Composite profiles, stacked value areas, ledges

**Definition.** A **composite** aggregates volume across many sessions into one profile, revealing
macro **stacked value areas** (HVN shelves) and **ledges**. Composite nodes carry more weight.

**Detection.** Sum `V[i]` across the chosen date range; run §1–§4 on it. Stacked VAs = the set of
composite HVN zones separated by LVNs. **Ledge** = a price where high volume **drops off abruptly**
into low volume — a one-sided gradient: `(V[i] − V[i+1])/V[i]` large with `V[i]` an HVN and a run of
LVN rows on the drop-off side (distinct from a symmetric peak that tapers both ways).

**Use.** Composite HVNs/POC = highest-conviction long-term S/R / magnets; ledges restrict movement and
act as launch/rejection points; stacked VAs map balance areas to trade between.

**Pitfalls.** Composite window choice is subjective and outcome-determining — parameterize (consider
anchored composites from a swing/event). Old volume can dominate → stale POC (consider decay / rolling
window). Keep RTH/ETH consistent across the span. Use prominence filtering to avoid over-reporting nodes.

---

## Cross-cutting notes

- **Bin/row size** is the single most influential parameter — fix it deliberately and hold it constant
  when comparing days.
- **Smoothing** (3-row moving average) before peak/trough detection cuts noise at the cost of slight
  level displacement — make it optional.
- **TPO vs Volume:** excess / poor highs-lows / single prints are TPO-native; HVN/LVN/POC/VA/shapes work
  on either.
- **Thresholds are conventions, not laws** (`N`, `c`/`c2`, 70%, prominence) — expose and document defaults.

---

## Sources

- https://www.tradingsim.com/blog/advanced-day-trading-strategies-using-volume-profile
- https://www.luxalgo.com/library/indicator/volume-profile-with-node-detection/
- https://www.quantvps.com/blog/mastering-volume-profile
- https://www.overcharts.com/en/helpcenter/docs/volume-profile-distribution-types/
- https://www.trader-dale.com/market-profile-different-profiles-and-their-application/
- https://www.marketcalls.in/market-profile/market-profile-different-types-of-profile-days.html
- https://www.marketcalls.in/market-profile/poor-high-and-poor-low-market-profile-structure-explained.html
- https://www.quantvue.io/post/understanding-market-profile-excess
- https://www.mypivots.com/dictionary/definition/442/naked-point-of-control-npoc
- https://www.mypivots.com/dictionary/definition/158/virgin-point-of-control-vpoc
- https://gocharting.com/docs/orderflow/market-profile-aka-tpo-charts
- https://gocharting.com/blog/volume-profile/point-of-control-trading-guide
- https://tradeproacademy.com/uncovering-volume-profile-inflection-points/
- https://www.buildix.trade/blog/volume-profile-trading-strategies-value-area-naked-poc-free-guide-2026
