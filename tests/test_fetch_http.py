from __future__ import annotations

import json
from pathlib import Path

import blocklist_builder.fetch as fetch


class _Resp:
    def __init__(self, text: str, status_code: int = 200, headers: dict | None = None) -> None:
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None


def test_fetch_to_cache_http_retries(tmp_path: Path, monkeypatch) -> None:
    calls = {"n": 0}

    def fake_get(_url: str, timeout: int = 30, headers=None):
        calls["n"] += 1
        if calls["n"] < 2:
            raise fetch.requests.RequestException("boom")
        return _Resp("a\nb\n")

    monkeypatch.setattr(fetch.requests, "get", fake_get)
    monkeypatch.setattr(fetch.time, "sleep", lambda _t: None)

    cache_dir = tmp_path / "cache"
    cache_path, metadata = fetch.fetch_to_cache(
        "http://example.com/list.txt", cache_dir, source_id="s1"
    )
    assert cache_path.exists()
    assert metadata.line_count == 2


def test_fetch_http_raises_after_retries(monkeypatch) -> None:
    def fake_get(_url: str, timeout: int = 30, headers=None):
        raise fetch.requests.RequestException("boom")

    monkeypatch.setattr(fetch.requests, "get", fake_get)
    monkeypatch.setattr(fetch.time, "sleep", lambda _t: None)

    try:
        fetch._fetch_http("http://example.com/fail.txt", timeout_s=1)
    except fetch.requests.RequestException:
        return
    raise AssertionError("Expected RequestException")


def test_load_metadata_missing_and_invalid(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert fetch._load_metadata(missing) is None

    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert fetch._load_metadata(bad) is None


def test_fetch_to_cache_http_first_fetch_saves_headers(tmp_path: Path, monkeypatch) -> None:
    def fake_get(_url: str, timeout: int = 30, headers=None):
        return _Resp(
            "domain1\n",
            status_code=200,
            headers={"ETag": '"abc123"', "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"},
        )

    monkeypatch.setattr(fetch.requests, "get", fake_get)

    cache_dir = tmp_path / "cache"
    _cache_path, metadata = fetch.fetch_to_cache(
        "http://example.com/list.txt", cache_dir, source_id="s1"
    )
    assert metadata.etag == '"abc123"'
    assert metadata.last_modified == "Wed, 01 Jan 2025 00:00:00 GMT"
    assert (_cache_path).read_text(encoding="utf-8") == "domain1\n"


def test_fetch_to_cache_http_304_reuses_cache(tmp_path: Path, monkeypatch) -> None:
    url = "http://example.com/list.txt"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    key = fetch._cache_key(url)
    cache_file = cache_dir / f"{key}.txt"
    sidecar = cache_dir / f"{key}.json"
    cache_file.write_text("original\n", encoding="utf-8")
    sidecar.write_text(
        json.dumps({
            "source_id": "s1",
            "hash": "abc",
            "size_bytes": 9,
            "line_count": 1,
            "parsed_ok": 0,
            "sanitized_ok": 0,
            "etag": '"abc123"',
            "last_modified": "Wed, 01 Jan 2025 00:00:00 GMT",
            "fetch_timestamp": 1.0,
        }),
        encoding="utf-8",
    )

    captured_headers: dict = {}

    def fake_get(_url: str, timeout: int = 30, headers=None):
        captured_headers.update(headers or {})
        return _Resp("", status_code=304, headers={"ETag": '"abc123"'})

    monkeypatch.setattr(fetch.requests, "get", fake_get)

    _cache_path, metadata = fetch.fetch_to_cache(url, cache_dir, source_id="s1")
    assert "If-None-Match" in captured_headers
    assert cache_file.read_text(encoding="utf-8") == "original\n"
    assert metadata.etag == '"abc123"'


def test_fetch_to_cache_http_200_updates_cache(tmp_path: Path, monkeypatch) -> None:
    url = "http://example.com/list.txt"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    key = fetch._cache_key(url)
    cache_file = cache_dir / f"{key}.txt"
    sidecar = cache_dir / f"{key}.json"
    cache_file.write_text("original\n", encoding="utf-8")
    sidecar.write_text(
        json.dumps({
            "source_id": "s1",
            "hash": "abc",
            "size_bytes": 9,
            "line_count": 1,
            "parsed_ok": 0,
            "sanitized_ok": 0,
            "etag": '"abc123"',
            "last_modified": "Wed, 01 Jan 2025 00:00:00 GMT",
            "fetch_timestamp": 1.0,
        }),
        encoding="utf-8",
    )

    def fake_get(_url: str, timeout: int = 30, headers=None):
        return _Resp("updated\n", status_code=200, headers={"ETag": '"def456"'})

    monkeypatch.setattr(fetch.requests, "get", fake_get)

    _cache_path, metadata = fetch.fetch_to_cache(url, cache_dir, source_id="s1")
    assert cache_file.read_text(encoding="utf-8") == "updated\n"
    assert metadata.etag == '"def456"'


def test_fetch_to_cache_http_304_missing_cache_file(tmp_path: Path, monkeypatch) -> None:
    url = "http://example.com/list.txt"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    key = fetch._cache_key(url)
    sidecar = cache_dir / f"{key}.json"
    sidecar.write_text(
        json.dumps({
            "source_id": "s1",
            "hash": "abc",
            "size_bytes": 9,
            "line_count": 1,
            "parsed_ok": 0,
            "sanitized_ok": 0,
            "etag": '"abc123"',
            "last_modified": "Wed, 01 Jan 2025 00:00:00 GMT",
            "fetch_timestamp": 1.0,
        }),
        encoding="utf-8",
    )

    def fake_get(_url: str, timeout: int = 30, headers=None):
        return _Resp("recovered\n", status_code=200, headers={})

    monkeypatch.setattr(fetch.requests, "get", fake_get)

    cache_path, metadata = fetch.fetch_to_cache(url, cache_dir, source_id="s1")
    assert cache_path.read_text(encoding="utf-8") == "recovered\n"
