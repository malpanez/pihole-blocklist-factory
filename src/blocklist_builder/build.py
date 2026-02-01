from __future__ import annotations

import contextlib
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Final

from .classify import build_provenance, partition_by_precedence
from .collapse import collapse_subdomains
from .regex import generate_regex_patterns, write_regex_file
from .config import Settings
from .fetch import fetch_to_cache
from .parallel import parallel_fetch_sources, parallel_parse_and_sanitize
from .parse import parse_lines
from .report import Stats, write_reports
from .sanitize import sanitize_domain

# Configuration constants
_PARALLEL_THRESHOLD: Final = 100000  # Lines threshold for parallelization
_ENCODING: Final = "utf-8"
_PARSE_PREFIX: Final = "parse_"
_SANITIZE_PREFIX: Final = "sanitize_"
_SOURCE_MISSING_REASON: Final = "source_missing"
_OK_REASON: Final = "ok"
_ALLOWLIST_REASON: Final = "allowlisted"
_PARSE_OK_REASON: Final = "parse_ok"
_MARGINAL_JSON_FILE: Final = "marginal.json"
_MARGINAL_MD_FILE: Final = "marginal.md"
_MARGINAL_HEADER: Final = "# Marginal contribution por fuente"
_COLLAPSED_REASON: Final = "collapsed_subdomain"


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
    match src.url:
        case url if url.startswith("file://"):
            return Path(url.removeprefix("file://"))
        case url if not no_fetch:
            src_path, _ = fetch_to_cache(url, cache_dir, source_id=src.id)
            return src_path
        case url:
            p = Path(url)
            return p if p.exists() else None


def _process_parsed_lines(
    src_id: str,
    lines: list[str],
    drop_patterns: Sequence[re.Pattern[str]],
    use_parallel: bool,
    src_category: str,
    discarded: Counter,
    source_stats: dict[str, int],
    debug_log: list[str] | None = None,
):
    """Parse and sanitize lines, yielding (domain, category, source_id, reason) tuples."""
    if use_parallel:
        valid_domains, discarded_local, parsed_ok, sanitized_ok = parallel_parse_and_sanitize(
            lines, drop_patterns=drop_patterns
        )
        for k, v in discarded_local.items():
            discarded[k] += v
            source_stats[k] = source_stats.get(k, 0) + v
        discarded[f"{_PARSE_PREFIX}ok"] += parsed_ok
        discarded[f"{_SANITIZE_PREFIX}ok"] += sanitized_ok
        source_stats[f"{_PARSE_PREFIX}ok"] = source_stats.get(f"{_PARSE_PREFIX}ok", 0) + parsed_ok
        source_stats[f"{_SANITIZE_PREFIX}ok"] = (
            source_stats.get(f"{_SANITIZE_PREFIX}ok", 0) + sanitized_ok
        )
        for domain in valid_domains:
            yield (domain, src_category, src_id, _OK_REASON)
    else:
        # Sequential for small sources
        for pl in parse_lines(lines, drop_patterns=drop_patterns):
            if pl.reason != _OK_REASON or not pl.domain:
                discarded[f"{_PARSE_PREFIX}{pl.reason}"] += 1
                source_stats[f"{_PARSE_PREFIX}{pl.reason}"] = (
                    source_stats.get(f"{_PARSE_PREFIX}{pl.reason}", 0) + 1
                )
                yield (None, None, src_id, f"{_PARSE_PREFIX}{pl.reason}")
                continue

            discarded[f"{_PARSE_PREFIX}ok"] += 1
            source_stats[f"{_PARSE_PREFIX}ok"] = source_stats.get(f"{_PARSE_PREFIX}ok", 0) + 1
            san = sanitize_domain(pl.domain)
            if san.reason != _OK_REASON or not san.domain:
                discarded[f"{_SANITIZE_PREFIX}{san.reason}"] += 1
                source_stats[f"{_SANITIZE_PREFIX}{san.reason}"] = (
                    source_stats.get(f"{_SANITIZE_PREFIX}{san.reason}", 0) + 1
                )
                yield (None, None, src_id, f"{_SANITIZE_PREFIX}{san.reason}")
                continue

            discarded[f"{_SANITIZE_PREFIX}ok"] += 1
            source_stats[f"{_SANITIZE_PREFIX}ok"] = source_stats.get(f"{_SANITIZE_PREFIX}ok", 0) + 1
            yield (san.domain, src_category, src_id, _OK_REASON)


