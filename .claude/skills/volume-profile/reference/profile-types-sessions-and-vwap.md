# Volume Profile Reference — Types, Sessions & VWAP

Profile scopes, session boundaries, day/open types, and VWAP. **Use
`America/New_York` (ET) as the canonical session timezone** and let a tz/calendar
library handle DST — never hardcode UTC offsets. See `../SKILL.md` for the VA
algorithm and conventions.

---

## 1. Volume Profile Visible Range (VPVR / VRVP)

**Definition.** A profile over **only the currently visible bars**. Dynamic: scrolling/zooming
recomputes POC/VA. (TradingView tool = "VRVP".)

**Calculation.** No fixed time anchor — the range is the viewport. Inputs: rows (or ticks-per-row),
VA %, total vs up/down volume.

**Use.** Identify *current-context* HVNs (S/R) and LVNs (fast-move zones); the visible POC is a magnet.

**Pitfalls.** **Non-reproducible** — depends on zoom/screen width → impossible to replicate in a
backtest/bot. For the bot, **do not emulate VPVR**; use an explicit rolling lookback ("last N bars/days").
Results also change silently with timeframe (intrabar distribution differs).

---

## 2. Fixed Range Volume Profile (FRVP)

**Definition.** A profile over a **user-selected fixed start→end range** (time or bar index); does not
change on scroll.

**Calculation.** Two anchors + the standard row/VA machinery. Range can be a swing, consolidation, news
window, or trend leg.

**Use.** Profile a *specific structural move* to get its POC/VAH/VAL as forward reference levels.

**Pitfalls.** **Most bot-friendly** (explicit, deterministic). Define anchors as concrete
timestamps/bar conditions. A live end-anchor keeps updating until the bar closes. Intrabar distribution
still depends on the binning timeframe.

---

## 3. Session / Periodic Volume Profile (SVP)

**Definition.** A separate profile per session period — per day (most common), week, or month; each with
its own POC/VAH/VAL ("developing" intraday, "final" at close).

**Session boundaries (the critical config), `America/New_York`:**
- **US equities (cash):** RTH = **09:30–16:00 ET**, Mon–Fri.
- **CME equity-index futures (ES/NQ/MES/MNQ):**
  - **RTH (cash-aligned):** **09:30–16:00 ET** (= 08:30–15:00 CT). *Caveat:* some platforms/CME show
    index-futures RTH/pit as **08:30–15:15 CT → 09:30–16:15 ET** — **16:00 vs 16:15 close is disputed;
    make it configurable.**
  - **ETH / Globex:** **Sun 18:00 ET → Fri 17:00 ET**, daily maintenance break **17:00–18:00 ET (Mon–Thu)**.
- Daily rollover anchor: **18:00 ET** (ETH) or **09:30 ET** (RTH).

**Use.** Prior-day POC/VAH/VAL are the canonical next-day references: open inside prior VA → expect
rotation back to POC; open outside → expect acceptance/continuation or rejection back in. Naked POCs are
magnets.

**Pitfalls.** **RTH vs ETH is first-class** and changes every level (ETH's thin overnight drags POC; RTH
≈ 70% of ES volume = cleaner). DST: anchor to `America/New_York`. Holidays/half-days/Sunday-open/Friday-
close need an exchange calendar. Define week start (Sun Globex vs Mon).

---

## 4. Composite profile

**Definition.** One profile merging many consecutive sessions (5-day, 20-day, or "since the swing low").
Like a multi-session FRVP, framed around balance areas.

**Calculation.** Choose a span; aggregate all volume into one bin set; compute one composite POC/VAH/VAL.
Longer span → longer-timeframe participants.

**Use.** Major structural S/R and the dominant balance/fair-value zone over weeks–months; best in
balanced/rotational markets.

**Pitfalls.** Span selection is subjective and outcome-determining (use a rule-based / anchored start).
Old volume can dominate → stale POC (consider decay/rolling window). Keep RTH/ETH consistent across the span.

---

## 5. Initial Balance (IB)

**Definition.** The price range of the **first hour** of RTH = the first two 30-min TPO periods (A+B).
IBH = highest print, IBL = lowest, IB range = IBH − IBL.

**Timing (ET):** **09:30–10:30** for US equities / ES (A = 09:30–10:00, B = 10:00–10:30). IB midpoint is
sometimes an intraday pivot.

