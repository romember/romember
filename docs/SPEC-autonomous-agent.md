# Autonomous Trading Agent — Stage 1 Spec (DRAFT, awaiting approval)

Status: **Gate 1 of 6 — Spec.** Nothing in this document has been built. No
strategy here has been tested. Every number marked *(verify)* is from
documentation as remembered and must be confirmed against the broker's current
docs before code depends on it. No backtest or performance number appears
anywhere in this document, because none has been run yet.

Phases (each needs your approval before the next starts):
**1. Spec** → 2. Architecture → 3. Plan → 4. Test-first build → 5. Review → 6. Ship (paper only).

> About "AgenKit": the prompt asks to work inside the AgenKit harness
> (agenkit.xyz). I have not verified what that tool is or does, so this project
> follows the same six phases by hand: written spec, written architecture,
> written plan, tests before code, review, then ship. Nothing depends on it.

---

## 0. The short version (plain English)

- **What exists today:** a stock *checker*. You give it a ticker, it checks the
  stock against your rules and says GO / REVIEW / NO-GO. It never trades.
- **What this spec proposes:** a robot that runs all the time, watches US stocks
  and crypto, looks for trade setups, tests them against hard safety limits,
  and places **fake-money (paper) trades** at Interactive Brokers.
- **What it will NOT do:** use borrowed money, short anything, trade options or
  futures, or touch real money. Real money stays physically disabled in code.
- **The likely honest outcome:** most candidate strategies will fail testing.
  That is the system working, not breaking. If nothing passes, the robot runs
  a "do nothing / benchmark only" mode and we say so.

---

## 1. Your decisions so far

| Question | Your answer | Consequence |
|---|---|---|
| Market | Stocks **and** crypto | Crypto trades 24/7; stocks only in market hours. Two schedules, one risk budget. |
| Broker | Interactive Brokers (IBKR) | Powerful, but its API needs a desktop/gateway app running at all times (see §3). |
| Money | Paper trading only | Fees and fills are simulated, and paper fills are kinder than real ones (see §9). |
| Deliverable | This spec in the repo | — |

### Rule conflicts with the current checklist (need your sign-off)

The existing tool's rules (see `README.md`) say: *zero leverage, zero options,
no penny stocks, equity only — no crypto, no funds.* Choosing "stocks and
crypto" breaks the **no crypto** rule. Proposal:

1. **Drop "no crypto"** for the autonomous agent only, limited to spot coins
   with deep markets (BTC, ETH to start). The existing checker keeps its rules.
2. **Keep** zero leverage, zero options, no futures, no shorting, no penny
   stocks. All trades are buy-then-sell with cash.
3. **Decide on funds:** the checklist bans funds, but the best benchmark and
   the cheapest trend-following instrument are broad ETFs (SPY, QQQ), and your
   own graduation rule moves profits into VTI/VOO. Proposal: allow a short
   allow-list of broad index ETFs. (Open decision D2.)

---

## 2. Market and venue

### 2.1 Asset classes

| | US stocks / ETFs | Crypto (spot) |
|---|---|---|
| Hours | Regular session 9:30–16:00 ET weekdays; no trading on market holidays. Extended hours exist but the agent stays out of them (thin, wide spreads). | 24/7 *(verify for IBKR paper)* |
| Universe (start) | Large, liquid US names + allow-listed ETFs (decision D2). Price ≥ $5 (existing penny rule), avg daily dollar volume ≥ $50M. | BTC, ETH only. |
| Direction | Long only, cash only | Long only, cash only |

### 2.2 Interactive Brokers facts the design depends on (all *verify*)

| Topic | What we expect | Why it matters |
|---|---|---|
| API access | Through **TWS** or **IB Gateway**, a Java app that must be running and logged in. Python client: `ib_async` (successor to `ib_insync`). Default paper ports: TWS 7497, Gateway 4002. Live ports: 7496 / 4001. | The agent can only refuse live trading reliably if it refuses live ports. |
| Session resets | Gateway/TWS restarts daily and needs a fresh login with 2-factor auth about weekly. Tools like IBC automate the restart, not the 2FA. | **Biggest 24/7 weak spot.** The robot will go blind at least once a day and needs a human weekly. |
| Rate limits | ~50 API messages/second; historical-data "pacing" limits (on the order of 60 requests per 10 minutes, and no identical request within 15 s). | Can't scan hundreds of stocks by hammering history requests; must stream and cache. |
| Market data | Real-time data needs paid subscriptions on a live account; paper accounts share the live account's subscriptions. Without them, data is delayed ~15 min. | Delayed data + a fast strategy = guaranteed fake results. Strategy speed must match data speed. |
| Stock commissions | IBKR Pro "Fixed": ~$0.005/share, $1.00 minimum, capped at 1% of trade value. | Small orders pay the $1 minimum — hurts small trades. |
| Crypto | Executed via partners (Paxos / Zero Hash). Commission ~0.12–0.18% of trade value with a ~$1.75 minimum. Cash only, no shorting. | The $1.75 floor means orders under ~$1,000 pay more than 0.18%. Paper support for crypto must be confirmed. |
| Min order size | Stocks: 1 share (fractional exists, API support limited). Crypto: small dollar minimum *(verify)*. | Sets the smallest test size. |
| Pattern-day-trader rule | Margin accounts under $25k are limited to 3 day trades per 5 days. Cash accounts avoid it but must wait for settlement. | Rules out fast stock strategies if this ever goes live under $25k. |

