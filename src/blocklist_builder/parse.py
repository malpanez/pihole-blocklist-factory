from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Final, Literal

# Compile regex patterns once at module load
_ABP_SIMPLE_PATTERN: Final = re.compile(r"^\|\|(?P<domain>[A-Za-z0-9.-]+)\^$")
_HOSTS_IP_PREFIXES: Final[frozenset[str]] = frozenset({"0.0.0.0", "127.0.0.1", "::", "0"})

# Literal reason strings for type safety
ReasonType = Literal["ok", "comment", "empty", "unsupported", "invalid", "pattern_drop"]


@dataclass(frozen=True, slots=True)
class ParsedLine:
    """Immutable parsed line with optimized memory layout."""

    raw: str
    domain: str | None
    reason: ReasonType


def _check_drop_patterns(line: str, drop_patterns: Sequence[re.Pattern[str]]) -> bool:
    """Check if line matches any drop pattern."""
    return any(p.search(line) for p in drop_patterns)


def _try_parse_hosts_format(parts: Sequence[str]) -> str | None:
    """Try to parse hosts format (0.0.0.0/127.0.0.1/::/0 domain)."""
    if len(parts) >= 2 and parts[0] in _HOSTS_IP_PREFIXES:
        return parts[1]
    return None


def _try_parse_domain_only(parts: Sequence[str]) -> str | None:
    """Try to parse domain-only format (single domain per line)."""
    if len(parts) == 1 and "." in parts[0] and not parts[0].startswith("||"):
        return parts[0]
    return None


def _try_parse_abp_simple(line: str) -> str | None:
    """Try to parse ABP simple format (||domain^)."""
    if m := _ABP_SIMPLE_PATTERN.match(line):
        return m.group("domain")
    return None


def classify_line(
    raw: str,
    drop_patterns: Sequence[re.Pattern[str]],
) -> tuple[str | None, ReasonType]:
    """Classify a single raw line, returning (domain, reason).

    Lightweight counterpart to parse_lines: no ParsedLine allocation per line.
    """
    line = raw.strip()

    if not line:
        return None, "empty"

    if _check_drop_patterns(line, drop_patterns):
        return None, "pattern_drop"

    match line[0]:
        case "#" | "!":
            return None, "comment"

    parts = line.split()

    # Try multiple formats using walrus operator
    if (
        (domain := _try_parse_hosts_format(parts))
        or (domain := _try_parse_domain_only(parts))
        or (domain := _try_parse_abp_simple(line))
    ):
        return domain, "ok"
    return None, "unsupported"


def parse_lines(
    lines: Iterable[str],
    drop_patterns: Sequence[re.Pattern[str]] | None = None,
) -> Iterator[ParsedLine]:
    """Parse lines from a blocklist, optionally filtering by regex patterns.

    Args:
        lines: Input lines from blocklist.
        drop_patterns: List of compiled regex patterns to drop matching lines.

    Yields:
        ParsedLine with domain and reason.
    """
    drop_patterns_seq: Sequence[re.Pattern[str]] = drop_patterns or ()

    for raw in lines:
        domain, reason = classify_line(raw, drop_patterns_seq)
        yield ParsedLine(raw=raw, domain=domain, reason=reason)
