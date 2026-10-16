from decimal import Decimal
import pytest
from app.afiliados.pricing import annual_savings, format_brl, plan_price
from app.afiliados.showcase import public_plan_comparison

@pytest.mark.parametrize("plan,monthly,annual,savings", [
    ("gratis", "0.00", "0.00", "0.00"),
    ("pro", "69.90", "699.00", "139.80"),
    ("premium", "119.90", "1199.00", "239.80"),
    ("creator", "199.90", "1999.00", "399.80"),
])
def test_prices(plan, monthly, annual, savings):
    assert plan_price(plan) == Decimal(monthly)
    assert plan_price(plan, "annual") == Decimal(annual)
    assert annual_savings(plan) == Decimal(savings)

def test_invalid_period_or_plan_rejected():
    with pytest.raises(ValueError):
        plan_price("creator", "weekly")
    with pytest.raises(ValueError):
        plan_price("unknown")

def test_public_showcase_prices():
    table = public_plan_comparison()
    assert table["Plano"] == ["Grátis", "Pro", "Premium", "Creator"]
    assert table["Mensal"] == ["R$ 0,00", "R$ 69,90", "R$ 119,90", "R$ 199,90"]
    assert table["Anual (12 meses)"] == ["R$ 0,00", "R$ 699,00", "R$ 1.199,00", "R$ 1.999,00"]
    assert table["Economia anual"] == ["R$ 0,00", "R$ 139,80", "R$ 239,80", "R$ 399,80"]
    assert format_brl(Decimal("1999.00")) == "R$ 1.999,00"
