"""Core data structures shared across the agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class Status(str, Enum):
    """Outcome of a single checklist item."""

    PASS = "PASS"        # rule satisfied
    FAIL = "FAIL"        # rule violated — a hard blocker
    WARN = "WARN"        # borderline / caution, does not block on its own
    MANUAL = "MANUAL"    # requires human judgment or missing account inputs
    UNKNOWN = "UNKNOWN"  # data unavailable, could not evaluate

    @property
    def symbol(self) -> str:
        return {
            Status.PASS: "[x]",
            Status.FAIL: "[!]",
            Status.WARN: "[~]",
            Status.MANUAL: "[ ]",
            Status.UNKNOWN: "[?]",
        }[self]


@dataclass
class StockData:
    """Normalized snapshot of a single ticker.

    Providers are responsible for populating whatever they can and appending a
    note to ``warnings`` for anything they could not resolve. Every field is
    optional so a partial fetch still yields a usable (if incomplete) screen.
    """

    ticker: str
    name: Optional[str] = None
    quote_type: Optional[str] = None           # e.g. "EQUITY", "ETF", "CRYPTOCURRENCY"
    price: Optional[float] = None
    currency: Optional[str] = None

    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None

    market_cap: Optional[float] = None
    total_revenue: Optional[float] = None
    trailing_pe: Optional[float] = None

    # Technicals (computed from price history)
    week_return_pct: Optional[float] = None     # ~5 trading-day % change
    support_level: Optional[float] = None       # recent swing-low support
    pct_above_support: Optional[float] = None    # (price - support) / support * 100
    ma50: Optional[float] = None

    # Catalyst
    next_earnings_date: Optional[date] = None
    days_to_earnings: Optional[int] = None

    fetched_at: datetime = field(default_factory=datetime.utcnow)
    source: str = "unknown"
    warnings: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """Result of evaluating one rule from the pre-trade checklist."""

    id: str
    phase: str
    title: str
    status: Status
    detail: str
    ai_backed: bool = False


@dataclass
class Verdict:
    """Aggregate decision for a ticker."""

    ticker: str
    decision: str                       # "GO" | "NO-GO" | "REVIEW"
    reasons: list[str]
    checks: list[CheckResult]
    data: StockData
    ai_assessment: Optional[dict] = None

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.checks:
            out[c.status.value] = out.get(c.status.value, 0) + 1
        return out
