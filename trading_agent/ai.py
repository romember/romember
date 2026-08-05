"""Claude-powered qualitative assessment.

Two of the checklist rules are genuine judgment calls that no market-data field
answers cleanly:

* Macro Tailwind — does the industry ride a broader economic/technological trend?
* Company Baseline narrative — is there a real valuation floor?

This module asks Claude to reason about those from the company's sector,
industry, and business summary, and returns a structured verdict the agent
merges back into the checklist. It degrades gracefully: if the ``anthropic``
package or credentials are missing, ``assess`` returns ``None`` and the agent
falls back to the MANUAL placeholders.
"""

from __future__ import annotations

import json
from typing import Optional

from .config import Config
from .models import StockData

# JSON schema the model must fill. Structured outputs guarantee it parses.
_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "macro_tailwind": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "verdict": {"type": "string", "enum": ["yes", "no", "unclear"]},
                "trend": {"type": "string"},
                "rationale": {"type": "string"},
            },
            "required": ["verdict", "trend", "rationale"],
        },
        "company_baseline": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "has_floor": {"type": "boolean"},
                "rationale": {"type": "string"},
            },
            "required": ["has_floor", "rationale"],
        },
        "catalyst_ideas": {
            "type": "array",
            "items": {"type": "string"},
        },
        "risk_flags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": [
        "macro_tailwind",
        "company_baseline",
        "catalyst_ideas",
        "risk_flags",
        "summary",
    ],
}

_SYSTEM = (
    "You are a disciplined swing-trading analyst applying a fixed pre-trade "
    "checklist. You capitalize on single-stock catalysts while strictly avoiding "
    "wipeout risk. Judge only what the data supports; when uncertain, say so. "
    "You are not giving personalized financial advice — you are scoring a stock "
    "against mechanical rules. Be concise and specific."
)


def _prompt(data: StockData) -> str:
    lines = [
        f"Ticker: {data.ticker}",
        f"Name: {data.name or 'unknown'}",
        f"Sector: {data.sector or 'unknown'}",
        f"Industry: {data.industry or 'unknown'}",
    ]
    if data.market_cap:
        lines.append(f"Market cap: ${data.market_cap:,.0f}")
    if data.total_revenue:
        lines.append(f"Revenue (ttm): ${data.total_revenue:,.0f}")
    if data.next_earnings_date:
        lines.append(
            f"Next earnings: {data.next_earnings_date} "
            f"({data.days_to_earnings} days out)"
        )
    if data.description:
        lines.append(f"Business summary: {data.description[:1500]}")
    lines.append(
        "\nAssess: (1) macro_tailwind — does this industry benefit from a broader "
        "economic or technological trend right now? (2) company_baseline — is there "
        "a real valuation floor (revenue, strategic assets, real operations)? "
        "(3) catalyst_ideas — specific events in the next 1-3 months beyond earnings. "
        "(4) risk_flags — anything that would violate a no-wipeout discipline."
    )
    return "\n".join(lines)


def assess(data: StockData, cfg: Config) -> Optional[dict]:
    """Return the structured assessment, or ``None`` if AI is unavailable."""
    if not cfg.ai_enabled:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    try:
        client = anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY / profile
    except Exception:  # noqa: BLE001 - missing credentials, etc.
        return None

    try:
        response = client.messages.create(
            model=cfg.ai_model,
            max_tokens=4096,
            system=_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content": _prompt(data)}],
        )
    except Exception as exc:  # noqa: BLE001 - network/auth/rate errors
        return {"_error": f"AI assessment failed: {exc}"}

    if getattr(response, "stop_reason", None) == "refusal":
        return {"_error": "AI assessment refused by safety classifier."}

    try:
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"Could not parse AI response: {exc}"}
