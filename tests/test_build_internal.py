from __future__ import annotations

from collections import Counter
from pathlib import Path

import blocklist_builder.build as build_mod
from blocklist_builder.config import Policies, ProfilesConfig, Settings
from blocklist_builder.types import Profile, Provenance, Source


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
        sensitive_domains=set(),
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


def test_resolve_source_path_file_url(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("example.com\n", encoding="utf-8")

    class S:
        def __init__(self, url: str, id: str = "s1") -> None:
            self.url = url
            self.id = id

    src = S(f"file://{source}")
    out = build_mod._resolve_source_path(src, no_fetch=True, cache_dir=tmp_path)
    assert out == source


def test_resolve_source_path_local_no_fetch(tmp_path: Path) -> None:
    source = tmp_path / "list2.txt"
    source.write_text("example.com\n", encoding="utf-8")

    class S:
        def __init__(self, url: str, id: str = "s1") -> None:
            self.url = url
            self.id = id

    src = S(str(source))
    out = build_mod._resolve_source_path(src, no_fetch=True, cache_dir=tmp_path)
    assert out == source


def test_resolve_source_path_fetch(monkeypatch, tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.txt"

    def fake_fetch(url: str, cache_dir: Path, source_id: str = "s1"):
        cache_file.write_text("example.com\n", encoding="utf-8")
        return cache_file, None

    monkeypatch.setattr(build_mod, "fetch_to_cache", fake_fetch)

    class S:
        def __init__(self, url: str, id: str = "s1") -> None:
            self.url = url
            self.id = id

    src = S("http://example.com/list.txt")
    out = build_mod._resolve_source_path(src, no_fetch=False, cache_dir=tmp_path)
    assert out == cache_file


def test_process_parsed_lines_parallel(monkeypatch) -> None:
    def fake_parallel(lines, drop_patterns=None):
        return ["a.com"], {"parse_comment": 1}, 2, 1

    monkeypatch.setattr(build_mod, "parallel_parse_and_sanitize", fake_parallel)
    discarded = Counter()
    source_stats: dict[str, int] = {}

    out = list(
        build_mod._process_parsed_lines(
            "s1",
            ["# comment", "a.com"],
            drop_patterns=[],
            use_parallel=True,
            src_category="advertising",
            discarded=discarded,
            source_stats=source_stats,
        )
    )
    assert out == [("a.com", "advertising", "s1", "ok")]
    assert discarded["parse_comment"] == 1
    assert discarded["parse_ok"] == 2
    assert discarded["sanitize_ok"] == 1
    assert source_stats["parse_comment"] == 1


def test_process_source_disabled(tmp_path: Path) -> None:
    class S:
        def __init__(self) -> None:
            self.enabled = False
            self.url = "x"
            self.id = "s1"
            self.category = "advertising"

    out = list(
        build_mod._process_source(
            S(),
            no_fetch=True,
            cache_dir=tmp_path,
            drop_patterns=[],
            discarded=Counter(),
            source_stats={},
        )
    )
    assert out == []


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
            sensitive_domains=set(),
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
    )
    assert "example.com" in cats
    assert "s2" not in source_stats


def test_add_deny_extras(tmp_path: Path) -> None:
    from collections import defaultdict

    domain_to_categories: dict[str, set[str]] = defaultdict(set)
    build_mod._add_deny_extras(domain_to_categories, frozenset({"Example.com.", "bad"}))
    assert "example.com" in domain_to_categories


def test_write_provenance_error(tmp_path: Path, monkeypatch) -> None:
    def boom(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "write_text", boom)
    prov = {
        "a.com": Provenance("a.com", frozenset({"s1"}), frozenset({"advertising"}), "advertising")
    }
    build_mod._write_provenance(tmp_path, prov)


def test_write_source_stats_empty_and_error(tmp_path: Path, monkeypatch) -> None:
    build_mod._write_source_stats(tmp_path, {})
    assert not (tmp_path / "reports" / "source_stats.json").exists()

    def boom(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(Path, "write_text", boom)
    build_mod._write_source_stats(tmp_path, {"s1": {"lines": 1}})


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
