"""Published plan prices in Brazilian reais, without billing side effects."""
from decimal import Decimal

MONTHLY_BRL = {
    "gratis": Decimal("0.00"),
    "pro": Decimal("69.90"),
    "premium": Decimal("119.90"),
    "creator": Decimal("199.90"),
}
ANNUAL_PAID_MONTHS = 10
ANNUAL_ACCESS_MONTHS = 12


def plan_price(plan: str, period: str = "monthly") -> Decimal:
    if plan not in MONTHLY_BRL:
        raise ValueError("Plano inválido")
    if period == "monthly":
        return MONTHLY_BRL[plan]
    if period == "annual":
        return MONTHLY_BRL[plan] * ANNUAL_PAID_MONTHS
    raise ValueError("Período inválido")


def annual_savings(plan: str) -> Decimal:
    return plan_price(plan, "monthly") * (ANNUAL_ACCESS_MONTHS - ANNUAL_PAID_MONTHS)


def format_brl(amount: Decimal) -> str:
    return "R$ " + f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
