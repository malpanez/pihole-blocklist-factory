from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Type aliases with Literal for type safety
Category = Literal["advertising", "tracking", "malicious", "suspicious", "other", "telemetry"]
Tier = Literal["stable", "edge"]


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    name: str
    category: Category
    url: str
    enabled: bool = True
    tier: Tier = "stable"
    license: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Metadata tracked for each source after fetch/parse."""
    source_id: str
    hash: str  # SHA256 of content
    size_bytes: int
    line_count: int
    parsed_ok: int
    sanitized_ok: int
    etag: str | None = None
    last_modified: str | None = None
    fetch_timestamp: float | None = None


@dataclass(frozen=True, slots=True)
class Provenance:
    """Domain's provenance: set of source_ids where it appears."""
    domain: str
    source_ids: frozenset[str]
    categories: frozenset[Category]  # categories from those sources
    assigned_category: Category  # final assigned category by precedence


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    include_categories: set[str] = field(default_factory=set)
    include_sources: set[str] = field(default_factory=set)
    exclude_sources: set[str] = field(default_factory=set)
    strict: bool = False  # strict=True can block telemetry; false must respect core_domains
