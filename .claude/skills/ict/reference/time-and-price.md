# ICT Reference — Time, Premium/Discount & Fibonacci

**Global timezone note (read first).** ICT specifies all times in **New York local
time** — **EST (UTC−5) winter / EDT (UTC−4) summer**. The *wall-clock* killzone/macro
times never change across DST, but the underlying UTC offset shifts twice a year (US
DST: 2nd Sun Mar → 1st Sun Nov; US and EU transitions are misaligned ~3 weeks each
spring/fall). **Anchor everything to `"America/New_York"`; never hardcode UTC offsets.**

---

## 1. Dealing range & equilibrium (50%)

- **Definition.** A *dealing range* = the span between a significant swing high and low
  that price trades inside; *equilibrium (EQ)* = its exact 50% midpoint.
- **Parameters.** `EQ = (rangeHigh + rangeLow)/2` = the 0.50 fib. Prior-day variant
  `PDEQ = (PDH + PDL)/2`.
- **Use.** EQ divides discount (buy) and premium (sell) zones; a return to EQ is the first
  decision point. Trades exactly at EQ are considered 50/50 / low-edge.
- **Pitfall.** No algorithmic ICT rule picks *which* swings define "the" range
  (discretionary — usually the most recent clean displacement leg).

---

## 2. Premium vs discount

- **Definition.** **Premium** = above EQ (expensive → favor selling); **discount** = below
  EQ (cheap → favor buying).
- **Parameters.** Above 0.50 = premium; below = discount. Discount buy zone 0.50→1.0 with
  OTE inside it.
- **Use.** With bias: bullish → buy only in discount; bearish → sell only in premium.
- **Pitfall.** Relative to the chosen range; recompute when a new range forms.

---

## 3. Optimal Trade Entry (OTE) & Fibonacci targets

- **Definition.** A deep Fibonacci **retracement** zone within the dealing range from which
  price is expected to reverse and continue with bias.
- **Parameters (high agreement).** Retracement levels **0.50, 0.62, 0.705, 0.79**; OTE zone
  = **0.62 → 0.79**, with **0.705** the focal "sweet spot."
  - **Long:** draw fib from swing **low (1.0) → high (0.0)**; buy the 0.62–0.79 discount zone.
  - **Short:** from swing **high (1.0) → low (0.0)**; sell the 0.62–0.79 premium zone.
  - Compute explicitly (longs): `level = low + (high-low)*r`.
  - **Targets / negative extensions past the 0.0 anchor:** **−0.27, −0.62** (universal),
    plus (per "ICT fib settings") −1.0, −2.0, −2.5, −4.0.
- **Use.** After a sweep + MSS, enter as price retraces into 0.62–0.79; stop beyond
  0.79/swing extreme; TP at prior swing (0.0), then −0.27, −0.62.
- **Pitfalls.** 0.705 is **not** a standard fib (midpoint of 0.618 and 0.79) — set custom
  levels. TradingView's fib sign convention is opposite ICT's "negative" labels; define
  extensions arithmetically rather than via a drawing tool. The deeper extension set is
  where sources diverge most.

---

## 4. Standard-deviation projections (range-based targets)

- **Definition.** Targets projected as multiples of a *reference range* above/below it.
- **Parameters.** `projection = boundary ± N*(rangeHigh − rangeLow)`, N = ±1, ±2, ±3
  (sometimes ±4). Reference ranges: **CBDR**, **Asian range**, or **Flout**.
- **Use.** ±1 SD often caps the Judas swing; ±2/±3 SD become daily high/low targets.
- **Pitfall.** "Standard deviation" is a **misnomer** — it is range size × N, not statistical σ.

---

## 5. Reference ranges: CBDR, Asian range, Flout (NY time)

- **Asian range / session:** **19:00 → 00:00 ET** (killzone subset 20:00–22:00).
- **CBDR (Central Bank Dealing Range):** **14:00 → 20:00 ET**.
- **Flout:** wider, commonly **15:00 → 24:00 ET**.
- Daily-range estimation also uses the **average daily range over N days (default 5)**.
- **Use.** A *narrow* chosen range (e.g. <~40 pips FX) makes SD projections reliable for the
  coming London/NY sessions.
- **Pitfalls.** Competing ranges (CBDR vs Asian vs Flout); Asian *session* (19:00–00:00) ≠
  Asian *killzone* (20:00–22:00). All cross midnight → two-day date handling.

---

## 6. Killzones (NY time)

High-probability intraday windows. **Highest-disagreement area — make them configurable.**

