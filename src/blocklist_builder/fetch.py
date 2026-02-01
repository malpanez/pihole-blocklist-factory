from __future__ import annotations

import hashlib
import json
import time
from functools import cache
from pathlib import Path
from typing import Final

import requests

from .types import SourceMetadata

# Pre-compiled constants
_HASH_ENCODING: Final = "utf-8"
_HASH_DIGEST_LENGTH: Final = 32
_REQUESTS_TIMEOUT_DEFAULT: Final = 30
_USER_AGENT: Final = "blocklist-factory/0.1"
_RETRY_ATTEMPTS: Final = 3


@cache
def _cache_key(url: str) -> str:
    """Generate cache key from URL (cached)."""
    return hashlib.sha256(url.encode(_HASH_ENCODING)).hexdigest()[:_HASH_DIGEST_LENGTH]


@cache
def _compute_hash(content: str) -> str:
    """Compute SHA256 hash of content (cached)."""
    return hashlib.sha256(content.encode(_HASH_ENCODING)).hexdigest()


def _load_metadata(metadata_path: Path) -> dict | None:
    """Load metadata JSON if exists, else None."""
    if not metadata_path.exists():
        return None
    try:
        return json.loads(metadata_path.read_text(encoding=_HASH_ENCODING))
    except Exception:
        return None


def _save_metadata(metadata_path: Path, metadata: SourceMetadata) -> None:
    """Save metadata to JSON."""
    data = {
        "source_id": metadata.source_id,
        "hash": metadata.hash,
        "size_bytes": metadata.size_bytes,
        "line_count": metadata.line_count,
        "parsed_ok": metadata.parsed_ok,
        "sanitized_ok": metadata.sanitized_ok,
        "etag": metadata.etag,
        "last_modified": metadata.last_modified,
        "fetch_timestamp": metadata.fetch_timestamp,
    }
    metadata_path.write_text(json.dumps(data, indent=2), encoding=_HASH_ENCODING)


def _fetch_http(
    url: str, timeout_s: int = _REQUESTS_TIMEOUT_DEFAULT, user_agent: str = _USER_AGENT
) -> str:
    """Fetch content from HTTP URL with retries and user-agent."""
    headers = {"User-Agent": user_agent}
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            r = requests.get(url, timeout=timeout_s, headers=headers)
            r.raise_for_status()
            return r.text
        except requests.RequestException:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(2 ** attempt)  # exponential backoff
    return ""  # pragma: no cover


def fetch_to_cache(
    url: str,
    cache_dir: Path,
    source_id: str = "unknown",
    timeout_s: int = _REQUESTS_TIMEOUT_DEFAULT,
) -> tuple[Path, SourceMetadata]:
    """Fetch content and cache with metadata.

    Args:
        url: Source URL (http(s)://, file://, or local path).
        cache_dir: Cache directory.
        source_id: Source identifier.
        timeout_s: Request timeout.

    Returns:
        (cache_file_path, SourceMetadata).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url)
    target = cache_dir / f"{key}.txt"
    metadata_path = cache_dir / f"{key}.json"

    # Handle file:// URLs and local paths using match/case
    match url:
        case url if url.startswith("file://"):
            src = Path(url.removeprefix("file://"))
            content = src.read_text(encoding=_HASH_ENCODING, errors="ignore")
        case url if (p := Path(url)).exists():
            content = p.read_text(encoding=_HASH_ENCODING, errors="ignore")
        case _:
            content = _fetch_http(url, timeout_s=timeout_s)

    target.write_text(content, encoding=_HASH_ENCODING)

    # Compute metadata
    content_hash = _compute_hash(content)
    line_count = len(content.splitlines())

    metadata = SourceMetadata(
        source_id=source_id,
        hash=content_hash,
        size_bytes=len(content.encode(_HASH_ENCODING)),
        line_count=line_count,
        parsed_ok=0,  # Will be filled by caller
        sanitized_ok=0,  # Will be filled by caller
        etag=None,
        last_modified=None,
        fetch_timestamp=time.time(),
    )

    _save_metadata(metadata_path, metadata)
    return target, metadata
