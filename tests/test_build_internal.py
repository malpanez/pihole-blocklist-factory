from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

import blocklist_builder.build as build_mod
from blocklist_builder.config import Policies, ProfilesConfig, Settings
from blocklist_builder.types import Profile, Source


def _settings_for(tmp_path: Path, sources: list[Source]) -> Settings:
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
    return Settings(sources=sources, policies=policies, profiles=profiles)


def test_read_overrides_ignores_comments(tmp_path: Path) -> None:
    path = tmp_path / "allowlist.txt"
    path.write_text("# comment\nExample.COM.\n\n", encoding="utf-8")
    out = build_mod._read_overrides(path)
    assert "example.com" in out


def test_load_drop_patterns_invalid_regex(tmp_path: Path) -> None:
    path = tmp_path / "drop_patterns.txt"
    path.write_text("(\n^skip\\.me$\n", encoding="utf-8")
    patterns = build_mod._load_drop_patterns(path)
    assert len(patterns) == 1
    assert patterns[0].pattern == "^skip\\.me$"


def test_resolve_all_source_paths_fetch_mode(monkeypatch, tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.txt"
    cache_file.write_text("example.com\n", encoding="utf-8")

    def fake_parallel_fetch(sources, cache_dir, no_fetch=False, timeout_s=30, repo_root=None):
        return {src.id: (cache_file if src.id == "s1" else None) for src in sources}

    monkeypatch.setattr(build_mod, "parallel_fetch_sources", fake_parallel_fetch)

    ok = Source(id="s1", name="s1", category="advertising", url="https://example.com/a.txt")
    failed = Source(id="s2", name="s2", category="advertising", url="https://example.com/b.txt")
    settings = _settings_for(tmp_path, [ok, failed])
    discarded = Counter()
    source_stats: dict[str, dict[str, int]] = {}
    result = build_mod._resolve_all_source_paths(
        settings,
        no_fetch=False,
        cache_dir=tmp_path,
        discarded=discarded,
        source_stats=source_stats,
    )
    assert result == {"s1": cache_file}
    assert discarded["source_missing"] == 1
    assert source_stats["s2"]["source_missing"] == 1


def test_resolve_all_source_paths_skips_disabled(tmp_path: Path) -> None:
    source = tmp_path / "s1.txt"
    source.write_text("example.com\n", encoding="utf-8")
    enabled = Source(id="s1", name="s1", category="advertising", url=str(source))
    disabled = Source(id="s2", name="s2", category="advertising", url="x", enabled=False)
    settings = _settings_for(tmp_path, [enabled, disabled])
    discarded = Counter()
    source_stats: dict[str, dict[str, int]] = {}
    result = build_mod._resolve_all_source_paths(
        settings,
        no_fetch=True,
        cache_dir=tmp_path,
        discarded=discarded,
        source_stats=source_stats,
        repo_root=tmp_path,
    )
    assert "s1" in result
    assert "s2" not in result


def test_resolve_all_source_paths_missing_source(tmp_path: Path) -> None:
    missing = Source(id="s1", name="s1", category="advertising", url=str(tmp_path / "nope.txt"))
    settings = _settings_for(tmp_path, [missing])
    discarded = Counter()
    source_stats: dict[str, dict[str, int]] = {}
    result = build_mod._resolve_all_source_paths(
        settings,
        no_fetch=True,
        cache_dir=tmp_path,
        discarded=discarded,
        source_stats=source_stats,
        repo_root=tmp_path,
    )
    assert "s1" not in result
    assert discarded["source_missing"] == 1
    assert source_stats["s1"]["source_missing"] == 1


def test_write_profiles_include_categories(tmp_path: Path) -> None:
    profiles = ProfilesConfig(
        by_name={"ads_only": Profile(name="ads_only", include_categories={"advertising"})}
    )
    settings = Settings(
        sources=[],
        policies=Policies(
            category_precedence=["advertising"],
            core_domains=set(),
            base_allowlist=set(),
        ),
        profiles=profiles,
    )
    chosen = {"a.com": "advertising", "b.com": "tracking"}
    (tmp_path / "profiles").mkdir(parents=True, exist_ok=True)
    build_mod._write_profiles(tmp_path, chosen, settings)
    out = (tmp_path / "profiles" / "ads_only.txt").read_text(encoding="utf-8")
    assert "a.com" in out
    assert "b.com" not in out


def test_collect_domains_skips_disabled(tmp_path: Path) -> None:
    enabled = Source(id="s1", name="s1", category="advertising", url=str(tmp_path / "s1.txt"))
    disabled = Source(id="s2", name="s2", category="advertising", url="x", enabled=False)
    (tmp_path / "s1.txt").write_text("example.com\n", encoding="utf-8")
    settings = _settings_for(tmp_path, [enabled, disabled])
    discarded = Counter()
    source_stats: dict[str, dict[str, int]] = {}
    cats, sources = build_mod._collect_domains(
        settings,
        no_fetch=True,
        cache_dir=tmp_path,
        drop_patterns=[],
        allow=frozenset(),
        discarded=discarded,
        source_stats=source_stats,
        repo_root=tmp_path,
    )
    assert "example.com" in cats
    assert "s2" not in source_stats


def test_build_rejects_local_source_outside_repo_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside" / "list.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("example.com\n", encoding="utf-8")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    escapee = Source(id="esc", name="esc", category="advertising", url=str(outside))
    settings = _settings_for(repo_root, [escapee])
    stats = build_mod.build(repo_root, settings, no_fetch=True)
    assert stats.discarded["source_missing"] == 1
    assert stats.unique_domains == 0


def test_add_deny_extras(tmp_path: Path) -> None:
    from collections import defaultdict

    domain_to_categories: dict[str, set[str]] = defaultdict(set)
    build_mod._add_deny_extras(domain_to_categories, frozenset({"Example.com.", "bad"}))
    assert "example.com" in domain_to_categories


def test_write_provenance_streamed(tmp_path: Path) -> None:
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    domain_to_sources = {
        "a.com": {"s1"},
        "b.com": {"s1", "s2"},
        "c.com": {"s1", "s2", "s3"},
    }
    source_map = {
        "s1": Source(id="s1", name="s1", category="advertising", url="x"),
        "s2": Source(id="s2", name="s2", category="tracking", url="y"),
        "s3": Source(id="s3", name="s3", category="malicious", url="z"),
    }
    per_source = build_mod._write_provenance_streamed(
        tmp_path, domain_to_sources, source_map, ["malicious", "tracking", "advertising"]
    )

    with gzip.open(tmp_path / "reports" / "provenance.jsonl.gz", "rt", encoding="utf-8") as f:
        records = [json.loads(line) for line in f]
    by_domain = {r["domain"]: r for r in records}
    assert by_domain["a.com"]["source_ids"] == ["s1"]
    assert by_domain["a.com"]["assigned"] == "advertising"
    assert by_domain["b.com"]["assigned"] == "tracking"
    assert by_domain["c.com"]["assigned"] == "malicious"
    assert by_domain["c.com"]["categories"] == ["advertising", "malicious", "tracking"]

    aggregates = json.loads(
        (tmp_path / "reports" / "provenance_aggregates.json").read_text(encoding="utf-8")
    )
    assert aggregates["total_unique"] == 3
    assert aggregates["overlap_2"] == 1
    assert aggregates["overlap_3_plus"] == 1
    assert aggregates["per_source"]["s1"] == {"total_contributions": 3, "unique_domains": 1}
    assert aggregates["per_source"]["s2"] == {"total_contributions": 2, "unique_domains": 0}
    assert per_source == aggregates["per_source"]


def test_write_provenance_streamed_error(tmp_path: Path, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(build_mod.gzip, "open", boom)
    build_mod._write_provenance_streamed(
        tmp_path,
        {"a.com": {"s1"}},
        {"s1": Source(id="s1", name="s1", category="advertising", url="x")},
        ["advertising"],
    )


def test_write_source_stats_empty_and_error(tmp_path: Path, monkeypatch) -> None:
    build_mod._write_source_stats(tmp_path, {})
    assert not (tmp_path / "reports" / "source_stats.json").exists()

    def boom(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "write_text", boom)
    build_mod._write_source_stats(tmp_path, {"s1": {"lines": 1}})


def test_write_marginal_single_pass(tmp_path: Path) -> None:
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    domain_to_sources = {
        "a.com": {"s1"},
        "b.com": {"s1", "s2"},
        "c.com": {"s2"},
        "d.com": {"s2"},
        "e.com": {"unknown"},
    }
    source_map = {
        "s1": Source(id="s1", name="s1", category="advertising", url="x"),
        "s2": Source(id="s2", name="s2", category="tracking", url="y"),
        "s3": Source(id="s3", name="s3", category="malicious", url="z"),
    }
    build_mod._write_marginal(tmp_path, domain_to_sources, source_map)
    marginal = json.loads((tmp_path / "reports" / "marginal.json").read_text(encoding="utf-8"))
    assert marginal == {"s1": 1, "s2": 2, "s3": 0}


def test_write_marginal_error(tmp_path: Path, monkeypatch) -> None:
    def boom(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "write_text", boom)
    build_mod._write_marginal(
        tmp_path,
        {"a.com": {"s1"}},
        {"s1": Source(id="s1", name="s1", category="advertising", url="x")},
    )


def test_write_allowlist_empty(tmp_path: Path) -> None:
    build_mod._write_allowlist(tmp_path, frozenset(), frozenset())
    assert not (tmp_path / "allowlist.txt").exists()
