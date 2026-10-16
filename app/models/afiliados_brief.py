"""Validated Afiliados Creator product briefs (no user-supplied file paths)."""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from app.models.afiliados_product_source import ProductSource


class ProductVideoBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_name: str = Field(min_length=3, max_length=180)
    description: str = Field(default="", max_length=2000)
    tone: Literal["energetic", "friendly", "professional"] = "energetic"
    voice: Literal["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"] = "pt-BR-FranciscaNeural"
    cta: str = Field(default="Comente EU QUERO nos comentários", max_length=300)
    language: Literal["pt-BR"] = "pt-BR"
    source: ProductSource | None = None
    duration_seconds: Literal[15, 20, 30] = 15

    @field_validator("product_name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Product name required")
        return value


def to_generation_payload(brief: ProductVideoBrief) -> dict:
    data = brief.model_dump()
    duration = data.pop("duration_seconds")
    return {"p_duration": duration, "p_brief": data}
