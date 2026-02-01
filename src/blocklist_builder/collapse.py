from __future__ import annotations

from collections import Counter
from typing import Final

_MIN_LABELS: Final = 2  # Mínimo de labels para considerar colapso (ej: example.com)
_MIN_SUBDOMAINS_TO_COLLAPSE: Final = 5  # Solo colapsar si el padre tiene 5+ subdominios


def _get_parent_domain(domain: str) -> str | None:
    """Obtiene el dominio padre (un nivel arriba).

    Ejemplo: ads.tracker.example.com -> tracker.example.com
    """
    parts = domain.split(".")
    if len(parts) <= _MIN_LABELS:
        return None
    return ".".join(parts[1:])


def _get_immediate_parent(domain: str) -> str | None:
    """Obtiene solo el padre inmediato (un nivel arriba)."""
    return _get_parent_domain(domain)


def collapse_subdomains(domains: set[str]) -> tuple[set[str], int]:
    """Elimina subdominios redundantes cuando el dominio padre existe.

    Solo colapsa si el dominio padre tiene al menos _MIN_SUBDOMAINS_TO_COLLAPSE
    subdominios en la lista. Esto evita colapsar casos aislados.

    Args:
        domains: Set de dominios únicos.

    Returns:
        Tuple de (dominios colapsados, número de dominios eliminados).
    """
    domain_lookup = frozenset(domains)

    # Contar cuántos subdominios tiene cada dominio padre
    parent_subdomain_count: Counter[str] = Counter()
    for domain in domains:
        parent = _get_immediate_parent(domain)
        if parent and parent in domain_lookup:
            parent_subdomain_count[parent] += 1

    # Identificar padres que tienen suficientes subdominios para colapsar
    collapsible_parents = {
        parent
        for parent, count in parent_subdomain_count.items()
        if count >= _MIN_SUBDOMAINS_TO_COLLAPSE
    }

    collapsed = set()
    removed_count = 0

    for domain in domains:
        parent = _get_immediate_parent(domain)
        # Solo colapsar si el padre inmediato es collapsible
        if parent and parent in collapsible_parents:
            removed_count += 1
        else:
            collapsed.add(domain)

    return collapsed, removed_count
