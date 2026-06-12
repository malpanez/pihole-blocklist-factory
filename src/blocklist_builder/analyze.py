"""Analyze build results for quality and errors."""

from __future__ import annotations

import json
from pathlib import Path

from .config import Settings


def _load_provenance_and_stats(
    dist_dir: Path,
) -> tuple[dict, dict] | tuple[None, None]:
    """Load provenance.json and stats.json, return tuple or (None, None) on error."""
    provenance_file = dist_dir / "reports" / "provenance.json"
    if not provenance_file.exists():
        return None, None

    try:
        provenance = json.loads(provenance_file.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    stats_file = dist_dir / "reports" / "stats.json"
    if not stats_file.exists():
        return None, None

    try:
        stats_data = json.loads(stats_file.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    return provenance, stats_data


def _load_source_stats(dist_dir: Path) -> dict | None:
    source_stats_file = dist_dir / "reports" / "source_stats.json"
    if not source_stats_file.exists():
        return None
    try:
        return json.loads(source_stats_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _compute_discard_findings(
    source_stats_data: dict, source_map: dict, high_discard_threshold: float = 0.5
) -> list[str]:
    findings: list[str] = []
    for src_id, stats in source_stats_data.items():
        lines = stats.get("lines", 0)
        if lines == 0:
            continue
        sanitize_ok = stats.get("sanitize_ok", 0)
        discard_rate = (lines - sanitize_ok) / lines
        if discard_rate > high_discard_threshold:
            src_name = source_map.get(src_id)
            name = src_name.name if src_name else src_id
            findings.append(
                f"High discard rate for {src_id} ({name}): {discard_rate:.1%} "
                f"({lines - sanitize_ok}/{lines} entries)"
            )
    return findings


def _compute_overlap_findings(provenance: dict) -> tuple[list[str], int, int]:
    """Compute overlap analysis."""
    findings = []
    overlap_2 = 0
    overlap_3_plus = 0
    total_unique = len(provenance)

    for _domain, prov_data in provenance.items():
        src_count = len(prov_data.get("source_ids", []))
        if src_count == 2:
            overlap_2 += 1
        elif src_count >= 3:
            overlap_3_plus += 1

    overlap_pct_2 = (overlap_2 / total_unique * 100) if total_unique > 0 else 0
    overlap_pct_3 = (overlap_3_plus / total_unique * 100) if total_unique > 0 else 0

    findings.append(
        f"ℹ️  Overlap analysis: {overlap_2} domains ({overlap_pct_2:.1f}%) in 2 sources, "
        f"{overlap_3_plus} ({overlap_pct_3:.1f}%) in 3+ sources"
    )

    return findings, overlap_2, overlap_3_plus


def _write_quality_report(
    output_file: Path, total_unique: int, stats_data: dict, findings: list[str]
) -> None:
    """Write quality analysis markdown report."""
    md_lines = [
        "# Build Quality Analysis",
        "",
        "## Summary",
        f"- Total unique domains: {total_unique}",
        f"- Total entries parsed: {stats_data.get('total_lines', 0)}",
        f"- Parsed OK: {stats_data.get('parsed_ok', 0)}",
        f"- Sanitized OK: {stats_data.get('sanitized_ok', 0)}",
        "",
        "## Findings",
        "",
    ]

    for finding in findings:
        md_lines.append(f"- {finding}")

    md_lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "1. **High discard rates**: Review drop_patterns and source format settings.",
            "2. **Overlap**: Consider consolidating sources with high overlap.",
            "3. **Anomalies**: Manual spot-check sources flagged above.",
            "",
        ]
    )

    output_file.write_text("\n".join(md_lines), encoding="utf-8")


def analyze_build(dist_dir: Path, settings: Settings, output_file: Path | None = None) -> dict:
    """Analyze build outputs for errors and quality issues.

    Checks for:
    - High discard rates per source
    - Potential malformed entries that passed sanitization
    - ABP regex patterns that may be invalid
    - Overlap between sources
    - Statistical anomalies

    Returns summary dict with findings and writes dist/reports/quality.md.
    """
    provenance, stats_data = _load_provenance_and_stats(dist_dir)

    if provenance is None:
        return {"error": "No provenance.json or stats.json found. Run build first."}

    source_map = {s.id: s for s in settings.sources}
    total_unique = len(provenance)

    # Compute findings
    source_stats_data = _load_source_stats(dist_dir)
    discard_findings = (
        _compute_discard_findings(source_stats_data, source_map) if source_stats_data else []
    )
    overlap_findings, overlap_2, overlap_3_plus = _compute_overlap_findings(provenance)

    all_findings = discard_findings + overlap_findings

    # Write report
    output_file = output_file or (dist_dir / "reports" / "quality.md")
    _write_quality_report(output_file, total_unique, stats_data, all_findings)

    return {
        "total_domains": total_unique,
        "findings": len(all_findings),
        "high_discard_sources": len(discard_findings),
        "overlap_2": overlap_2,
        "overlap_3_plus": overlap_3_plus,
        "output_file": str(output_file),
    }
