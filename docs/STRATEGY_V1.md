# Strategy V1 — Volume Profile setup (3m) → ICT entry (1m)

> **Context timeframe:** the setup runs on a **3-minute** profile by default
> (chosen for a finer profile and more frequent setups than 5m). It is
> configurable; everywhere below "the context chart" means the 3m chart.

> Status: **draft for owner validation.** Per `AGENTS.md` this is presented for
> review before any commit/tests. The mechanics below mirror
> [`indicator/vp_ict_strategy_v1.pine`](../indicator/vp_ict_strategy_v1.pine).

## 1. The idea in one paragraph

Strategy V1 is a **top-down, two-timeframe** method. The **3-minute** chart is
used for **context**: a session Volume Profile tells us *where value is* and
which price levels institutions defend (POC, Value-Area edges, untested "naked"
POC). When price reaches one of those levels we have a **setup** and a
directional **bias**. We then drop to the **1-minute** chart to **time the
entry** with ICT price action — we wait for a **liquidity sweep**, a
**market-structure shift with displacement** (which leaves a Fair Value Gap),
and we enter on the **retrace into that gap**, in the direction of the 3m bias.
Volume Profile answers *where* and *which way*; ICT answers *exactly when*.

This pairs the two expert skills already in the repo
([`volume-profile`](../.claude/skills/volume-profile/SKILL.md) and
[`ict`](../.claude/skills/ict/SKILL.md)) — they describe the **same**
institutional zones from two angles, so an entry is only taken where they agree.

## 2. Why these two tools combine well

| Volume Profile (3m, "where") | ICT (1m, "when") |
| --- | --- |
| POC / HVN = acceptance, heavy trade | Order block (institutional zone) |
| LVN / single print = inefficiency | Fair Value Gap (imbalance to be filled) |
| VAH / VAL / naked POC = liquidity edges | Liquidity pool / draw on liquidity |
| VWAP / POC = fair value | Equilibrium of the dealing range |

The high-conviction play both skills point to is identical: **a liquidity sweep
at/near a Value-Area edge or POC, followed by a displacement/FVG back toward
value.** That is exactly what V1 automates.

## 3. Step 1 — The setup (3-minute Volume Profile)

On the 3m chart the indicator builds a **session-anchored** Volume Profile
(default RTH `09:30–16:00`, `America/New_York`) and derives:

- **POC** — highest-volume price row (fair value / magnet).
- **Value Area (VAH / VAL)** — the ~70% volume band around POC (canonical
  70% / two-rows-per-side / tie-break-upper algorithm).
- **HVN / LVN** — local volume peaks (acceptance) and valleys (rejection).
- **Naked POC** — the *prior* session's POC if price has not traded back through
  it yet (an untested magnet).

A **setup arms** when price comes within a tolerance (`ATR × tolAtrMult`, default
0.25 ATR) of a key level, setting a bias:

| Level reached | Bias | Rationale |
| --- | --- | --- |
| **VAL** (lower value edge) | **Long** | Mean-reversion / value-area rejection back toward POC. |
| **VAH** (upper value edge) | **Short** | Symmetric fade from the top of value. |
| **Naked POC** | Long/short toward the level | Untested POC acts as a magnet. |
| **POC** | Context tag only (no edge bias in V1) | Fair value; used for confluence/targets. |

The bias stays active for `setupBars` bars (default 120) — that is the window in
which a 1m entry sequence is allowed. If no entry triggers, the setup expires.

**Compressed-value-area filter.** A VAL/VAH setup is **skipped** when the POC sits
closer than `minPocEdgeAtr` ATR (default 1.25) to the edge being traded — a
compressed value area leaves almost no room from the edge to the POC target, so
the trade is not worth taking. (Naked-POC setups have no value-area-edge geometry
and are unaffected.) On the test window this lifted the win rate from ~44% to
~47%; note the benefit is mild and larger thresholds overfit this small sample.

