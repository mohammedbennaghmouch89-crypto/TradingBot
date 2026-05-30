# Volume Profile Reference — Foundations & Calculation

Algorithmic, calculable definitions for building a profile. See `../SKILL.md` for
the cross-cutting conventions (data approximation, row size, VA %, parity checklist).

---

## 1. Auction Market Theory (AMT) — the foundation

**Definition.** Every market is a continuous two-way auction whose purpose is to
*facilitate trade*. Price rises to shut off buying and falls to shut off selling,
searching for the price where the most trade occurs (fair value / the POC). Volume
Profile and Market Profile quantify this auction.

**Operationalizing the abstract ideas.**
- **Fair value / equilibrium** = POC + Value Area (no separate formula — AMT defines
  *what* the profile measures).
- **Balance (consolidation)** → symmetric, bell-shaped ("D") profile: POC near range
  midpoint, smooth taper to thin tails. Detect via POC near `(rangeHigh+rangeLow)/2`,
  low skew, overlapping VAs across sessions.
- **Imbalance (trend / discovery)** → "P"/"b"/elongated profile, POC skewed to one
  extreme, long thin tail in the trend direction. Detect via high skewness / POC in the
  top or bottom third.
- **Acceptance** = price trades **and builds volume/time** beyond prior value and holds.
  Operational rule: ≥2 consecutive periods (two 30-min TPOs) or ≥1–2 closes beyond.
- **Rejection** = price probes beyond value but **fails to build volume** and snaps back:
  thin/single-print rows at the extreme, long wick, quick return inside VAH/VAL.

**Pitfalls.** AMT terms are qualitative — every rule needs a chosen numeric threshold
(skew cutoff, "thin row" multiplier, acceptance periods). No canonical constants; expose
as tunables.

---

## 2. Volume Profile vs Market Profile (TPO)

**Definition.**
- **Volume Profile** = horizontal histogram of **volume traded at each price** (committed
  capital).
- **Market Profile (TPO)** = histogram of **time spent at each price**, built from letters
  (Steidlmayer, CBOT ~1980s).
- **TPO (Time Price Opportunity)** = the atomic unit: one letter marking that price traded
  at a level during a time bracket (classically 30 min: A, B, C, …).

**Calculation.**
- Volume per row: `rowVolume[i] += bar.volume` for every bin `i` the bar overlapped.
- TPO per row: split the session into brackets; for each, append its letter to every price
  level the bracket's range touched. `tpoCount[i]` = number of distinct brackets touching `i`.
- **POC differs:** Volume POC = `argmax(rowVolume)`; TPO POC = `argmax(tpoCount)` — often at
  different prices (capital committed vs time spent). Their divergence is itself a signal.
- **Initial Balance** (Market Profile) = range of the first two 30-min brackets (A+B).
- **Single prints** = rows touched by exactly one TPO letter (`tpoCount[i] == 1`).

**Pitfalls.** TPO needs **no volume data** → works on FX / thin instruments where Volume
Profile is noisy. TPO is session/time-sensitive (bracket length, session definition).
Decide explicitly which POC the bot uses; never conflate the two.

---

## 3. Building the histogram (rows / bins / row size)

**Definition.** Divide the price range `[Bottom, Top]` into contiguous equal-height rows,
accumulate volume into each → a sideways histogram.

**Two inverse "Rows Layout" modes (TradingView formulas).**
1. **Number of Rows** (fix the count):
   `ticksPerRow = (Top − Bottom) / NumberOfRows / tickSize`.
2. **Ticks Per Row** (fix row height):
   `NumberOfRows = (Top − Bottom) / tickSize / ticksPerRow`.
- Row price height = `ticksPerRow × tickSize`. Bin assignment:
  `rowIndex = floor((p − Bottom) / rowHeight)`, clamped to `[0, NumberOfRows−1]`.
- TradingView rounds fractional `ticksPerRow` to a whole tick height, choosing the rounding
  that yields a row count closest to requested, adding rows if needed to cover all data.

**Pitfalls.** `Top`/`Bottom` depend on scope (visible / fixed / session / anchored) —
recompute when they change. `tickSize` must be the instrument's real tick (`syminfo.mintick`).
Clamp the exact-`Top` off-by-one. Cost scales `NumberOfRows × bars`.

---

## 4. Up / down / total volume per row (and delta)

**Definition.** Each row can store total volume, up volume (buying), down volume (selling);
**delta = up − down**.

