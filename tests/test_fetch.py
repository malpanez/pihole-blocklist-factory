from __future__ import annotations

from pathlib import Path

import pytest

from blocklist_builder.fetch import _compute_hash, fetch_to_cache


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_fetch_to_cache_local_path(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    _write(source, "a\nb\nc\n")

    cache_dir = tmp_path / "cache"
    cache_path, metadata = fetch_to_cache(str(source), cache_dir, source_id="s1")

    assert cache_path.exists()
    assert metadata.line_count == 3
    assert metadata.source_id == "s1"


def test_fetch_to_cache_file_url(tmp_path: Path) -> None:
    source = tmp_path / "source2.txt"
    _write(source, "x\ny\n")

    cache_dir = tmp_path / "cache2"
    url = f"file://{source}"
    cache_path, metadata = fetch_to_cache(url, cache_dir, source_id="s2")

    assert cache_path.exists()
    assert metadata.line_count == 2
    assert metadata.source_id == "s2"


def test_fetch_to_cache_traversal_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path traversal"):
        fetch_to_cache("file:///tmp/../etc/passwd", tmp_path / "cache", source_id="x")


def test_compute_hash_not_cached() -> None:
    assert not hasattr(_compute_hash, "cache_info")