> **Regime note (V1 scope).** V1 implements the **mean-reversion / value-edge
> fade** family (range/rotational behaviour). Trend-day continuation
> (VA/LVN breakout) is intentionally **out of scope for V1** and noted as a
> V2 candidate — see §7.

## 4. Step 2 — The entry (1-minute ICT)

While a 3m bias is armed and price sits at the level, the 1m logic runs the ICT
backbone. These four gates fire **in sequence** (not on one candle — ICT
describes an ordered manipulation→shift→entry move), in the bias direction:

1. **Liquidity sweep** — a wick beyond the most recent 1m swing that **closes
   back inside** (a stop raid; long needs a swept *low*, short a swept *high*).
   This *starts* the sequence and records the swept extreme.
2. **Market-structure shift (MSS)** — within `sweep_window` bars of the sweep, a
   candle **close** beyond the opposing minor swing (ICT-standard; a wick-only
   break is configurable via `useCloseForBreak`)…
3. **…with displacement → Fair Value Gap** — that same break leaves a 3-candle
   FVG (the only non-arbitrary displacement test). The FVG becomes the entry
   zone (the setup is now "armed").
4. **Entry on the retrace** — within `entry_window` bars, price pulls back
   **into the FVG** to at least the `oteMax` fraction (default 0.5 = "consequent
   encroachment", the 50% of the gap). That fill is the entry.

Each stage ages out independently (`sweep_window`, then `entry_window`), so a
sweep that never produces a displacement, or an armed FVG that never gets
retraced, is abandoned rather than left hanging.

> **Implementation parity.** Both the Pine indicator
> (`indicator/vp_ict_strategy_v1.pine`) and the Python backtest
> (`src/tradingbot/strategy/vp_ict_v1.py`) implement this as the **same
> sequential** state machine (`idle → swept → armed → entry`), so the chart and
> the bot agree. See [`docs/BACKTEST.md`](BACKTEST.md).

### Trade management (printed on the entry)

- **Entry:** the FVG retrace level.
- **Stop:** just beyond the swept extreme (`ATR × stopBuffAtr` buffer) — i.e.
  where "the sweep was real after all" would prove the idea wrong.
- **Exit target (`targetMode`):** with a single MNQ contract there is no scaling
  out, so one target is taken. **`POC`** (default) = back to fair value — the
  nearer, higher-win-rate target. **`opposite_edge`** = the opposite Value-Area
  edge (full rotation) — bigger winners, lower win rate. Both levels are computed
  and shown on the chart label regardless.
- **Breakeven stop (`breakevenAt`, default 0.5):** once price reaches 50% of the
  entry→target distance, the stop is moved to **breakeven (entry)**. This
  protects open profit on trades that run in your favour and then reverse (a
  winner that round-trips becomes a ~flat scratch instead of a full stop loss).
  The move is applied at bar close (no intrabar look-ahead). Set 0 to disable.

The setup is **invalidated** (arm state cleared) if price closes back beyond the
swept extreme before the retrace fills, or if the setup window expires.

### Selection filters (trade quality — raise win rate *and* profit)

The biggest gains come not from tuning a single knob (closer/further target just
trades win rate for average win) but from **only taking the better setups**. Two
skill-backed confluence filters, applied at the entry trigger:

- **VWAP premium/discount gate** (`useVwapPD`, **on**). VWAP is fair value /
  equilibrium (VP↔ICT mapping). Take **longs only at/below VWAP** (a discount)
  and **shorts only at/above VWAP** (a premium). On the test window this roughly
  **doubled net P&L (+$113 → +$208) and cut drawdown (−$259 → −$199)** while
  keeping a usable trade count (~11), win rate steady (~46%).
- **Killzone time filter** (`useKillzone`, **off** by default). Only enter inside
  the high-probability NY-AM window (≈09:30–11:30 ET, incl. the 10–11 Silver
  Bullet). It pushes win rate to ~60–67% and lowers drawdown further, but on a
  3-week sample it leaves only 3–5 trades — too few to trust, so it ships off and
  is enabled once more data is available.

These compose with the compressed-value-area filter above; all are configurable.

## 5. End-to-end example (long)

1. **3m:** price sells off into **VAL** within tolerance → **long bias armed**,
   "VAL" diamond prints below the bar.
2. **1m:** price wicks below a minor swing low and closes back above it →
   **sweep**. The next candle closes above the prior minor swing high → **MSS**,
   and it gaps (low > high[2]) → **FVG**.
3. **1m:** price retraces down into the FVG to its 50% → **ENTRY (long)** arrow
   prints with `SL` under the swept low and `TP` at POC / VAH.
4. Manual review on the chart, or (Phase 2) the `alert()` JSON fires to the bot.

## 6. Parameters (all tunable / backtestable)

| Input | Default | Meaning |
| --- | --- | --- |
| `vpSession` / `vpTz` | `0930-1600` / NY | Profile session window & timezone. |
| `vpRows` | 24 | Profile resolution (bin height — most impactful VP setting). |
| `vaPercent` | 0.70 | Value-Area target (0.68 = true 1σ; 0.80 for 80% rule). |
| `tolAtrMult` | 0.75 | How close to a level arms a setup (ATR-based). |
| `minPocEdgeAtr` | 1.25 | Skip VAL/VAH setups when POC is closer than this (ATR) to the edge (compressed VA). 0 disables. |
| `setupBars` | 120 | How long the bias stays active after a touch. |
| `pivotLen` | 4 | 1m swing lookback (confirms `pivotLen` bars later — repaint lag). Smaller ⇒ more swings ⇒ more sweeps ⇒ more trades. |
| `useCloseForBreak` | true | MSS needs a body close (vs wick). |
| `sweep_window` | 60 | Bars after a sweep to still accept the MSS+FVG. |
| `entry_window` | 60 | Bars after arming the FVG to still accept the retrace. |
| `oteMax` | 0.5 | Required retrace into the FVG before entering. |
| `stopBuffAtr` | 0.1 | Stop buffer beyond the swept extreme. |
| `useVwapPD` | true | VWAP premium/discount gate (long ≤ VWAP, short ≥ VWAP). |
| `useKillzone` | false | Restrict entries to the NY-AM killzone window. |
| `targetMode` | `POC` | Exit target: `POC` (win rate) or `opposite_edge` (profit). |
| `breakevenAt` | 0.5 | Move stop to entry once price reaches this fraction of the target. 0 disables. |

Every default is a **convention, not a validated constant** (both skills flag
this) — they exist to be tuned and, in Phase 2, backtested.

## 7. Known limitations / honest caveats

- **OHLCV profile is a model, not tick truth.** Volume-at-price is approximated
  by distributing each bar's volume across its high–low range (no tick data on a
  chart). POC/VA are therefore approximations of a platform/footprint profile.
