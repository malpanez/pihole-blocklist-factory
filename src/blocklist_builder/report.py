from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

# Report file constants
_STATS_JSON_FILE: Final = "stats.json"
_STATS_MD_FILE: Final = "stats.md"
_ENCODING: Final = "utf-8"


@dataclass(frozen=True, slots=True)
class Stats:
    total_lines: int
    parsed_ok: int
    sanitized_ok: int
    unique_domains: int
    discarded: dict[str, int]


def _generate_stats_markdown(stats: Stats) -> str:
    """Generate human-readable statistics markdown."""
    md_lines = [
        "# Build statistics",
        "",
        "## Summary",
        f"- Total líneas leídas: {stats.total_lines}",
        f"- Parse OK: {stats.parsed_ok}",
        f"- Sanitized OK: {stats.sanitized_ok}",
        f"- Dominios únicos finales: {stats.unique_domains}",
        "",
        "## Detalles de descartes",
    ]

    # Sort by count descending, then by name
    sorted_discards = sorted(stats.discarded.items(), key=lambda x: (-x[1], x[0]))
    for reason, count in sorted_discards:
        md_lines.append(f"- {reason}: {count}")

    return "\n".join(md_lines) + "\n"


def write_reports(dist_reports_dir: Path, stats: Stats) -> None:
    """Write comprehensive reports in multiple formats.

    Generates:
      - stats.json: Machine-readable stats
      - stats.md: Human-readable summary
    """
    dist_reports_dir.mkdir(parents=True, exist_ok=True)

    # stats.json
    (dist_reports_dir / _STATS_JSON_FILE).write_text(
        json.dumps(asdict(stats), indent=2), encoding=_ENCODING
    )

    # stats.md
    (dist_reports_dir / _STATS_MD_FILE).write_text(
        _generate_stats_markdown(stats), encoding=_ENCODING
    )
