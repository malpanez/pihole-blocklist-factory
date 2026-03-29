from __future__ import annotations

import json
from pathlib import Path

from blocklist_builder.analyze import analyze_build
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


def test_compute_discard_findings_triggers(monkeypatch) -> None:
    import blocklist_builder.analyze as analyze_mod

    class FakeDefaultDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def __missing__(self, key):
            val = {"sanitized_ok": 0, "discarded": 2}
            self[key] = val
            return val

    monkeypatch.setattr(analyze_mod, "defaultdict", lambda factory: FakeDefaultDict())
    provenance = {"a.com": {"source_ids": ["s1"]}}
    source_map = {"s1": type("S", (), {"name": "S1"})()}
    findings = analyze_mod._compute_discard_findings(
        provenance, source_map, high_discard_threshold=0.5
    )
    assert findings
