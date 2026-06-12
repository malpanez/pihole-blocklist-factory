from __future__ import annotations

from .types import Category


def _build_rank_map(precedence: list[str]) -> dict[str, int]:
    """Build category rank map for sorting (cached across calls)."""
    return {c: i for i, c in enumerate(precedence)}


def partition_by_precedence(
    domain_to_cats: dict[str, set[Category]], precedence: list[str]
) -> dict[str, Category]:
    """Assign each domain to single category by precedence order.

    Args:
        domain_to_cats: Domain -> set of categories it appears in.
        precedence: Priority list of categories (first=highest).

    Returns:
        Domain -> final assigned category.
    """
    out: dict[str, Category] = {}
    rank = _build_rank_map(precedence)
    for d, cats in domain_to_cats.items():
        # Pick first (highest rank) category using min()
        chosen = min(cats, key=lambda c: rank.get(c, 999))
        out[d] = chosen
    return out
