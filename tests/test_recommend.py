from __future__ import annotations

import json
from pathlib import Path

from blocklist_builder.config import Policies, ProfilesConfig, Settings
from blocklist_builder.recommend import compute_recommendations
from blocklist_builder.types import Profile, Source


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _settings() -> Settings:
    policies = Policies(
        category_precedence=["advertising", "tracking", "malicious", "suspicious", "other", "telemetry"],
        core_domains=set(),
        base_allowlist=set(),
        sensitive_domains=set(),
    )
    profiles = ProfilesConfig(by_name={"default": Profile(name="default")})
    sources = [
        Source(id="s1", name="S1", category="advertising", url="u1"),
        Source(id="s2", name="S2", category="tracking", url="u2"),
    ]
    return Settings(sources=sources, policies=policies, profiles=profiles)


def test_compute_recommendations_success(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    provenance = {
        "a.example": {"source_ids": ["s1"], "categories": ["advertising"], "assigned": "advertising"},
        "b.example": {"source_ids": ["s1", "s2"], "categories": ["advertising", "tracking"], "assigned": "tracking"},
        "c.example": {"source_ids": ["s2"], "categories": ["tracking"], "assigned": "tracking"},
    }
    marginal = {"s1": 1, "s2": 1}

    _write(dist_dir / "reports" / "provenance.json", json.dumps(provenance))
    _write(dist_dir / "reports" / "marginal.json", json.dumps(marginal))

    result = compute_recommendations(dist_dir, _settings())
    assert result["total_domains"] == 3
    assert result["high_value_sources"] + result["moderate_value_sources"] + result["low_value_sources"] == 2
    assert (dist_dir / "reports" / "recommend.md").exists()


def test_compute_recommendations_missing(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    result = compute_recommendations(dist_dir, _settings())
    assert "error" in result


def test_compute_recommendations_invalid_provenance(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    (dist_dir / "reports").mkdir(parents=True, exist_ok=True)
    (dist_dir / "reports" / "provenance.json").write_text("{", encoding="utf-8")
    result = compute_recommendations(dist_dir, _settings())
    assert "error" in result


def test_compute_recommendations_no_marginal(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    provenance = {
        "a.example": {"source_ids": ["s1"], "categories": ["advertising"], "assigned": "advertising"},
    }
    _write(dist_dir / "reports" / "provenance.json", json.dumps(provenance))
    result = compute_recommendations(dist_dir, _settings())
    assert result["total_domains"] == 1


def test_compute_recommendations_moderate_and_low(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    provenance = {}
    # Total domains = 1000
    for i in range(997):
        provenance[f"shared-{i}.com"] = {
            "source_ids": ["s1", "s2"],
            "categories": ["advertising", "tracking"],
            "assigned": "tracking",
        }
    provenance["unique-s1-1.com"] = {
        "source_ids": ["s1"],
        "categories": ["advertising"],
        "assigned": "advertising",
    }
    provenance["unique-s1-2.com"] = {
        "source_ids": ["s1"],
        "categories": ["advertising"],
        "assigned": "advertising",
    }
    provenance["unique-s2-1.com"] = {
        "source_ids": ["s2"],
        "categories": ["tracking"],
        "assigned": "tracking",
    }

    _write(dist_dir / "reports" / "provenance.json", json.dumps(provenance))
    _write(dist_dir / "reports" / "marginal.json", json.dumps({"s1": 2, "s2": 1}))

    result = compute_recommendations(dist_dir, _settings())
    assert result["moderate_value_sources"] >= 1
    assert result["low_value_sources"] >= 1
