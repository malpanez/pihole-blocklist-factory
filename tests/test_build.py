from __future__ import annotations

import json
from pathlib import Path

from blocklist_builder.build import build
from blocklist_builder.config import Policies, ProfilesConfig, Settings
from blocklist_builder.types import Profile, Source


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


def test_build_writes_stats_and_source_stats(tmp_path: Path) -> None:
    repo_root = tmp_path

    source1 = repo_root / "inputs" / "source1.txt"
    source2 = repo_root / "inputs" / "source2.txt"

    _write(
        source1,
        "\n".join(
            [
                "# comment",
                "",
                "0.0.0.0 ads.example.com",
                "0.0.0.0 1.2.3.4",
                "||tracker.example.net^",
                "foo-.bar.com",
                "badline",
                "example.com",
                "0.0.0.0 bad",
                "0.0.0.0 test.example.com",
            ]
        )
        + "\n",
    )
    _write(
        source2,
        "\n".join(
            [
                "0.0.0.0 test.example.com",
                "example.org",
                "0.0.0.0 5.6.7.8",
                "||ads.example.com^",
                "weird^line",
            ]
        )
        + "\n",
    )

    allowlist = repo_root / "inputs" / "current_overrides" / "allowlist.txt"
    _write(allowlist, "ads.example.com\n")

    settings = _settings_for(
        repo_root,
        sources=[
            Source(
                id="src1",
                name="src1",
                category="advertising",
                url=str(source1),
                enabled=True,
            ),
            Source(
                id="src2",
                name="src2",
                category="advertising",
                url=str(source2),
                enabled=True,
            ),
        ],
    )

    stats = build(repo_root, settings, no_fetch=True)

    assert stats.unique_domains == 4
    assert stats.parsed_ok == 11
    assert stats.sanitized_ok == 7
    assert stats.discarded["parse_comment"] == 1
    assert stats.discarded["parse_empty"] == 1
    assert stats.discarded["parse_unsupported"] == 2
    assert stats.discarded["sanitize_ip"] == 2
    assert stats.discarded["sanitize_not_fqdn"] == 1
    assert stats.discarded["sanitize_single_label"] == 1
    assert stats.discarded["allowlisted"] == 2
    assert stats.total_lines == 15
    assert "parse_ok" not in stats.discarded
    assert "sanitize_ok" not in stats.discarded

    all_txt = (repo_root / "dist" / "all.txt").read_text(encoding="utf-8").splitlines()
    assert set(all_txt) == {
        "example.com",
        "example.org",
        "test.example.com",
        "tracker.example.net",
    }

    allowlist_txt = (repo_root / "dist" / "allowlist.txt").read_text(encoding="utf-8")
    assert "ads.example.com" in allowlist_txt

    assert (repo_root / "dist" / "reports" / "provenance.jsonl.gz").exists()
    aggregates = json.loads(
        (repo_root / "dist" / "reports" / "provenance_aggregates.json").read_text(encoding="utf-8")
    )
    assert aggregates["total_unique"] == 4
    assert set(aggregates["per_source"]) == {"src1", "src2"}

    source_stats_path = repo_root / "dist" / "reports" / "source_stats.json"
    source_stats = json.loads(source_stats_path.read_text(encoding="utf-8"))
    assert source_stats["src1"]["lines"] == 10
    assert source_stats["src2"]["lines"] == 5
    assert source_stats["src1"]["parse_ok"] == 7
    assert source_stats["src2"]["parse_ok"] == 4
    assert source_stats["src1"]["sanitize_ok"] == 4
    assert source_stats["src2"]["sanitize_ok"] == 3
    assert source_stats["src1"]["allowlisted"] == 1
    assert source_stats["src2"]["allowlisted"] == 1


def test_build_source_missing_and_drop_patterns(tmp_path: Path) -> None:
    repo_root = tmp_path
    source1 = repo_root / "inputs" / "source1.txt"
    _write(source1, "example.com\nskip.me\n")

    overrides = repo_root / "inputs" / "current_overrides"
    _write(
        overrides / "drop_patterns.txt",
        "\n".join(
            [
                "# comment",
                "(",
                "^skip\\.me$",
            ]
        )
        + "\n",
    )

    settings = _settings_for(
        repo_root,
        sources=[
            Source(
                id="src1",
                name="src1",
                category="advertising",
                url=str(source1),
                enabled=True,
            ),
            Source(
                id="missing",
                name="missing",
                category="advertising",
                url=str(repo_root / "inputs" / "missing.txt"),
                enabled=True,
            ),
        ],
    )

    stats = build(repo_root, settings, no_fetch=True)
    assert stats.discarded["source_missing"] == 1
    assert stats.discarded["parse_pattern_drop"] == 1


def test_build_file_traversal_rejected(tmp_path: Path) -> None:
    repo_root = tmp_path
    settings = _settings_for(
        repo_root,
        sources=[
            Source(
                id="trav",
                name="trav",
                category="advertising",
                url="file:///tmp/../etc/passwd",
                enabled=True,
            )
        ],
    )
    stats = build(repo_root, settings, no_fetch=True)
    assert stats.discarded["source_missing"] == 1


def test_build_http_emits_warning(tmp_path: Path, caplog) -> None:
    import logging

    repo_root = tmp_path
    settings = _settings_for(
        repo_root,
        sources=[
            Source(
                id="insecure",
                name="insecure",
                category="advertising",
                url="http://example.com/list.txt",
                enabled=True,
            )
        ],
    )
    with caplog.at_level(logging.WARNING):
        stats = build(repo_root, settings, no_fetch=True)
    assert any("http://" in r.message for r in caplog.records)
    assert stats.discarded["source_missing"] == 1


def test_build_debug_log(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    source1 = repo_root / "inputs" / "source1.txt"
    _write(source1, "example.com\n")

    settings = _settings_for(
        repo_root,
        sources=[
            Source(
                id="src1",
                name="src1",
                category="advertising",
                url=str(source1),
                enabled=True,
            )
        ],
    )

    monkeypatch.setenv("BLOCKLIST_DEBUG", "1")
    build(repo_root, settings, no_fetch=True)

    debug_log = (repo_root / "dist" / "reports" / "debug.log").read_text(encoding="utf-8")
    assert "src1:" in debug_log
