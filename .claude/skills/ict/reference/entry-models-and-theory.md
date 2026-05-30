# ICT Reference — Displacement, Entry Models & Theory

Implementation-oriented reference: each model gives a definition, an ordered
state-machine sequence, entry/stop/target rules, and pitfalls. Times are NY/ET.
Two recurring binary forks: **wick-through vs body-close-through** for MSS, and
**direct-on-sweep vs wait-for-LTF-confirmation** for entries.

---

## 0. Primitives (referenced by every model)

- **Swing high/low:** candle whose high (low) exceeds N candles each side; pivots confirm
  N bars late — never act on an unconfirmed pivot.
- **FVG:** bullish = `low[C3] > high[C1]` (zone `[high(C1), low(C3)]`); bearish =
  `high[C3] < low[C1]` (zone `[high(C3), low(C1)]`).
- **Order Block:** last opposite-color candle before a displacement move.
- **Breaker:** an OB that failed (price traded through it), flipping support↔resistance.
- **Liquidity:** BSL = buy stops above old/equal highs; SSL = sell stops below old/equal lows
  — the magnets/targets.
- **Premium/discount:** 50% of the dealing range; longs from discount, shorts from premium.

---

## 1. Displacement

- **Definition.** A strong, rapid, one-directional move signaling institutional
  participation — large-bodied, small-wick candles that almost always **leave an FVG**. It
  separates a real MSS from a weak CHoCH.
- **Quantification (a filter, not a setup):**
  1. body = `abs(close-open)`, range = `high-low`.
  2. **body/range ≥ ~0.6–0.7** → conviction candle.
  3. **range/body ≥ k×ATR** or ≥ k×avg range of last M candles (k≈1.5–2; no official number).
  4. LTF: require **3+** consecutive strong candles; HTF (D/W/M): 1–2 suffice.
  5. **FVG existence** — the most reliable, non-arbitrary criterion → use as the primary anchor.
  6. Strongest when the move **breaks a swing** (BOS/MSS).
- **Pitfall.** ICT published no numeric threshold; anchor on FVG-left-behind, parameterize the
  rest; timeframe-dependent.

### 1b. MSS vs BOS
- **BOS:** close beyond a swing **with** the trend → continuation.
- **MSS:** break of a **counter-trend** swing **with displacement** → reversal. = CHoCH + a
  displacement candle. **CHoCH** = the same counter-trend break **without** displacement
  (weaker). Code MSS = (counter-trend swing broken) AND (break candle/leg qualifies as
  displacement); flag "wick-through vs body-close-through."

---

## 2. SMT Divergence (Smart Money Technique)

- **Definition.** Divergence between two **correlated** instruments on the same timeframe: one
  makes a new extreme, the other fails to confirm. The non-confirming leg is the manipulated
  one → reversal signal.
- **Sequence (two synced feeds A, B):**
  1. Pick a correlated pair: **ES/NQ** (canonical), EUR/USD vs GBP/USD; negatively correlated:
     EUR/USD vs DXY (invert logic).
  2. Same timeframe (≤15m for execution).
  3. Wait for price at a key swing / PD array (SMT is a confirmation, not standalone).
  4. **Bearish SMT:** A makes HH, B makes LH → downside. **Bullish SMT:** A makes LL, B makes
     HL → upside.
  5. Stack with MSS to validate the entry.
- **Entry/stop/target.** No standalone entry; stop beyond the failing leg's swept extreme,
  target opposing liquidity.
- **Pitfalls.** Needs **time-synchronized multi-symbol** data; invert logic for negatively
  correlated pairs (common bug); pivots lag; intraday correlation can break (consider a rolling
  correlation filter).

---

## 3. Turtle Soup (false-break reversal)

- **Definition.** A stop-hunt fade: price spikes through a prior swing to grab liquidity, fails
  to follow through, and snaps back into the range.
- **Sequence (bearish at a swing high; bullish mirrors):**
  1. Mark BSL (prior swing high / equal highs / session high).
  2. Price trades **above** it (wick sweep).
  3. Price **closes back below** the level (fails to hold).
  4. *(Option)* LTF bearish MSS and/or OB/FVG forms.
  5. Short.
- **Entry/stop/target.** Entry direct on the reversal, or on the retrace into the OB/FVG after
  an LTF MSS (higher confidence). Stop just **beyond the false-break extreme** + buffer (tight →
  often 1:3–1:4 RR). Target the **opposite** HTF liquidity pool.
