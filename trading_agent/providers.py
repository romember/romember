"""Market-data providers.

The agent talks to data through a small interface so the source can be swapped
without touching the rule logic:

* ``YFinanceProvider`` — live data via Yahoo Finance. Use this in an
  environment with outbound network access to the finance hosts.
* ``JSONProvider`` — reads a normalized snapshot from a dict/JSON file. Useful
  for offline runs, deterministic tests, or restricted networks where the live
  finance hosts are blocked by policy.

Technical indicators are computed in pure Python (``compute_technicals``) so
the same logic is exercised by both providers and by the unit tests.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from .models import StockData


def compute_technicals(
    closes: list[float],
    lows: Optional[list[float]] = None,
    *,
    week_lookback: int = 5,
    support_window: int = 20,
) -> dict:
    """Derive the technicals the checklist needs from a price series.

    ``closes`` and ``lows`` are ordered oldest -> newest.

    Returns a dict with ``price``, ``week_return_pct``, ``support_level``,
    ``pct_above_support`` and ``ma50`` (any of which may be ``None`` when the
    series is too short).
    """

    out: dict[str, Optional[float]] = {
        "price": None,
        "week_return_pct": None,
        "support_level": None,
        "pct_above_support": None,
        "ma50": None,
    }
    closes = [float(c) for c in closes if c is not None]
    if not closes:
        return out

    price = closes[-1]
    out["price"] = price

    # ~1 trading week ago (fall back to the earliest point we have).
    if len(closes) > week_lookback:
        prior = closes[-(week_lookback + 1)]
    else:
        prior = closes[0]
    if prior:
        out["week_return_pct"] = (price / prior - 1.0) * 100.0

    # Support = recent swing low over the window (use lows if available).
    series = [float(x) for x in (lows if lows else closes) if x is not None]
    window = series[-support_window:] if series else []
    if window:
        support = min(window)
        out["support_level"] = support
        if support > 0:
            out["pct_above_support"] = (price - support) / support * 100.0

    if len(closes) >= 50:
        out["ma50"] = sum(closes[-50:]) / 50.0

    return out


class DataProvider:
    """Provider interface."""

    def fetch(self, ticker: str) -> StockData:  # pragma: no cover - interface
        raise NotImplementedError


class JSONProvider(DataProvider):
    """Build a :class:`StockData` from a plain dict (or JSON file).

    The dict may supply computed technicals directly, or supply a ``closes``
    (and optional ``lows``) price series to have them computed here.
    """

    def __init__(self, records: dict[str, dict]):
        # keyed by upper-cased ticker
        self._records = {k.upper(): v for k, v in records.items()}

    @classmethod
    def from_file(cls, path: str) -> "JSONProvider":
        import json

        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        # Accept either {"AAPL": {...}} or a single {"ticker": "AAPL", ...}
        if "ticker" in raw and not any(isinstance(v, dict) for v in raw.values()):
            raw = {raw["ticker"]: raw}
        return cls(raw)

    def fetch(self, ticker: str) -> StockData:
        rec = self._records.get(ticker.upper())
        if rec is None:
            return StockData(
                ticker=ticker.upper(),
                source="json",
                warnings=[f"No record for {ticker} in JSON source."],
            )

        warnings: list[str] = list(rec.get("warnings", []))

        # Technicals: prefer an explicit series, else use precomputed fields.
        tech = {}
        if rec.get("closes"):
            tech = compute_technicals(rec["closes"], rec.get("lows"))

        def pick(key: str):
            return rec.get(key, tech.get(key))

        earnings = _parse_date(rec.get("next_earnings_date"))
        days_to = _days_until(earnings)

        return StockData(
            ticker=ticker.upper(),
            name=rec.get("name"),
            quote_type=rec.get("quote_type"),
            price=pick("price"),
            currency=rec.get("currency", "USD"),
            sector=rec.get("sector"),
            industry=rec.get("industry"),
            description=rec.get("description"),
            market_cap=rec.get("market_cap"),
            total_revenue=rec.get("total_revenue"),
            trailing_pe=rec.get("trailing_pe"),
            week_return_pct=pick("week_return_pct"),
            support_level=pick("support_level"),
            pct_above_support=pick("pct_above_support"),
            ma50=pick("ma50"),
            next_earnings_date=earnings,
            days_to_earnings=days_to,
            source="json",
            warnings=warnings,
        )


class YFinanceProvider(DataProvider):
    """Live data via the ``yfinance`` package (Yahoo Finance)."""

    def __init__(self, period: str = "3mo"):
        self.period = period

    def fetch(self, ticker: str) -> StockData:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "yfinance is not installed. Run `pip install -r requirements.txt`, "
                "or use the JSON provider (--from-json) for offline runs."
            ) from exc

        warnings: list[str] = []
        tkr = yf.Ticker(ticker)

        info: dict = {}
        try:
            info = tkr.get_info()  # type: ignore[assignment]
        except Exception as exc:  # noqa: BLE001 - network/parse errors vary widely
            warnings.append(f"Could not load fundamentals: {exc}")

        closes: list[float] = []
        lows: list[float] = []
        try:
            hist = tkr.history(period=self.period, interval="1d")
            if hist is not None and not hist.empty:
                closes = [float(x) for x in hist["Close"].tolist()]
                lows = [float(x) for x in hist["Low"].tolist()]
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Could not load price history: {exc}")

        tech = compute_technicals(closes, lows) if closes else {}
        if not closes:
            warnings.append(
                "No price history returned (host may be unreachable from this "
                "network). Technical checks will be UNKNOWN."
            )

        earnings = self._earnings_date(tkr, warnings)
        days_to = _days_until(earnings)

        price = tech.get("price") or info.get("currentPrice") or info.get(
            "regularMarketPrice"
        )

        return StockData(
            ticker=ticker.upper(),
            name=info.get("shortName") or info.get("longName"),
            quote_type=info.get("quoteType"),
            price=price,
            currency=info.get("currency", "USD"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            description=info.get("longBusinessSummary"),
            market_cap=info.get("marketCap"),
            total_revenue=info.get("totalRevenue"),
            trailing_pe=info.get("trailingPE"),
            week_return_pct=tech.get("week_return_pct"),
            support_level=tech.get("support_level"),
            pct_above_support=tech.get("pct_above_support"),
            ma50=tech.get("ma50"),
            next_earnings_date=earnings,
            days_to_earnings=days_to,
            source="yfinance",
            warnings=warnings,
        )

    @staticmethod
    def _earnings_date(tkr, warnings: list[str]) -> Optional[date]:
        try:
            cal = tkr.calendar
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Could not load earnings calendar: {exc}")
            return None
        if not cal:
            return None
        # yfinance returns either a DataFrame or a dict depending on version.
        try:
            if isinstance(cal, dict):
                val = cal.get("Earnings Date")
                if isinstance(val, (list, tuple)) and val:
                    return _parse_date(val[0])
                return _parse_date(val)
            # DataFrame form
            val = cal.loc["Earnings Date"][0]  # type: ignore[index]
            return _parse_date(val)
        except Exception:  # noqa: BLE001
            return None


def _parse_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(value[:10], fmt).date()
            except ValueError:
                continue
    # pandas Timestamp / numpy datetime64 duck-typing
    try:
        return value.date()  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        return None


def _days_until(target: Optional[date]) -> Optional[int]:
    if target is None:
        return None
    today = datetime.now(timezone.utc).date()
    return (target - today).days
