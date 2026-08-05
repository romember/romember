#!/usr/bin/env bash
# One-command runner for the trading ruleset agent.
#
#   ./run.sh                      -> offline demo (no keys, no network)
#   ./run.sh AAPL NVDA            -> screen live tickers via Yahoo Finance
#   ./run.sh --config config.yaml AAPL
#   ./run.sh --provider alphavantage AAPL
#
# On first run it creates a virtualenv in .venv and installs dependencies.
# Set ANTHROPIC_API_KEY to enable the Claude qualitative layer.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
VENV=".venv"

if [ ! -d "$VENV" ]; then
  echo "[setup] creating virtualenv in $VENV ..."
  "$PY" -m venv "$VENV"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  echo "[setup] installing dependencies ..."
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
else
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

if [ "$#" -eq 0 ]; then
  echo "[demo] no tickers given — running the offline sample screen."
  echo "       (pass ticker symbols to screen live data, e.g. ./run.sh AAPL)"
  echo
  exec python -m trading_agent --no-ai --from-json examples/sample_stocks.json GOODCO PARABOLIC CRYPTOX
fi

exec python -m trading_agent "$@"
