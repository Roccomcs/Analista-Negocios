from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(text: str) -> str:
    return re.sub(r"\W+", " ", "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))).strip()


def website_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("//"):
        value = "https:" + value
    elif "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
        return ""
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", parts.query, ""))


@dataclass
class Contact:
    kind: str
    value: str
    source: str
    verification: str = "publicado"


@dataclass
class Business:
    source_id: str
    name: str
    zone: str
    category: str
    address: str = ""
    website: str = ""
    source_url: str = ""
    latitude: float | None = None
    longitude: float | None = None
    contacts: list[Contact] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class Page:
    url: str
    title: str
    text: str


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=500)
    source: str
    quote: str = Field(min_length=8, max_length=240)


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=600)
    observations: list[Observation] = Field(max_length=2)
    opportunities: list[str] = Field(max_length=2)
    questions: list[str] = Field(max_length=2)
    priority: Literal["baja", "media", "alta", "sin evidencia"]
    draft: str = Field(max_length=1500)
