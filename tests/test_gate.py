from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

import blocklist_builder.cli as cli
from blocklist_builder.gate import (
    GateResult,
    blocking_entry,
    check_drop,
    check_must_not_block,
    run_gate,
)

ROOT = Path(__file__).resolve().parents[1]


def _make_dist(
    tmp_path: Path,
    domains: list[str] | None = None,
    discarded: dict[str, Any] | None = None,
) -> Path:
    dist = tmp_path / "dist"
    (dist / "reports").mkdir(parents=True)
    names = domains if domains is not None else ["ads.example", "track.example"]
    (dist / "all.txt").write_text("".join(f"{d}\n" for d in names), encoding="utf-8")
    stats = {"unique_domains": len(names), "discarded": discarded if discarded is not None else {}}
    (dist / "reports" / "stats.json").write_text(json.dumps(stats), encoding="utf-8")
    return dist


def _canaries(tmp_path: Path, names: list[str] | None = None) -> Path:
    path = tmp_path / "must_not_block.txt"
    body = names if names is not None else ["login.safe.example"]
    path.write_text("# canaries\n\n" + "".join(f"{n}\n" for n in body), encoding="utf-8")
    return path


def _gate(dist: Path, canaries: Path, **kwargs: Any) -> GateResult:
    return run_gate(
        dist,
        kwargs.get("previous"),
        kwargs.get("max_drop", 0.10),
        kwargs.get("allow_drop", False),
        canaries,
    )


def test_blocking_entry_parent_exact_and_none() -> None:
    assert blocking_entry("a.b.example.com", {"example.com"}) == "example.com"
    assert blocking_entry("a.b.example.com", {"a.b.example.com"}) == "a.b.example.com"
    assert blocking_entry("a.b.example.com", {"other.com"}) is None
    assert blocking_entry("a.b.example.com", {"com"}) == "com"


def test_blocking_entry_does_not_match_partial_labels() -> None:
    assert blocking_entry("badexample.com", {"example.com"}) is None


def test_check_must_not_block_reports_name_and_entry_once_per_name() -> None:
    failures = check_must_not_block(
        ["x.example.com", "y.fine.org", "z.example.com"], {"example.com", "x.example.com"}
    )
    assert len(failures) == 2
    assert "x.example.com" in failures[0]
    assert "x.example.com" in failures[0].split("by list entry")[1]
    assert "z.example.com" in failures[1]
    assert "example.com" in failures[1]


@pytest.mark.parametrize(
    ("current", "failures"),
    [(90, 0), (89, 1), (200, 0), (100, 0)],
)
def test_check_drop_boundary(current: int, failures: int) -> None:
    assert len(check_drop(current, 100, 0.10)) == failures


def test_run_gate_passes_without_source_missing(tmp_path: Path) -> None:
    result = _gate(_make_dist(tmp_path), _canaries(tmp_path))
    assert result.failures == []
    assert result.domains == 2
    assert result.previous is None
    assert any("no previous" in n for n in result.notes)


def test_run_gate_fails_on_source_missing(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, discarded={"source_missing": 1})
    result = _gate(dist, _canaries(tmp_path))
    assert len(result.failures) == 1
    assert "source_stats.json" in result.failures[0]


def test_run_gate_source_missing_zero_passes(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, discarded={"source_missing": 0})
    assert _gate(dist, _canaries(tmp_path)).failures == []


def test_run_gate_stats_missing_fails_closed(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path)
    (dist / "reports" / "stats.json").unlink()
    result = _gate(dist, _canaries(tmp_path))
    assert len(result.failures) == 1
    assert "stats.json" in result.failures[0]


@pytest.mark.parametrize("payload", ["{nope", "[]", '{"unique_domains": 3}', '{"discarded": []}'])
def test_run_gate_stats_unusable_fails_closed(tmp_path: Path, payload: str) -> None:
    dist = _make_dist(tmp_path)
    (dist / "reports" / "stats.json").write_text(payload, encoding="utf-8")
    assert len(_gate(dist, _canaries(tmp_path)).failures) == 1


@pytest.mark.parametrize("value", ['"1"', "1.5", "true", "null"])
def test_run_gate_source_missing_non_int_fails(tmp_path: Path, value: str) -> None:
    dist = _make_dist(tmp_path)
    (dist / "reports" / "stats.json").write_text(
        f'{{"discarded": {{"source_missing": {value}}}}}', encoding="utf-8"
    )
    result = _gate(dist, _canaries(tmp_path))
    assert len(result.failures) == 1
    assert "non-integer" in result.failures[0]


def test_run_gate_all_txt_missing_fails_closed(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path)
    (dist / "all.txt").unlink()
    result = _gate(dist, _canaries(tmp_path))
    assert len(result.failures) == 1
    assert "all.txt" in result.failures[0]


