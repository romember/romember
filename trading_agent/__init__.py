"""Trading Ruleset Agent.

An AI agent that screens common stocks against a fixed pre-trade checklist:
capitalize on single-stock growth catalysts while eliminating total-portfolio
wipeout risks (no leverage, no options, no penny stocks).

The ruleset is encoded as deterministic checks (from market data) plus
Claude-powered qualitative judgments (macro tailwind, catalyst narrative).
"""

from .models import CheckResult, Status, StockData, Verdict

__version__ = "1.0.0"

__all__ = ["CheckResult", "Status", "StockData", "Verdict", "__version__"]
