# Volume Profile Reference — Trading Strategies & Application

Ordered, state-machine-codeable setups. Each: thesis → step-by-step → entry/stop/target →
pitfalls. See `../SKILL.md` for the regime gate and the VP↔ICT mapping.

---

## 0. Acceptance vs rejection (define once, reused everywhere)

This distinction is the crux of nearly every setup — make it configurable state.

- **Acceptance:** sustained two-way trade beyond a level. Operational options:
  - *Time/TPO (Market Profile):* holds ≥2 thirty-min periods (~1h) — the canonical 80%-rule confirmation
    (some sources: ≥30 min).
  - *Close-based:* ≥1–2 closes beyond the level, ideally on volume ≥ average.
  - Some sources insist it is observational (tape slows, rotations increase, pullbacks find bids/offers
    inside). **Make it a parameter** (`acceptance_periods` default 2×30min, or `acceptance_closes` default 2).
- **Rejection:** quick move through/at a level with little trade — reverses within ~1 candle leaving a wick
  (≥~50% of range), OR fails the acceptance threshold and returns.

Model as `APPROACH → TOUCH → {ACCEPT (N periods/closes beyond) | REJECT (returns within M / qualifying wick)}`.

---

## 1. Value Area rejection (fade) — mean-reversion

**Thesis.** Price extends to a value edge (VAH/VAL), fails to find business outside, reverts toward POC and
often the opposite edge. Dominant on range/rotational days.

**Steps.** Reference = prior-session VAH/POC/VAL → `ARMED`: price trades into VAH (short) / VAL (long),
ideally from inside or only a marginal poke out → `REJECTION_TEST`: rejection at the edge (wick back inside,
no close outside, stalling volume) → `TRIGGER`: candle **closes back inside** VA → `IN_TRADE`.

**Entry/stop/target.** Entry on the close back inside (or a retest of the edge from inside). Stop just
**beyond VAH/VAL / the rejection wick** (a close back outside invalidates). T1 = **POC**; T2 = **opposite VA
edge**; scale at POC, trail the rest.

**Pitfalls.** The danger is fading a true breakout — invalidate the moment **acceptance** outside is
confirmed. Require an explicit wick%/no-acceptance rule. Fails on trend days (see §8).

---

## 2. The 80% rule (high-conviction VA-rotation fade)

**Thesis.** If price **opens outside** prior value, trades back **into** it, and **holds** (acceptance), it
tends (~80%) to traverse the *entire* value area to the far edge.

**Steps.** Confirm open is outside prior VA → `RE_ENTRY`: price trades back into VA → `CONFIRM_HOLD`: holds
the acceptance threshold (**two 30-min TPOs ~1h**; a quick dip does not count) → `TRIGGER`: trade toward the
**far edge**. Opened **above VAH**, re-enter heading down → **short, target VAL**. Opened **below VAL**,
re-enter heading up → **long, target VAH**.

**Entry/stop/target.** Entry after the ~1h hold confirms, at the VA-edge re-entry. Stop just **outside the VA
boundary you entered through** (failure to hold negates the statistic). Target = opposite VA boundary (full
rotation).

