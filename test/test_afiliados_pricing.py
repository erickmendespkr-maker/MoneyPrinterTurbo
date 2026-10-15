from decimal import Decimal

import pytest

from app.afiliados.pricing import annual_savings, format_brl, plan_price
from app.afiliados.showcase import public_plan_comparison


def test_monthly_and_annual_prices():
    assert plan_price("gratis") == Decimal("0.00")
    assert plan_price("pro") == Decimal("39.90")
    assert plan_price("creator") == Decimal("119.90")
    assert plan_price("pro", "annual") == Decimal("438.90")
    assert plan_price("creator", "annual") == Decimal("1318.90")
    assert annual_savings("pro") == Decimal("39.90")
    assert annual_savings("creator") == Decimal("119.90")


def test_invalid_period_or_plan_rejected():
    with pytest.raises(ValueError):
        plan_price("creator", "weekly")
    with pytest.raises(ValueError):
        plan_price("unknown")


def test_public_showcase_displays_real_prices():
    comparison = public_plan_comparison()
    assert comparison["Mensal"] == ["R$ 0,00", "R$ 39,90", "R$ 119,90"]
    assert comparison["Anual (12 meses)"] == ["R$ 0,00", "R$ 438,90", "R$ 1.318,90"]
    assert comparison["Economia anual"] == ["R$ 0,00", "R$ 39,90", "R$ 119,90"]
    assert format_brl(Decimal("1318.90")) == "R$ 1.318,90"
