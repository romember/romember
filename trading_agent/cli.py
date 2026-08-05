"""Command-line interface for the trading ruleset agent.

Examples
--------
    # Live data via Yahoo Finance (needs network access to the finance hosts):
    python -m trading_agent AAPL NVDA

    # Offline / restricted networks — screen from a JSON snapshot:
    python -m trading_agent --from-json examples/sample_stocks.json AAPL

    # With account rules + thresholds:
    python -m trading_agent --config config.yaml AAPL

    # Skip the AI layer (pure deterministic checks):
    python -m trading_agent --no-ai AAPL

    # Machine-readable output:
    python -m trading_agent --json AAPL
"""

from __future__ import annotations

import argparse
import json
import sys

from .agent import TradingAgent, render_report
from .config import Config
from .models import Status
from .providers import JSONProvider, YFinanceProvider


def _verdict_to_dict(v) -> dict:
    return {
        "ticker": v.ticker,
        "decision": v.decision,
        "reasons": v.reasons,
        "counts": v.counts,
        "checks": [
            {
                "id": c.id,
                "phase": c.phase,
                "title": c.title,
                "status": c.status.value,
                "detail": c.detail,
                "ai_backed": c.ai_backed,
            }
            for c in v.checks
        ],
        "ai_assessment": v.ai_assessment,
        "price": v.data.price,
        "source": v.data.source,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trading_agent",
        description="Screen common stocks against the pre-trade checklist.",
    )
    p.add_argument("tickers", nargs="+", help="One or more ticker symbols.")
    p.add_argument("--config", help="Path to a YAML config file.")
    p.add_argument(
        "--from-json",
        metavar="PATH",
        help="Read a JSON snapshot instead of live data (offline mode).",
    )
    p.add_argument(
        "--no-ai", action="store_true", help="Disable the Claude qualitative layer."
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of a report.")
    p.add_argument(
        "--period", default="3mo", help="yfinance history window (default: 3mo)."
    )
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    cfg = Config.load(args.config)
    if args.no_ai:
        cfg.ai_enabled = False

    if args.from_json:
        provider = JSONProvider.from_file(args.from_json)
    else:
        provider = YFinanceProvider(period=args.period)

    agent = TradingAgent(provider, cfg)

    verdicts = []
    for ticker in args.tickers:
        try:
            verdicts.append(agent.screen(ticker))
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {ticker}: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps([_verdict_to_dict(v) for v in verdicts], indent=2, default=str))
    else:
        for v in verdicts:
            print(render_report(v, cfg))
            print()

    # Exit code: 0 if no hard NO-GO, 1 if any ticker failed a hard rule.
    return 1 if any(v.decision == "NO-GO" for v in verdicts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
