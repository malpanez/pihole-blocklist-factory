from __future__ import annotations

from pathlib import Path

import blocklist_builder.fetch as fetch


class _Resp:
    def __init__(self, text: str) -> None:
        self.text = text

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
