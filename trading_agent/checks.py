"""The pre-trade checklist, encoded as deterministic checks.

Each function takes a :class:`StockData` and :class:`Config` and returns a
:class:`CheckResult`. ``run_all`` executes them in checklist order. Qualitative
rules that need judgment (macro tailwind, catalyst narrative) are stubbed here
as MANUAL and upgraded by the AI layer when it is available.
"""

from __future__ import annotations

from .config import Config
from .models import CheckResult, Status, StockData

# Phase labels mirror the source ruleset.
P1 = "Phase 1: Risk & Instrument Verification"
P2 = "Phase 2: Fundamental & Catalyst Setup"
P3 = "Phase 3: Technical & Price Action Guardrails"


def check_asset_instrument(data: StockData, cfg: Config) -> CheckResult:
    """Is this a common stock of an operating company?"""
    qt = (data.quote_type or "").upper()
    if not qt:
        return CheckResult(
            "asset_instrument", P1, "Asset Instrument (common stock)",
            Status.UNKNOWN, "Quote type unavailable — verify manually.",
        )
    if qt in {t.upper() for t in cfg.allowed_quote_types}:
        return CheckResult(
            "asset_instrument", P1, "Asset Instrument (common stock)",
            Status.PASS, f"Quote type is {qt} (common equity).",
        )
    return CheckResult(
        "asset_instrument", P1, "Asset Instrument (common stock)",
        Status.FAIL,
        f"Quote type is {qt}; ruleset permits only {', '.join(cfg.allowed_quote_types)} "
        "(no options, crypto, or funds).",
    )


def check_not_penny(data: StockData, cfg: Config) -> CheckResult:
    """No penny stocks."""
    if data.price is None:
        return CheckResult(
            "not_penny", P1, "Not a penny stock",
            Status.UNKNOWN, "Price unavailable.",
        )
    if data.price >= cfg.penny_price_threshold:
        return CheckResult(
            "not_penny", P1, "Not a penny stock",
            Status.PASS,
            f"Price ${data.price:,.2f} >= ${cfg.penny_price_threshold:,.2f} threshold.",
        )
    return CheckResult(
        "not_penny", P1, "Not a penny stock",
        Status.FAIL,
        f"Price ${data.price:,.2f} is below the ${cfg.penny_price_threshold:,.2f} "
        "penny-stock threshold.",
    )


def check_leverage(data: StockData, cfg: Config) -> CheckResult:
    """Executed 100% cash, no margin. Account-level rule."""
    return CheckResult(
        "leverage", P1, "Leverage Check (100% cash)",
        Status.MANUAL,
        "Confirm the order is placed in a cash account with settled funds — "
        "no margin, borrowed capital, or leverage.",
    )


def check_loss_tolerance(data: StockData, cfg: Config) -> CheckResult:
    """Position sized so a max gap-down does not compromise essentials."""
    if cfg.position_size is None or cfg.max_acceptable_loss is None:
        detail = (
            "Provide `position_size` and `max_acceptable_loss` in the config to "
            f"evaluate automatically. Rule of thumb: a {cfg.max_gap_down_pct:.0f}% "
            "gap-down must not touch essential living needs (which stay in a "
            "separate high-yield cash buffer)."
        )
        return CheckResult(
            "loss_tolerance", P1, "Loss Tolerance (max gap-down)",
            Status.MANUAL, detail,
        )
    potential_loss = cfg.position_size * cfg.max_gap_down_pct / 100.0
    if potential_loss <= cfg.max_acceptable_loss:
        return CheckResult(
            "loss_tolerance", P1, "Loss Tolerance (max gap-down)",
            Status.PASS,
            f"A {cfg.max_gap_down_pct:.0f}% gap-down on ${cfg.position_size:,.0f} "
            f"= ${potential_loss:,.0f} loss, within your ${cfg.max_acceptable_loss:,.0f} "
            "tolerance.",
        )
    return CheckResult(
        "loss_tolerance", P1, "Loss Tolerance (max gap-down)",
        Status.FAIL,
        f"A {cfg.max_gap_down_pct:.0f}% gap-down on ${cfg.position_size:,.0f} "
        f"= ${potential_loss:,.0f} loss, exceeding your ${cfg.max_acceptable_loss:,.0f} "
        "tolerance. Cut the position size.",
    )