### 2.3 Data sources

| Source | Use | Limit found today |
|---|---|---|
| IBKR market data | Live signals and execution | See pacing limits above. |
| Alpha Vantage (connected) | Historical research, delisted-stock list (`LISTING_STATUS`) | **Free key: 25 requests/day, 1/second** (hit while writing this spec). Fine for research, useless for 24/7 operation. |
| Already in repo | `yfinance`, Alpha Vantage, JSON snapshots | yfinance is unofficial and can break without notice. |

Stock research **must** include delisted names, or every backtest is biased
toward winners (survivorship bias, see §7).

---

## 3. Current regime (real data, pulled 2026-10-17)

Source: Alpha Vantage daily closes. SPY = last 100 trading days to 2026-10-16.
BTC = last ~726 days to 2026-10-17 (the 10-17 bar is a partial day).

| | SPY | BTC/USD |
|---|---|---|
| Last close | 763.25 | 81,545 |
| vs 20-day avg | below (771.18) | below (83,412) |
| vs 50-day avg | below (768.50) | just above (81,324) |
| vs 100-day avg | above (757.62) | above (74,022) |
| 20-day return | +0.2% | −3.5% |
| 100-day return | +1.7% | +27.2% |
| 1-year return | n/a (only 100 days pulled) | −23.4% (1-yr high 114,548) |
| Off 100-day high | −2.0% | −5.8% |
| Realized volatility (annualized) | 20d 10.5%, 60d 10.9% | 20d 25.7%, 60d 43.6%, 1y 44.2% |

**Plain reading:**
- **Stocks:** calm and drifting sideways near highs. Low volatility. Trend
  signals will be weak and choppy; this is the kind of market where trend
  systems bleed small losses.
- **Bitcoin:** still well below last year's high, recovered strongly over the
  summer, now pausing. Volatility has cooled from ~44% to ~26%. Mixed trend.

**Not yet covered:** funding rates and open interest only exist for crypto
*futures*, which we are not trading. They could be read as a sentiment signal
from an outside data source, but that adds a dependency; deferred (D5).
Macro event calendar (Fed meetings, CPI, jobs report) needs a data source;
Alpha Vantage has an earnings calendar but not an economic one (D6).

### 3.1 When the agent trades vs. stays out (proposal)

Stay flat / no new entries when **any** of these is true:
- Data is stale (stocks: no tick for 60 s in session; crypto: 30 s) or the
  broker connection is down.
- Within 30 min of a scheduled high-impact macro release (once calendar exists).
- Stock: within 2 trading days before that company's earnings (unless the
  strategy *is* an earnings strategy).
- Spread wider than a per-asset limit (e.g. > 0.10% for large caps, > 0.05% BTC).
- Realized 20-day vol above 2× its 1-year median (a "storm" filter).
- Daily-loss or drawdown limit hit (§6).

---

## 4. Candidate strategies (hypotheses only — none tested)

Rule: each must be explainable in one sentence and must say **who loses money
to us**. Simple first. All long-only, cash only.

| # | Name | Edge in one sentence | Who is on the other side | Market | Timeframe |
|---|---|---|---|---|---|
| B | **Benchmark: buy & hold** | None — this is the bar to beat. | — | SPY, BTC | — |
| 1 | Trend filter | Prices that are above their long-term average tend to keep drifting because investors under-react and then pile in. | Late sellers and early profit-takers | SPY/QQQ, BTC, ETH | Daily, holds weeks–months |
| 2 | Vol-targeted trend | Same as #1 but position size shrinks when markets get wild, which historically cuts the worst drops. | Same as #1 | BTC, ETH, SPY | Daily |
| 3 | Short-term dip-buy in uptrends | Large stocks that drop sharply for 2–3 days while still in a long-term uptrend tend to bounce, because forced/impatient sellers pay for quick exits. | Impatient sellers, liquidity takers | Large-cap stocks | Daily, holds 2–7 days |
| 4 | Cross-sectional momentum | The stocks that rose most over the past 12 months (skipping the last month) tend to keep beating the laggards. | Investors who anchor on old prices | Large-cap universe | Monthly rebalance |
| 5 | Post-earnings drift | Stocks that beat earnings by a lot tend to keep drifting up for weeks, because the market digests surprises slowly. | Slow-to-update holders | Stocks with earnings | Event, holds 20–60 days |
| 6 | **Your current checklist as a strategy** | Buy only names your existing GO rules pass; sell at target/support break. | Whoever sells into catalysts | Stocks | Weeks |

