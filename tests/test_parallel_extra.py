from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import requests

import blocklist_builder.parallel as parallel
from blocklist_builder.parallel import (
    get_optimal_workers,
    parallel_fetch_sources,
)


def test_get_optimal_workers_env(monkeypatch) -> None:
    monkeypatch.setenv("BLOCKLIST_WORKERS", "3")
    assert get_optimal_workers() == 3


def test_get_optimal_workers_default(monkeypatch) -> None:
    monkeypatch.delenv("BLOCKLIST_WORKERS", raising=False)
    monkeypatch.setattr(parallel, "cpu_count", lambda: 8)
    assert get_optimal_workers() == 6


def test_parallel_fetch_sources_no_fetch(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("example.com\n", encoding="utf-8")

    class S:
        def __init__(self, url: str, enabled: bool = True, id: str = "s1") -> None:
            self.url = url
            self.enabled = enabled
            self.id = id

    sources = [
        S(str(source), True, "s1"),
        S(f"file://{source}", True, "s2"),
        S(str(source), False, "s3"),
    ]
    result = parallel_fetch_sources(sources, tmp_path / "cache", no_fetch=True, repo_root=tmp_path)
    assert result["s1"].exists()
    assert result["s2"].exists()
    assert "s3" not in result


def test_parallel_fetch_sources_with_errors(monkeypatch, tmp_path: Path) -> None:
    class S:
        def __init__(self, url: str, enabled: bool = True, id: str = "s1") -> None:
            self.url = url
            self.enabled = enabled
            self.id = id

    sources = [
        S("http://example.com/ok", True, "s1"),
        S("http://example.com/fail", True, "s2"),
        S("http://example.com/disabled", False, "s3"),
    ]

    class _Future:
        def __init__(self, result=None, exc=None):
            self._result = result
            self._exc = exc

        def result(self):
            if self._exc:
                raise self._exc
            return self._result

    class _Executor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, url, cache_dir, source_id=None, timeout_s=None, allowed_base=None):
            if "fail" in url:
                return _Future(exc=RuntimeError("boom"))
            return _Future(result=(tmp_path / "ok.txt", None))

    monkeypatch.setattr(parallel, "ThreadPoolExecutor", _Executor)
    monkeypatch.setattr(parallel, "as_completed", lambda futures: futures)

    result = parallel_fetch_sources(sources, tmp_path / "cache", no_fetch=False)
    assert result["s1"] == tmp_path / "ok.txt"
    assert result["s2"] is None
    assert "s3" not in result


