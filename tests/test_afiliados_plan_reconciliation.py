"""Regression tests for the real Supabase free code and approved commercial rules."""
from decimal import Decimal
import pytest
from app.afiliados.plans import get_plan_policy, normalize_plan_code
from app.afiliados.pricing import plan_price

def test_real_free_code_maps_to_legacy_policy():
    assert normalize_plan_code("free") == "gratis"
    assert get_plan_policy("free") == get_plan_policy("gratis")
    assert plan_price("free") == Decimal("0.00")

@pytest.mark.parametrize("plan,limit,monthly,annual", [
    ("gratis", 1, "0.00", "0.00"),
    ("pro", 3, "69.90", "699.00"),
    ("premium", 5, "119.90", "1199.00"),
    ("creator", 10, "199.90", "1999.00"),
])
def test_approved_plan_contract(plan, limit, monthly, annual):
    assert get_plan_policy(plan).daily_video_limit == limit
    assert plan_price(plan) == Decimal(monthly)
    assert plan_price(plan, "annual") == Decimal(annual)

def test_paid_entitlements():
    assert get_plan_policy("pro").thumbnails_per_ad == 0
    assert get_plan_policy("premium").thumbnails_per_ad == 3
    assert not get_plan_policy("premium").platform_watermark_required
    assert get_plan_policy("creator").videos_per_ad == 3
    assert get_plan_policy("creator").thumbnails_per_ad == 9

@pytest.mark.parametrize("invalid", ["FREE", "unknown", "", None])
def test_unknown_plan_fails_closed(invalid):
    with pytest.raises(ValueError):
        normalize_plan_code(invalid)