- **Pitfalls.** Candle counts unspecified; "direct vs wait-for-MSS" = two valid implementations.
  Disambiguate sweep vs genuine breakout by requiring a **body close back inside** within X bars.

---

## 4. Unicorn Model (Breaker + FVG overlap)

- **Definition.** A high-precision entry from the **overlap** of a **breaker block** and an
  **FVG** created by the same displacement.
- **Sequence (bullish; bearish mirrors):**
  1. Form a bullish breaker (low → lower low sweep → displacement up breaking structure).
  2. The up-displacement leaves a **bullish FVG**.
  3. **Overlap test:** FVG must overlap / sit inside the breaker's range — **no overlap → not a
     Unicorn** (the defining condition).
  4. Wait for price to retrace into the overlap (not at the MSS itself).
  5. Enter at the overlap.
- **Entry/stop/target.** Limit inside FVG∩breaker; stop below the bullish breaker (above the
  bearish breaker for shorts); target ~1:2 RR or next opposing liquidity. ≤15m to identify,
  3m/5m to time.
- **Pitfalls.** Overlap = `[max(lowerbounds), min(upperbounds)]`, require non-empty intersection
  (proximity ≠ overlap). Pin one breaker definition.

---

## 5. ICT 2022 Mentorship Model (the flagship)

- **Definition.** Sweep liquidity → shift structure with displacement → enter on the retrace
  into the FVG/OB → target opposing liquidity.
- **Sequence (bullish; bearish mirrors):**
  1. **Daily bias** set (bullish) via top-down. No bias → no trade.
  2. Mark HTF liquidity and premium/discount.
  3. **Liquidity sweep:** price first moves **down** to take SSL.
  4. LTF (5/3/1m): **MSS with displacement** up (aligned to bias) leaving an **FVG** in discount.
  5. Identify the nearest PD array (FVG/OB/breaker) in discount.
  6. **Entry** on retrace into it.
  7. Manage to target.
