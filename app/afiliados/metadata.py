"""Extract conservative product metadata from supplied HTML (no network requests)."""
from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.scripts = []
        self._in_jsonld = False
        self._parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            value = attrs.get("content", "").strip()
            if key and value and key not in self.meta:
                self.meta[key] = value
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self._in_jsonld = True
            self._parts = []

    def handle_data(self, data):
        if self._in_jsonld:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self.scripts.append("".join(self._parts))
            self._in_jsonld = False
            self._parts = []


def _products(node, depth=0):
    if depth > 8:
        return
    if isinstance(node, list):
        for value in node[:100]:
            yield from _products(value, depth + 1)
    elif isinstance(node, dict):
        kinds = node.get("@type", [])
        if isinstance(kinds, str):
            kinds = [kinds]
        if isinstance(kinds, list) and "Product" in kinds:
            yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _products(node[key], depth + 1)


def extract_product_metadata(page_html: str) -> dict[str, str]:
    """Read user-supplied page source. Never claim it is verified or current."""
    if not isinstance(page_html, str) or not page_html.strip() or len(page_html) > 2_000_000:
        raise ValueError("HTML vazio ou acima de 2 MB")
    parser = _MetadataParser()
    parser.feed(page_html)
    result = {}
    for raw in parser.scripts[:30]:
        try:
            products = list(_products(json.loads(raw)))
        except (ValueError, TypeError, RecursionError):
            continue
        for product in products:
            for source, target, limit in (("name", "name", 140), ("description", "description", 3000), ("image", "image_url", 2048)):
                value = product.get(source)
                if source == "image" and isinstance(value, list):
                    value = next((v for v in value if isinstance(v, str)), "")
                if isinstance(value, str) and value.strip() and target not in result:
                    result[target] = re.sub(r"\\s+", " ", html.unescape(value)).strip()[:limit]
    for source, target, limit in (("og:title", "name", 140), ("og:description", "description", 3000), ("og:image", "image_url", 2048)):
        value = parser.meta.get(source)
        if value and target not in result:
            result[target] = re.sub(r"\\s+", " ", value).strip()[:limit]
    # Never trust arbitrary image URLs for server-side downloads.
    if "image_url" in result and not result["image_url"].startswith("https://"):
        del result["image_url"]
    return result