| Killzone | NY time (ET) |
| --- | --- |
| Asian Range killzone | 20:00 – 22:00 (*some: 19:00/20:00 – 00:00*) |
| London Open | 02:00 – 05:00 |
| New York AM | 07:00 – 10:00 (FX) |
| London Close | 10:00 – 12:00 |
| New York PM | 13:30 – 16:00 (less standardized) |

Indices/equities variant: NY killzone often **08:30 – 11:00** (to capture 8:30 data + 9:30
open). Only take setups inside a killzone; London and NY AM are highest-probability.

---

## 7. Silver Bullet (three 1-hour windows, NY time)

Strong agreement:
- **London Open SB:** 03:00 – 04:00
- **NY AM SB:** 10:00 – 11:00 (flagship)
- **NY PM SB:** 14:00 – 15:00

Inside the hour, after a short-term liquidity sweep, enter on the first FVG in the bias
direction; target the nearest opposing liquidity. Anchor to NY time.

---

## 8. Macros (NY time, ~20-min windows)

Used on 1–5m charts; expect a sweep then displacement toward the draw on liquidity. The
underlying heuristic is "last 10 min of one hour + first 10 min of the next" (xx:50–xx:10).
**Make the macro set an editable list** — the named list is not fully standardized.

- **London:** 02:33 – 03:00, 04:03 – 04:30 (odd-minute starts are intentional)
- **NY AM:** 08:50 – 09:10, 09:50 – 10:10, 10:50 – 11:10
- **NY lunch:** 11:50 – 12:10
- **NY PM / last hour:** 15:15 – 15:45 (consistent across sources)
- **Afternoon (sources disagree):** writofinance adds 13:10–13:40; ictflow/TradingFinder use
  13:50–14:10 and 14:50–15:10 instead, plus a 09:30–09:50 open macro and two Asian macros
  (19:50–20:10, 20:50–21:10).

---

## 9. Judas swing

- **Definition.** A deliberate **false move** early in a session — price pushes one way to
  grab liquidity, then reverses to the true direction. It is the *Manipulation* phase of PO3.
- **Parameters.** Classic **London Judas:** 00:00 – 02:00 ET, capped near ±1 SD of the
  CBDR/Asian range (00:00–02:00 = "Normal Protraction"; only after 02:00 = "Delayed"). Also
  seen near the NY open (09:30) and 08:30 data.
- **Use.** Fade it — the high/low it prints often becomes the session high/low (the day's
  draw-from level).
- **Pitfall.** Session-relative (London vs NY each have one); London Judas straddles midnight
  → depends on the true-day-open choice.

---

## 10. Asian range & daily-range estimation

- **Definition.** Use the low-volatility Asian session range to estimate the coming day's
  expansion and project targets.
- **Parameters.** Asian session **19:00 – 00:00 ET**; project ±1/±2/±3 SD of the Asian (or
  CBDR) range; a narrow Asian range → more reliable projections.
- **Use.** Asian high/low = liquidity pools London/NY likely raid (the Judas usually sweeps
  one side of the Asian range first).
- **Pitfall.** Pip thresholds are instrument-specific (keep as input); window crosses midnight.

---

## 11. Power of 3 (PO3) / AMD

- **Definition.** Every candle/session unfolds **Accumulation → Manipulation → Distribution**.
- **Mapping.** Accumulation = sideways near the daily open (≈ Asian / pre-London);
  Manipulation = the Judas swing sweeping liquidity (≈ London / NY open); Distribution = the
  expansion in the true direction (≈ NY AM). Bullish day: Open → drop to Low (Manipulation) →
  rally to High (Distribution) → close near high.
- **Use.** Anchor on the daily open (midnight ET); expect manipulation away from open, then
  distribution toward the daily draw.
- **Pitfall.** Which clock anchors "the open" is the key choice (midnight ET most common;
  sometimes 18:00). AMD is fractal (sessions/days/weeks) → let the user pick anchor/timeframe.

---

## 12. Session opens & true-day boundary

- **Midnight Open (00:00 ET):** primary bias reference — **above = bullish intent, below =
  bearish**; also intraday S/R.
- **08:30 ET:** US data release; frequent Judas/OB formation.
- **09:30 ET:** NYSE/index regular open; major expansion start.
- **True-day open — SOURCE DISAGREEMENT:** most ICT usage = day runs **midnight–midnight ET**
  (00:00 = true-day open / bias anchor); CME/futures alternative = day starts **18:00 ET**.
  Make it a dropdown (00:00 default, 18:00 option). 09:30 is an equities/index concept (less
  meaningful on pure FX). All NY-time → DST-safe via `America/New_York`.

---

## 13. Daily bias (direction)

- **Definition.** The expected next major directional move, from where liquidity rests and
  imbalances sit.
