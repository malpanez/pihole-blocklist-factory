"""Parallel processing utilities for blocklist building.

Optimizations:
1. Parallel source fetching (concurrent HTTP requests)
2. Parallel parsing and sanitization
3. Streaming deduplication (avoid loading all domains in memory)
4. Batch I/O operations
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path

from .fetch import fetch_to_cache
from .parse import parse_lines
from .sanitize import sanitize_domain
from .types import Source


def _process_chunk_local(
    chunk_lines: list[str],
    drop_patterns: list,
) -> tuple[list[str], dict[str, int], int, int]:
    """Process a chunk of lines (parse + sanitize) in the current process."""
    valid = []
    discarded: dict[str, int] = {}
    parsed_ok = 0
    sanitized_ok = 0
    for pl in parse_lines(chunk_lines, drop_patterns=drop_patterns):
        if pl.reason != "ok" or not pl.domain:
            key = f"parse_{pl.reason}"
            discarded[key] = discarded.get(key, 0) + 1
            continue
        parsed_ok += 1
        san = sanitize_domain(pl.domain)
        if san.reason == "ok" and san.domain:
            sanitized_ok += 1
            valid.append(san.domain)
        else:
            key = f"sanitize_{san.reason}"
            discarded[key] = discarded.get(key, 0) + 1
    return valid, discarded, parsed_ok, sanitized_ok


def _process_chunk_worker(
    args: tuple[list[str], list[str]],
) -> tuple[list[str], dict[str, int], int, int]:
    """Worker-safe chunk processor (picklable)."""
    chunk_lines, drop_pattern_texts = args
    patterns = [re.compile(p) for p in drop_pattern_texts] if drop_pattern_texts else []
    return _process_chunk_local(chunk_lines, patterns)


def get_optimal_workers() -> int:
    """Get optimal number of workers based on CPU count and environment."""
    # Allow override via BLOCKLIST_WORKERS env var
    if workers := os.environ.get("BLOCKLIST_WORKERS"):
        return max(1, int(workers))
    # Default: use 75% of CPUs
    return max(1, cpu_count() * 3 // 4)


def _resolve_local_sources(sources: list[Source]) -> dict[str, Path]:
    """Resolve local source paths for no-fetch mode."""
    result = {}
    for src in sources:
        if not src.enabled:
            continue
        url = src.url
        raw_path = Path(url.removeprefix("file://")) if url.startswith("file://") else Path(url)
        if url.startswith("file://") and ".." in raw_path.parts:
            logging.warning("Rejected file:// URL with path traversal: %s", url)
            continue
        src_path = raw_path.resolve() if url.startswith("file://") else raw_path
        if src_path.exists():
            result[src.id] = src_path
    return result


def parallel_fetch_sources(
    sources: list[Source],
    cache_dir: Path,
    no_fetch: bool = False,
    timeout_s: int = 30,
) -> dict[str, Path]:
    """Fetch multiple sources in parallel.

    Args:
        sources: List of Source objects.
        cache_dir: Cache directory.
        no_fetch: Skip fetch, use cached files.
        timeout_s: Request timeout per source.

    Returns:
        Dict mapping source_id -> cache_file_path.
    """
    if no_fetch:
        return _resolve_local_sources(sources)

    enabled = [s for s in sources if s.enabled]
    workers = min(get_optimal_workers(), len(enabled)) if enabled else 1
    result: dict[str, Path] = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                fetch_to_cache, src.url, cache_dir, source_id=src.id, timeout_s=timeout_s
            ): src.id
            for src in enabled
        }
        for future in as_completed(futures):
            src_id = futures[future]
            try:
                cache_path, _ = future.result()
                result[src_id] = cache_path
            except Exception:
                logging.warning("Failed to fetch source %s", src_id, exc_info=True)
                result[src_id] = None

    return result


def _process_source_file_worker(
    args: tuple[str, list[str], frozenset[str]],
) -> tuple[list[str], dict[str, int]]:
    """Process one source file in a worker process.

    Reads the file, parses lines, sanitizes domains, and filters allowlisted entries.

    Args:
        args: (file_path_str, drop_pattern_texts, allow_frozenset)

    Returns:
        (valid_domains, stats_dict)
    """
    file_path_str, drop_pattern_texts, allow = args
    patterns = [re.compile(p) for p in drop_pattern_texts] if drop_pattern_texts else []
    lines = Path(file_path_str).read_text(encoding="utf-8", errors="ignore").splitlines()
    valid, discarded, parsed_ok, sanitized_ok = _process_chunk_local(lines, patterns)

    # Filter allowlisted domains
    allowlisted = 0
    if allow:
        filtered = []
        for d in valid:
            if d in allow:
                allowlisted += 1
            else:
                filtered.append(d)
        valid = filtered

    stats = dict(discarded)
    stats["lines"] = len(lines)
    stats["parse_ok"] = parsed_ok
    stats["sanitize_ok"] = sanitized_ok
    stats["allowlisted"] = allowlisted
    return valid, stats


def parallel_process_all_sources(
    source_files: dict[str, Path],
    drop_patterns: Sequence[re.Pattern[str]],
    allow: frozenset[str],
) -> dict[str, tuple[list[str], dict[str, int]]]:
    """Process all source files in parallel, one worker per source.

    Each worker independently reads, parses, sanitizes, and filters a source file.
    This provides source-level parallelism instead of only chunk-level parallelism
    within a single source.

    Args:
        source_files: Dict of source_id -> resolved file path.
        drop_patterns: Compiled regex patterns for dropping lines.
        allow: Frozenset of allowlisted domains to exclude.

    Returns:
        Dict of source_id -> (valid_domains, stats_dict).
    """
    if not source_files:
        return {}

    drop_pattern_texts = [p.pattern for p in drop_patterns]
    results: dict[str, tuple[list[str], dict[str, int]]] = {}

    # For few sources, skip process pool overhead
    if len(source_files) <= 2:
        for src_id, file_path in source_files.items():
            results[src_id] = _process_source_file_worker(
                (str(file_path), drop_pattern_texts, allow)
            )
        return results

    workers = min(get_optimal_workers(), len(source_files))
    try:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _process_source_file_worker,
                    (str(file_path), drop_pattern_texts, allow),
                ): src_id
                for src_id, file_path in source_files.items()
            }
            for future in as_completed(futures):
                src_id = futures[future]
                try:
                    results[src_id] = future.result()
                except Exception:
                    logging.warning(
                        "Worker failed for source %s, processing locally",
                        src_id,
                        exc_info=True,
                    )
                    results[src_id] = _process_source_file_worker(
                        (str(source_files[src_id]), drop_pattern_texts, allow)
                    )
    except Exception:
        logging.warning(
            "ProcessPoolExecutor failed, falling back to sequential",
            exc_info=True,
        )
        for src_id, file_path in source_files.items():
            if src_id not in results:
                results[src_id] = _process_source_file_worker(
                    (str(file_path), drop_pattern_texts, allow)
                )

    return results
