"""Plan-aware ad placement policy for the affiliate dashboard.

Ad networks require independent approval and explicit publisher configuration.
Never render ad markup from user-provided HTML, query strings, or project JSON.
"""
from __future__ import annotations

import re

from app.afiliados.plans import get_plan_policy

PUBLISHER_PATTERN = re.compile(r"^ca-pub-[0-9]{16}$")
SLOT_PATTERN = re.compile(r"^[0-9]{8,20}$")
PLACEMENTS = ("dashboard", "render_complete")


def ads_enabled(plan: str) -> bool:
    get_plan_policy(plan)
    return plan == "gratis"


def validated_adsense_config(publisher_id: str | None, slots: dict | None) -> dict | None:
    if not isinstance(publisher_id, str) or not PUBLISHER_PATTERN.fullmatch(publisher_id):
        return None
    if not isinstance(slots, dict):
        return None
    if any(not isinstance(slots.get(place), str)
           or not SLOT_PATTERN.fullmatch(slots[place]) for place in PLACEMENTS):
        return None
    return {"publisher_id": publisher_id, "slots": {p: slots[p] for p in PLACEMENTS}}


def ad_placement(plan: str, placement: str, config: dict | None) -> dict | None:
    """Return trusted ad slot metadata only for free users and configured placements."""
    if placement not in PLACEMENTS:
        raise ValueError("Posição de anúncio inválida")
    if not ads_enabled(plan) or config is None:
        return None
    return {"publisher_id": config["publisher_id"], "slot": config["slots"][placement]}
