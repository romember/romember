"""The agent: gather data -> run rule checks -> enrich with AI -> verdict."""

from __future__ import annotations

from typing import Optional

from . import ai as ai_module
from . import checks as checks_module
from .config import Config
from .models import CheckResult, Status, StockData, Verdict
from .providers import DataProvider


class TradingAgent:
    def __init__(self, provider: DataProvider, config: Optional[Config] = None):
        self.provider = provider
        self.config = config or Config()

    # -- public API --------------------------------------------------------
    def screen(self, ticker: str) -> Verdict:
        data = self.provider.fetch(ticker)
        results = checks_module.run_all(data, self.config)
        assessment = ai_module.assess(data, self.config)
        if assessment and "_error" not in assessment:
            results = self._merge_ai(results, assessment)
        return self._verdict(ticker, data, results, assessment)

    # -- internals ---------------------------------------------------------
    def _merge_ai(
        self, results: list[CheckResult], assessment: dict
    ) -> list[CheckResult]:
        by_id = {c.id: c for c in results}

        macro = assessment.get("macro_tailwind") or {}
        if macro:
            verdict = macro.get("verdict")
            status = {
                "yes": Status.PASS,
                "no": Status.FAIL,
                "unclear": Status.WARN,
            }.get(verdict, Status.MANUAL)
            trend = macro.get("trend", "")
            rationale = macro.get("rationale", "")
            detail = f"{trend + ': ' if trend else ''}{rationale}".strip()
            by_id["macro_tailwind"] = CheckResult(
                "macro_tailwind", checks_module.P2, "Macro Tailwind",
                status, detail or "AI returned no rationale.", ai_backed=True,
            )

        baseline = assessment.get("company_baseline") or {}
        # Only override baseline with AI if the deterministic check couldn't decide.
        if baseline and by_id["company_baseline"].status in {
            Status.MANUAL, Status.UNKNOWN, Status.WARN
        }:
            status = Status.PASS if baseline.get("has_floor") else Status.WARN
            by_id["company_baseline"] = CheckResult(
                "company_baseline", checks_module.P2,
                "Company Baseline (real operations)",
                status, baseline.get("rationale", ""), ai_backed=True,
            )

        return list(by_id.values())

    def _verdict(
        self,
        ticker: str,
        data: StockData,
        results: list[CheckResult],
        assessment: Optional[dict],
    ) -> Verdict:
        fails = [c for c in results if c.status is Status.FAIL]
        open_items = [
            c for c in results
            if c.status in {Status.MANUAL, Status.WARN, Status.UNKNOWN}
        ]

        reasons: list[str] = []
        if fails:
            decision = "NO-GO"
            reasons = [f"{c.title}: {c.detail}" for c in fails]
        elif open_items:
            decision = "REVIEW"
            reasons = [f"{c.title} ({c.status.value})" for c in open_items]
        else:
            decision = "GO"
            reasons = ["All checklist items satisfied."]

        return Verdict(
            ticker=ticker.upper(),
            decision=decision,
            reasons=reasons,
            checks=results,
            data=data,
            ai_assessment=assessment,
        )


# --------------------------------------------------------------------------
# Report rendering
# --------------------------------------------------------------------------
def render_report(verdict: Verdict, cfg: Config) -> str:
    d = verdict.data
    out: list[str] = []
    banner = {
        "GO": "GO  ✅",
        "NO-GO": "NO-GO  ⛔",
        "REVIEW": "REVIEW  ⚠️",
    }.get(verdict.decision, verdict.decision)

    name = f" — {d.name}" if d.name else ""
    out.append("=" * 68)
    out.append(f" {verdict.ticker}{name}")
    px = f"${d.price:,.2f}" if d.price is not None else "n/a"
    out.append(f" Price: {px}   Source: {d.source}   Decision: {banner}")
    out.append("=" * 68)

    # Grouped checklist
    current_phase = None
    for c in verdict.checks_sorted():
        if c.phase != current_phase:
            current_phase = c.phase
            out.append("")
            out.append(current_phase)
            out.append("-" * len(current_phase))
        tag = " (AI)" if c.ai_backed else ""
        out.append(f" {c.status.symbol} {c.title}{tag}")
        out.append(f"      {c.detail}")

    # Verdict reasons
    out.append("")
    out.append("Decision rationale")
    out.append("-" * len("Decision rationale"))
    for r in verdict.reasons:
        out.append(f" - {r}")

    # AI summary / flags
    a = verdict.ai_assessment
    if a and "_error" not in a:
        if a.get("summary"):
            out.append("")
            out.append("AI summary")
            out.append("-" * len("AI summary"))
            out.append(f" {a['summary']}")
        flags = a.get("risk_flags") or []
        if flags:
            out.append("")
            out.append("AI risk flags")
            out.append("-" * len("AI risk flags"))
            for f in flags:
                out.append(f" - {f}")
        ideas = a.get("catalyst_ideas") or []
        if ideas:
            out.append("")
            out.append("Catalyst ideas (1-3 months)")
            out.append("-" * len("Catalyst ideas (1-3 months)"))
            for i in ideas:
                out.append(f" - {i}")
    elif a and "_error" in a:
        out.append("")
        out.append(f"[AI unavailable] {a['_error']}")

    # Trade plan template (Part 3) — only worth filling in if not a NO-GO.
    if verdict.decision != "NO-GO":
        out.append("")
        out.append("Trade Execution & Exit Plan (fill in before ordering)")
        out.append("-" * 53)
        out.append(f" Ticker:            {verdict.ticker}")
        out.append(f" Entry Price:       ${d.price:,.2f}" if d.price else " Entry Price:       $______")
        cat = (
            f"{d.next_earnings_date} (earnings, {d.days_to_earnings}d)"
            if d.next_earnings_date else "[ insert event / narrative ]"
        )
        out.append(f" Identified Catalyst: {cat}")
        if d.support_level is not None:
            out.append(
                f" Invalidation/Stop:  daily close below ~${d.support_level:,.2f} "
                "(support floor)"
            )
        else:
            out.append(" Invalidation/Stop:  $______ (exit on daily close below)")
        out.append(" Take-Profit:        [ price target OR 'exit on catalyst date' ]")

    # Data caveats
    if d.warnings:
        out.append("")
        out.append("Data notes")
        out.append("-" * len("Data notes"))
        for w in d.warnings:
            out.append(f" - {w}")

    out.append("")
    out.append(
        "Reminders: sell 100% on the catalyst/target — don't hold for the "
        "cool-off. Exit immediately if the thesis breaks or price closes below "
        "support; never average down. Stay off hype threads while holding."
    )
    if cfg.graduation_target:
        out.append(
            f"Graduation: at ${cfg.graduation_target:,.0f}, move "
            f"{cfg.graduation_transfer_pct:.0f}% of profits to broad-market index "
            "funds (VTI/VOO)."
        )
    out.append("")
    out.append(
        "This is a rules-screening tool, not financial advice. Verify every "
        "figure before trading."
    )
    return "\n".join(out)


# Small helper on Verdict for stable phase ordering in the report.
def _checks_sorted(self: Verdict) -> list[CheckResult]:
    phase_order = {checks_module.P1: 0, checks_module.P2: 1, checks_module.P3: 2}
    return sorted(self.checks, key=lambda c: phase_order.get(c.phase, 99))


Verdict.checks_sorted = _checks_sorted  # type: ignore[attr-defined]
