"""Transparent, opt-in sponsor destination configuration.

Opening a sponsor page is never required for product creation or video export.
Only an administrator-configured HTTPS destination is accepted.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from app.afiliados.plans import get_plan_policy


def sponsor_destination(plan: str, url: str | None) -> str | None:
    get_plan_policy(plan)
    if plan != "gratis" or not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if (parsed.scheme != "https" or not host or not parsed.netloc
                or parsed.username or parsed.password or parsed.port is not None
                or host in ("localhost",) or host.endswith((".local", ".internal"))
                or "." not in host or any(c.isspace() for c in url)
                or parsed.fragment):
            return None
    except ValueError:
        return None
    return url
