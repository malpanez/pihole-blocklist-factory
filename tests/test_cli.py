from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
import pytest

import blocklist_builder.cli as cli
from blocklist_builder.report import Stats


def test_cli_build_json(monkeypatch) -> None:
    runner = CliRunner()

    def fake_load_settings(_path: Path):
        return object()

    def fake_build(_root: Path, _settings, no_fetch: bool = False):
        return Stats(
            total_lines=1,
            parsed_ok=1,
            sanitized_ok=1,
            unique_domains=1,
            discarded={},
        )

    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "build", fake_build)

    result = runner.invoke(cli.build_cmd, ["--json"])
    assert result.exit_code == 0
    assert '"unique_domains": 1' in result.output


def test_cli_group_callback() -> None:
    # Covers the no-op group function body.
    assert cli.cli.callback() is None


def test_cli_report_missing_stats(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    def fake_root() -> Path:
        return tmp_path

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    result = runner.invoke(cli.report, [])
    assert result.exit_code == 1
    assert "No build stats found" in result.output


def test_cli_report_success(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    reports_dir = tmp_path / "dist" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "stats.json").write_text(
        '{"total_lines": 1, "parsed_ok": 1, "sanitized_ok": 1, "unique_domains": 1, "discarded": {}}',
        encoding="utf-8",
    )

    def fake_root() -> Path:
        return tmp_path

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    result = runner.invoke(cli.report, [])
    assert result.exit_code == 0
    assert '"unique_domains": 1' in result.output


def test_cli_report_invalid_json(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    reports_dir = tmp_path / "dist" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "stats.json").write_text("{", encoding="utf-8")

    def fake_root() -> Path:
        return tmp_path

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    result = runner.invoke(cli.report, [])
    assert result.exit_code == 1
    assert "Error reading stats" in result.output


def test_cli_analyze_missing_dist(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    def fake_root() -> Path:
        return tmp_path

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    result = runner.invoke(cli.analyze, [])
    assert result.exit_code == 1
    assert "No dist/ found" in result.output


def test_cli_analyze_success(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    def fake_root() -> Path:
        return tmp_path

    def fake_load_settings(_path: Path):
        return object()

    def fake_analyze(_dist_dir: Path, _settings):
        return {
            "total_domains": 10,
            "findings": 1,
            "high_discard_sources": 0,
            "overlap_2": 2,
            "overlap_3_plus": 1,
            "output_file": str(dist_dir / "reports" / "quality.md"),
        }

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "analyze_build", fake_analyze)

    result = runner.invoke(cli.analyze, [])
    assert result.exit_code == 0
    assert "Analysis complete" in result.output


def test_cli_analyze_error(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    def fake_root() -> Path:
        return tmp_path

    def fake_load_settings(_path: Path):
        return object()

    def fake_analyze(_dist_dir: Path, _settings):
        return {"error": "boom"}

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "analyze_build", fake_analyze)

    result = runner.invoke(cli.analyze, [])
    assert result.exit_code == 1
    assert "boom" in result.output


def test_cli_analyze_exception(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    def fake_root() -> Path:
        return tmp_path

    def fake_load_settings(_path: Path):
        return object()

    def fake_analyze(_dist_dir: Path, _settings):
        raise RuntimeError("explode")

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "analyze_build", fake_analyze)

    result = runner.invoke(cli.analyze, [])
    assert result.exit_code == 1
    assert "Analysis failed" in result.output


def test_cli_build_error(monkeypatch) -> None:
    runner = CliRunner()

    def fake_load_settings(_path: Path):
        return object()

    def fake_build(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "build", fake_build)

    result = runner.invoke(cli.build_cmd, [])
    assert result.exit_code == 1
    assert "Build failed" in result.output


def test_cli_build_human_output(monkeypatch) -> None:
    runner = CliRunner()

    def fake_load_settings(_path: Path):
        return object()

    def fake_build(_root: Path, _settings, no_fetch: bool = False):
        return Stats(
            total_lines=1,
            parsed_ok=1,
            sanitized_ok=1,
            unique_domains=1,
            discarded={},
        )

    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "build", fake_build)

    result = runner.invoke(cli.build_cmd, [])
    assert result.exit_code == 0
    assert "Unique domains" in result.output


def test_cli_validate_success(monkeypatch) -> None:
    runner = CliRunner()

    class DummySettings:
        def __init__(self) -> None:
            self.sources = [1, 2]
            self.profiles = type("P", (), {"by_name": {"default": object()}})
            self.policies = type("Pol", (), {"category_precedence": ["a", "b"]})

    def fake_load_settings(_path: Path):
        return DummySettings()

    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    result = runner.invoke(cli.validate, [])
    assert result.exit_code == 0
    assert "Config valid" in result.output


def test_cli_validate_error(monkeypatch) -> None:
    runner = CliRunner()

    def fake_load_settings(_path: Path):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    result = runner.invoke(cli.validate, [])
    assert result.exit_code == 1
    assert "Config error" in result.output


def test_cli_recommend_missing_dist(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    def fake_root() -> Path:
        return tmp_path

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    result = runner.invoke(cli.recommend, [])
    assert result.exit_code == 1
    assert "No dist/ found" in result.output


def test_cli_recommend_success(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    def fake_root() -> Path:
        return tmp_path

    def fake_load_settings(_path: Path):
        return object()

    def fake_recommend(_dist_dir: Path, _settings):
        return {
            "total_domains": 10,
            "high_value_sources": 2,
            "moderate_value_sources": 1,
            "low_value_sources": 0,
            "top_sources": ["s1", "s2"],
            "output_file": str(dist_dir / "reports" / "recommend.md"),
        }

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "compute_recommendations", fake_recommend)

    result = runner.invoke(cli.recommend, [])
    assert result.exit_code == 0
    assert "Recommendations generated" in result.output


def test_cli_recommend_error(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    def fake_root() -> Path:
        return tmp_path

    def fake_load_settings(_path: Path):
        return object()

    def fake_recommend(_dist_dir: Path, _settings):
        return {"error": "boom"}

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "compute_recommendations", fake_recommend)

    result = runner.invoke(cli.recommend, [])
    assert result.exit_code == 1
    assert "boom" in result.output


def test_cli_recommend_exception(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    def fake_root() -> Path:
        return tmp_path

    def fake_load_settings(_path: Path):
        return object()

    def fake_recommend(_dist_dir: Path, _settings):
        raise RuntimeError("explode")

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "compute_recommendations", fake_recommend)

    result = runner.invoke(cli.recommend, [])
    assert result.exit_code == 1
    assert "Recommendation failed" in result.output


def test_cli_sync_firebog_success(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    def fake_root() -> Path:
        return tmp_path

    def fake_sync(_config_dir: Path, dry_run: bool = False):
        return {"by_category": {"ads": 2}, "sources_generated": 2}

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "sync_firebog", fake_sync)

    result = runner.invoke(cli.sync_firebog_cmd, [])
    assert result.exit_code == 0
    assert "Firebog sync complete" in result.output


def test_cli_sync_firebog_error(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    def fake_root() -> Path:
        return tmp_path

    def fake_sync(_config_dir: Path, dry_run: bool = False):
        return {"error": "boom"}

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "sync_firebog", fake_sync)

    result = runner.invoke(cli.sync_firebog_cmd, [])
    assert result.exit_code == 1
    assert "boom" in result.output


def test_cli_sync_firebog_exception(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    def fake_root() -> Path:
        return tmp_path

    def fake_sync(_config_dir: Path, dry_run: bool = False):
        raise RuntimeError("explode")

    monkeypatch.setattr(cli, "_repo_root", fake_root)
    monkeypatch.setattr(cli, "sync_firebog", fake_sync)

    result = runner.invoke(cli.sync_firebog_cmd, [])
    assert result.exit_code == 1
    assert "Sync failed" in result.output


def test_cli_sync_firebog_import_error(monkeypatch) -> None:
    runner = CliRunner()

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "requests":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = runner.invoke(cli.sync_firebog_cmd, [])
    assert result.exit_code == 1
    assert "requests package required" in result.output


def test_cli_sync_github_catalog() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.sync_github_catalog_cmd, [])
    assert result.exit_code == 0
    assert "sync-github-catalog" in result.output


def test_cli_main_returns_codes(monkeypatch) -> None:
    def fake_cli(argv=None, standalone_mode=False):
        raise SystemExit(2)

    monkeypatch.setattr(cli, "cli", fake_cli)
    assert cli.main([]) == 2

    def fake_cli_ok(argv=None, standalone_mode=False):
        return None

    monkeypatch.setattr(cli, "cli", fake_cli_ok)
    assert cli.main([]) == 0

    def fake_cli_boom(argv=None, standalone_mode=False):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "cli", fake_cli_boom)
    assert cli.main([]) == 1


@pytest.mark.filterwarnings(
    "ignore:.*blocklist_builder\\.cli.*prior to execution.*:RuntimeWarning"
)
def test_cli_run_as_main(monkeypatch) -> None:
    import runpy
    import sys
    import warnings

    monkeypatch.setattr(sys, "argv", ["blocklist_builder.cli", "--help"])
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*blocklist_builder\\.cli.*prior to execution.*",
            category=RuntimeWarning,
        )
        try:
            runpy.run_module("blocklist_builder.cli", run_name="__main__")
        except SystemExit:
            assert True