def test_process_source_file_worker_drop_patterns(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("bad\nexample.com\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker(
        (str(source), [r"^bad$"], frozenset(), None)
    )
    assert valid == ["example.com"]
    assert stats["parse_ok"] == 1
    assert stats["sanitize_ok"] == 1
    assert stats["parse_pattern_drop"] == 1


def test_process_source_file_worker_sanitize_discard(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("0.0.0.0 1.2.3.4\nexample.com\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset(), None))
    assert valid == ["example.com"]
    assert stats["sanitize_ip"] == 1
    assert stats["parse_ok"] == 2
    assert stats["sanitize_ok"] == 1


def test_process_source_file_worker_wildcard_and_multihost(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("*.wild.example.com\n0.0.0.0 a.example.com b.example.com\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset(), None))
    assert set(valid) == {"a.example.com", "b.example.com"}
    assert stats["parse_wildcard"] == 1
    assert stats["parse_ok"] == 2
    assert stats["lines"] == 2


def test_process_source_file_worker(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("# comment\nexample.com\n0.0.0.0 ads.example.com\nbad\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset(), None))
    assert set(valid) == {"example.com", "ads.example.com"}
    assert stats["lines"] == 4
    assert stats["parse_ok"] == 2
    assert stats["sanitize_ok"] == 2
    assert stats["parse_comment"] == 1


def test_process_source_file_worker_allowlist(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("example.com\nads.example.com\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker(
        (str(source), [], frozenset({"example.com"}), None)
    )
    assert valid == ["ads.example.com"]
    assert stats["allowlisted"] == 1


def test_parallel_process_all_sources_empty() -> None:
    result = parallel.parallel_process_all_sources({}, [], frozenset())
    assert result == {}


def test_parallel_process_all_sources_few_sources(tmp_path: Path) -> None:
    """With <= 2 sources, processes locally without process pool."""
    s1 = tmp_path / "s1.txt"
    s1.write_text("example.com\n", encoding="utf-8")
    s2 = tmp_path / "s2.txt"
    s2.write_text("test.org\n", encoding="utf-8")
    result = parallel.parallel_process_all_sources({"s1": s1, "s2": s2}, [], frozenset())
    assert "s1" in result
    assert "s2" in result
    assert result["s1"][0] == ["example.com"]
    assert result["s2"][0] == ["test.org"]


def test_parallel_process_all_sources_with_pool(monkeypatch, tmp_path: Path) -> None:
    """With 3+ sources, uses ProcessPoolExecutor."""
    files = {}
    for i in range(3):
        f = tmp_path / f"s{i}.txt"
        f.write_text(f"domain{i}.com\n", encoding="utf-8")
        files[f"s{i}"] = f

    class _Future:
        def __init__(self, fn, args) -> None:
            self._result = fn(args)

        def result(self):
            return self._result

    class _Executor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, args):
            return _Future(fn, args)

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", _Executor)
    monkeypatch.setattr(parallel, "as_completed", lambda futures: futures)
    monkeypatch.setattr(parallel, "get_optimal_workers", lambda: 2)

    result = parallel.parallel_process_all_sources(files, [], frozenset())
    assert len(result) == 3
    for i in range(3):
        assert f"domain{i}.com" in result[f"s{i}"][0]


def test_parallel_process_all_sources_pool_failure(monkeypatch, tmp_path: Path) -> None:
    """Falls back to sequential on ProcessPoolExecutor failure."""
    files = {}
    for i in range(3):
        f = tmp_path / f"s{i}.txt"
        f.write_text(f"domain{i}.com\n", encoding="utf-8")
        files[f"s{i}"] = f

    class _Executor:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", _Executor)

    result = parallel.parallel_process_all_sources(files, [], frozenset())
    assert len(result) == 3
    for i in range(3):
        assert f"domain{i}.com" in result[f"s{i}"][0]


def test_resolve_local_sources_traversal_rejected() -> None:
    class S:
        def __init__(self, url: str, enabled: bool = True, id: str = "bad") -> None:
            self.url = url
            self.enabled = enabled
            self.id = id

    source = S(url="file:///../etc/passwd", enabled=True, id="bad")
    result = parallel._resolve_local_sources([source], Path("/nonexistent-cache"))
    assert result == {}


def test_resolve_local_sources_outside_repo_root_rejected(tmp_path: Path) -> None:
    class S:
        def __init__(self, url: str, enabled: bool = True, id: str = "s1") -> None:
            self.url = url
            self.enabled = enabled
            self.id = id

    outside = tmp_path / "outside" / "list.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("example.com\n", encoding="utf-8")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    sources = [S(str(outside), True, "escapee")]
    # escapes repo_root -> rejected
    assert parallel._resolve_local_sources(sources, tmp_path / "cache", repo_root) == {}
    # no repo_root at all -> fail closed
    assert parallel._resolve_local_sources(sources, tmp_path / "cache", None) == {}


def test_resolve_local_sources_http_from_cache(tmp_path: Path) -> None:
    from blocklist_builder.fetch import _cache_key

    class S:
        def __init__(self, url: str, enabled: bool = True, id: str = "s1") -> None:
            self.url = url
            self.enabled = enabled
            self.id = id

    cached_url = "https://example.com/cached.txt"
    uncached_url = "https://example.com/uncached.txt"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached_file = cache_dir / f"{_cache_key(cached_url)}.txt"
    cached_file.write_text("example.com\n", encoding="utf-8")

    sources = [S(cached_url, True, "hit"), S(uncached_url, True, "miss")]
    result = parallel._resolve_local_sources(sources, cache_dir)
    assert result == {"hit": cached_file}


def test_process_source_file_worker_carriage_return_only(tmp_path: Path) -> None:
    """Domains separated only by a bare \\r (no \\n) are both parsed.

    Universal-newline file reading splits on \\r as well; this locks that behavior.
    """
    source = tmp_path / "list.txt"
    # Write raw bytes so the \r is preserved exactly (no normalization on write).
    source.write_bytes(b"a.example.com\rb.example.com\r")
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset(), None))
    assert set(valid) == {"a.example.com", "b.example.com"}
    assert stats["parse_ok"] == 2
    assert stats["sanitize_ok"] == 2


def test_process_source_file_worker_no_trailing_newline(tmp_path: Path) -> None:
    """A file whose last line has no trailing newline still yields its last domain."""
    source = tmp_path / "list.txt"
    source.write_bytes(b"a.example.com\nlast.example.com")
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset(), None))
    assert set(valid) == {"a.example.com", "last.example.com"}
    assert stats["parse_ok"] == 2


def test_process_source_file_worker_glued_host_ip(tmp_path: Path) -> None:
    """A glued sink-IP line (0.0.0.0kryptonchain.org) is repaired to a valid domain."""
    source = tmp_path / "list.txt"
    source.write_text("0.0.0.0kryptonchain.org\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset(), None))
    assert valid == ["kryptonchain.org"]
    assert stats["parse_ok"] == 1
    assert stats["sanitize_ok"] == 1


def test_parallel_process_all_sources_worker_failure(monkeypatch, tmp_path: Path) -> None:
    """Falls back to local processing when a single worker fails."""
    files = {}
    for i in range(3):
        f = tmp_path / f"s{i}.txt"
        f.write_text(f"domain{i}.com\n", encoding="utf-8")
        files[f"s{i}"] = f

    call_count = 0

    class _Future:
        def __init__(self, fn, args) -> None:
            nonlocal call_count
            call_count += 1
            self._fn = fn
            self._args = args
            self._fail = call_count == 1  # First task fails

        def result(self):
            if self._fail:
                raise RuntimeError("boom")
            return self._fn(self._args)

    class _Executor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, args):
            return _Future(fn, args)

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", _Executor)
    monkeypatch.setattr(parallel, "as_completed", lambda futures: futures)
    monkeypatch.setattr(parallel, "get_optimal_workers", lambda: 2)

    result = parallel.parallel_process_all_sources(files, [], frozenset())
    # All 3 sources should still be processed (failed one falls back to local)
    assert len(result) == 3


def _write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _assert_failed_source(result: tuple[list[str], dict[str, int]]) -> None:
    valid, stats = result
    assert valid == []
    assert stats["source_missing"] == 1
    assert stats["lines"] == 0
    assert stats["sanitize_ok"] == 0


def test_json_worker_reads_only_the_named_array(tmp_path: Path) -> None:
    source = _write_json(
        tmp_path / "config.json",
        {
            "fuzzylist": ["fuzzy.example"],
            "whitelist": ["white.example"],
            "blacklist": ["evil.example", 42, None, "other.example"],
        },
    )
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset(), "blacklist"))
    assert set(valid) == {"evil.example", "other.example"}
    assert stats["lines"] == 2
    assert stats["sanitize_ok"] == 2
    assert "source_missing" not in stats


def test_json_worker_rejects_path_and_wildcard_entries(tmp_path: Path) -> None:
    source = _write_json(
        tmp_path / "config.json",
        {"blacklist": ["evil.example", "sites.google.com/view/x", "*.star.example"]},
    )
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset(), "blacklist"))
    assert valid == ["evil.example"]
    assert "sites.google.com" not in valid
    assert stats["parse_wildcard"] == 1
    assert sum(v for k, v in stats.items() if k.startswith("sanitize_") and k != "sanitize_ok") == 1