**Pitfalls.** Sources disagree on the confirmation ("two 30-min closes" vs "hold ≥30 min" vs loose "comes
back in") — make `hold_periods` configurable; the entire edge is in the hold step. Do **not** enter on first
touch back inside. "80%" is a heuristic to backtest.

---

## 3. Value Area breakout / acceptance — trend continuation

**Thesis.** Price **closes and accepts outside** the VA on expanding volume → new value builds in the
breakout direction.

**Steps.** Reference = prior VAH/VAL/POC (open typically inside) → `BREAK`: close above VAH (bull) / below
VAL (bear) on **volume ≥ average** → `ACCEPT`: confirm acceptance outside (don't fade back in) → `PULLBACK`:
retest of the broken edge from outside → `TRIGGER`: retest holds as new S/R → enter in breakout direction.

**Entry/stop/target.** Entry on the **retest-and-hold** of VAH/VAL (aggressive: on the acceptance close).
Stop **back inside the VA** (close back inside = failed breakout; in strong trends tuck behind a breakout
FVG/OB). Target = next HTF HVN / prior swing / measured move (balance height projected); trail with developing
POC.

**Pitfalls.** Breakout vs failed poke = the acceptance threshold. Low-volume breaks fail back into value
(becomes a §1 fade against you). Beware breakouts straight into an HTF HVN (likely to stall).

---

## 4. POC as S/R & POC magnet

**Thesis.** The POC is where institutions transacted most; they defend it → S/R, and price gravitates back
to it from thin areas.

**Steps (S/R bounce).** Identify POC (prior session / anchored) → price moves away (establishes side: above =
support, below = resistance) → `RETURN`: pullback to POC → `TRIGGER`: reaction (rejection/hold) → enter in the
direction of the original move away. **Magnet variant:** when price is stranded in an LVN with no opposing
structure, target a drift back to POC.

**Entry/stop/target.** Entry at the POC retest reaction. Stop just **beyond POC** (acceptance through it flips
its role). Target = VA edge in trade direction, or the POC itself (magnet).

**Pitfalls.** **First test of a POC beats 2nd+** (Trader Dale) — encode `test_count` and prefer/size-up the
1st. Use developing POC (migrates) vs prior/fixed POC (stable reference) deliberately — don't confuse them.

---

## 5. Naked / Virgin POC target trades

**Thesis.** A prior POC never revisited ("naked") is unfinished business that acts as a magnet; the first test
produces a reaction.

**Steps.** Maintain a live nPOC list (prior session POCs with no subsequent trade-through). **Target play:**
when price trends toward a naked POC with no intervening HVN, use the nearest nPOC as the objective.
**Fade-the-test play:** `TOUCH` at the nPOC → watch for a bounce; `TRIGGER` (one method): anchor a VWAP at the
bounce and enter the fade when price breaks the anchored VWAP.

**Entry/stop/target.** Entry on the nPOC touch/rejection (anchored-VWAP break or rejection candle). Stop just
beyond the nPOC (acceptance removes the thesis). Target = the nPOC (for the magnet play) or trail via anchored
VWAP (for the fade).

**Pitfalls.** Once touched, it is no longer naked — update state immediately. Infrequent exact setups — a
selectivity play, not a daily signal. Stacked nPOCs imply a stronger pull.

---

## 6. LVN trades (rejection at, and breakout through)

**Thesis.** LVNs are thin zones → two opposite, context-dependent plays.

**Steps.**
- **LVN rejection (fade back to HVN):** LVN borders an HVN → price approaches from the HVN side → fast
  rejection (wick) at the LVN → enter back toward the originating HVN/POC.
- **LVN breakout (traverse):** LVN between two HVNs → price pushes through on **volume ≥ ~1.5× average** →
  enter in the breakout direction → target the next HVN.

**Entry/stop/target.** Rejection: entry at the LVN edge on rejection; stop just **past the LVN** (into the
void); target the adjacent HVN/POC. Breakout: entry as price commits through (volume-confirmed); stop on the
**near side of the LVN**; target the **next HVN**; aim **≥2:1** and **cut size ~50%** (failed LVN breakouts
reverse violently).

**Pitfalls.** Same LVN → opposite trades by context — condition on **prior location + push volume**.
Low-volume "breakouts" are traps. LVNs are also natural stop locations.

---

## 7. HVN trades (consolidation / reversal)

**Thesis.** HVNs are dense acceptance zones; price slows/sticks/chops → strong S/R and reversal/consolidation.

**Steps.** Identify HVN clusters (incl. prior POC) → `APPROACH` → branch: **reversal/fade** at the far edge on
rejection (fade back through toward origin) **or** **range/scalp** the rotation inside (buy lower edge / sell
upper). **Breakout** only on a strong momentum candle closing outside the HVN (acceptance) → continuation to
the next HVN across the LVN.

**Entry/stop/target.** Entry at HVN-edge rejection (fade) or confirmed close beyond (breakout). Stop just
**beyond the HVN** (past the prior HVN to buffer churn). Target = opposite HVN edge / POC (fade) or next HVN
through the LVN (breakout).

**Pitfalls.** HVNs whipsaw — entries *inside* get chopped; prefer edges. Genuine breakout vs fake-out needs
the acceptance + momentum/volume filter.

---

## 8. Trend-day vs range-day playbooks (regime switch)

**Thesis.** Day type dictates the valid strategy class: range → mean-reversion; trend → breakout/continuation
(and *forbid* fading).

**Identify early (first 30–60 min).** **Trend day:** elongated one-sided developing profile (thin/vertical),
Open-Drive, opening-range breakout that holds, persistent breadth (e.g. NYSE TICK consistently >+400 / <−400),
opens at one extreme & closes at the other. **Range day:** balanced/bell developing profile, rotates around
POC/VWAP, respects prior VAH/VAL, open-auction, no conviction.

**Playbook (`day_type` gate).** `RANGE`: enable §1/§2/§4 fades; **disable breakouts** (or require strong
volume); target POC / opposite edge. `TREND`: enable §3 breakout, §6 LVN traverse, pullback-to-POC/VWAP
continuation; **disable edge fades**; trail with developing POC; expect close at the extreme.

**Pitfalls.** Misclassification is the big risk (fading a trend = death by a thousand cuts; holding a range
day = giving back gains). Build a confidence score + a flip rule (if a "trend" day rotates back through its
opening range and accepts inside prior VA → downgrade to range).

---

## 9. Open-outside-value & open-type strategies

**Thesis.** Where price opens vs prior value, and the open type, set expected behavior. Gaps into LVNs tend to
continue (fast traverse); gaps into HVNs tend to stall/fill.

**Open-type plays.** **Open-Drive** → trade with the drive, stop on the far side of the open; do not fade.
**Open-Test-Drive** → trade the drive after the test fails; the test extreme is reliable. **Open-Rejection-
Reverse** → trade the reversal cautiously (~50%). **Open-Auction** → rotational; use §1/§2/§4 fades.

**Gap-vs-VA logic.** Open above prior VAH / below VAL = trigger for the **80% rule** (§2) if price re-enters
and holds, OR a gap-and-go if it accepts further away. Gap into an LVN → fast continuation; gap into an HVN →
stall / gap-fill toward POC.

**Entry/stop/target.** Open-Drive: enter with the drive on the first shallow pullback; stop on the far side of
the opening range; target next HVN / prior extreme. 80% re-entry: as §2. Gap-fill: target prior-day POC; stop
beyond the developing extreme.

**Pitfalls.** Open type is confirmable only after 1–3 periods — wait before classifying. ORR is the trap.

---

## 10. Volume Profile + VWAP confluence

**Thesis.** VWAP = dynamic fair value; VP = structural fair value (POC) and S/R. Coincidence = much stronger
level (POC and VWAP frequently converge).

**Steps.** Compute session VWAP (±1/±2σ) + prior/developing POC/VAH/VAL → `CONFLUENCE`: a VP level sits within
a small tolerance of VWAP (or a band) → apply the relevant base setup (§1/§3/§4) but **only fire / size up when
confluence is present.**

**Entry/stop/target.** Entry at the confluence level on the base trigger. Stop beyond **both** references (VP
level *and* VWAP band). Target = next confluence cluster / opposite VA edge / POC.

**Pitfalls.** Treat "triple-confluence 85% win-rate" claims as marketing — use confluence as a filter/size
multiplier, not a standalone signal. Parameterize the tolerance (ticks/ATR).

---

## 11. Volume Profile + ICT smart-money concepts

**Thesis.** VP (volume) and ICT (price action) often mark the **same** institutional zones; independent
agreement = high confluence. See the `ict` skill.

**Mapping.** HVN/POC ↔ Order Block · LVN/single-print ↔ FVG/imbalance · VA edges & nPOC ↔ liquidity pools /
draw on liquidity · VWAP/POC ↔ equilibrium / dealing-range midpoint.

**Sweep-reversion example.** Mark prior VAH/VAL/swing highs-lows (liquidity) + POC/HVN (value) → `SWEEP`:
price runs the liquidity at/near a POC or VA edge → `DISPLACEMENT`: strong reversal candle (+ optional FVG)
back toward value → `TRIGGER`: enter on the displacement/FVG retest, target POC then opposite VA edge.

**Entry/stop/target.** Entry on the displacement/FVG retest at the VP level. Stop beyond the swept liquidity /
order block (and the VP level). Target = POC → opposite VA edge / next HVN.

**Pitfalls.** Don't double-count the *same* level as "two confluences" — real confluence = volume *and* price
action independently agree. Win-rate claims are heuristics to backtest.

---

## 12. Risk management relative to VP levels

- **Fades (§1/§2/§4):** stop **beyond the VA edge / POC / rejection wick** — where *acceptance* would prove the
  fade wrong (a **close** beyond is the cleanest invalidation).
- **Breakouts (§3/§6):** stop **back inside** the broken structure (inside VA, near side of the LVN); in trends,
  tuck behind a breakout FVG/OB.
- **HVN trades (§7):** stop **beyond the HVN** (past the prior HVN to buffer churn).
- **LVNs = natural stop locations** (price shouldn't dwell there).

**Target order of preference:** POC (T1) → opposite VA edge (full rotation) → next HVN (breakouts) → naked POC.
**Sizing/R:R:** rotations/POC bounces ≥1.5:1; LVN breakouts ≥2:1 with ~50% size; scale up on multi-tool
confluence, down on counter-day-type trades.

---

## 13. Multi-timeframe Volume Profile

**Thesis.** HTF composite = "where" (bias, walls, magnets, naked POCs); session/intraday = "when" (entries).

**Steps.** **HTF (composite/weekly):** map dominant POC, value, big HVNs (walls), LVNs (acceleration), naked
POCs → set bias. **ITF (daily/60m):** locate session VAH/VAL/POC vs HTF levels; find where they **stack**.
**LTF (15/5m):** execute §1–§9 **only at HTF/ITF-confluent levels**, with HTF bias for continuation (counter
only at major HTF walls).

**Entry/stop/target.** Entry = LTF trigger at an HTF/ITF confluence. Stop beyond the **HTF** level (structural;
LTF noise shouldn't stop you). Target = next HTF node.

**Pitfalls.** HTF/LTF conflict → HTF wins for bias/targets, LTF for timing. An LTF breakout straight into an
HTF HVN likely stalls — filter it. Composite window choice changes levels — parameterize.

---

## Implementation notes (state machine)

- **Config:** `acceptance_mode` (periods|closes), `acceptance_periods` (2×30min), `acceptance_closes` (2),
  `rejection_wick_pct` (50%), `breakout_vol_mult` (1.0–1.5×), `lvn_break_vol_mult` (1.5×), `confluence_tol`
  (ticks/ATR), `poc_max_tests` (1).
- **Regime gate:** compute `day_type` early; it enables/disables the fade vs breakout families.
- **Shared sub-states:** `APPROACH → TOUCH → {ACCEPT | REJECT}` reused everywhere.
- **Level bookkeeping:** prior-session VAH/VAL/POC, developing VAH/VAL/POC, HVN/LVN lists, live naked-POC list
  (retire on first touch).
- Treat all cited win-rates (80%, 85%, 75%) as **priors to backtest**, not guarantees.

---

## Sources

- https://www.metrotrade.com/what-is-the-80-rule-in-futures-trading/
- https://internationaltradinginstitute.com/blog/reading-the-volume-profile-from-acceptance-to-rejection/
- https://www.quantvps.com/blog/value-area-trading-strategy-guide
- https://arongroups.co/forex-articles/value-area-trading/
- https://www.pipsafe.com/the-value-area-80-rule/
- https://damnpropfirms.com/prop-firms/volume-profile-strategies-high-probability-trades/
- https://alchemymarkets.com/education/indicators/volume-profile/
- https://ftmo.com/en/blog/master-volume-profile-trading-with-the-va-breakout-strategy/
- https://ftmo.com/en/blog/market-profile-types-of-opens-and-the-anatomy-of-a-trading-day/
- https://www.tradingsim.com/blog/advanced-day-trading-strategies-using-volume-profile
- https://www.trader-dale.com/how-to-trade-the-point-of-control-poc/
- https://www.chartspots.com/volume-profile-strategy-profiting-from-naked-vpoc-levels/
- https://gocharting.com/blog/volume-profile/point-of-control-trading-guide
- https://www.buildix.trade/blog/volume-profile-trading-strategies-value-area-naked-poc-free-guide-2026
- https://tradingstrategyguides.com/fixed-range-volume-node-breakout-strategy/
- https://www.angelone.in/knowledge-center/online-share-trading/high-volume-nodes-hvn
- https://daytradingtoolkit.com/strategies/trend-day-trading-strategy/
- https://tradersmastermind.com/types-of-market-open/
- https://atas.net/volume-analysis/strategies-and-trading-patterns/open-drive/
- https://www.luxalgo.com/blog/volume-profile-map-where-smart-money-trades/
