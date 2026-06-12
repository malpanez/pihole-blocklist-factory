"""Firebog blocklist catalog sync and parsing."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

from .types import Source


@dataclass
class FirebogEntry:
    """Single entry from Firebog CSV (v.firebog.net/hosts/csv.txt).

    CSV format (no headers): category,status,home,title,url
    """

    category: str
    status: str  # "tick", "std", "cross"
    home: str
    title: str
    url: str


def fetch_firebog_csv() -> list[FirebogEntry]:
    """Download Firebog CSV catalog from https://v.firebog.net/hosts/csv.txt.

    Returns list of FirebogEntry objects (stable/ticked lists only).
    CSV format: "category","status","home","title","url"
    """
    url = "https://v.firebog.net/hosts/csv.txt"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    entries = []

    for parts in csv.reader(io.StringIO(resp.text)):
        if len(parts) < 5:
            continue

        category = parts[0].strip()
        status = parts[1].strip()
        home = parts[2].strip()
        title = parts[3].strip()
        url = parts[4].strip()

        # Only include "tick" (stable) entries
        if status != "tick":
            continue

        try:
            entry = FirebogEntry(
                category=category.lower(),
                status=status,
                home=home,
                title=title,
                url=url,
            )
            entries.append(entry)
        except Exception:
            continue

    return entries


def sync_firebog(config_dir: Path, dry_run: bool = False) -> dict:
    """Download Firebog catalog and generate config/sources.firebog.yml.

    Merges with existing config/sources.yml if present.
    Does NOT overwrite config/sources.local.yml.

    Returns summary dict with counts and generated config.
    """
    print("Fetching Firebog catalog...")
    entries = fetch_firebog_csv()
    print(f"  Found {len(entries)} blocklists in Firebog")

    # Enforce https:// on catalog URLs (skip insecure entries)
    secure_entries = []
    for entry in entries:
        if not entry.url.startswith("https://"):
            print(f"  ⚠ Skipping non-https Firebog entry: {entry.url}")
            continue
        secure_entries.append(entry)
    entries = secure_entries

    # Group by category
    by_category = {}
    for entry in entries:
        cat = entry.category or "uncategorized"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(entry)

    # Convert to Source objects
    sources = []
    for cat, cat_entries in sorted(by_category.items()):
        for i, entry in enumerate(cat_entries, start=1):
            # Generate ID: category_number_slugified_title
            slug = entry.title.lower().replace(" ", "_").replace("-", "_")[:30]
            source_id = f"firebog_{cat}_{i}_{slug}"

            src = Source(
                id=source_id,
                name=entry.title,
                url=entry.url,
                category=cat,  # type: ignore
                enabled=True,
                tier="stable",
                license=None,
                notes=f"Firebog {cat}: {entry.home}",
            )
            sources.append(src)

    sources_data = []
    for src in sources:
        entry: dict = {
            "id": src.id,
            "name": src.name,
            "url": src.url,
            "category": src.category,
            "enabled": src.enabled,
        }
        if src.notes:
            entry["notes"] = src.notes
        sources_data.append(entry)

    header = (
        "# Auto-generated from https://v.firebog.net/hosts/csv.txt\n"
        "# DO NOT EDIT manually; regenerate with: blocklist-factory sync-firebog\n\n"
    )
    yaml_content = header + yaml.dump(
        {"sources": sources_data}, default_flow_style=False, allow_unicode=True
    )

    output_file = config_dir / "sources.firebog.yml"
    if not dry_run:
        output_file.write_text(yaml_content, encoding="utf-8")
        print(f"✓ Generated {output_file} with {len(sources)} sources")
    else:
        print(f"[DRY RUN] Would write {len(sources)} sources to {output_file}")

    return {
        "total_entries": len(entries),
        "by_category": {cat: len(ents) for cat, ents in by_category.items()},
        "sources_generated": len(sources),
        "output_file": str(output_file),
    }