def test_run_gate_all_txt_empty_fails_closed(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, domains=[])
    result = _gate(dist, _canaries(tmp_path))
    assert len(result.failures) == 1
    assert "empty" in result.failures[0]


def test_run_gate_canary_file_missing_fails_closed(tmp_path: Path) -> None:
    result = run_gate(_make_dist(tmp_path), None, 0.10, False, tmp_path / "absent.txt")
    assert len(result.failures) == 1
    assert "absent.txt" in result.failures[0]


def test_run_gate_canary_file_empty_fails_closed(tmp_path: Path) -> None:
    result = _gate(_make_dist(tmp_path), _canaries(tmp_path, names=[]))
    assert len(result.failures) == 1
    assert "no names" in result.failures[0]


def test_run_gate_reports_every_failure(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, domains=["safe.example"], discarded={"source_missing": 2})
    previous = tmp_path / "previous.txt"
    previous.write_text("".join(f"d{i}.example\n" for i in range(100)), encoding="utf-8")
    canaries = _canaries(tmp_path, names=["login.safe.example"])
    result = _gate(dist, canaries, previous=previous)
    assert len(result.failures) == 3
    joined = "\n".join(result.failures)
    assert "source_missing" in joined
    assert "login.safe.example" in joined
    assert "shrank" in joined


def test_run_gate_canary_parent_in_list_fails(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, domains=["safe.example"])
    result = _gate(dist, _canaries(tmp_path, names=["Login.Safe.Example."]))
    assert len(result.failures) == 1
    assert "login.safe.example" in result.failures[0]
    assert "safe.example" in result.failures[0]


def test_run_gate_previous_none_or_absent_is_a_note(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path)
    canaries = _canaries(tmp_path)
    for previous in (None, tmp_path / "nope.txt"):
        result = _gate(dist, canaries, previous=previous)
        assert result.failures == []
        assert result.previous is None
        assert result.notes


def test_run_gate_previous_empty_is_a_note_without_zero_division(tmp_path: Path) -> None:
    previous = tmp_path / "previous.txt"
    previous.write_text("# only a comment\n\n", encoding="utf-8")
    result = _gate(_make_dist(tmp_path), _canaries(tmp_path), previous=previous)
    assert result.failures == []
    assert result.previous is None
    assert any("0 entries" in n for n in result.notes)


def test_run_gate_previous_unreadable_fails(tmp_path: Path) -> None:
    result = _gate(_make_dist(tmp_path), _canaries(tmp_path), previous=tmp_path)
    assert len(result.failures) == 1
    assert "previous" in result.failures[0]


def test_run_gate_drop_check_counts_unique_and_ignores_comments(tmp_path: Path) -> None:
    previous = tmp_path / "previous.txt"
    previous.write_text("# header\n\na.example\na.example\nb.example\n", encoding="utf-8")
    result = _gate(_make_dist(tmp_path), _canaries(tmp_path), previous=previous)
    assert result.failures == []
    assert result.previous == 2
    assert result.domains == 2


def test_run_gate_allow_drop_skips_a_90_percent_drop(tmp_path: Path) -> None:
    previous = tmp_path / "previous.txt"
    previous.write_text("".join(f"d{i}.example\n" for i in range(20)), encoding="utf-8")
    dist = _make_dist(tmp_path, domains=["a.example", "b.example"])
    canaries = _canaries(tmp_path)
    assert len(_gate(dist, canaries, previous=previous).failures) == 1
    result = _gate(dist, canaries, previous=previous, allow_drop=True)
    assert result.failures == []
    assert any("--allow-drop" in n for n in result.notes)


def _cli_args(dist: Path, canaries: Path, *extra: str) -> list[str]:
    return ["gate", "--dist", str(dist), "--must-not-block", str(canaries), *extra]


def test_cli_gate_pass_returns_zero_and_prints_summary(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, domains=[f"d{i}.example" for i in range(11)])
    previous = tmp_path / "previous.txt"
    previous.write_text("".join(f"d{i}.example\n" for i in range(10)), encoding="utf-8")
    canaries = _canaries(tmp_path)
    args = _cli_args(dist, canaries, "--previous", str(previous))

    assert cli.main(args) == 0
    result = CliRunner().invoke(cli.cli, args)
    assert result.exit_code == 0
    assert "domains=11" in result.output
    assert "previous=10" in result.output
    assert "+10.00%" in result.output


def test_cli_gate_pass_without_previous_prints_none(tmp_path: Path) -> None:
    args = _cli_args(_make_dist(tmp_path), _canaries(tmp_path))
    result = CliRunner().invoke(cli.cli, args)
    assert result.exit_code == 0
    assert "previous=none" in result.output


def test_cli_gate_failure_returns_one_through_main_and_prints_each_failure(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, domains=["safe.example"], discarded={"source_missing": 1})
    canaries = _canaries(tmp_path, names=["login.safe.example"])
    args = _cli_args(dist, canaries)

    assert cli.main(args) == 1
    result = CliRunner().invoke(cli.cli, args)
    assert result.exit_code == 1
    assert "source_missing" in result.output
    assert "login.safe.example" in result.output