Detailed rules (entry, exit, stop, holding period, expected trade count) for
each go into the **Plan** phase. Draft defaults:

- **#1** Enter when daily close > 200-day average; exit when close < 200-day
  average. No separate stop (the exit *is* the stop). Few trades per year
  per asset.
- **#2** Hold #1's signal, sized to target 10–15% annualized volatility.
- **#3** Enter when close > 200-day average AND 2-day RSI < 10 (or 3 straight
  down days); exit on close > 5-day average or after 7 days; stop at −8%.
  Dozens of trades per year per name.
- **#4** Monthly: rank universe by 12-1 month return, hold top decile equally
  weighted subject to position caps.
- **#5** Enter day after earnings if surprise > threshold and gap up; exit at
  60 days or on close below the gap day's low.
- **#6** Re-use `trading_agent/checks.py` as the entry filter.

**Honest priors** (to be confirmed or killed by testing, not trusted):
#3 and #5 are widely known and have weakened over time. #4 and #3 need a
survivorship-free stock history to test fairly. #1/#2 on crypto have only a
short, regime-changing history. #6 has the fewest historical trades to judge.

Signals and execution are separate code: a strategy only emits *"I want X%
of equity in asset Y"*. It never places orders.

---

## 5. Data and validation rules

1. **No future leakage.** A signal on day *t* uses data up to the close of
   *t* and trades at the open (or next bar) of *t+1*. Tested by a unit test
   that shuffles future bars and confirms signals don't change.
2. **Realistic costs:** IBKR commission model (§2.2) + spread + slippage
   (start at 0.05% stocks, 0.10% crypto per side; then stress at 2× and 3×).
3. **Time-ordered splits, never random:** walk-forward (train on years 1–N,
   test on N+1, roll). **The most recent 12 months are locked away** and used
   once, at the end, for the final verdict.
4. **Parameter neighborhoods:** sweep nearby values (e.g. 150/200/250-day
   averages). If only one exact setting works, the strategy is rejected.
5. **Report for every candidate:** Sharpe, max drawdown, win rate, profit
   factor, number of trades, turnover, cost sensitivity.
6. **Count every variant tried.** Results are judged with a multiple-testing
   adjustment (deflated Sharpe ratio), because if you try 100 variants, a few
   will look great by luck.
7. **Survivorship:** stock universe rebuilt as of each historical date,
   including companies that later delisted.

### Pass bar to reach paper trading (proposal)

A strategy must pass **all** of:
- Out-of-sample Sharpe ≥ 0.5 **after** costs, and better risk-adjusted than buy-and-hold on the same asset.
- Max drawdown ≤ 1.5× buy-and-hold's over the same window, or ≤ 25%, whichever is smaller.
- Still profitable at 2× costs.
- ≥ 100 out-of-sample trades **or** (for slow strategies) ≥ 10 years of history.
- Neighboring parameters also pass.
- Deflated Sharpe probability ≥ 0.95.

---

## 6. Execution and risk (enforced in code, not by any AI)

The Claude layer already in the repo can **advise** but can never send,
size, or approve an order. Risk checks run in a separate module that every
order must pass, and that module has its own tests.

| Limit | Proposed value (paper) |
|---|---|
| Max single stock position | 10% of equity |
| Max total crypto exposure | 25% of equity |
| Max gross exposure | 100% (cash only, no leverage, ever) |
| Max daily loss | 2% of equity → no new entries until next day |
| Max drawdown from peak | 10% → **kill switch**, flatten, stop, wait for you |
| Sizing | Volatility targeting, or ¼ Kelly at most. Never full Kelly. |
| Stale data | No new orders if data older than §3.1 thresholds |
| API errors | 5 errors in 5 minutes → halt new orders, alert |
| Order sanity | Reject any order > 2% away from last price, or > position cap |
| Live trading | Refuses live ports. Unlocking needs a config flag **and** an env var **and** a typed confirmation. Not part of this project. |

**Kill switch:** one command (and one file-based trigger the watchdog checks)
cancels all open orders and flattens all positions.

**Journal:** every decision is written to an append-only SQLite log: time,
inputs (prices, signal values), output (target position), risk-check result,
order sent, fill received.

---

## 7. Bear case (how each part could be fooling us)

