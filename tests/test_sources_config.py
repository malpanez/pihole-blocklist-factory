from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from blocklist_builder.config import load_settings
from blocklist_builder.types import Source

ROOT = Path(__file__).resolve().parents[1]

DISABLED_IDS = [
    "notracking_tracker",
    "blocklistproject_ads",
    "easyprivacy_hosts",
    "phishing_army",
    "pyenb_blocklist",
    "urlhaus_online",
    "1hosts_lite",
    "openphish",
    "firebog_malicious_5_quidsup_malicious",
    "firebog_advertising_7_fademind's_unchecky_ads",
    "firebog_malicious_3_fademind's_risky_hosts",
    "firebog_suspicious_2_fademind's_spammers",
    "firebog_tracking_3_fademind's_2o7_network_tracker",
    "firebog_malicious_8_urlhaus_malicious_url_blocklis",
]
FIREBOG_OVERRIDE_IDS = [i for i in DISABLED_IDS if i.startswith("firebog_")]
RETIRED_URL_PARTS = ["FadeMind/", "urlhaus.abuse.ch", "cdn.jsdelivr.net"]


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> dict[str, Source]:
    monkeypatch.delenv("BLOCKLIST_SOURCES", raising=False)
    settings = load_settings(ROOT / "config")
    return {s.id: s for s in settings.sources}


@pytest.mark.parametrize("source_id", DISABLED_IDS)
def test_retired_sources_are_disabled(sources: dict[str, Source], source_id: str) -> None:
    assert source_id in sources
    assert sources[source_id].enabled is False


def test_firebog_override_ids_still_exist_in_generated_catalog() -> None:
    generated = yaml.safe_load(
        (ROOT / "config" / "sources.firebog.yml").read_text(encoding="utf-8")
    )
    generated_ids = {item["id"] for item in generated["sources"]}
    assert set(FIREBOG_OVERRIDE_IDS) <= generated_ids


def test_no_enabled_source_uses_a_retired_host(sources: dict[str, Source]) -> None:
    offenders = [
        (s.id, part)
        for s in sources.values()
        if s.enabled
        for part in RETIRED_URL_PARTS
        if part in s.url
    ]
    assert offenders == []


def test_no_two_enabled_sources_share_a_url(sources: dict[str, Source]) -> None:
    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str]] = []
    for s in sources.values():
        if not s.enabled:
            continue
        if s.url in seen:
            duplicates.append((seen[s.url], s.id))
        seen[s.url] = s.id
    assert duplicates == []


def test_metamask_source_reads_only_the_blacklist(sources: dict[str, Source]) -> None:
    metamask = sources["metamask_phishing"]
    assert metamask.json_key == "blacklist"
    assert metamask.category == "malicious"
    assert metamask.enabled is True


def test_new_sources_are_enabled(sources: dict[str, Source]) -> None:
    for source_id in ("hagezi_pro", "hagezi_tif", "urlhaus_filter", "metamask_phishing"):
        assert sources[source_id].enabled is True


def test_must_not_block_has_26_unique_names() -> None:
    path = ROOT / "inputs" / "current_overrides" / "must_not_block.txt"
    names = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(names) == 26
    assert len(set(names)) == 26
