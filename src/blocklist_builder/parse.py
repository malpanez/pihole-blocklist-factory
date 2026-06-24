from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Final, Literal

# Compile regex patterns once at module load
_ABP_SIMPLE_PATTERN: Final = re.compile(r"^\|\|(?P<domain>[A-Za-z0-9.-]+)\^$")
_HOSTS_IP_PREFIXES: Final[frozenset[str]] = frozenset({"0.0.0.0", "127.0.0.1", "::", "0"})
_GLUED_HOST_IP_RE: Final = re.compile(
    r"^(?:0\.0\.0\.0|127\.0\.0\.1|255\.255\.255\.255)(?=[a-z0-9])", re.ASCII
)


def _strip_glued_host_ip(token: str) -> str:
    """Strip a sink IP glued (no separator) to a hostname: 0.0.0.0kryptonchain.org -> kryptonchain.org."""
    return _GLUED_HOST_IP_RE.sub("", token)


# Literal reason strings for type safety
ReasonType = Literal["ok", "comment", "empty", "unsupported", "invalid", "pattern_drop", "wildcard"]


@dataclass(frozen=True, slots=True)
class ParsedLine:
    """Immutable parsed line with optimized memory layout."""

    raw: str
    domain: str | None
    reason: ReasonType


def _check_drop_patterns(line: str, drop_patterns: Sequence[re.Pattern[str]]) -> bool:
    """Check if line matches any drop pattern."""
    return any(p.search(line) for p in drop_patterns)


def _try_parse_hosts_format(parts: Sequence[str]) -> tuple[str, ...] | None:
    """Try to parse hosts format (0.0.0.0/127.0.0.1/::/0 host [host ...]).

    Returns all hostnames on the line, truncated at an inline comment token.
    """
    if len(parts) >= 2 and parts[0] in _HOSTS_IP_PREFIXES:
        hosts: list[str] = []
        for p in parts[1:]:
            if p.startswith("#") or p.startswith("!"):
                break
            hosts.append(p)
        return tuple(hosts) or None
    return None


def _try_parse_domain_only(parts: Sequence[str]) -> str | None:
    """Try to parse domain-only format (single domain per line)."""
    if len(parts) == 1 and not parts[0].startswith("||"):
        token = _strip_glued_host_ip(parts[0])
        if "." in token:
            return token
    return None


def _try_parse_abp_simple(line: str) -> str | None:
    """Try to parse ABP simple format (||domain^)."""
    if m := _ABP_SIMPLE_PATTERN.match(line):
        return m.group("domain")
    return None


def classify_line(
    raw: str,
    drop_patterns: Sequence[re.Pattern[str]],
) -> tuple[tuple[str, ...], ReasonType]:
    """Classify a single raw line, returning (domains, reason).

    Lightweight counterpart to parse_lines: no ParsedLine allocation per line.
    Hosts-format lines may carry multiple hostnames; all are returned.
    Wildcard handling (``*.example.com``) is the caller's responsibility.
    """
    line = raw.strip()

    if not line:
        return (), "empty"

    if _check_drop_patterns(line, drop_patterns):
        return (), "pattern_drop"

    match line[0]:
        case "#" | "!":
            return (), "comment"

    parts = line.split()

    if hosts := _try_parse_hosts_format(parts):
        return hosts, "ok"
    if (domain := _try_parse_domain_only(parts)) or (domain := _try_parse_abp_simple(line)):
        return (domain,), "ok"
    return (), "unsupported"


def parse_lines(
    lines: Iterable[str],
    drop_patterns: Sequence[re.Pattern[str]] | None = None,
) -> Iterator[ParsedLine]:
    """Parse lines from a blocklist, optionally filtering by regex patterns.

    Multi-hostname hosts lines yield one ParsedLine per hostname.
    Wildcard hostnames (``*.example.com``) yield reason "wildcard" (unsupported).

    Args:
        lines: Input lines from blocklist.
        drop_patterns: List of compiled regex patterns to drop matching lines.

    Yields:
        ParsedLine with domain and reason.
    """
    drop_patterns_seq: Sequence[re.Pattern[str]] = drop_patterns or ()

    for raw in lines:
        domains, reason = classify_line(raw, drop_patterns_seq)
        if reason != "ok":
            yield ParsedLine(raw=raw, domain=None, reason=reason)
            continue
        for domain in domains:
            if domain.startswith("*."):
                yield ParsedLine(raw=raw, domain=None, reason="wildcard")
            else:
                yield ParsedLine(raw=raw, domain=domain, reason="ok")
