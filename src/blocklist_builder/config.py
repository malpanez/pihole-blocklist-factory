from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import yaml

from .types import Profile, Source

# Configuration constants
_DEFAULT_CATEGORY_PRECEDENCE: Final = [
    "malicious",
    "tracking",
    "advertising",
    "suspicious",
    "other",
    "telemetry",
]
_BLOCKLIST_SOURCES_MODE: Final = os.environ.get("BLOCKLIST_SOURCES", "sources")
ConfigMode = Literal["sources", "test"]


@dataclass(frozen=True, slots=True)
class Policies:
    category_precedence: list[str]
    core_domains: set[str]
    base_allowlist: set[str]
    sensitive_domains: set[str] | None = None


@dataclass(frozen=True, slots=True)
class ProfilesConfig:
    by_name: dict[str, Profile]


@dataclass(frozen=True, slots=True)
class Settings:
    sources: list[Source]
    policies: Policies
    profiles: ProfilesConfig


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read YAML file safely; return empty dict if not found."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def load_settings(config_dir: Path) -> Settings:
    """Load config from sources.yml, sources.firebog.yml, sources.local.yml, policies.yml, profiles.yml.

    Environment variable BLOCKLIST_SOURCES can override which sources to load:
    - sources (default): sources.yml + sources.firebog.yml + sources.local.yml
    - test: sources.test.yml (for local testing)
    """
    # Use match/case for mode selection
    match _BLOCKLIST_SOURCES_MODE:
        case "test":
            # Load only test sources
            sources_yml = _read_yaml(config_dir / "sources.test.yml")
            sources_firebog_yml = {}
            sources_local_yml = {}
        case _:
            # Load public + firebog + local
            sources_yml = _read_yaml(config_dir / "sources.yml")
            sources_firebog_yml = _read_yaml(config_dir / "sources.firebog.yml")
            sources_local_yml = _read_yaml(config_dir / "sources.local.yml")

    policies_yml = _read_yaml(config_dir / "policies.yml")
    profiles_yml = _read_yaml(config_dir / "profiles.yml")

    # Merge sources: public + firebog (auto-gen) + local (overrides/extends)
    all_sources_data = sources_yml.get("sources", [])
    if sources_firebog_yml.get("sources"):
        all_sources_data.extend(sources_firebog_yml["sources"])
    if sources_local_yml.get("sources"):
        all_sources_data.extend(sources_local_yml["sources"])

    sources: list[Source] = []
    seen_ids: set[str] = set()
    for item in all_sources_data:
        src_id = str(item["id"])
        if src_id in seen_ids:
            continue  # skip duplicate IDs (local can't override public yet)
        seen_ids.add(src_id)
        sources.append(
            Source(
                id=src_id,
                name=str(item.get("name", src_id)),
                category=str(item.get("category", "other")),
                url=str(item["url"]),
                enabled=bool(item.get("enabled", True)),
                tier=str(item.get("tier", "stable")),
                license=item.get("license"),
                notes=item.get("notes"),
            )
        )

    policies_data = policies_yml.get("policies", {})
    pol = Policies(
        category_precedence=(
            [str(x) for x in policies_data.get("category_precedence", [])]
            or _DEFAULT_CATEGORY_PRECEDENCE
        ),
        core_domains=set(policies_data.get("core_domains", []) or []),
        base_allowlist=set(policies_data.get("base_allowlist", []) or []),
        sensitive_domains=set(policies_data.get("sensitive_domains", []) or []),
    )

    # Parse profiles with better structure
    profiles_data = profiles_yml.get("profiles", {}) or {}
    profiles_dict: dict[str, Profile] = {}
    for pname, pconf in profiles_data.items():
        profiles_dict[str(pname)] = Profile(
            name=str(pname),
            include_categories=set(pconf.get("include_categories", []) or []),
            include_sources=set(pconf.get("include_sources", []) or []),
            exclude_sources=set(pconf.get("exclude_sources", []) or []),
            strict=bool(pconf.get("strict", False)),
        )

    prof = ProfilesConfig(by_name=profiles_dict)
    return Settings(sources=sources, policies=pol, profiles=prof)
