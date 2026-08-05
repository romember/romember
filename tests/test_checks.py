"""Unit tests for the rule logic.

These run entirely offline with synthetic data, so the checklist logic is
verifiable even where the live market-data hosts are unreachable.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from trading_agent.agent import TradingAgent, render_report
from trading_agent.checks import (
    check_asset_instrument,
    check_catalyst,
    check_company_baseline,
    check_no_chasing,
    check_not_penny,
    check_support_floor,
)
from trading_agent.config import Config
from trading_agent.models import Status, StockData
from trading_agent.providers import JSONProvider, compute_technicals


# --------------------------------------------------------------------------
# compute_technicals
# --------------------------------------------------------------------------
def test_compute_technicals_week_return():
    # 6 points: price 110 vs. 6-back 100 => +10%
    closes = [100, 101, 102, 103, 104, 105, 110]
    t = compute_technicals(closes)
    assert t["price"] == 110
    # index -6 is 101 -> (110/101 - 1)*100
    assert t["week_return_pct"] == pytest.approx((110 / 101 - 1) * 100)


def test_compute_technicals_support_and_pct():
    closes = [90, 95, 100, 105]
    t = compute_technicals(closes, lows=[88, 92, 98, 103])
    assert t["support_level"] == 88
    assert t["pct_above_support"] == pytest.approx((105 - 88) / 88 * 100)


def test_compute_technicals_empty():
    assert compute_technicals([])["price"] is None


# --------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------
def test_asset_instrument_rejects_crypto():
    cfg = Config()
    d = StockData(ticker="X", quote_type="CRYPTOCURRENCY")
    assert check_asset_instrument(d, cfg).status is Status.FAIL


def test_asset_instrument_accepts_equity():
    cfg = Config()
    d = StockData(ticker="X", quote_type="EQUITY")
    assert check_asset_instrument(d, cfg).status is Status.PASS


def test_penny_stock_fails():
    cfg = Config()
    assert check_not_penny(StockData("X", price=3.0), cfg).status is Status.FAIL
    assert check_not_penny(StockData("X", price=25.0), cfg).status is Status.PASS


def test_no_chasing_blocks_parabolic():
    cfg = Config()
    assert check_no_chasing(StockData("X", week_return_pct=35.0), cfg).status is Status.FAIL
    assert check_no_chasing(StockData("X", week_return_pct=4.0), cfg).status is Status.PASS


def test_support_floor_bands():
    cfg = Config()
    # tight entry
    assert check_support_floor(StockData("X", pct_above_support=3.0), cfg).status is Status.PASS
    # within 10% band
    assert check_support_floor(StockData("X", pct_above_support=8.0), cfg).status is Status.PASS
    # extended
    assert check_support_floor(StockData("X", pct_above_support=25.0), cfg).status is Status.WARN
    # below support
    assert check_support_floor(StockData("X", pct_above_support=-5.0), cfg).status is Status.WARN


def test_catalyst_window():
    cfg = Config()
    d = StockData("X", days_to_earnings=30, next_earnings_date=date.today() + timedelta(days=30))
    assert check_catalyst(d, cfg).status is Status.PASS
    far = StockData("X", days_to_earnings=200, next_earnings_date=date.today() + timedelta(days=200))
    assert check_catalyst(far, cfg).status is Status.WARN
    none = StockData("X")
    assert check_catalyst(none, cfg).status is Status.MANUAL


def test_company_baseline():
    cfg = Config()
    assert check_company_baseline(StockData("X", total_revenue=5e9), cfg).status is Status.PASS
    assert check_company_baseline(StockData("X", total_revenue=0), cfg).status is Status.WARN


def test_loss_tolerance_numeric():
    from trading_agent.checks import check_loss_tolerance

    cfg = Config(position_size=2000, max_acceptable_loss=600, max_gap_down_pct=20)
    # 20% of 2000 = 400 <= 600
    assert check_loss_tolerance(StockData("X"), cfg).status is Status.PASS
    cfg2 = Config(position_size=5000, max_acceptable_loss=600, max_gap_down_pct=20)
    # 20% of 5000 = 1000 > 600
    assert check_loss_tolerance(StockData("X"), cfg2).status is Status.FAIL


# --------------------------------------------------------------------------
# End-to-end via JSONProvider (AI disabled so it is deterministic)
# --------------------------------------------------------------------------
@pytest.fixture()
def agent():
    provider = JSONProvider.from_file("examples/sample_stocks.json")
    return TradingAgent(provider, Config(ai_enabled=False))


def test_e2e_crypto_is_nogo(agent):
    v = agent.screen("CRYPTOX")
    assert v.decision == "NO-GO"
    assert any(c.id == "asset_instrument" and c.status is Status.FAIL for c in v.checks)


def test_e2e_penny_is_nogo(agent):
    v = agent.screen("PENNYCO")
    assert v.decision == "NO-GO"
    assert any(c.id == "not_penny" and c.status is Status.FAIL for c in v.checks)


def test_e2e_parabolic_is_nogo(agent):
    v = agent.screen("PARABOLIC")
    assert v.decision == "NO-GO"
    assert any(c.id == "no_chasing" and c.status is Status.FAIL for c in v.checks)


def test_e2e_goodco_reviewable(agent):
    v = agent.screen("GOODCO")
    # No hard FAIL; macro tailwind stays MANUAL without AI -> REVIEW.
    assert v.decision in {"REVIEW", "GO"}
    assert not any(c.status is Status.FAIL for c in v.checks)
    # Report renders without error.
    text = render_report(v, Config(ai_enabled=False))
    assert "GOODCO" in text
    assert "Trade Execution & Exit Plan" in text


def test_unknown_ticker_is_handled(agent):
    v = agent.screen("NOPE")
    assert v.data.warnings  # provider noted the miss