def test_json_worker_respects_allowlist(tmp_path: Path) -> None:
    source = _write_json(tmp_path / "config.json", {"blacklist": ["a.example", "b.example"]})
    valid, stats = parallel._process_source_file_worker(
        (str(source), [], frozenset({"a.example"}), "blacklist")
    )
    assert valid == ["b.example"]
    assert stats["allowlisted"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        "{not json",
        "[1, 2, 3]",
        '"just a string"',
        '{"whitelist": ["a.example"]}',
        '{"blacklist": "a.example"}',
        '{"blacklist": {"a.example": 1}}',
        '{"blacklist": []}',
        '{"blacklist": [1, 2, null]}',
    ],
)
def test_json_worker_failure_modes_count_as_source_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, payload: str
) -> None:
    source = tmp_path / "config.json"
    source.write_text(payload, encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        result = parallel._process_source_file_worker((str(source), [], frozenset(), "blacklist"))
    _assert_failed_source(result)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert str(source) in warnings[0].getMessage()
    assert "blacklist" in warnings[0].getMessage()


def test_json_worker_missing_file_is_source_missing(tmp_path: Path) -> None:
    result = parallel._process_source_file_worker(
        (str(tmp_path / "absent.json"), [], frozenset(), "blacklist")
    )
    _assert_failed_source(result)


def test_json_worker_deep_nesting_is_source_missing(tmp_path: Path) -> None:
    source = tmp_path / "deep.json"
    source.write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
    result = parallel._process_source_file_worker((str(source), [], frozenset(), "blacklist"))
    _assert_failed_source(result)


def test_json_worker_ignores_key_for_text_sources(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("example.com\n", encoding="utf-8")
    valid, _ = parallel._process_source_file_worker((str(source), [], frozenset(), None))
    assert valid == ["example.com"]


def test_parallel_process_all_sources_json_keys_sequential(tmp_path: Path) -> None:
    js = _write_json(tmp_path / "c.json", {"blacklist": ["evil.example"], "other": ["x.example"]})
    txt = tmp_path / "t.txt"
    txt.write_text("plain.example\n", encoding="utf-8")
    result = parallel.parallel_process_all_sources(
        {"js": js, "txt": txt}, [], frozenset(), json_keys={"js": "blacklist"}
    )
    assert result["js"][0] == ["evil.example"]
    assert result["txt"][0] == ["plain.example"]


def test_parallel_process_all_sources_json_keys_pool(monkeypatch, tmp_path: Path) -> None:
    js = _write_json(tmp_path / "c.json", {"blacklist": ["evil.example"]})
    files = {"js": js}
    for i in range(2):
        f = tmp_path / f"s{i}.txt"
        f.write_text(f"domain{i}.com\n", encoding="utf-8")
        files[f"s{i}"] = f

    class _Future:
        def __init__(self, fn, args, fail: bool = False) -> None:
            self._fn = fn
            self._args = args
            self._fail = fail

        def result(self):
            if self._fail:
                raise RuntimeError("boom")
            return self._fn(self._args)

    class _Executor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, args):
            return _Future(fn, args, fail=args[3] is not None)

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", _Executor)
    monkeypatch.setattr(parallel, "as_completed", lambda futures: futures)
    monkeypatch.setattr(parallel, "get_optimal_workers", lambda: 2)

    result = parallel.parallel_process_all_sources(
        files, [], frozenset(), json_keys={"js": "blacklist"}
    )
    assert len(result) == 3
    # the pool submit carried the key, and the per-future retry carried it too
    assert result["js"][0] == ["evil.example"]


def test_parallel_process_all_sources_json_keys_pool_fallback(monkeypatch, tmp_path: Path) -> None:
    js = _write_json(tmp_path / "c.json", {"blacklist": ["evil.example"]})
    files = {"js": js}
    for i in range(2):
        f = tmp_path / f"s{i}.txt"
        f.write_text(f"domain{i}.com\n", encoding="utf-8")
        files[f"s{i}"] = f

    class _Executor:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", _Executor)
    result = parallel.parallel_process_all_sources(
        files, [], frozenset(), json_keys={"js": "blacklist"}
    )
    assert result["js"][0] == ["evil.example"]


class _Src:
    def __init__(self, id: str, url: str = "https://example.test/list.txt") -> None:
        self.id = id
        self.url = url or id
        self.enabled = True


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"HTTP {status}", response=response)


