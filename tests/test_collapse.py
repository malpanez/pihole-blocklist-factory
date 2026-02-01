from __future__ import annotations

from blocklist_builder.collapse import _get_parent_domain, collapse_subdomains


def test_get_parent_domain() -> None:
    assert _get_parent_domain("a.b.example.com") == "b.example.com"
    assert _get_parent_domain("example.com") is None


def test_collapse_subdomains() -> None:
    domains = {
        "example.com",
        "a.example.com",
        "b.example.com",
        "c.example.com",
        "d.example.com",
        "e.example.com",
    }
    collapsed, removed = collapse_subdomains(domains)
    assert removed == 5
    assert collapsed == {"example.com"}