def _process_source(
    src,
    no_fetch: bool,
    cache_dir: Path,
    drop_patterns: Sequence[re.Pattern[str]],
    discarded: Counter,
    source_stats: dict[str, dict[str, int]],
    debug_log: list[str] | None = None,
):
    """Process a single source and yield (domain, category, source_id, reason) tuples."""
    if not src.enabled:
        return

    src_path = _resolve_source_path(src, no_fetch, cache_dir)
    if not src_path:
        discarded[_SOURCE_MISSING_REASON] += 1
        stats = source_stats.setdefault(src.id, {})
        stats[_SOURCE_MISSING_REASON] = stats.get(_SOURCE_MISSING_REASON, 0) + 1
        yield (None, None, src.id, _SOURCE_MISSING_REASON)
        return

    lines = src_path.read_text(encoding=_ENCODING, errors="ignore").splitlines()
    use_parallel = len(lines) > _PARALLEL_THRESHOLD
    if debug_log is not None:
        debug_log.append(f"{src.id}: lines={len(lines)} parallel={'yes' if use_parallel else 'no'}")
    stats = source_stats.setdefault(src.id, {})
    stats["lines"] = stats.get("lines", 0) + len(lines)

    yield from _process_parsed_lines(
        src.id,
        lines,
        drop_patterns,
        use_parallel,
        src.category,
        discarded,
        source_stats=stats,
        debug_log=debug_log,
    )


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
    """Collect and validate domains from all sources.

    Returns:
        (domain_to_categories, domain_to_sources)
    """
    domain_to_categories: dict[str, set[str]] = defaultdict(set)
    domain_to_sources: dict[str, set[str]] = defaultdict(set)

    for src in settings.sources:
        if not src.enabled:
            continue
        for domain, category, source_id, reason in _process_source(
            src,
            no_fetch,
            cache_dir,
            drop_patterns,
            discarded,
            source_stats,
            debug_log=debug_log,
        ):
            if reason != _OK_REASON:
                continue

            if domain in allow:
                discarded[_ALLOWLIST_REASON] += 1
                stats = source_stats.setdefault(src.id, {})
                stats[_ALLOWLIST_REASON] = stats.get(_ALLOWLIST_REASON, 0) + 1
                continue

            domain_to_categories[domain].add(category)
            domain_to_sources[domain].add(source_id)

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
        pass


def _write_source_stats(dist_dir: Path, source_stats: dict[str, dict[str, int]]) -> None:
    """Write per-source parsing/sanitization stats."""
    if not source_stats:
        return
    out = dist_dir / "reports" / "source_stats.json"
    with contextlib.suppress(Exception):
        out.write_text(json.dumps(source_stats, indent=2), encoding=_ENCODING)


def _write_marginal(
    dist_dir: Path,
    domain_to_sources: dict[str, set[str]],
    source_map: dict[str, any],
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
        pass


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

    # Parallel fetch all sources first
    _ = parallel_fetch_sources(
        [s for s in settings.sources if s.enabled],
        cache_dir,
        no_fetch=no_fetch,
    )

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

    # NOTE: Subdomain collapsing desactivado.
    # Pi-hole NO hace wildcard blocking con listas normales.
    # Si bloqueas example.com, NO bloqueas ads.example.com automáticamente.
    # Por eso necesitamos mantener todos los subdominios explícitos.

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
    total_lines = sum(discarded.values())

    stats = Stats(
        total_lines=total_lines,
        parsed_ok=parsed_ok,
        sanitized_ok=sanitized_ok,
        unique_domains=len(all_domains),
        discarded=dict(discarded),
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