class _FetchScript:
    """Scripted fetch_to_cache: per-url list of outcomes (exception or Path), in call order."""

    def __init__(self, script: dict[str, list[Exception | Path]]) -> None:
        self.script = script
        self.calls: list[str] = []

    def __call__(self, url, cache_dir, source_id=None, timeout_s=None, allowed_base=None):
        self.calls.append(source_id)
        outcome = self.script[source_id].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, None


@pytest.fixture
def fetch_env(monkeypatch, tmp_path: Path):
    sleeps: list[float] = []
    monkeypatch.setattr(parallel.time, "sleep", sleeps.append)
    monkeypatch.setattr(parallel, "get_optimal_workers", lambda: 1)

    def install(script: dict[str, list[Exception | Path]]) -> _FetchScript:
        fake = _FetchScript(script)
        monkeypatch.setattr(parallel, "fetch_to_cache", fake)
        return fake

    return sleeps, install


def _fetch(sources: list[_Src], tmp_path: Path):
    return parallel.parallel_fetch_sources(sources, tmp_path / "cache")


def test_fetch_retry_delays_constant() -> None:
    assert parallel._FETCH_RETRY_DELAYS_S == (30, 60, 120)


def test_fetch_transient_failure_recovers_on_first_round(fetch_env, tmp_path: Path) -> None:
    sleeps, install = fetch_env
    ok = tmp_path / "ok.txt"
    install({"a": [network_unreachable(), ok], "b": [ok]})
    result = _fetch([_Src("a"), _Src("b")], tmp_path)
    assert result == {"a": ok, "b": ok}
    assert sleeps == [30]


def test_fetch_transient_failure_recovers_on_later_round(fetch_env, tmp_path: Path) -> None:
    sleeps, install = fetch_env
    ok = tmp_path / "ok.txt"
    fake = install({"a": [network_unreachable(), network_unreachable(), ok]})
    result = _fetch([_Src("a")], tmp_path)
    assert result == {"a": ok}
    assert sleeps == [30, 60]
    assert fake.calls == ["a", "a", "a"]