def check_catalyst(data: StockData, cfg: Config) -> CheckResult:
    """Identifiable catalyst within ~1-3 months.

    Uses the next earnings date as the machine-checkable catalyst. The AI layer
    may broaden this to product milestones / regulatory decisions.
    """
    d = data.days_to_earnings
    if d is None:
        return CheckResult(
            "catalyst", P2, "Identifiable Catalyst (1-3 months)",
            Status.MANUAL,
            "No earnings date found. Identify a specific upcoming event (earnings, "
            "product milestone, regulatory decision, industry event) within 1-3 months.",
        )
    if d < 0:
        return CheckResult(
            "catalyst", P2, "Identifiable Catalyst (1-3 months)",
            Status.WARN,
            f"Next earnings date is {abs(d)} days in the past; the calendar may be "
            "stale. Confirm the next forward catalyst.",
        )
    if cfg.catalyst_min_days <= d <= cfg.catalyst_max_days:
        band = ""
        if not (cfg.catalyst_ideal_min_days <= d <= cfg.catalyst_ideal_max_days):
            band = " (just outside the 1-3 month comfort band, but valid)."
        return CheckResult(
            "catalyst", P2, "Identifiable Catalyst (1-3 months)",
            Status.PASS,
            f"Earnings in {d} days on {data.next_earnings_date}{band}",
        )
    return CheckResult(
        "catalyst", P2, "Identifiable Catalyst (1-3 months)",
        Status.WARN,
        f"Earnings in {d} days ({data.next_earnings_date}) is outside the "
        f"{cfg.catalyst_min_days}-{cfg.catalyst_max_days} day window. Too far out "
        "means capital is idle; look for a nearer catalyst.",
    )


def check_macro_tailwind(data: StockData, cfg: Config) -> CheckResult:
    """Does the industry benefit from a broader trend? Qualitative."""
    ctx = " / ".join(x for x in (data.sector, data.industry) if x)
    return CheckResult(
        "macro_tailwind", P2, "Macro Tailwind",
        Status.MANUAL,
        f"Judge whether {ctx or 'this industry'} benefits from a broader economic "
        "or technological trend. (Enable AI assessment for an automated read.)",
    )


def check_company_baseline(data: StockData, cfg: Config) -> CheckResult:
    """Real revenue / operations providing a valuation floor."""
    if data.total_revenue is None:
        return CheckResult(
            "company_baseline", P2, "Company Baseline (real operations)",
            Status.MANUAL,
            "Revenue figure unavailable. Confirm the business has actual revenue, "
            "strategic assets, or real operations providing a valuation floor.",
        )
    if data.total_revenue > 0:
        return CheckResult(
            "company_baseline", P2, "Company Baseline (real operations)",
            Status.PASS,
            f"Reports ${data.total_revenue:,.0f} in revenue — an operating business, "
            "not a pure story stock.",
        )
    return CheckResult(
        "company_baseline", P2, "Company Baseline (real operations)",
        Status.WARN,
        "No reported revenue — treat any valuation floor with skepticism.",
    )


def check_no_chasing(data: StockData, cfg: Config) -> CheckResult:
    """Has the stock risen less than the no-chasing threshold this week?"""
    r = data.week_return_pct
    if r is None:
        return CheckResult(
            "no_chasing", P3, "No-Chasing Rule (< 20% / week)",
            Status.UNKNOWN, "One-week return unavailable.",
        )
    if r < cfg.no_chasing_max_week_gain_pct:
        return CheckResult(
            "no_chasing", P3, "No-Chasing Rule (< 20% / week)",
            Status.PASS,
            f"Up {r:.1f}% over the last week (< {cfg.no_chasing_max_week_gain_pct:.0f}%).",
        )
    return CheckResult(
        "no_chasing", P3, "No-Chasing Rule (< 20% / week)",
        Status.FAIL,
        f"Up {r:.1f}% this week (>= {cfg.no_chasing_max_week_gain_pct:.0f}%). "
        "Parabolic / social-media momentum — DO NOT ENTER.",
    )


def check_support_floor(data: StockData, cfg: Config) -> CheckResult:
    """Is the current price within 5-10% of a clear support level?"""
    p = data.pct_above_support
    if p is None:
        return CheckResult(
            "support_floor", P3, "Support Floor (within 5-10%)",
            Status.UNKNOWN, "Support level unavailable.",
        )
    if p < 0:
        return CheckResult(
            "support_floor", P3, "Support Floor (within 5-10%)",
            Status.WARN,
            f"Price is {abs(p):.1f}% below the recent support low — support may have "
            "broken. Reassess the level.",
        )
    if p <= cfg.support_within_pct_ideal:
        return CheckResult(
            "support_floor", P3, "Support Floor (within 5-10%)",
            Status.PASS,
            f"{p:.1f}% above support — tight entry, favorable risk/reward.",
        )
    if p <= cfg.support_within_pct_max:
        return CheckResult(
            "support_floor", P3, "Support Floor (within 5-10%)",
            Status.PASS,
            f"{p:.1f}% above support (within the {cfg.support_within_pct_max:.0f}% band).",
        )
    return CheckResult(
        "support_floor", P3, "Support Floor (within 5-10%)",
        Status.WARN,
        f"{p:.1f}% above support — extended from the floor, so a stop-out would hurt "
        "more. Wait for a pullback toward support.",
    )


# Ordered exactly as the checklist reads.
ALL_CHECKS = [
    check_asset_instrument,
    check_not_penny,
    check_leverage,
    check_loss_tolerance,
    check_catalyst,
    check_macro_tailwind,
    check_company_baseline,
    check_no_chasing,
    check_support_floor,
]


def run_all(data: StockData, cfg: Config) -> list[CheckResult]:
    return [fn(data, cfg) for fn in ALL_CHECKS]
