from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

# Compile regex patterns once with optimal flags
_DOMAIN_RE: Final = re.compile(
    r"^(?=.{1,253}$)(?!-)([a-z0-9-]{1,63}(?<!-)\.)+[a-z]{2,63}$",
    re.ASCII,
)
_IPV4_RE: Final = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$", re.ASCII)

ReasonType = Literal["ok", "invalid", "ip", "single_label", "label_too_long", "not_fqdn"]


@dataclass(frozen=True, slots=True)
class Sanitized:
    """Immutable sanitization result with optimized memory layout."""

    domain: str | None
    reason: ReasonType


def _normalize_domain(domain: str) -> str:
    """Normalize domain: lowercase, strip whitespace and trailing dots."""
    return domain.strip().rstrip(".").lower()


def _is_ipv4(domain: str) -> bool:
    """Check if domain is an IPv4 address."""
    return bool(_IPV4_RE.fullmatch(domain))


def _apply_idna(domain: str) -> str | None:
    """Apply IDNA encoding (punycode) and return ASCII domain, or None if invalid."""
    try:
        return domain.encode("idna").decode("ascii")
    except Exception:
        return None


def _validate_domain_regex(domain: str) -> bool:
    """Validate domain against regex pattern."""
    return bool(_DOMAIN_RE.fullmatch(domain))


def sanitize_domain(domain: str) -> Sanitized:
    """Sanitize and validate a domain.

    Applies: normalization, IDNA, regex validation.
    Rejects: IPs, single-label domains, invalid FQDNs.

    Args:
        domain: Raw domain string.

    Returns:
        Sanitized with domain (if ok) and reason.
    """
    d = _normalize_domain(domain)

    if not d:
        return Sanitized(domain=None, reason="invalid")

    if _is_ipv4(d):
        return Sanitized(domain=None, reason="ip")

    if "." not in d:
        return Sanitized(domain=None, reason="single_label")

    # Apply IDNA (punycode) for internationalized domains
    if not (d_ascii := _apply_idna(d)):
        return Sanitized(domain=None, reason="invalid")

    # Validate final domain
    if not _validate_domain_regex(d_ascii):
        return Sanitized(domain=None, reason="not_fqdn")

    return Sanitized(domain=d_ascii, reason="ok")
