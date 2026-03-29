from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any, Final

from .classify import build_provenance, partition_by_precedence
from .config import Settings
from .fetch import fetch_to_cache
from .parallel import parallel_process_all_sources
from .regex import generate_regex_patterns, write_regex_file
from .report import Stats, write_reports
from .sanitize import sanitize_domain

# Configuration constants
_ENCODING: Final = "utf-8"
_PARSE_PREFIX: Final = "parse_"
_SANITIZE_PREFIX: Final = "sanitize_"
_SOURCE_MISSING_REASON: Final = "source_missing"
_MARGINAL_JSON_FILE: Final = "marginal.json"
_MARGINAL_MD_FILE: Final = "marginal.md"
_MARGINAL_HEADER: Final = "# Marginal contribution por fuente"


@cache
def _read_overrides(path: Path) -> frozenset[str]:
    """Read override file (one domain per line, ignoring comments) - cached."""
    if not path.exists():
        return frozenset()
    out: set[str] = set()
    for line in path.read_text(encoding=_ENCODING, errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s.lower().rstrip("."))
    return frozenset(out)


def _load_drop_patterns(drop_file: Path) -> Sequence[re.Pattern[str]]:
    """Load regex patterns for dropping lines (one pattern per line)."""
    if not drop_file.exists():
        return []
    patterns = []
    for line in drop_file.read_text(encoding=_ENCODING, errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                patterns.append(re.compile(line))
            except re.error:
                continue
    return patterns


def _resolve_source_path(src, no_fetch: bool, cache_dir: Path) -> Path | None:
    """Resolve source path handling file://, relative, and HTTP URLs.

    Returns None if source cannot be resolved.
    """
    if src.url.startswith("http://") and not src.url.startswith("https://"):
        logging.warning(
            "Source %s uses http:// (not HTTPS) — connection is insecure: %s",
            src.id if hasattr(src, "id") else "unknown",
            src.url,
        )
    match src.url:
        case url if url.startswith("file://"):
            raw = Path(url.removeprefix("file://"))
            if ".." in raw.parts:
                logging.warning("Rejected file:// URL with path traversal: %s", url)
                return None
            return raw.resolve()
        case url if not no_fetch:
            src_path, _ = fetch_to_cache(url, cache_dir, source_id=src.id)
            return src_path
        case url:
            p = Path(url)
            return p if p.exists() else None


def _resolve_all_source_paths(
    settings: Settings,
    no_fetch: bool,
    cache_dir: Path,
    discarded: Counter,
    source_stats: dict[str, dict[str, int]],
) -> dict[str, Path]:
    """Resolve file paths for all enabled sources.

    Returns:
        Dict of source_id -> resolved file path (only for sources that resolved successfully).
    """
    source_files: dict[str, Path] = {}
    for src in settings.sources:
        if not src.enabled:
            continue
        src_path = _resolve_source_path(src, no_fetch, cache_dir)
        if src_path:
            source_files[src.id] = src_path
        else:
            discarded[_SOURCE_MISSING_REASON] += 1
            stats = source_stats.setdefault(src.id, {})
            stats[_SOURCE_MISSING_REASON] = stats.get(_SOURCE_MISSING_REASON, 0) + 1
    return source_files


def _write_categories(dist_dir: Path, chosen: dict[str, str]) -> None:
    """Write per-category files."""
    cats: dict[str, list[str]] = defaultdict(list)
    for d, c in chosen.items():
        cats[c].append(d)
    for c, ds in cats.items():
        ds_sorted = sorted(set(ds))
        (dist_dir / "categories" / f"{c}.txt").write_text(
            "\n".join(ds_sorted) + ("\n" if ds_sorted else ""), encoding=_ENCODING
        )


def _write_profiles(dist_dir: Path, chosen: dict[str, str], settings: Settings) -> None:
    """Write profile files (by include_categories)."""
    for pname, pconf in settings.profiles.by_name.items():
        if pconf.include_categories:
            selected = [d for d, c in chosen.items() if c in pconf.include_categories]
        else:
            selected = list(chosen.keys())
        selected = sorted(set(selected))
        (dist_dir / "profiles" / f"{pname}.txt").write_text(
            "\n".join(selected) + ("\n" if selected else ""), encoding=_ENCODING
        )


def _collect_domains(
    settings: Settings,
    no_fetch: bool,
    cache_dir: Path,
    drop_patterns: Sequence[re.Pattern[str]],
    allow: frozenset[str],
    discarded: Counter,
    source_stats: dict[str, dict[str, int]],
    debug_log: list[str] | None = None,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Collect and validate domains from all sources using source-level parallelism.

    Each source is processed in a separate worker (parse + sanitize + allowlist filter).

    Returns:
        (domain_to_categories, domain_to_sources)
    """
    domain_to_categories: dict[str, set[str]] = defaultdict(set)
    domain_to_sources: dict[str, set[str]] = defaultdict(set)

    # Resolve all source paths in the main process
    source_files = _resolve_all_source_paths(settings, no_fetch, cache_dir, discarded, source_stats)

    # Process all sources in parallel (one worker per source)
    results = parallel_process_all_sources(source_files, drop_patterns, allow)

    # Merge results into global counters and domain mappings
    source_map = {s.id: s for s in settings.sources}
    for src_id, (valid_domains, stats) in results.items():
        source_stats[src_id] = stats
        for k, v in stats.items():
            if k != "lines":  # "lines" is metadata, not a discard reason
                discarded[k] += v

        src = source_map[src_id]
        for domain in valid_domains:
            domain_to_categories[domain].add(src.category)
            domain_to_sources[domain].add(src_id)

        if debug_log is not None:
            debug_log.append(
                f"{src_id}: lines={stats.get('lines', 0)} "
                f"valid={len(valid_domains)} parallel=source-level"
            )

    return domain_to_categories, domain_to_sources


def _add_deny_extras(domain_to_categories: dict[str, set[str]], deny_extra: frozenset[str]) -> None:
    """Add explicitly denied domains to the category dict."""
    for d in deny_extra:
        san = sanitize_domain(d)
        if san.domain:
            domain_to_categories[san.domain].add("other")


def _write_provenance(dist_dir: Path, provenance: dict) -> None:
    """Write provenance metadata JSON."""
    prov_out = dist_dir / "reports" / "provenance.json"
    try:
        prov_data = {}
        for d, p in provenance.items():
            prov_data[d] = {
                "source_ids": sorted(p.source_ids),
                "categories": sorted(p.categories),
                "assigned": p.assigned_category,
            }
        prov_out.write_text(json.dumps(prov_data, indent=2), encoding=_ENCODING)
    except Exception:
        logging.warning("Failed to write provenance file %s", prov_out, exc_info=True)


def _write_source_stats(dist_dir: Path, source_stats: dict[str, dict[str, int]]) -> None:
    """Write per-source parsing/sanitization stats."""
    if not source_stats:
        return
    out = dist_dir / "reports" / "source_stats.json"
    try:
        out.write_text(json.dumps(source_stats, indent=2), encoding=_ENCODING)
    except Exception:
        logging.warning("Failed to write source stats to %s", out, exc_info=True)


def _write_marginal(
    dist_dir: Path,
    domain_to_sources: dict[str, set[str]],
    source_map: dict[str, Any],
) -> None:
    """Write marginal contribution per source."""
    try:
        marginal: dict[str, int] = {}
        for src_id in source_map:
            cnt = sum(1 for d, sset in domain_to_sources.items() if sset == {src_id})
            marginal[src_id] = cnt

        (dist_dir / "reports" / _MARGINAL_JSON_FILE).write_text(
            json.dumps(marginal, indent=2), encoding=_ENCODING
        )
        # human readable
        md = [_MARGINAL_HEADER, ""]
        for sid, cnt in sorted(marginal.items(), key=lambda x: -x[1]):
            src = source_map.get(sid)
            name = src.name if src else sid
            md.append(f"- {sid} ({name}): {cnt} dominios únicos netos")
        (dist_dir / "reports" / _MARGINAL_MD_FILE).write_text(
            "\n".join(md) + "\n", encoding=_ENCODING
        )
    except Exception:
        logging.warning("Failed to write marginal contribution report", exc_info=True)


def build(
    repo_root: Path,
    settings: Settings,
    no_fetch: bool = False,
) -> Stats:
    """Build blocklist from sources with sanitization and categorization."""
    dist_dir = repo_root / "dist"
    (dist_dir / "categories").mkdir(parents=True, exist_ok=True)
    (dist_dir / "profiles").mkdir(parents=True, exist_ok=True)
    (dist_dir / "reports").mkdir(parents=True, exist_ok=True)

    overrides_dir = repo_root / "inputs" / "current_overrides"
    allow = _read_overrides(overrides_dir / "allowlist.txt") | settings.policies.base_allowlist
    deny_extra = _read_overrides(overrides_dir / "denylist_extra.txt")
    drop_patterns = _load_drop_patterns(overrides_dir / "drop_patterns.txt")

    cache_dir = repo_root / ".cache" / "sources"

    debug_enabled = os.environ.get("BLOCKLIST_DEBUG", "").lower() in {"1", "true", "yes"}
    debug_log: list[str] | None = [] if debug_enabled else None

    discarded = Counter()
    source_stats: dict[str, dict[str, int]] = {}
    domain_to_categories, domain_to_sources = _collect_domains(
        settings,
        no_fetch,
        cache_dir,
        drop_patterns,
        allow,
        discarded,
        source_stats,
        debug_log=debug_log,
    )

    # Force deny extras
    _add_deny_extras(domain_to_categories, deny_extra)

    # Assign categories by precedence
    chosen = partition_by_precedence(domain_to_categories, settings.policies.category_precedence)

    # Build provenance and write metadata
    source_map = {s.id: s for s in settings.sources}
    provenance = build_provenance(
        domain_to_sources, source_map, settings.policies.category_precedence
    )
    _write_provenance(dist_dir, provenance)
    _write_source_stats(dist_dir, source_stats)

    # Write outputs
    all_domains = sorted(chosen.keys())
    (dist_dir / "all.txt").write_text(
        "\n".join(all_domains) + ("\n" if all_domains else ""), encoding=_ENCODING
    )

    _write_categories(dist_dir, chosen)
    _write_profiles(dist_dir, chosen, settings)
    _write_marginal(dist_dir, domain_to_sources, source_map)
    _write_allowlist(dist_dir, allow, settings.policies.core_domains)

    # Generate regex patterns for efficient blocking
    regex_patterns = generate_regex_patterns(set(chosen.keys()))
    write_regex_file(dist_dir / "regex.txt", regex_patterns)

    # Generate stats
    parsed_ok = discarded.get(f"{_PARSE_PREFIX}ok", 0)
    sanitized_ok = discarded.get(f"{_SANITIZE_PREFIX}ok", 0)
    total_lines = sum(s.get("lines", 0) for s in source_stats.values())

    _ok_keys = {f"{_PARSE_PREFIX}ok", f"{_SANITIZE_PREFIX}ok"}
    stats = Stats(
        total_lines=total_lines,
        parsed_ok=parsed_ok,
        sanitized_ok=sanitized_ok,
        unique_domains=len(all_domains),
        discarded={k: v for k, v in discarded.items() if k not in _ok_keys},
    )
    write_reports(dist_dir / "reports", stats)

    if debug_log is not None:
        debug_path = dist_dir / "reports" / "debug.log"
        debug_path.write_text("\n".join(debug_log) + "\n", encoding=_ENCODING)

    return stats


def _write_allowlist(
    dist_dir: Path,
    allow: frozenset[str],
    core_domains: frozenset[str],
) -> None:
    """Write consolidated allowlist for Pi-hole v6 Antigravity.

    Combines user allowlist with core_domains for a single subscribable list.
    """
    combined = sorted(allow | core_domains)
    if not combined:
        return

    header = [
        "# Pi-hole v6 Antigravity Allowlist",
        "# Generated by blocklist-factory",
        "# Subscribe to this list in Pi-hole: Lists > Add allowlist",
        "#",
    ]
    content = "\n".join(header) + "\n" + "\n".join(combined) + "\n"
    (dist_dir / "allowlist.txt").write_text(content, encoding=_ENCODING)