**Calculation (OHLCV approximation).** Per bar (or LTF sub-bar): `if close >= open → up else
down`; add the bar's whole volume to `rowUp[i]` or `rowDown[i]` for each overlapped row;
`rowTotal[i] = rowUp[i] + rowDown[i]`; `rowDelta[i] = rowUp[i] − rowDown[i]`. Display modes:
Total / Up-Down / Delta. **True** bid/ask delta needs tick or `request.footprint()` data.

**Pitfalls.** `close >= open` is **crude** (a green bar can hold heavy selling); ties
(`close == open`) count **up** by this rule — document it. Tagging a whole bar one direction
across all its rows is an approximation artifact.

---

## 5. Point of Control (POC)

**Definition.** The price row with the **highest traded volume** (Volume POC). (TPO POC =
most letters, may differ.)

**Detection.** `pocIndex = argmax(rowTotal)`; `pocPrice = Bottom + (pocIndex + 0.5) × rowHeight`
(row center). Tie-break (TradingView): prefer the row closer to the POC region / the upper of
two equidistant ties; for raw global ties some pick nearest the range midpoint (implementation-
defined).

**Pitfalls.** POC is sensitive to row size (re-binning shifts it). With distributed (approx.)
volume, the POC may land on a distribution artifact. With raw ticks the argmax can be jumpy —
consider merging adjacent rows within 1–2 ticks before argmax.

---

## 6. Value Area (VA), VAH, VAL

**Definition.** The contiguous range around the POC containing a target % (default ~70%) of
total volume. **VAH** = its highest price; **VAL** = its lowest.

**Detection.** Output a contiguous row span `[loIdx, hiIdx]` from the algorithm in §7;
`VAL = Bottom + loIdx × rowHeight`, `VAH = Bottom + (hiIdx+1) × rowHeight`; POC sits inside.

**Pitfalls.** The VA is contiguous *by construction* even if the distribution is bimodal — a
double-distribution profile can produce a VA spanning a low-volume gap; detect multi-distribution
separately if needed.

---

## 7. The standard Value Area algorithm (step-by-step)

Canonical "POC outward, compare two-above vs two-below, add the larger pair." Works identically
for volume (`rows = rowVolume`) or TPO (`rows = tpoCount`).

```
INPUT:  rows[]      # per-row volume (or TPO count), index 0 = lowest price
        vaPercent   # default 0.70
total   = sum(rows)
target  = total * vaPercent
poc     = argmax(rows)
vaVol   = rows[poc];  upIdx = poc;  dnIdx = poc
while vaVol < target:
    aboveSum = (rows[upIdx+1] if upIdx+1<=last else 0) + (rows[upIdx+2] if upIdx+2<=last else 0)
    belowSum = (rows[dnIdx-1] if dnIdx-1>=0   else 0) + (rows[dnIdx-2] if dnIdx-2>=0   else 0)
    if aboveSum == 0 and belowSum == 0: break          # exhausted
    if   aboveSum >  belowSum: vaVol += aboveSum; upIdx = min(upIdx+2, last)
    elif belowSum >  aboveSum: vaVol += belowSum; dnIdx = max(dnIdx-2, 0)
    else:                      vaVol += aboveSum; upIdx = min(upIdx+2, last)   # TIE -> see notes
VAL = price_at(dnIdx);  VAH = price_at(upIdx);  POC = price_at(poc)
```

**Specifics & disagreements.**
- **Two rows at a time** is the textbook (CBOT/Steidlmayer) method and the platform standard;
  some implementations add **one row at a time** → can differ by a row. State which you use.
- **Tie-break (TradingView):** equal candidate sums → choose the row closer to POC; if equal
  distance, choose the row above.
- **Edge handling:** if one side is exhausted, keep adding from the other until target met.
- **Stop condition:** the row that crosses the target is included ("reaches or slightly surpasses").
- **TPO vs Volume:** same algorithm, different per-row metric; can give different VAH/VAL/POC.

**Pitfalls.** Results depend on row size, the 2-vs-1-row choice, and tie rules — two "correct"
implementations can disagree by a row. Match all three to reproduce a platform.

---

## 8. Why 70% (≈1 standard deviation), and configurability

**Rationale.** ±1σ of a normal distribution contains ~**68.2%** of observations; Steidlmayer
rounded to **70%** for the value area. 68% (statistical) and 70% (conventional) name the same
idea; sources use them interchangeably. ±2σ ≈ 95%, ±3σ ≈ 99.7%.

