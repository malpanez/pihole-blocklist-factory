from __future__ import annotations

from blocklist_builder.classify import partition_by_precedence


def test_partition_by_precedence() -> None:
    domain_to_cats = {
        "a.example": {"tracking", "advertising"},
        "b.example": {"malicious"},
    }
    precedence = ["malicious", "tracking", "advertising"]
    out = partition_by_precedence(domain_to_cats, precedence)
    assert out["a.example"] == "tracking"
    assert out["b.example"] == "malicious"
