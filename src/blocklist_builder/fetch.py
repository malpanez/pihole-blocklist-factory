from __future__ import annotations

import hashlib
import json
import time
from functools import cache
from pathlib import Path
from typing import Any, Final

import requests

from .types import SourceMetadata

# Pre-compiled constants
_HASH_ENCODING: Final = "utf-8"
_HASH_DIGEST_LENGTH: Final = 32
_REQUESTS_TIMEOUT_DEFAULT: Final = 30
_USER_AGENT: Final = "blocklist-factory/0.1"
_RETRY_ATTEMPTS: Final = 3
_MAX_DOWNLOAD_BYTES: Final = 64 * 1024 * 1024
_STREAM_CHUNK_SIZE: Final = 64 * 1024


class DownloadTooLargeError(ValueError):
    """Raised when a download exceeds the size cap. Never retried."""


@cache
def _cache_key(url: str) -> str:
    """Generate cache key from URL (cached)."""
    return hashlib.sha256(url.encode(_HASH_ENCODING)).hexdigest()[:_HASH_DIGEST_LENGTH]


def _compute_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode(_HASH_ENCODING)).hexdigest()


def _load_metadata(metadata_path: Path) -> dict[str, Any] | None:
    """Load metadata JSON if exists, else None."""
    if not metadata_path.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(metadata_path.read_text(encoding=_HASH_ENCODING))
    except Exception:
        return None
    return data


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


def _read_capped_body(r: requests.Response, url: str) -> str:
    """Read a streamed response enforcing the 64MB cap, returning decoded text."""
    content_length = r.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > _MAX_DOWNLOAD_BYTES:
        raise DownloadTooLargeError(
            f"download exceeds {_MAX_DOWNLOAD_BYTES} bytes (Content-Length): {url}"
        )

    chunks: list[bytes] = []
    total = 0
    for chunk in r.iter_content(chunk_size=_STREAM_CHUNK_SIZE):
        total += len(chunk)
        if total > _MAX_DOWNLOAD_BYTES:
            raise DownloadTooLargeError(
                f"download exceeds {_MAX_DOWNLOAD_BYTES} bytes (streamed): {url}"
            )
        chunks.append(chunk)

    data = b"".join(chunks)
    encoding = r.encoding or _HASH_ENCODING
    try:
        return data.decode(encoding, errors="ignore")
    except LookupError:
        return data.decode(_HASH_ENCODING, errors="ignore")


def _fetch_http(
    url: str,
    timeout_s: int = _REQUESTS_TIMEOUT_DEFAULT,
    user_agent: str = _USER_AGENT,
    conditional_headers: dict[str, str] | None = None,
) -> tuple[str, str | None, str | None]:
    """Fetch content from HTTP URL with retries, user-agent, and a 64MB cap.

    Retry policy: 4xx responses and oversized downloads are raised immediately;
    5xx responses and network errors are retried with exponential backoff.
    """
    headers: dict[str, str] = {"User-Agent": user_agent}
    if conditional_headers:
        headers.update(conditional_headers)
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            r = requests.get(url, timeout=timeout_s, headers=headers, stream=True)
            if r.status_code == 304:
                return "", r.headers.get("ETag"), r.headers.get("Last-Modified")
            r.raise_for_status()
            text = _read_capped_body(r, url)
            return text, r.headers.get("ETag"), r.headers.get("Last-Modified")
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and 400 <= status < 500:
                raise  # client errors are permanent — never retry
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(2**attempt)  # exponential backoff
        except requests.RequestException:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(2**attempt)  # exponential backoff
    return "", None, None  # pragma: no cover


def _ensure_contained(path: Path, allowed_base: Path | None, url: str) -> Path:
    """Resolve a local path and verify containment under allowed_base (fail closed)."""
    resolved = path.resolve()
    if allowed_base is None:
        raise ValueError(f"local source rejected (no allowed base configured): {url}")
    if not resolved.is_relative_to(allowed_base.resolve()):
        raise ValueError(f"local source escapes allowed base {allowed_base}: {url}")
    return resolved


def fetch_to_cache(
    url: str,
    cache_dir: Path,
    source_id: str = "unknown",
    timeout_s: int = _REQUESTS_TIMEOUT_DEFAULT,
    allowed_base: Path | None = None,
) -> tuple[Path, SourceMetadata]:
    """Fetch content and cache with metadata.

    Args:
        url: Source URL (http(s)://, file://, or local path).
        cache_dir: Cache directory.
        source_id: Source identifier.
        timeout_s: Request timeout.
        allowed_base: Containment root for file:// and local-path sources.
            Local sources are rejected (fail closed) when None or escaping it.

    Returns:
        (cache_file_path, SourceMetadata).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(url)
    target = cache_dir / f"{key}.txt"
    metadata_path = cache_dir / f"{key}.json"

    # Handle file:// URLs and local paths using match/case
    resp_etag: str | None = None
    resp_last_modified: str | None = None
    match url:
        case url if url.startswith("file://"):
            raw = Path(url.removeprefix("file://"))
            if ".." in raw.parts:
                raise ValueError(f"path traversal detected in file:// URL: {url}")
            src = _ensure_contained(raw, allowed_base, url)
            content = src.read_text(encoding=_HASH_ENCODING, errors="ignore")
        case url if not url.startswith(("http://", "https://")) and (p := Path(url)).exists():
            contained = _ensure_contained(p, allowed_base, url)
            content = contained.read_text(encoding=_HASH_ENCODING, errors="ignore")
        case _:
            prior = _load_metadata(metadata_path)
            cond: dict[str, str] = {}
            if prior and target.exists():
                if prior.get("etag"):
                    cond["If-None-Match"] = prior["etag"]
                if prior.get("last_modified"):
                    cond["If-Modified-Since"] = prior["last_modified"]
            content, resp_etag, resp_last_modified = _fetch_http(
                url, timeout_s=timeout_s, conditional_headers=cond or None
            )
            if not content and target.exists() and prior and cond:
                existing_meta = SourceMetadata(
                    source_id=source_id,
                    hash=prior["hash"],
                    size_bytes=prior["size_bytes"],
                    line_count=prior["line_count"],
                    parsed_ok=0,
                    sanitized_ok=0,
                    etag=resp_etag or prior.get("etag"),
                    last_modified=resp_last_modified or prior.get("last_modified"),
                    fetch_timestamp=time.time(),
                )
                _save_metadata(metadata_path, existing_meta)
                return target, existing_meta

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
        etag=resp_etag,
        last_modified=resp_last_modified,
        fetch_timestamp=time.time(),
    )

    _save_metadata(metadata_path, metadata)
    return target, metadata