- **Pivots lag.** 1m swings confirm `pivotLen` bars after the fact; the indicator
  never acts on an unconfirmed pivot, but this means entries are detected with
  that inherent delay (documented, not a bug).
- **Single-symbol, single timeframe per chart.** You apply the script to the 3m
  chart for context and to the 1m chart for entries; the session anchor keeps the
  POC/VA aligned between them without cross-timeframe `request.security`.
- **V1 is mean-reversion only.** Trend-day continuation, SMT divergence, killzone
  time-gating, and HTF bias confirmation are deliberately deferred to V2.
- **Decision support, not auto-execution.** It marks setups/entries and emits
  alerts; acting on them is Phase 2's job.

## 8. How we validate it (ties into `docs/TESTING.md`)

1. **Visual, 3m:** confirm POC/VAH/VAL match TradingView's native Volume Profile
   on the same session; check the Data Window values.
2. **Visual, 1m:** step through **Bar Replay** and confirm sweep→MSS→FVG→entry
   fires on the right candles and does **not repaint** past entries.
3. **Backtest:** wrap the signal logic in a `strategy()` (Strategy Tester) to get
   win rate / drawdown / trade count across history and across symbols.
4. **Python parity (Phase 2):** the vectorized port in `src/tradingbot/` is
   checked against known values so the bot and the indicator agree.
