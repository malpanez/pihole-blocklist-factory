from __future__ import annotations

import importlib
from pathlib import Path

import blocklist_builder.config as config_mod


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_settings_merges_sources(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    _write(
        config_dir / "sources.yml",
        "\n".join(
            [
                "sources:",
                "  - id: s1",
                "    name: S1",
                "    category: advertising",
                "    url: inputs/s1.txt",
                "    enabled: true",
            ]
        )
        + "\n",
    )
    _write(
        config_dir / "sources.firebog.yml",
        "\n".join(
            [
                "sources:",
                "  - id: s2",
                "    name: S2",
                "    category: tracking",
                "    url: inputs/s2.txt",
                "    enabled: true",
            ]
        )
        + "\n",
    )
    _write(
        config_dir / "sources.local.yml",
        "\n".join(
            [
                "sources:",
                "  - id: s1",
                "    name: S1-override",
                "    category: other",
                "    url: inputs/s1-local.txt",
                "    enabled: true",
            ]
        )
        + "\n",
    )
    _write(
        config_dir / "policies.yml",
        "\n".join(
            [
                "policies:",
                "  category_precedence: [tracking, advertising]",
                "  core_domains: [core.example]",
                "  base_allowlist: [allow.example]",
            ]
        )
        + "\n",
    )
    _write(
        config_dir / "profiles.yml",
        "\n".join(
            [
                "profiles:",
                "  default:",
                "    include_categories: [advertising]",
            ]
        )
        + "\n",
    )

    settings = config_mod.load_settings(config_dir)
    assert len(settings.sources) == 2
    assert [s.id for s in settings.sources] == ["s1", "s2"]
    assert settings.policies.category_precedence == ["tracking", "advertising"]
    assert "core.example" in settings.policies.core_domains


def test_load_settings_test_mode(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    _write(
        config_dir / "sources.test.yml",
        "\n".join(
            [
                "sources:",
                "  - id: test1",
                "    name: Test1",
                "    category: advertising",
                "    url: inputs/test1.txt",
                "    enabled: true",
            ]
        )
        + "\n",
    )
    _write(config_dir / "policies.yml", "policies: {}\n")
    _write(config_dir / "profiles.yml", "profiles: {}\n")

    monkeypatch.setenv("BLOCKLIST_SOURCES", "test")
    cfg = importlib.reload(config_mod)

    settings = cfg.load_settings(config_dir)
    assert len(settings.sources) == 1
    assert settings.sources[0].id == "test1"

    monkeypatch.delenv("BLOCKLIST_SOURCES", raising=False)
    importlib.reload(config_mod)


def test_read_yaml_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yml"
    data = config_mod._read_yaml(missing)
    assert data == {}
