from __future__ import annotations

from pathlib import Path

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
    result = parallel_fetch_sources(sources, tmp_path / "cache", no_fetch=True)
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

        def submit(self, fn, url, cache_dir, source_id=None, timeout_s=None):
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
    valid, stats = parallel._process_source_file_worker((str(source), [r"^bad$"], frozenset()))
    assert valid == ["example.com"]
    assert stats["parse_ok"] == 1
    assert stats["sanitize_ok"] == 1
    assert stats["parse_pattern_drop"] == 1


def test_process_source_file_worker_sanitize_discard(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("0.0.0.0 1.2.3.4\nexample.com\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset()))
    assert valid == ["example.com"]
    assert stats["sanitize_ip"] == 1
    assert stats["parse_ok"] == 2
    assert stats["sanitize_ok"] == 1


def test_process_source_file_worker(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("# comment\nexample.com\n0.0.0.0 ads.example.com\nbad\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker((str(source), [], frozenset()))
    assert set(valid) == {"example.com", "ads.example.com"}
    assert stats["lines"] == 4
    assert stats["parse_ok"] == 2
    assert stats["sanitize_ok"] == 2
    assert stats["parse_comment"] == 1


def test_process_source_file_worker_allowlist(tmp_path: Path) -> None:
    source = tmp_path / "list.txt"
    source.write_text("example.com\nads.example.com\n", encoding="utf-8")
    valid, stats = parallel._process_source_file_worker(
        (str(source), [], frozenset({"example.com"}))
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
