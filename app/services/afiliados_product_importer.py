"""Safely resolve marketplace product pages for affiliate video drafts.

Only supported public marketplace hosts are fetched. Never fetch image URLs,
private IPs, arbitrary redirects, or credentials from a submitted link.
Marketplace pages can block bots; missing metadata is an expected outcome.
"""
from __future__ import annotations

import html
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlsplit
from pydantic import BaseModel, Field
import requests

MAX_HTML_BYTES = 1_000_000
MAX_REDIRECTS = 4
HOSTS = {
    "shopee": ("shopee.com.br", "s.shopee.com.br"),
    "mercadolivre": ("mercadolivre.com.br", "mercadolivre.com", "produto.mercadolivre.com.br", "mercadolivre.com.br"),
}

class ProductLinkPreview(BaseModel):
    platform: str
    original_url: str
    resolved_url: str
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    status: str = "metadata_unavailable"

def _platform(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("HTTPS marketplace URL required")
    host = parsed.hostname.lower().rstrip(".")
    for platform, domains in HOSTS.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return platform
    raise ValueError("Unsupported marketplace domain")

def _public_dns(host: str) -> None:
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("Marketplace DNS unavailable")
    for record in addresses:
        address = ipaddress.ip_address(record[4][0])
        if not address.is_global:
            raise ValueError("Marketplace resolved to a non-public address")

def _meta(content: str, field: str) -> str | None:
    for match in re.finditer(r"<meta\b[^>]*>", content, re.IGNORECASE):
        tag = match.group()
        attrs = dict((key.lower(), html.unescape(value)) for key, value in re.findall(
            r"""([\w:-]+)\s*=\s*["']([^"']*)["']""", tag))
        if attrs.get("property") == field or attrs.get("name") == field:
            return attrs.get("content", "").strip()[:2000] or None
    return None

def preview_product_link(url: str, session=None) -> ProductLinkPreview:
    original = url.strip()
    platform = _platform(original)
    client = session or requests.Session()
    current = original
    response = None
    try:
        for _ in range(MAX_REDIRECTS + 1):
            if _platform(current) != platform:
                raise ValueError("Redirect leaves supported marketplace")
            host = urlsplit(current).hostname
            _public_dns(host)
            response = client.get(current, allow_redirects=False, stream=True,
                                  timeout=(5, 12), headers={"User-Agent": "Mozilla/5.0 AfiliadosCreatorPreview/1.0"})
            if response.status_code in (301, 302, 303, 307, 308):
                target = response.headers.get("Location")
                if not target:
                    raise ValueError("Missing redirect target")
                current = urljoin(current, target)
                response.close()
                response = None
                continue
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                return ProductLinkPreview(platform=platform, original_url=original, resolved_url=current)
            data = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                data.extend(chunk)
                if len(data) > MAX_HTML_BYTES:
                    raise ValueError("Marketplace page too large")
            page = data.decode("utf-8", errors="replace")
            title = _meta(page, "og:title")
            description = _meta(page, "og:description")
            image = _meta(page, "og:image")
            if image:
                image = urljoin(current, image)
                if urlsplit(image).scheme != "https":
                    image = None
            return ProductLinkPreview(
                platform=platform, original_url=original, resolved_url=current,
                title=title[:180] if title else None,
                description=description[:2000] if description else None,
                image_url=image, status="metadata_found" if title else "metadata_unavailable"
            )
        raise ValueError("Too many marketplace redirects")
    except (requests.RequestException, OSError):
        return ProductLinkPreview(platform=platform, original_url=original,
                                  resolved_url=current, status="metadata_unavailable")
    finally:
        if response is not None:
            response.close()
