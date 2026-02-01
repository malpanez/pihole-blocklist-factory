from __future__ import annotations

from pathlib import Path

from blocklist_builder.report import Stats, write_reports


def test_write_reports_creates_files(tmp_path: Path) -> None:
    stats = Stats(
        total_lines=10,
        parsed_ok=7,
        sanitized_ok=6,
        unique_domains=5,
        discarded={"parse_comment": 1, "sanitize_ip": 1, "parse_empty": 1},
    )

    write_reports(tmp_path, stats)

    stats_json = (tmp_path / "stats.json").read_text(encoding="utf-8")
    stats_md = (tmp_path / "stats.md").read_text(encoding="utf-8")

    assert '"total_lines": 10' in stats_json
    assert "Build statistics" in stats_md
    assert "Total líneas leídas: 10" in stats_md
