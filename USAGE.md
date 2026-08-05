# Usage

A quick reference for running the trading ruleset agent. Full detail is in
[README.md](README.md).

## Fastest path (one command)

```bash
git clone https://github.com/romember/romember.git
cd romember
./run.sh                 # first run sets up everything, then prints a demo screen
```

`run.sh` creates the virtualenv, installs dependencies on first use, and then
runs the agent. With no arguments it runs the offline sample screen (no API key,
no network). Pass tickers to screen live data:

```bash
./run.sh AAPL NVDA
```

## Manual setup (if you prefer)

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m trading_agent AAPL
```

## Common commands

| Goal | Command |
|---|---|
| Offline demo (no keys/network) | `./run.sh` |
| Screen a live ticker (Yahoo Finance) | `./run.sh AAPL` |
| Enable the Claude judgment layer | `export ANTHROPIC_API_KEY=sk-ant-... ; ./run.sh AAPL` |
| Use Alpha Vantage instead of Yahoo | `export ALPHAVANTAGE_API_KEY=key ; ./run.sh --provider alphavantage AAPL` |
| Apply your account rules | `cp config.example.yaml config.yaml` then `./run.sh --config config.yaml AAPL` |
| Machine-readable output | `./run.sh --json AAPL` |
| Offline / restricted network | `./run.sh --from-json examples/sample_stocks.json AAPL` |

## Reading the output

Each ticker prints its checklist grouped by phase, then a verdict and a
pre-filled trade/exit plan.

| Mark | Meaning |
|---|---|
| `[x]` | rule satisfied |
| `[!]` | hard fail — blocks the trade (NO-GO) |
| `[~]` | caution — does not block on its own |
| `[ ]` | needs your confirmation / account input |
| `[?]` | data unavailable, could not evaluate |

**Decision:** any `[!]` → **NO-GO**; open `[ ]`/`[~]`/`[?]` items → **REVIEW**;
everything satisfied → **GO**. The process exits non-zero on any NO-GO.

## Notes

- The machine you run on needs outbound access to the data host (Yahoo or
  Alpha Vantage). If your network blocks them, use `--from-json`.
- This is a rules-screening tool, **not financial advice** — it checks a stock
  against your rules; it does not decide what to buy.
