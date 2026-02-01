from __future__ import annotations

from blocklist_builder.classify import build_provenance, partition_by_precedence
from blocklist_builder.types import Source


def test_partition_by_precedence() -> None:
    domain_to_cats = {
        "a.example": {"tracking", "advertising"},
        "b.example": {"malicious"},
    }
    precedence = ["malicious", "tracking", "advertising"]
    out = partition_by_precedence(domain_to_cats, precedence)
    assert out["a.example"] == "tracking"
    assert out["b.example"] == "malicious"


def test_build_provenance_assigns_categories() -> None:
    domain_to_sources = {"a.example": {"s1", "s2"}}
    source_map = {
        "s1": Source(id="s1", name="S1", category="advertising", url="x"),
        "s2": Source(id="s2", name="S2", category="tracking", url="y"),
    }
    precedence = ["tracking", "advertising"]
    prov = build_provenance(domain_to_sources, source_map, precedence)
    assert prov["a.example"].assigned_category == "tracking"
    assert prov["a.example"].source_ids == frozenset({"s1", "s2"})
