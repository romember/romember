# Trading Ruleset Agent

An AI agent that screens common stocks against a fixed **pre-trade checklist**.
The system objective is to capitalize on single-stock growth catalysts while
strictly eliminating total-portfolio wipeout risk: **zero leverage, zero
options, no penny stocks.**

It combines two layers:

1. **Deterministic checks** — the numeric guardrails (penny-stock filter,
   no-chasing rule, support-floor proximity, catalyst window, revenue floor,
   position sizing) evaluated directly from market data.
2. **Claude qualitative layer** — the genuine judgment calls (macro tailwind,
   valuation-floor narrative, extra catalyst ideas, risk flags) assessed by
   `claude-opus-5`. This layer is optional and degrades gracefully.

Each ticker gets a checklist, a **GO / REVIEW / NO-GO** decision, and a filled
trade-execution template.

> This is a rules-screening tool, **not financial advice**. It automates a
> discipline checklist; it does not decide what you should buy. Verify every
> figure before trading.

---

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Offline demo (no network needed) — uses the bundled JSON snapshot:
python -m trading_agent --no-ai --from-json examples/sample_stocks.json GOODCO PARABOLIC CRYPTOX

# Live data via Yahoo Finance (needs outbound network to the finance hosts):
python -m trading_agent AAPL NVDA

# With account rules + the AI layer:
export ANTHROPIC_API_KEY=sk-ant-...
python -m trading_agent --config config.yaml AAPL
```

### Network note

The AI layer talks to the Anthropic API; the default data layer talks to Yahoo
Finance. Some restricted/sandboxed networks block the finance hosts by policy —
in that case use `--from-json` with a snapshot (see below), or point the data
layer at a provider your network allows. The rule logic is identical either way.

---

## How the ruleset maps to code

| Checklist rule | Where | Type |
|---|---|---|
| Equity-only / no crypto / no funds | `check_asset_instrument` | deterministic |
| No penny stocks | `check_not_penny` | deterministic |
| 100% cash / no margin | `check_leverage` | manual confirmation |
| Loss tolerance (max gap-down) | `check_loss_tolerance` | deterministic when sized |
| Identifiable catalyst (1–3 months) | `check_catalyst` | deterministic (earnings) + AI ideas |
| Macro tailwind | `check_macro_tailwind` → AI | qualitative (Claude) |
| Company baseline / real operations | `check_company_baseline` | deterministic + AI |
| No-chasing rule (< 20% / week) | `check_no_chasing` | deterministic |
| Support floor (within 5–10%) | `check_support_floor` | deterministic |

Thresholds (penny price, chasing %, support band, catalyst window, gap-down
assumption, position sizing, graduation target) all live in
[`config.example.yaml`](config.example.yaml) and are overridable per run.

### Decision logic

- Any **hard-rule FAIL** (wrong asset class, penny stock, chasing a parabolic
  move, over-sized position) → **NO-GO**.
- No fails but open judgment/confirmation items → **REVIEW**.
- Everything satisfied → **GO**.

The process exits non-zero if any ticker is NO-GO, so it composes into scripts.

---

## Architecture

```
providers.py   data in  ──►  YFinanceProvider (live)  |  JSONProvider (offline/tests)
checks.py      rules    ──►  one function per checklist item -> CheckResult
ai.py          judgment ──►  Claude structured-output assessment (optional)
agent.py       orchestrate ─►  fetch -> checks -> merge AI -> Verdict -> report
cli.py         interface ──►  python -m trading_agent ...
```

Technical indicators (`compute_technicals`) are pure Python, so both providers
and the test suite exercise the same logic.

### Swapping the data source

`JSONProvider` reads a snapshot like [`examples/sample_stocks.json`](examples/sample_stocks.json).
Each record may supply computed fields directly, or a `closes` (and optional
`lows`) price series to have the technicals derived. To wire up a different live
API (Alpha Vantage, Polygon, FMP, …), implement `DataProvider.fetch(ticker)`
returning a populated `StockData` — nothing else changes.

---

## CLI reference

```
python -m trading_agent [TICKERS...] [options]

  --from-json PATH   Read a JSON snapshot instead of live data (offline mode)
  --config PATH      YAML config with account rules / thresholds
  --no-ai            Disable the Claude qualitative layer
  --json             Emit machine-readable JSON instead of the text report
  --period P         yfinance history window (default: 3mo)
```

---

## Development

```bash
pip install pytest
python -m pytest -q        # 16 offline tests covering the rule logic
```

The tests run entirely on synthetic data, so the checklist logic is verifiable
even where the live market-data hosts are unreachable.

---

## Post-trade discipline (baked into every report)

- Sell 100% on the catalyst/target — don't hold through the cool-off.
- Exit immediately if the thesis breaks or price closes below support; never
  average down.
- Stay off social-media hype threads while holding.
- **Graduation rule:** at your capital milestone, move 70% of profits into
  broad-market index funds (VTI/VOO).