**Configurability.** Yes — expose `vaPercent` (common: 0.68, 0.70; 0.80 for the 80%-rule context;
default 0.70).

**Pitfalls.** The 68%/70% gap is conventional, not a bug. The "1σ" justification only holds for a
bell-shaped profile; trending (skewed) profiles violate it — treat as a heuristic.

---

## 9. The data-source problem in Pine Script (core gotcha)

**Definition.** A *true* profile needs volume **at each price** (tick/intrabar). Chart bars give
one volume per bar with no intrabar price detail, so volume-at-price must be **approximated**.

**Approximation methods (worst → best).**
1. **Distribute the bar's volume across its high–low range:** *uniform* (`rowVol[i] += vol /
   nRowsCovered`), *weighted* (toward close/body/triangular), or *single-price dump* (all volume
   at close/hlc3 — crudest, spiky).
2. **Lower-timeframe (LTF) sampling — better:** `request.security_lower_tf()` pulls e.g. 1-min
   sub-bars of each chart bar, then distributes each sub-bar's volume over its much smaller range.
   TradingView's own VP indicators do this. More sub-bars → finer/more accurate.
3. **`request.footprint()` (newer Pine):** pre-computed accurate bid/ask footprint (volume-at-price
   + delta). Prefer where available — faster and more precise.

**Inaccuracy.** OHLCV profiles are *models*: they cannot recover true intrabar volume-at-price or
real delta (the `close>=open` proxy is coarse); POC/VA can shift vs an exchange-tick profile. LTF
narrows the gap; only tick/footprint is exact.

**Python advantage.** With raw trades, **bin each trade at its actual execution price** — accurate,
no approximation. Fall back to OHLCV distribution only when ticks are unavailable.

**Pitfalls.** `request.security_lower_tf()` caps sub-bars (limited history depth — deep historical
profiles lose granularity or fail silently), is slow, and counts against script limits. Different
distribution methods → different POC/VAH/VAL (the dominant cross-platform divergence).

---

## 10. Resolution vs noise / performance (row count tradeoff)

`NumberOfRows ≈ (Top − Bottom) / (ticksPerRow × tickSize)`; cost ≈ O(rows) storage + O(bars ×
avgRowsPerBar) accumulation; in Pine also bounded by `max_boxes_count` / `max_lines_count` (~500
default, ~10,000 max) when drawing rows.

- **Too many rows:** noisy/jagged, spurious micro-POCs, slow, may exceed object limits; with
  approximated data, fine rows mostly render artifacts.
- **Too few rows:** over-smoothed, imprecise POC/VA, merges HVN/LVN structure.

Heuristics: intraday session profiles ~24–50 rows; wide multi-month ranges need more (or tie
"Ticks Per Row" to a meaningful increment). For Pine↔Python parity fix the **same `rowHeight` in
price terms**, not just row count (count depends on the range). Recompute bins when the range
changes.

---

## Parity checklist (Pine ↔ Python)

Match all of: `tickSize`, range `[Bottom, Top]`, `rowHeight`, volume-distribution method,
up/down rule (`close>=open`), VA percent, 2-vs-1-row expansion, tie-break. A mismatch in *any one*
makes the two disagree. POC/VA are emergent from binning — never hard-code; recompute on
range/param change. Prefer `request.footprint()` (Pine) and raw ticks (Python) over OHLCV
distribution.

---

## Sources

- https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/
- https://www.tradingview.com/support/solutions/43000703076-visible-range-volume-profile/
- https://www.tradingview.com/support/solutions/43000707985-fixed-range-volume-profile-drawing-tool/
- https://www.tradingview.com/support/solutions/43000713306-time-price-opportunity-tpo-indicator/
- https://www.warriortrading.com/volume-profile-vs-market-profile/
- https://marketprofile.info/articles/market-profile-vs-volume-profile
- https://marketprofile.info/articles/value-area-explained
- https://en.wikipedia.org/wiki/Market_profile
- https://blog.tradingriot.com/p/auction-market-theory
- https://algostorm.com/auction-market-theory/
- https://bookmap.com/blog/understanding-market-moves-the-principles-of-auction-market-theory
- https://www.schwab.com/learn/story/using-volume-profile-indicator
- https://tradingstrategyguides.com/value-area-trading-strategy/
- https://gocharting.com/docs/orderflow/volume-profile-charts
- https://blog.traderspost.io/article/pine-script-footprint-requests
- https://pineify.app/resources/blog/pinescript/session-volume-profile-pine-script-a-concise-guide-for-traders
