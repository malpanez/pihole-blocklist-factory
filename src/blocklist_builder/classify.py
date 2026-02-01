from __future__ import annotations

from .types import Category, Provenance, Source


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


def build_provenance(
    domain_to_sources: dict[str, set[str]],
    source_map: dict[str, Source],
    precedence: list[str],
) -> dict[str, Provenance]:
    """Build provenance info for each domain.

    Args:
        domain_to_sources: Domain -> set of source_ids.
        source_map: source_id -> Source object.
        precedence: Category precedence for tie-breaking.

    Returns:
        Domain -> Provenance object.
    """
    out: dict[str, Provenance] = {}
    rank = _build_rank_map(precedence)

    for domain, source_ids in domain_to_sources.items():
        # Collect categories from all sources
        categories: set[Category] = set()
        for src_id in source_ids:
            if src_id in source_map:
                categories.add(source_map[src_id].category)

        # Assign category by precedence using min()
        assigned = min(categories, key=lambda c: rank.get(c, 999))

        out[domain] = Provenance(
            domain=domain,
            source_ids=frozenset(source_ids),
            categories=frozenset(categories),
            assigned_category=assigned,
        )

    return out