def test_cli_gate_missing_dist_returns_one(tmp_path: Path) -> None:
    args = _cli_args(tmp_path / "empty", _canaries(tmp_path))
    assert cli.main(args) == 1


def test_cli_gate_allow_drop_flag(tmp_path: Path) -> None:
    previous = tmp_path / "previous.txt"
    previous.write_text("".join(f"d{i}.example\n" for i in range(20)), encoding="utf-8")
    dist = _make_dist(tmp_path)
    canaries = _canaries(tmp_path)
    base = _cli_args(dist, canaries, "--previous", str(previous))
    assert cli.main(base) == 1
    assert cli.main([*base, "--allow-drop"]) == 0


def test_cli_gate_max_drop_option(tmp_path: Path) -> None:
    previous = tmp_path / "previous.txt"
    previous.write_text("".join(f"d{i}.example\n" for i in range(4)), encoding="utf-8")
    dist = _make_dist(tmp_path)
    base = _cli_args(dist, _canaries(tmp_path), "--previous", str(previous))
    assert cli.main(base) == 1
    assert cli.main([*base, "--max-drop", "0.5"]) == 0


def _workflow() -> dict[str, Any]:
    path = ROOT / ".forgejo" / "workflows" / "build-lists.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps() -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = _workflow()["jobs"]["build"]["steps"]
    return steps


def _index(name: str) -> int:
    return next(i for i, step in enumerate(_steps()) if step.get("name") == name)


def test_workflow_gate_sits_between_build_and_stage() -> None:
    assert _index("Build lists") < _index("Fetch previous release") < _index("Gate")
    assert _index("Gate") < _index("Stage release assets")
    assert "blocklist-factory gate --previous previous-all.txt" in _steps()[_index("Gate")]["run"]


def test_workflow_alert_is_last_and_runs_on_failure() -> None:
    last = _steps()[-1]
    assert last["name"] == "Alert on failure"
    assert last["if"] == "failure()"
    assert "high" in last["run"].lower()
    assert "github.run_number" in last["env"]["RUN_URL"]
    assert "${RUN_URL}" in last["run"]


def test_workflow_stage_does_not_publish_previous_file() -> None:
    assert "previous-all.txt" not in _steps()[_index("Stage release assets")]["run"]


def test_workflow_allow_drop_goes_through_env() -> None:
    gate = _steps()[_index("Gate")]
    assert gate["env"]["ALLOW_DROP"] == "${{ github.event.inputs.allow_drop }}"
    assert "${{" not in gate["run"]
    dispatch = _workflow()[True]["workflow_dispatch"]["inputs"]["allow_drop"]
    assert dispatch["type"] == "boolean"
    assert dispatch["default"] is False


def test_workflow_previous_download_is_atomic_and_fails_closed() -> None:
    run = _steps()[_index("Fetch previous release")]["run"]
    assert "--fail" in run
    assert "previous-all.txt.part" in run
    assert "mv previous-all.txt.part previous-all.txt" in run


def _write_source_stats(dist: Path, payload: str) -> None:
    (dist / "reports" / "source_stats.json").write_text(payload, encoding="utf-8")


def test_gate_names_the_failed_sources(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, discarded={"source_missing": 2})
    _write_source_stats(
        dist,
        json.dumps(
            {
                "zeta": {"source_missing": 1, "lines": 0},
                "alpha": {"source_missing": 1},
                "fine": {"lines": 10, "sanitize_ok": 9},
                "zero": {"source_missing": 0},
                "flag": {"source_missing": True},
                "odd": "not a dict",
            }
        ),
    )
    result = _gate(dist, _canaries(tmp_path))
    assert len(result.failures) == 1
    assert result.failures[0].endswith(": alpha, zeta")
    assert "2 source(s)" in result.failures[0]


def test_gate_names_sources_through_the_cli(tmp_path: Path) -> None:
    dist = _make_dist(tmp_path, discarded={"source_missing": 1})
    _write_source_stats(dist, json.dumps({"cyberhost": {"source_missing": 1}}))
    args = _cli_args(dist, _canaries(tmp_path))
    assert cli.main(args) == 1
    assert "cyberhost" in CliRunner().invoke(cli.cli, args).output


@pytest.mark.parametrize("payload", [None, "{broken", "[1, 2]", '{"a": 1}', "{}"])
def test_gate_falls_back_when_source_stats_is_unusable(tmp_path: Path, payload: str | None) -> None:
    dist = _make_dist(tmp_path, discarded={"source_missing": 3})
    if payload is not None:
        _write_source_stats(dist, payload)
    result = _gate(dist, _canaries(tmp_path))
    assert len(result.failures) == 1
    assert "3 source(s)" in result.failures[0]
    assert "see reports/source_stats.json" in result.failures[0]
