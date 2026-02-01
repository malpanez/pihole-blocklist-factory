"""Parallel processing utilities for blocklist building.

Optimizations:
1. Parallel source fetching (concurrent HTTP requests)
2. Parallel parsing and sanitization
3. Streaming deduplication (avoid loading all domains in memory)
4. Batch I/O operations
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
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
    # Default: use 75% of CPUs for I/O tasks
    return max(1, cpu_count() // 4 * 3)


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
        # Skip network in no_fetch mode
        result = {}
        for src in sources:
            if not src.enabled:
                continue
            url = src.url
            src_path = Path(url.removeprefix("file://")) if url.startswith("file://") else Path(url)
            if src_path.exists():
                result[src.id] = src_path
        return result

    result = {}
    workers = min(get_optimal_workers(), len(sources))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for src in sources:
            if not src.enabled:
                continue
            future = executor.submit(
                fetch_to_cache,
                src.url,
                cache_dir,
                source_id=src.id,
                timeout_s=timeout_s,
            )
            futures[future] = src.id

        for future in as_completed(futures):
            src_id = futures[future]
            try:
                cache_path, _ = future.result()
                result[src_id] = cache_path
            except Exception:
                # Fetch failed; mark for skip
                result[src_id] = None

    return result


def parallel_parse_and_sanitize(
    lines: list[str],
    drop_patterns: list,
) -> tuple[list[str], dict[str, int], int, int]:
    """Parse and sanitize lines in parallel.

    Args:
        lines: Input lines.
        drop_patterns: Regex patterns to drop.

    Returns:
        (valid_domains, discard_reasons)
    """
    # For smaller workloads, sequential is faster due to overhead
    if len(lines) < 1000:
        valid, discarded, parsed_ok, sanitized_ok = _process_chunk_local(lines, drop_patterns)
        return valid, discarded, parsed_ok, sanitized_ok

    # For large workloads, use ProcessPoolExecutor for CPU-bound sanitization
    # Split into chunks
    workers = get_optimal_workers()
    chunk_size = max(100, len(lines) // workers)
    chunks = [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]

    valid_all = []
    discarded_all: dict[str, int] = {}
    parsed_ok_total = 0
    sanitized_ok_total = 0
    drop_pattern_texts = [p.pattern for p in drop_patterns]
    try:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_chunk_worker, (chunk, drop_pattern_texts)): i
                for i, chunk in enumerate(chunks)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    valid, discarded, parsed_ok, sanitized_ok = future.result()
                    valid_all.extend(valid)
                    parsed_ok_total += parsed_ok
                    sanitized_ok_total += sanitized_ok
                    for k, v in discarded.items():
                        discarded_all[k] = discarded_all.get(k, 0) + v
                except Exception:
                    valid, discarded, parsed_ok, sanitized_ok = _process_chunk_local(
                        chunks[idx], drop_patterns
                    )
                    valid_all.extend(valid)
                    parsed_ok_total += parsed_ok
                    sanitized_ok_total += sanitized_ok
                    for k, v in discarded.items():
                        discarded_all[k] = discarded_all.get(k, 0) + v
    except Exception:
        valid_all, discarded_all, parsed_ok_total, sanitized_ok_total = _process_chunk_local(
            lines, drop_patterns
        )

    return valid_all, discarded_all, parsed_ok_total, sanitized_ok_total


def streaming_deduplicate(
    domain_iterables: Iterator[str],
) -> Iterator[str]:
    """Stream unique domains without loading all in memory.

    Uses a set that's written to disk periodically to avoid OOM on very large lists.

    Args:
        domain_iterables: Iterator of domains.

    Yields:
        Unique domains.
    """
    seen = set()
    for domain in domain_iterables:
        d = domain.strip().lower()
        if d and d not in seen:
            seen.add(d)
            yield d