- **Entry/stop/target.** Limit at the FVG/OB mean threshold (50% of OB). Stop a few pips
  **beyond the swept level** (below the swing/Judas low for longs; some use "above London session
  high" for sells). Target the **opposing liquidity**; minimum **1:3 RR**. Timeframes: Daily =
  bias, H4/H1 = context, 15m = liquidity map, 5/3/1m = MSS + entry. Kill zones: London 02:00–05:00,
  NY AM 07:00–10:00; avoid 12:00–14:00 lunch.
- **Pitfalls.** Bias is the hardest part to automate. "Sweep" must be defined precisely
  (wick beyond + reversal). Displacement threshold tunable. FVG/OB/breaker preference order is
  not fixed — pick a priority. Stop-buffer is discretionary.

---

## 6. Silver Bullet

- **Definition.** A time-boxed 2022 model — trade only within a fixed 1-hour window, taking a
  post-sweep FVG entry. "One trade per window" discipline.
- **Windows (ET):** London 03:00–04:00; **NY AM 10:00–11:00 (highest probability)**; NY PM
  14:00–15:00.
- **Sequence.** Pre-window: set bias + mark liquidity. **Inside the hour only:** wait for a
  liquidity sweep → fast move printing an **FVG** (ideally + LTF MSS) → enter on the retrace.
- **Entry/stop/target.** Entry at the FVG (M1/M5); stop beyond the sweep extreme; target the next
  opposing pool (often a fixed RR within the hour).
- **Pitfalls.** Windows are **NY local, DST-sensitive** — compute in `America/New_York`. Zero or
  one setup per window — enforce "no setup → no trade." Bias step still subjective.

---

## 7. Optimal Trade Entry (OTE)

- **Definition.** A fib retracement entry into the **0.62–0.79** band (0.705 focal) of an
  established impulse leg, expected to reverse and continue.
- **Sequence.** Preconditions: bias set, a liquidity pool swept, displacement + MSS occurred.
  Draw fib swing low→high (long) / high→low (short); OTE zone 0.62–0.79 (0.705 primary, 0.79
  deepest); enter on retrace; targets reference **−0.27 / −0.62** extensions. Strongest when an
  FVG/OB sits inside the 0.62–0.79 band (OTE ∩ PD array).
- **Entry/stop/target.** Entry 0.705 (or zone); stop just **beyond the swing extreme** (1.0/leg
  origin); target the new high/low, then −0.27 (TP1), −0.62 (TP2).
- **Pitfalls.** 0.705 is non-standard (configure custom levels). The biggest ambiguity is *which*
  swing defines the leg — anchor it to the MSS-producing impulse. Direct vs wait-for-confirmation
  is a parameter.

---

## 8. IPDA (Interbank Price Delivery Algorithm) & algorithmic price theory

- **Definition.** ICT's premise that price is delivered by an **algorithm** whose objectives are
  (a) take liquidity at clustered stops and (b) rebalance imbalances (FVGs). References rolling
  **20 / 40 / 60 trading-day** lookback ranges as institutional levels.
- **Use as a contextual layer.** For each lookback (20/40/60 **trading** days) plot highest high,
  lowest low, and equilibrium (50%). Treat the highs/lows as **liquidity targets / DOL** and EQ as
  premium/discount divider. 20-day → intraday narrative & POIs; 40/60-day → swing/positional. IPDA
  "resets" ~every 20 days / quarterly → re-evaluate bias on that cadence. Feed levels into the
  models as HTF liquidity/bias context.
- **Pitfalls.** **Trading** days (exclude weekends/holidays). The quarterly/20-day reset is loosely
  defined — a heuristic, not a discrete trigger. It is theory/context, not a standalone signal.

---

## 9. Draw on Liquidity / liquidity run (the target engine)

- **Definition.** **DOL** = the pool price is being drawn toward (the **target**). A **liquidity
  run** = price actively moving to take a pool (vs a **sweep**, the spike that grabs and reverses).
- **Use.** Enumerate pools (relative equal highs/lows, prior day/week high & low, session
  highs/lows, IPDA box highs/lows); given bias, the **nearest opposing pool in the bias direction**
  is the target. Internal (FVGs/OBs inside the range) = entries; external (swing/equal highs/lows) =
  the real magnets. Price takes internal → runs to external. This is the target/stop rule for every
  model: exit into the next pool, stop just beyond the pool that originated the trade.
- **Pitfalls.** "Equal" highs/lows need a tolerance band (X ticks/ATR). Multiple pools → priority /
  closest-in-direction rule.

---

## 10. Power of Three (AMD) — algorithmic delivery

- **Definition.** **Accumulation → Manipulation → Distribution** on any timeframe (also the daily
  PO3 candle).
- **Daily mapping.** Accumulation ≈ Asian (consolidation; mark its range); Manipulation ≈ London
  open — the **Judas swing** sweeps one side of the Asian range; Distribution ≈ NY — the true move
  toward DOL.
- **Use.** Trade the *end of manipulation*: enter as the Judas sweep reverses (= the sweep step of
  §5/§6); stop beyond the Judas extreme; target the distribution destination (opposing pool).
- **Pitfalls.** Phase boundaries are session-time heuristics, not triggers — combine with concrete
  sweep+MSS logic. Manipulation direction is unknown until the sweep completes.

---

## 11. Risk management (as ICT teaches it)

- **Structural stops, never arbitrary:** beyond the **swept liquidity / Judas low / OB / swing**
  that, if violated, invalidates the thesis (longs: below the sweep low / OB; shorts: above), plus a
  small buffer so a retest wick doesn't stop you.
- **Size from stop distance, never the reverse:** `size = (Account × Risk%) / (StopDistance ×
  PipValue)`. Never tighten the stop to fit a size.
- **Risk:** 1–2% per trade (universal); max daily ~3%.
- **R multiples:** models target 1:2–1:5; the 2022 model wants **≥1:3**. Tight structural stops
  (often 10–30 pips FX) make high RR feasible.
- **Management:** partial at the first opposing pool / −0.27 extension; runner to the next pool.
- **Pitfalls.** Buffer size discretionary (ticks or ATR fraction); pip/tick value must be
  instrument-correct (FX vs ES/NQ multipliers); enforce daily-loss-limit and max-concurrent-risk
  circuit breakers in a bot.

---

## 12. Multi-timeframe top-down workflow (HTF bias → LTF entry)

A fixed, ordered routine producing a single bias **before** any entry. Neutral → no trade.

1. **HTF bias (Monthly/Weekly → Daily):** dealing range, side of equilibrium, last external BOS
   direction, IPDA context → output bullish / bearish / neutral.
2. **MTF (H4/H1):** locate the specific PD array where the bias-direction trade exists, and the DOL
   (target). No zone in reach → no trade today.
3. **LTF (15/5/1m):** wait for price at the zone; require confirmation = liquidity sweep + MSS with
   displacement + FVG/OB (or engulfing/rejection).
4. **Execute & stop:** stop on the **far side of the HTF zone / swept liquidity**, not the LTF candle.

Roles: HTF (D/W) = direction; MTF (H4/H1) = where; LTF (15/5/1m) = when. **Pitfall:** order matters —
anchoring to the wrong timeframe's bias is the classic error; expect many no-trade sessions.

---

## 13. A+ confluence checklist (codeable scoring)

All true = A+ setup:

1. IPDA narrative written; 20/40/60-day highs/lows marked.
2. Daily bias set before London open; price in the correct premium/discount.
3. Nearest PD array identified in the correct zone (discount for longs / premium for shorts).
4. Judas swing / liquidity sweep completed.
5. MSS with displacement, leaving a visible FVG.
6. Entry zone falls inside an active killzone (time filter).
7. Confluence stack: OTE (0.62–0.79) ∩ FVG ∩ OB/breaker; SMT divergence present; OB with FVG inside.
8. Stop below Judas/sweep low (or above high); targets at opposing liquidity / −0.27 & −0.62;
   risk ≤ 1–2%, RR ≥ 1:3.

**Bot logic:** make **bias + completed sweep + MSS/displacement + PD-array-in-discount/premium** the
*mandatory gates*; treat SMT / OTE-overlap / killzone as *score boosters*. The single strongest stack
ICT repeats: **OTE ∩ FVG ∩ OB at swept liquidity, in a killzone, with HTF bias and SMT confirmation.**

---

## Key disagreements & engineering must-dos

- **Displacement** has no official number — anchor on FVG-left-behind; parameterize body% / ATR /
  candle count.
- **MSS confirmation:** wick-through vs body-close-through — make it a flag.
- **Entry timing:** direct-on-sweep vs wait-for-LTF-MSS — two distinct state machines; the
  wait-for-confirmation variant is higher-probability / lower-frequency.
- **DST-aware** session math (`America/New_York`).
- **SMT** needs synchronized multi-symbol feeds; invert logic for negatively correlated pairs (DXY).
- **0.705** is a custom (non-standard) fib level.
- **Bias** is the irreducibly subjective gate — a rules-based proxy (last HTF external BOS + side of
  EQ + IPDA box position) is the most automatable substitute.

---

## Sources

- https://howtotrade.com/blog/ict-displacement/
- https://www.writofinance.com/ict-displacement-move-in-forex/
- https://www.equiti.com/sc-en/news/trading-ideas/mss-vs-bos-the-ultimate-guide-to-mastering-market-structure/
- https://fxopen.com/blog/en/market-structure-shift-meaning-and-use-in-ict-trading/
- https://www.luxalgo.com/blog/market-structure-shifts-mss-in-ict-trading/
- https://tradingfinder.com/education/forex/ict-smt-divergence/
- https://innercircletrader.net/tutorials/ict-smt-divergence-smart-money-technique/
- https://www.metrotrade.com/smt-trading-futures/
- https://www.fluxcharts.com/articles/ict-turtle-soup-strategy-explained-how-to-identify-and-trade-it
- https://innercircletrader.net/tutorials/ict-turtle-soup-pattern/
- https://innercircletrader.net/tutorials/ict-unicorn-model/
- https://www.luxalgo.com/blog/ict-unicorn-model-strategy-how-to-use/
- https://tradingfinder.com/education/forex/ict-mentorship-2022-model/
- https://innercircletrader.net/tutorials/complete-ict-trading-strategy-2022/
- https://fxopen.com/blog/en/what-is-the-ict-silver-bullet-strategy-and-how-does-it-work/
- https://innercircletrader.net/tutorials/ict-silver-bullet-strategy/
- https://innercircletrader.net/tutorials/ict-optimal-trade-entry-ote-pattern/
- https://howtotrade.com/blog/optimal-trade-entry-ict/
- https://innercircletrader.net/tutorials/ict-ipda/
- https://tradingfinder.com/education/forex/ict-interbank-price-delivery-algorithm/
- https://innercircletrader.net/tutorials/ict-liquidity-sweep-vs-liquidity-run/
- https://b2broker.com/news/buy-side-liquidity-and-sell-side-liquidity-in-ict-trading-how-does-it-work/
- https://ictflow.com/blog/ict-power-of-three-amd-complete
- https://ttrades.com/ict-power-of-three-amd-accumulation-manipulation-distribution-explained/
- https://tradingstrategyguides.com/day-17-risk-management-in-ict-smc-trading-position-sizing-stop-loss-drawdown/
- https://tradingfinder.com/education/forex/ict-top-down-analysis/
