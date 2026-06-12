from __future__ import annotations

import json
from pathlib import Path

from blocklist_builder.analyze import (
    _compute_discard_findings,
    _load_source_stats,
    analyze_build,
)
from blocklist_builder.config import Policies, ProfilesConfig, Settings
from blocklist_builder.types import Profile, Source


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _settings() -> Settings:
    policies = Policies(
        category_precedence=[
            "advertising",
            "tracking",
            "malicious",
            "suspicious",
            "other",
            "telemetry",
        ],
        core_domains=set(),
        base_allowlist=set(),
    )
    profiles = ProfilesConfig(by_name={"default": Profile(name="default")})
    sources = [
        Source(id="s1", name="S1", category="advertising", url="x"),
        Source(id="s2", name="S2", category="tracking", url="y"),
    ]
    return Settings(sources=sources, policies=policies, profiles=profiles)


def test_analyze_build_reports(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    provenance = {
        "a.example": {
            "source_ids": ["s1"],
            "categories": ["advertising"],
            "assigned": "advertising",
        },
        "b.example": {
            "source_ids": ["s1", "s2"],
            "categories": ["advertising", "tracking"],
            "assigned": "tracking",
        },
        "c.example": {
            "source_ids": ["s1", "s2", "s3"],
            "categories": ["advertising"],
            "assigned": "advertising",
        },
    }
    stats = {"total_lines": 10, "parsed_ok": 8, "sanitized_ok": 7}

    _write(dist_dir / "reports" / "provenance.json", json.dumps(provenance))
    _write(dist_dir / "reports" / "stats.json", json.dumps(stats))

    result = analyze_build(dist_dir, _settings())
    assert result["total_domains"] == 3
    assert result["overlap_2"] == 1
    assert result["overlap_3_plus"] == 1
    assert (dist_dir / "reports" / "quality.md").exists()


def test_analyze_build_missing_reports(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    result = analyze_build(dist_dir, _settings())
    assert "error" in result


def test_analyze_build_invalid_json(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    (dist_dir / "reports").mkdir(parents=True, exist_ok=True)
    (dist_dir / "reports" / "provenance.json").write_text("{", encoding="utf-8")
    (dist_dir / "reports" / "stats.json").write_text("{", encoding="utf-8")
    result = analyze_build(dist_dir, _settings())
    assert "error" in result


def test_analyze_build_missing_stats(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    (dist_dir / "reports").mkdir(parents=True, exist_ok=True)
    (dist_dir / "reports" / "provenance.json").write_text("{}", encoding="utf-8")
    result = analyze_build(dist_dir, _settings())
    assert "error" in result


def test_analyze_build_invalid_stats(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    (dist_dir / "reports").mkdir(parents=True, exist_ok=True)
    (dist_dir / "reports" / "provenance.json").write_text("{}", encoding="utf-8")
    (dist_dir / "reports" / "stats.json").write_text("{", encoding="utf-8")
    result = analyze_build(dist_dir, _settings())
    assert "error" in result


def test_compute_discard_findings_fires() -> None:
    source_stats = {
        "s1": {"lines": 100, "parse_ok": 100, "sanitize_ok": 40, "sanitize_ip": 60},
        "s2": {"lines": 100, "parse_ok": 100, "sanitize_ok": 95},
    }
    source_map = {
        "s1": Source(id="s1", name="Source One", category="advertising", url="x"),
        "s2": Source(id="s2", name="Source Two", category="tracking", url="y"),
    }
    findings = _compute_discard_findings(source_stats, source_map, high_discard_threshold=0.5)
    assert len(findings) == 1
    assert "s1" in findings[0]
    assert "60.0%" in findings[0]


def test_compute_discard_findings_no_finding() -> None:
    source_stats = {
        "s1": {"lines": 100, "parse_ok": 100, "sanitize_ok": 95},
    }
    source_map = {
        "s1": Source(id="s1", name="Source One", category="advertising", url="x"),
    }
    findings = _compute_discard_findings(source_stats, source_map, high_discard_threshold=0.5)
    assert len(findings) == 0


def test_compute_discard_findings_zero_lines() -> None:
    source_stats = {"s1": {"lines": 0, "sanitize_ok": 0}}
    findings = _compute_discard_findings(source_stats, {}, high_discard_threshold=0.5)
    assert len(findings) == 0


def test_compute_discard_findings_source_not_in_map() -> None:
    source_stats = {"unknown_src": {"lines": 100, "sanitize_ok": 10}}
    findings = _compute_discard_findings(source_stats, {}, high_discard_threshold=0.5)
    assert len(findings) == 1
    assert "unknown_src" in findings[0]


def test_load_source_stats_missing(tmp_path: Path) -> None:
    result = _load_source_stats(tmp_path / "nonexistent")
    assert result is None


def test_load_source_stats_valid(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    data = {"s1": {"lines": 50, "sanitize_ok": 40}}
    (reports / "source_stats.json").write_text(json.dumps(data), encoding="utf-8")
    result = _load_source_stats(tmp_path)
    assert result == data


def test_load_source_stats_invalid_json(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    (reports / "source_stats.json").write_text("{bad", encoding="utf-8")
    result = _load_source_stats(tmp_path)
    assert result is None