**Use.** **Narrow IB** → expect **range extension** (breakout likely); **wide IB** → range often contained
(day's high/low set early). IBH/IBL are intraday S/R and breakout triggers.

**Pitfalls.** **RTH-anchored** — meaningless on a 24h/ETH session; needs the cash open (anchor to each
market's open for non-US). On an Open-Drive trend day there is effectively no meaningful IB. Make IB length
configurable. DST: anchor 09:30 to `America/New_York`.

---

## 6. Range extension

**Definition.** Any trade **beyond the IB** after the first hour. Buying extension = new high above IBH;
selling extension = new low below IBL.

**Detection.** After 10:30 ET track: exceeded IBH? IBL? both? neither? + magnitude vs IB range (feeds day
type, §7).

**Use.** Direction reveals which timeframe participant (OTF) is in control; one-sided → directional bias;
both → two-sided/neutral.

**Pitfalls.** Only valid relative to a correctly-built IB (RTH/ETH error cascades). Distinguish single-tick
pokes from sustained extension (use a buffer/confirmation).

---

## 7. Day types (Dalton, *Mind Over Markets*)

Classified by **IB width** and **range extension**. (Frequencies vary by source/instrument — treat as
illustrative.)

| Day Type | IB | Range Extension | Close | Character |
| --- | --- | --- | --- | --- |
| Normal Day | **Wide** | Little/none | Within IB | Rare; first hour sets H&L. |
| Normal Variation Day | Average (~50% of range) | One side (≈doubles range) | — | Most common; one-sided follow-through. |
| Trend Day | **Narrow** | Persistent, one direction | Near the extreme | OTF in control, little rotation; opens near one extreme, closes near the other. |
| Double-Distribution Trend Day | **Narrow** | Quiet → midday drive → 2nd distribution | At/near far distribution | Two bell curves joined by a thin LVN neck. |
| Neutral Day | Average | **Both** sides | Within IB (center) or near an extreme | Two-sided fight / indecision. |

**Bot cues.** Compute IB range; after close measure extension up/down/both and close vs IB & day range.
Double-distribution = bimodal volume/TPO (two POCs + LVN). Trend day ≈ unidirectional extension + close in
top/bottom ~10–20% + narrow IB.

**Pitfalls.** Final only at close; intraday it's probabilistic. "Wide"/"narrow"/"near the extreme" are
subjective — parameterize (e.g. IB percentiles over trailing N days).

---

## 8. Open types (Dalton) — confidence-ordered

1. **Open-Drive (OD)** — highest confidence: opens and drives one way **without returning through the
   opening range**; the opening extreme tends to hold. → trend/normal-variation; trade with the drive.
2. **Open-Test-Drive (OTD)** — opens, **tests just beyond a known reference** (prior high/low, VA edge),
   confirms no business, then **reverses and drives back through the open**. Reliable extreme. → directional.
3. **Open-Rejection-Reverse (ORR)** — opens, goes one way, meets strong opposite activity that **reverses
   back through the open**. Initial extreme holds ~50%. → often neutral/rotational; trade the reversal cautiously.
4. **Open-Auction (OA)** — opens **inside prior value/range**, two-sided around the open; early extremes
   low-probability. → balance/range (use fades). *Open-Auction outside value* has higher odds of conviction.

**Detection (first 1–3 periods).** Move speed/distance from open, whether price returns through the open,
open location vs prior-day VA. OD = no trade back through open + sustained one-way move in period A.

**Pitfalls.** Classifiable only after the open develops — wait before labeling. ORR is the trap (looks like a
drive, then reverses). RTH-anchored.

---

## 9. VWAP and its relationship to Volume Profile

**Definition.** Volume-Weighted Average Price — the volume-weighted "fair value" benchmark, cumulative from
session start.

**Formula.** `VWAP = Σ(TPᵢ × Vᵢ) / Σ(Vᵢ)`, cumulative. Typical price `TP` default = **HLC3 = (H+L+C)/3**
(some use HL2 / close — configurable). The cumulative sums **reset at session start** (RTH open or Globex
open — match your session definition).

**Standard-deviation bands.** `σ² = [ Σ(Vᵢ·Pᵢ²)/ΣVᵢ ] − VWAP²`; `σ = √σ²`; bands = `VWAP ± k·σ`, k = 1,2,3.
(Some implementations compute σ from price dispersion around the running VWAP — document which; they differ
slightly.)

**Anchored VWAP (AVWAP).** Same formula, cumulative from a **user-chosen anchor** (swing high/low, gap,
earnings, breakout) instead of a daily reset — "fair value since event X."

**Use with POC/VA.** VWAP = dynamic intraday fair value / magnet (above = bullish control, below = bearish).
±1σ ≈ "value zone" (~68–70%), ±2σ stretched (~95%), ±3σ extreme. In balance, mean-revert toward VWAP from
±2σ; in trend, the **1σ band acts as pullback S/R**. **Confluence of VWAP ≈ POC ≈ prior VA edge = high
conviction.**

**Pitfalls.** Needs **real volume** (unreliable on spot FX). Reset point must match the session. HLC3 vs
HL2 vs close shifts the line. σ-band variants differ. DST-anchor the reset.

---

## 10. σ-bands vs Value Area (both ~1σ, but different)

| | VWAP ±1σ band | Value Area (70%) |
| --- | --- | --- |
| Built from | volume-weighted **price dispersion** around **VWAP** (the *mean*) | volume/TPO **distribution** around the **POC** (the *mode*) |
| Center | VWAP (mean) | POC (mode) |
| Coverage | statistical ±1σ ≈ 68% | 70% of actual volume via the add-rows algorithm |
| Shape | symmetric ± around VWAP | **asymmetric** — extends to the heavier-volume side |
| Time | continuous, per-tick; session reset | discrete bins; developing intraday, fixed at close |

**Clarification.** ±1σ is symmetric around the *mean*; the Value Area is asymmetric around the *mode* and
uses 70% of real volume (not 68% of an assumed normal). They overlap but **diverge in skewed/trending
auctions** — that divergence (mean ≠ mode) is information. Do not substitute one for the other in code.

---

## 11. Session opens, RTH vs ETH, timezone (futures)

**Definition.** Futures trade ~24h on **CME Globex (ETH)**; **RTH** aligns with US cash equities. Profiles,
IB, VWAP, and day-typing can anchor to either — the highest-impact config choice.

**Times (ES/NQ/MES/MNQ), `America/New_York`:**
- **ETH/Globex:** Sun **18:00 ET** → Fri **17:00 ET**; maintenance break **17:00–18:00 ET (Mon–Thu)**.
- **RTH:** **09:30–16:00 ET** (= 08:30–15:00 CT); *caveat:* index-futures RTH/pit shown by some as
  **08:30–15:15 CT → 09:30–16:15 ET** — make the close configurable.
- **IB:** 09:30–10:30 ET. **VWAP reset:** 09:30 ET (RTH) or 18:00 ET (Globex).

**Use.** RTH levels (~70% of ES volume, institutional) = "clean" POC/VA/VWAP; ETH captures overnight
positioning/gaps. Many run **both** (overnight high/low, ETH POC vs RTH POC).

**Pitfalls.** Always compute sessions in `America/New_York` with DST via a library (US/EU DST shift on
different dates). **Feed-UTC → ET conversion errors are the #1 off-by-one-hour bug** — convert before
bucketing. Holidays/half-days/Sunday-open/Friday-close need an exchange calendar. Volume meaning differs
RTH vs ETH (keep consistent across composites). Profiles/IB need ≤1-min bars for accurate bins; VWAP needs
real volume.

---

## Implementation flags to expose

`session_mode` (RTH | ETH), `session_tz = America/New_York`, RTH close 16:00 vs 16:15 ET,
`value_area_pct = 0.70`, row-pairing (2 per side), VWAP `typical_price = HLC3 | HL2 | close`, σ-band
formula variant, VWAP reset anchor, IB length (default 60 min), bin size by tick. **VPVR → replace with an
explicit rolling lookback in the bot.**

---

## Sources

- https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/
- https://www.tradingview.com/support/solutions/43000703076-visible-range-volume-profile/
- https://www.tradingview.com/support/solutions/43000707985-fixed-range-volume-profile-drawing-tool/
- https://www.tradingview.com/support/solutions/43000670909-regular-and-electronic-trading-hours-for-cme-futures/
- https://www.tradingview.com/scripts/vwap/
- https://www.shadowtrader.net/glossary/initial-balance/
- https://www.edgeful.com/blog/posts/eth-vs-rth-electronic-regular-trading-hours-futures
- https://www.quantvps.com/blog/cme-trading-sessions
- https://www.marketcalls.in/market-profile/market-profile-different-types-of-profile-days.html
- https://www.thenatureofmarkets.com/lessons/market-profile-course-2-day-types/
- https://www.thenatureofmarkets.com/market-profile-course-3-opening-types-open-range-strategy-and-practical-applications/
- https://www.windotrader.com/market-profile/market-profile-glossary-index/
- https://en.wikipedia.org/wiki/Market_profile
- https://gocharting.com/docs/orderflow/vwapbands
- https://help.trendspider.com/kb/indicators/vwap-with-st-dot-dev-bands
- https://www.sierrachart.com/index.php?page=doc%2FStudiesReference.php&ID=108
- https://www.cmegroup.com/trading-hours.html
