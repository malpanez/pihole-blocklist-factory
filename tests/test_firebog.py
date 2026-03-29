from __future__ import annotations

from pathlib import Path

import blocklist_builder.firebog as firebog
from blocklist_builder.firebog import FirebogEntry


class _Resp:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


def test_fetch_firebog_csv_parses(monkeypatch) -> None:
    csv = "\n".join(
        [
            '"ads","tick","home","Ads List","http://example.com/ads.txt"',
            '"ads","std","home","Ads Std","http://example.com/ads-std.txt"',
            '"malware","tick","home","Malware List","http://example.com/mal.txt"',
            "",
            '"broken","tick","home","Broken"',
        ]
    )

    def fake_get(_url: str, timeout: int = 30):
        return _Resp(csv)

    monkeypatch.setattr(firebog.requests, "get", fake_get)
    entries = firebog.fetch_firebog_csv()
    assert len(entries) == 2
    assert entries[0].category in {"ads", "malware"}


def test_fetch_firebog_csv_entry_error(monkeypatch) -> None:
    csv = '"ads","tick","home","Ads List","http://example.com/ads.txt"'

    def fake_get(_url: str, timeout: int = 30):
        return _Resp(csv)

    class Boom:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(firebog.requests, "get", fake_get)
    monkeypatch.setattr(firebog, "FirebogEntry", Boom)
    entries = firebog.fetch_firebog_csv()
    assert entries == []


def test_sync_firebog_dry_run(tmp_path: Path, monkeypatch) -> None:
    entries = [
        FirebogEntry(category="ads", status="tick", home="h", title="Ads One", url="u1"),
        FirebogEntry(category="ads", status="tick", home="h", title="Ads Two", url="u2"),
    ]

    def fake_fetch():
        return entries

    monkeypatch.setattr(firebog, "fetch_firebog_csv", fake_fetch)
    result = firebog.sync_firebog(tmp_path, dry_run=True)
    assert result["total_entries"] == 2
    assert result["sources_generated"] == 2
    assert not (tmp_path / "sources.firebog.yml").exists()


def test_sync_firebog_writes_file(tmp_path: Path, monkeypatch) -> None:
    entries = [
        FirebogEntry(category="ads", status="tick", home="h", title="Ads One", url="u1"),
    ]

    def fake_fetch():
        return entries

    monkeypatch.setattr(firebog, "fetch_firebog_csv", fake_fetch)
    result = firebog.sync_firebog(tmp_path, dry_run=False)
    out = tmp_path / "sources.firebog.yml"
    assert out.exists()
    assert "sources:" in out.read_text(encoding="utf-8")
    import yaml as _yaml
    parsed = _yaml.safe_load(out.read_text(encoding="utf-8"))
    assert len(parsed["sources"]) == 1
    assert parsed["sources"][0]["id"].startswith("firebog_ads_")
    assert parsed["sources"][0]["enabled"] is True
    assert result["sources_generated"] == 1
