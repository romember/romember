"""Account rules and screening thresholds.

These map directly onto Part 1 (Immutable Account Rules) and the numeric
guardrails in the pre-trade checklist. Everything is overridable via a YAML
config file so the ruleset can be tuned without touching code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Config:
    # --- Instrument / asset-class rules -----------------------------------
    penny_price_threshold: float = 5.0        # price below this => penny stock
    allowed_quote_types: tuple[str, ...] = ("EQUITY",)

    # --- Technical guardrails ---------------------------------------------
    no_chasing_max_week_gain_pct: float = 20.0  # Phase 3: no-chasing rule
    support_within_pct_max: float = 10.0        # within 5-10% of support
    support_within_pct_ideal: float = 5.0

    # --- Catalyst window (Phase 2) ----------------------------------------
    catalyst_min_days: int = 0                 # a catalyst any time from now...
    catalyst_max_days: int = 92                # ...through ~3 months out
    catalyst_ideal_min_days: int = 21          # "1 to 3 months" comfort band
    catalyst_ideal_max_days: int = 92

    # --- Risk / position sizing (Phase 1: Loss Tolerance) -----------------
    max_gap_down_pct: float = 20.0             # bad-earnings gap assumption

    # Optional account inputs. When provided, the Loss Tolerance check is
    # evaluated numerically instead of deferred to manual judgment.
    trading_capital: Optional[float] = None
    position_size: Optional[float] = None      # $ committed to this single trade
    max_acceptable_loss: Optional[float] = None  # $ loss that would hurt essentials

    # --- Graduation rule (informational) ----------------------------------
    graduation_target: Optional[float] = None  # capital milestone
    graduation_transfer_pct: float = 70.0      # % of profit to index funds (VTI/VOO)

    # --- AI assessment -----------------------------------------------------
    ai_enabled: bool = True                    # use Claude for qualitative rules
    ai_model: str = "claude-opus-5"

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        """Load config from a YAML file, falling back to defaults."""
        cfg = cls()
        if not path:
            return cfg
        import yaml  # local import so PyYAML is only needed when a file is used

        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        known = {f for f in cls().__dataclass_fields__}  # type: ignore[attr-defined]
        for key, value in raw.items():
            if key in known:
                setattr(cfg, key, value)
        return cfg

    def as_dict(self) -> dict:
        return asdict(self)
