"""Conservative product-name suggestion from an approved marketplace URL.

No network access, no claims about product attributes or live availability.
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from app.afiliados.core import validate_product_url

_GENERIC = {"product", "produto", "item", "dp", "gp", "p", "br", "oferta", "ofertas", "shop", "loja", "search"}


def suggest_name_from_link(url: str) -> str:
    """Suggest a name only if the URL contains a meaningful product slug."""
    url = validate_product_url(url)
    path = urlsplit(url).path
    parts = [unquote(p) for p in path.split("/") if p]
    for part in reversed(parts):
        # Avoid IDs and encoded delimiters: never use untrusted path as markup.
        if "/" in part or "\\" in part or len(part) > 180:
            continue
        if re.fullmatch(r"(?:MLB-?)?\d+|[A-Z0-9]{10}", part, flags=re.I):
            continue
        if part.lower() in _GENERIC:
            continue
        # Marketplace URLs frequently embed identifiers in the slug.
        clean = re.sub(r"(?i)(?:-?MLB-?\d+|-i\.\d+\.\d+)$", "", part)
        clean = re.sub(r"[-_]+", " ", clean)
        clean = re.sub(r"[^\w\sÀ-ÿ]", " ", clean, flags=re.UNICODE)
        clean = " ".join(clean.split()).strip()
        if len(clean) >= 8 and len(clean.split()) >= 2 and any(ch.isalpha() for ch in clean):
            return clean[:140]
    return ""