def test_fetch_5xx_is_retried(fetch_env, tmp_path: Path) -> None:
    sleeps, install = fetch_env
    ok = tmp_path / "ok.txt"
    install({"a": [_http_error(503), ok]})
    assert _fetch([_Src("a")], tmp_path) == {"a": ok}
    assert sleeps == [30]


@pytest.mark.parametrize(
    "exc",
    [
        _http_error(404),
        _http_error(403),
        ValueError("local source escapes allowed base"),
        None,
    ],
)
def test_fetch_permanent_failure_is_not_retried_or_slept_for(
    fetch_env, tmp_path: Path, exc: Exception | None
) -> None:
    from blocklist_builder.fetch import DownloadTooLargeError

    sleeps, install = fetch_env
    error = exc if exc is not None else DownloadTooLargeError("too big")
    fake = install({"a": [error]})
    assert _fetch([_Src("a")], tmp_path) == {"a": None}
    assert sleeps == []
    assert fake.calls == ["a"]


def test_fetch_failing_every_round_ends_as_none(fetch_env, tmp_path: Path, caplog) -> None:
    sleeps, install = fetch_env
    fake = install({"a": [network_unreachable() for _ in range(4)]})
    with caplog.at_level(logging.WARNING):
        result = _fetch([_Src("a")], tmp_path)
    assert result == {"a": None}
    assert sleeps == [30, 60, 120]
    assert fake.calls == ["a"] * 4
    final = [r for r in caplog.records if "after all retries" in r.getMessage()]
    assert len(final) == 1
    assert final[0].exc_info is not None
    intermediate = [r for r in caplog.records if "will retry" in r.getMessage()]
    assert intermediate
    assert all(r.exc_info is None for r in intermediate)


def test_fetch_retry_rounds_run_one_source_at_a_time(fetch_env, tmp_path: Path) -> None:
    sleeps, install = fetch_env
    ok = tmp_path / "ok.txt"
    fake = install(
        {
            "a": [network_unreachable(), ok],
            "b": [network_unreachable(), network_unreachable(), ok],
            "c": [network_unreachable(), ok],
        }
    )
    result = _fetch([_Src("a"), _Src("b"), _Src("c")], tmp_path)
    assert result == {"a": ok, "b": ok, "c": ok}
    # first pass (1 worker, in order), then round 1 over all three, then round 2 over b only
    assert fake.calls == ["a", "b", "c", "a", "b", "c", "b"]
    assert sleeps == [30, 60]


def test_fetch_stops_when_nothing_is_left(fetch_env, tmp_path: Path) -> None:
    sleeps, install = fetch_env
    install({"a": [tmp_path / "ok.txt"]})
    _fetch([_Src("a")], tmp_path)
    assert sleeps == []


def test_fetch_delays_come_from_the_constant(fetch_env, monkeypatch, tmp_path: Path) -> None:
    sleeps, install = fetch_env
    monkeypatch.setattr(parallel, "_FETCH_RETRY_DELAYS_S", (1, 2))
    fake = install({"a": [network_unreachable() for _ in range(3)]})
    assert _fetch([_Src("a")], tmp_path) == {"a": None}
    assert sleeps == [1, 2]
    assert fake.calls == ["a"] * 3


def test_fetch_mixed_permanent_and_transient(fetch_env, tmp_path: Path) -> None:
    sleeps, install = fetch_env
    ok = tmp_path / "ok.txt"
    fake = install({"gone": [_http_error(404)], "flaky": [network_unreachable(), ok]})
    result = _fetch([_Src("gone"), _Src("flaky")], tmp_path)
    assert result == {"gone": None, "flaky": ok}
    assert fake.calls.count("gone") == 1
    assert sleeps == [30]


def test_fetch_no_fetch_never_sleeps(monkeypatch, tmp_path: Path) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(parallel.time, "sleep", sleeps.append)
    result = parallel.parallel_fetch_sources(
        [_Src("a", "https://example.test/x.txt")], tmp_path / "cache", no_fetch=True
    )
    assert result == {}
    assert sleeps == []


def network_unreachable() -> requests.ConnectionError:
    return requests.ConnectionError("[Errno 101] Network is unreachable")


def test_fetch_failure_turning_permanent_in_a_retry_round_stops_retrying(
    fetch_env, tmp_path: Path
) -> None:
    sleeps, install = fetch_env
    fake = install({"a": [network_unreachable(), _http_error(404)]})
    assert _fetch([_Src("a")], tmp_path) == {"a": None}
    assert sleeps == [30]
    assert fake.calls == ["a", "a"]
