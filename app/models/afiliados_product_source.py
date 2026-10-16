"""Validate product input modes without fetching untrusted URLs.

The importer and renderer consume this normalized contract. Uploads must be
stored in the private Supabase product-images bucket under the user's UID.
"""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ProductSource(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    mode: Literal["link", "images", "both"]
    product_url: str | None = Field(default=None, max_length=2048)
    image_paths: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_sources(self):
        if self.mode in ("link", "both"):
            if not self.product_url:
                raise ValueError("Product URL required")
            parsed = urlsplit(self.product_url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("Product URL must be HTTPS")
            if parsed.username or parsed.password:
                raise ValueError("URL credentials are forbidden")
        elif self.product_url:
            raise ValueError("Unexpected product URL")
        if self.mode in ("images", "both") and not self.image_paths:
            raise ValueError("At least one product image required")
        if self.mode == "link" and self.image_paths:
            raise ValueError("Use both mode when images are supplied")
        if len(set(self.image_paths)) != len(self.image_paths):
            raise ValueError("Duplicate image paths")
        for path in self.image_paths:
            if not path or path.startswith("/") or ".." in path or "\\" in path:
                raise ValueError("Invalid storage path")
            if path.count("/") != 1:
                raise ValueError("Expected user-id/filename image path")
            if not path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                raise ValueError("Unsupported image type")
        return self

def validate_image_ownership(source: ProductSource, user_id: str) -> None:
    """Validate path ownership; storage authorization is still enforced by RLS."""
    for path in source.image_paths:
        if path.split("/", 1)[0] != user_id:
            raise ValueError("Image does not belong to user")