- **Reference levels.** PDH/PDL, PWH/PWL, and the **Midnight Open** (above = bullish, below =
  bearish). **Draw on Liquidity (DOL):** the nearest significant old high (above) or low
  (below) price is likely drawn toward; bias points to the more probable draw.
- **Use.** Combine, e.g. below midnight open + in premium + nearest DOL is PDL → bearish →
  sell rallies into premium/OTE.
- **Pitfall.** Discretionary (no single formula). PDH/PDL/PWH/PWL/MO are codeable; "which DOL"
  is judgmental — a simple "above/below midnight open" flag is the most automatable proxy.

---

## 14. Daily & weekly profiles

- **Definition.** Template "stories" of how a day/week tends to unfold (where the high/low forms
  and when).
- **Parameters.** Weekly: ~12 patterns; HOTW/LOTW (High/Low of Week) — classically set Tue–Wed.
  Daily: Classic Buy/Sell Day (best Mon–Wed); e.g. a London drop of ~15–30 pips from the daily
  open sets the low, then NY distributes up; range typically expands over ~7–8 hours.
- **Use.** Pick the likely profile from weekly bias, expect the high/low at the prescribed
  session, run intraday models inside it.
- **Pitfall.** Probabilistic templates, not signals — useful mainly as annotations; pip figures
  are FX-specific.

---

## 15. Quarterly theory (time-fractal)

- **Definition.** An AMD-derived fractal dividing every cycle into **four quarters (Q1–Q4)**,
  each running its own AMD-X sub-cycle.
- **Parameters.** Daily → **90-minute** quarters; weekly → Q1 Mon, Q2 Tue, Q3 Wed, Q4 Thu
  (Friday excluded); micro → ~**22.5-min** segments.
- **Use.** Expect manipulation in Q2, distribution in Q3 (e.g. Tue manipulation, Wed expansion).
- **Pitfall.** An ICT-*adjacent* extension (Daye/TTrades), **not core ICT** — label provenance;
  exact subdivisions vary → make anchor/segment length configurable.

---

## Implementation summary

- Timezone: `"America/New_York"` everywhere; never hardcode UTC offsets.
- Fib (longs): `level = low + (high-low)*r`; retracement r ∈ {0.50, 0.62, 0.705, 0.79};
  targets r ∈ {0, −0.27, −0.62, −1.0, −2.0, −2.5, −4.0} (mirror for shorts).
- EQ/premium/discount: midpoint; shade above = premium, below = discount.
- SD projections: `boundary ± N*(rangeHigh−rangeLow)`, N=1..3(4).
- Make configurable (sources disagree): killzone bounds, macro list, day-open anchor
  (00:00 vs 18:00 ET), Asian/CBDR/Flout windows, SD reference range.
- Midnight-crossing windows (Asian/CBDR/Flout) need two-day date handling.

---

## Sources

- https://innercircletrader.net/tutorials/master-ict-kill-zones/
- https://tradingrage.com/learn/ict-killzone-explained
- https://innercircletrader.net/tutorials/ict-fibonacci-levels/
- https://innercircletrader.net/tutorials/ict-optimal-trade-entry-ote-pattern/
- https://fxnx.com/en/blog/mastering-the-ict-fibonacci-retracement-a-traders-guide
- https://www.writofinance.com/trading-with-ict-optimal-trade-entry-ote-zone/
- https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/
- https://innercircletrader.net/tutorials/ict-macro-time-based-strategy/
- https://www.writofinance.com/ict-macros-times-in-forex/
- https://ictflow.com/blog/ict-macro-times-explained
- https://innercircletrader.net/tutorials/ict-power-of-3/
- https://fxnx.com/en/blog/mastering-the-ict-power-of-3-po3-strategy
- https://innercircletrader.net/tutorials/ict-asian-range/
- https://www.tradingview.com/script/bo56LlEd-Range-Deviations-joshuuu/
- https://innercircletrader.net/tutorials/ict-intraday-profiles/
- https://blog.trinitytrading.io/ict-premium-discount-smart-money-guide-2026/
- https://arongroups.co/technical-analyze/ict-dealing-range/
- https://arongroups.co/technical-analyze/ict-equilibrium-zones/
- https://innercircletrader.net/tutorials/ict-daily-bias-explained/
- https://tradingfinder.com/education/forex/ict-important-time-levels-for-trading/
- https://www.edgeful.com/blog/posts/ICT-trading-strategy-midnight-open-retracement-report
- https://innercircletrader.net/tutorials/ict-weekly-range-profiles/
- https://blog.opofinance.com/en/ict-daily-profiles-in-forex/
- https://www.writofinance.com/quarterly-theory-smc-and-ict/
