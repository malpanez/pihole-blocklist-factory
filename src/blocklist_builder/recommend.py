"""Generate recommendations for blocklist loading in Pi-hole."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from .config import Settings
from .types import Source


def _load_aggregates_and_marginal(
    dist_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    """Load provenance_aggregates.json and marginal.json."""
    aggregates_file = dist_dir / "reports" / "provenance_aggregates.json"
    if not aggregates_file.exists():
        return None, None

    try:
        aggregates: dict[str, Any] = json.loads(aggregates_file.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    marginal_file = dist_dir / "reports" / "marginal.json"
    marginal_data: dict[str, Any] = {}
    if marginal_file.exists():
        with contextlib.suppress(Exception):
            marginal_data = json.loads(marginal_file.read_text(encoding="utf-8"))

    return aggregates, marginal_data


def _compute_source_metrics(
    aggregates: dict[str, Any], source_map: dict[str, Source], marginal_data: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Compute metrics (contributions, unique domains, overlap) per source.

    Single dict lookup per source against pre-computed per-source aggregates.
    """
    metrics: dict[str, dict[str, Any]] = {}
    per_source = aggregates.get("per_source", {})

    for src_id in source_map:
        src_agg = per_source.get(src_id, {})
        total_contributions = int(src_agg.get("total_contributions", 0))
        unique_domains = int(src_agg.get("unique_domains", 0))

        # Count domains shared with others
        shared_domains = total_contributions - unique_domains

        # Overlap coefficient (0-1, higher = more shared)
        overlap_coeff = (shared_domains / total_contributions) if total_contributions > 0 else 0

        metrics[src_id] = {
            "total_domains": total_contributions,
            "unique_domains": unique_domains,
            "shared_domains": shared_domains,
            "overlap_coefficient": overlap_coeff,
            "marginal_json": marginal_data.get(src_id, unique_domains),
        }

    return metrics


def _categorize_contributions(
    metrics: dict[str, dict[str, Any]], source_map: dict[str, Source], total_domains: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Categorize sources as high/moderate/low value."""
    high_value: list[dict[str, Any]] = []
    moderate_value: list[dict[str, Any]] = []
    low_value: list[dict[str, Any]] = []

    for src_id, metric in metrics.items():
        src = source_map.get(src_id)
        src_name = src.name if src else src_id
        unique_pct = (metric["unique_domains"] / total_domains * 100) if total_domains > 0 else 0
        category = src.category if src else "uncategorized"

        contribution = {
            "id": src_id,
            "name": src_name,
            "category": category,
            "unique": metric["unique_domains"],
            "total": metric["total_domains"],
            "overlap": metric["overlap_coefficient"],
            "unique_pct": unique_pct,
            "url": src.url if src else "",
        }

        if unique_pct > 1.0 or metric["overlap_coefficient"] < 0.2:
            high_value.append(contribution)
        elif unique_pct > 0.1:
            moderate_value.append(contribution)
        else:
            low_value.append(contribution)

    return high_value, moderate_value, low_value


def _write_recommend_report(
    output_file: Path,
    total_domains: int,
    high_value: list[dict[str, Any]],
    moderate_value: list[dict[str, Any]],
    source_map: dict[str, Source],
) -> None:
    """Write recommendations markdown report."""
    md_lines = [
        "# Blocklist Recommendations for Pi-hole",
        "",
        "## Overview",
        f"- Total unique domains: {total_domains}",
        f"- Sources analyzed: {len(source_map)}",
        "",
        "## Contribution Analysis",
        "",
    ]

    md_lines.extend([f"### High-Value Sources ({len(high_value)} sources)", ""])
    for contrib in high_value[:20]:
        md_lines.append(f"- **{contrib['name']}** ({contrib['category']})")
        md_lines.append(
            f"  - Unique domains: {contrib['unique']} ({contrib['unique_pct']:.2f}% of total)"
        )
        md_lines.append(f"  - Total domains: {contrib['total']}")
        md_lines.append(f"  - Overlap: {contrib['overlap']:.1%}")
        md_lines.append("")

    md_lines.extend([f"### Moderate-Value Sources ({len(moderate_value)} sources)", ""])
    for contrib in moderate_value[:10]:
        md_lines.append(f"- **{contrib['name']}** ({contrib['category']})")
        md_lines.append(f"  - Unique domains: {contrib['unique']}")
        md_lines.append(f"  - Overlap: {contrib['overlap']:.1%}")
        md_lines.append("")

    # Sort by category and value
    from collections import defaultdict

    by_cat: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for contrib in high_value + moderate_value:
        by_cat[contrib["category"]].append(contrib)

    md_lines.extend(
        [
            "## Load Order Suggestion (Pi-hole GUI / API)",
            "",
            "To minimize overlap and performance impact, load in this order:",
            "",
        ]
    )

    load_order = 1
    for cat in sorted(by_cat.keys()):
        md_lines.append(f"### {cat.title()}")
        md_lines.append("")
        for contrib in sorted(by_cat[cat], key=lambda x: -x["unique"]):
            md_lines.append(f"{load_order}. {contrib['name']}")
            md_lines.append(f"   URL: {contrib['url']}")
            md_lines.append(f"   Unique: {contrib['unique']} | Overlap: {contrib['overlap']:.1%}")
            md_lines.append("")
            load_order += 1

    md_lines.extend(
        [
            "## Notes",
            "",
            "- **Unique domains**: Domains only in this source (not in others).",
            "- **Total domains**: All domains contributed by this source.",
            "- **Overlap**: Fraction of this source's domains shared with other sources.",
            "- Sources with low overlap are more valuable (less redundancy).",
            "- Consider GPU/CPU load when adding many sources; test incrementally.",
            "",
        ]
    )

    output_file.write_text("\n".join(md_lines), encoding="utf-8")


def compute_recommendations(
    dist_dir: Path, settings: Settings, output_file: Path | None = None
) -> dict[str, Any]:
    """Compute marginal contribution and overlap per source.

    Generates dist/reports/recommend.md with:
    - Marginal dominios (unique to each source)
    - Overlap (shared with others)
    - Suggestion score (combined metric)
    - Ranked list of sources to load in Pi-hole by country/profile

    Returns summary dict and writes markdown report.
    """
    aggregates, marginal_data = _load_aggregates_and_marginal(dist_dir)

    if aggregates is None or marginal_data is None:
        return {"error": "No provenance_aggregates.json found. Run build first."}

    source_map = {s.id: s for s in settings.sources}
    total_domains = int(aggregates.get("total_unique", 0))

    # Compute metrics
    metrics = _compute_source_metrics(aggregates, source_map, marginal_data)

    # Categorize contributions
    high_value, moderate_value, low_value = _categorize_contributions(
        metrics, source_map, total_domains
    )

    # Write report
    output_file = output_file or (dist_dir / "reports" / "recommend.md")
    _write_recommend_report(output_file, total_domains, high_value, moderate_value, source_map)

    return {
        "total_domains": total_domains,
        "high_value_sources": len(high_value),
        "moderate_value_sources": len(moderate_value),
        "low_value_sources": len(low_value),
        "output_file": str(output_file),
        "top_sources": [s["id"] for s in high_value[:5]],
    }
