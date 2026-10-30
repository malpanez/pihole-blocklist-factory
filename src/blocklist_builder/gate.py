"""Post-build gate: decide whether a freshly built list is safe to publish."""

from __future__ import annotations

import json
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_ENCODING: Final = "utf-8"
_SOURCE_MISSING: Final = "source_missing"


@dataclass(frozen=True, slots=True)
class GateResult:
    failures: list[str]
    notes: list[str]
    domains: int
    previous: int | None


def blocking_entry(name: str, domains: AbstractSet[str]) -> str | None:
    """Return the listed entry that blocks name, or None.

    Technitium blocks hierarchically: a listed parent blocks every child, so the name and
    each parent suffix down to the last label are checked.
    """
    labels = name.split(".")
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])
        if candidate in domains:
            return candidate
    return None


def check_must_not_block(names: Iterable[str], domains: AbstractSet[str]) -> list[str]:
    failures: list[str] = []
    for name in names:
        entry = blocking_entry(name, domains)
        if entry is not None:
            failures.append(f"must-not-block {name} is blocked by list entry {entry}")
    return failures


def check_drop(current: int, previous: int, max_drop: float) -> list[str]:
    """Fail when the list shrank by more than max_drop. Requires previous > 0."""
    if (previous - current) / previous > max_drop:
        return [
            f"list shrank from {previous} to {current} domains "
            f"({(previous - current) / previous:.1%} drop, limit {max_drop:.1%})"
        ]
    return []


def _read_names(path: Path) -> list[str]:
    names: list[str] = []
    for line in path.read_text(encoding=_ENCODING, errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        names.append(s.lower().rstrip("."))
    return names


def _failed_source_ids(source_stats_path: Path) -> list[str]:
    """Ids of sources with source_missing > 0, or [] when the file is absent or unusable."""
    try:
        data = json.loads(source_stats_path.read_text(encoding=_ENCODING))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    ids: list[str] = []
    for source_id, counters in data.items():
        if not isinstance(counters, dict):
            continue
        count = counters.get(_SOURCE_MISSING, 0)
        if isinstance(count, int) and not isinstance(count, bool) and count > 0:
            ids.append(str(source_id))
    return sorted(ids)


def _source_missing_failures(stats_path: Path) -> list[str]:
    try:
        data = json.loads(stats_path.read_text(encoding=_ENCODING))
    except (OSError, ValueError) as exc:
        return [f"cannot read {stats_path}: {type(exc).__name__}"]
    discarded = data.get("discarded") if isinstance(data, dict) else None
    if not isinstance(discarded, dict):
        return [f"{stats_path} has no discarded map"]
    missing = discarded.get(_SOURCE_MISSING, 0)
    if isinstance(missing, bool) or not isinstance(missing, int):
        return [f"{stats_path} has a non-integer {_SOURCE_MISSING}: {missing!r}"]
    if missing > 0:
        message = f"{missing} source(s) failed to fetch or parse ({_SOURCE_MISSING})"
        failed = _failed_source_ids(stats_path.with_name("source_stats.json"))
        if failed:
            return [f"{message}: {', '.join(failed)}"]
        return [f"{message}; see reports/source_stats.json"]
    return []


def run_gate(
    dist: Path,
    previous: Path | None,
    max_drop: float,
    allow_drop: bool,
    must_not_block: Path,
) -> GateResult:
    """Run every gate check and report all failures. Missing inputs fail closed."""
    failures: list[str] = []
    notes: list[str] = []

    failures.extend(_source_missing_failures(dist / "reports" / "stats.json"))

    domains: set[str] = set()
    all_path = dist / "all.txt"
    try:
        domains = set(_read_names(all_path))
    except OSError as exc:
        failures.append(f"cannot read {all_path}: {type(exc).__name__}")
    else:
        if not domains:
            failures.append(f"{all_path} is empty")

    canaries: list[str] = []
    try:
        canaries = _read_names(must_not_block)
    except OSError as exc:
        failures.append(f"cannot read {must_not_block}: {type(exc).__name__}")
    else:
        if not canaries:
            failures.append(f"{must_not_block} has no names")
    if domains:
        failures.extend(check_must_not_block(canaries, domains))

    previous_count: int | None = None
    if allow_drop:
        notes.append("drop check skipped (--allow-drop)")
    elif previous is None:
        notes.append("drop check skipped: no previous list given")
    elif not previous.exists():
        notes.append(f"drop check skipped: previous list {previous} not found")
    else:
        try:
            previous_domains = _read_names(previous)
        except OSError as exc:
            failures.append(f"cannot read previous list {previous}: {type(exc).__name__}")
        else:
            if not previous_domains:
                notes.append(f"drop check skipped: previous list {previous} has 0 entries")
            else:
                previous_count = len(set(previous_domains))
                if domains:
                    failures.extend(check_drop(len(domains), previous_count, max_drop))

    return GateResult(
        failures=failures,
        notes=notes,
        domains=len(domains),
        previous=previous_count,
    )