| Risk | How it fools us | Defense |
|---|---|---|
| Overfitting | Tune until the past looks great | Neighborhood test, locked hold-out, trial counting |
| Look-ahead bias | Use a close price we couldn't know yet | Next-bar execution + shuffle test |
| Survivorship bias | Only test today's winners | Point-in-time universe incl. delisted |
| Costs | Fast strategies die after fees | 2×/3× cost stress, min trade size vs $1/$1.75 minimums |
| Regime dependence | Works in 2020–21 bull only | Report results by year and by regime |
| Crowding | Everyone runs the same trend/momentum | Accept lower Sharpe; don't size up after wins |
| Liquidity traps | Can't exit in a crash | Universe liquidity floor, position caps |
| Infra single points | Gateway restart, 2FA, one server, one data feed | Watchdog, heartbeat alerts, flat-on-disconnect rule (§9) |

**Automatic live-failure triggers (per strategy, during paper trading):**
- Drawdown exceeds 1.5× worst out-of-sample drawdown → strategy disabled.
- Rolling 60-trade (or 6-month) results fall below the 5th percentile of the
  backtest's distribution → disabled.
- Average real slippage > 2× the assumed slippage → disabled.

---

## 8. Output plan for later gates

When strategies have been tested, the report will contain: a system overview,
a comparison table (Strategy, Edge, Market, Timeframe, Sharpe, Max Drawdown,
Trades, Cost Sensitivity, Verdict) with **real** numbers, per-strategy rules,
validation results, sizing, risk limits, kill criteria, monitoring metrics,
and the build plan.

**Proposed repo layout** (Architecture gate will refine):

```
trading_agent/            existing checker (unchanged)
autotrader/
  data/        historical loaders, live IBKR stream, cache
  strategies/  one file per candidate, pure functions -> target weights
  backtest/    event loop, cost model, walk-forward, metrics, trial log
  risk/        limits, kill switch (no strategy imports allowed)
  broker/      IBKR adapter (paper-only guard), simulated broker for tests
  journal/     SQLite decision log
  runner.py    scheduler: stock session + 24/7 crypto loop, watchdog
tests/autotrader/
```

**First module to build (proposal):** `risk/` with its tests — it is the part
that must be right before anything else is allowed to send an order, and it
needs no market data.

Command to start paper trading (target, not yet real):
`python -m autotrader.runner --paper --config autotrader.yaml`

---

## 9. HOW COULD THIS SYSTEM FAIL? (first pass)

- **Nothing passes testing.** Likely for several candidates. Then the right
  answer is to run benchmark-only and stop, not to loosen the pass bar.
- **Weakest assumption:** that a 200-day trend or dip-buy edge still exists
  after costs in 2026. These are famous; famous edges get competed away.
- **Paper ≠ real.** IBKR paper fills are simulated and often better than real
  ones (no queue position, no partial fills, optimistic prices). A strategy
  that barely passes on paper will likely lose live.
- **The gateway goes down at 3 a.m.** while holding crypto during a crash.
  Rule: if disconnected for > 5 minutes, the watchdog alerts; on reconnect,
  positions are reconciled with the broker before any new order.
  Weekly 2FA means the system is not truly unattended.
- **Data feed lies** (bad tick, stale quote, split not adjusted). Sanity
  filters on every price; reject moves > N× recent volatility until confirmed.
- **A bug sends a giant order.** Order-sanity checks in `risk/`, independent
  tests, and a max-notional cap per order.
- **Higher costs:** if real slippage is 3× the estimate, short-holding
  strategies (#3) die first. Slow ones (#1, #4) survive best.
- **Already arbitraged away?** Probably partly, for all six. The benchmark
  comparison is there to catch that.
- **The human gets bored and turns limits off.** Changing a risk limit
  requires editing a committed config file; the journal records the change.

Survival beats an impressive backtest.

---

## 10. Open decisions for you (needed to pass Gate 1)

| # | Decision | Recommendation |
|---|---|---|
| D1 | Drop "no crypto" for the agent only, spot BTC/ETH only? | Yes |
| D2 | Allow a short allow-list of broad index ETFs (SPY, QQQ, VTI)? | Yes |
| D3 | Do you have (or will you open) an IBKR account? Paper trading needs one, and real-time data needs paid subscriptions. | Needed before Build |
| D4 | Where will it run 24/7? (Your PC, a home server, a cloud VM.) This cloud session is temporary and can't run it. | Small cloud VM |
| D5 | Use crypto futures funding/open-interest as a sentiment input? | No, not at first |
| D6 | Pay for / pick an economic-calendar data source? | Defer; hard-code Fed/CPI dates at first |
| D7 | Accept the risk limits in §6 as starting values? | Yes, tune later only with a logged reason |
| D8 | Accept the pass bar in §5? | Yes |

Reply with approval (or changes) and the next gate is **Architecture**.
