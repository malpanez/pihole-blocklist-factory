from __future__ import annotations

from pathlib import Path

from blocklist_builder.regex import generate_regex_patterns, write_regex_file


def test_generate_regex_patterns_numeric_and_tracking() -> None:
    domains = {
        "adsc1.example.com",
        "adsc2.example.com",
        "adsc3.example.com",
        "adsc4.example.com",
        "adsc5.example.com",
        "track-1.example.com",
        "track-2.example.com",
        "track-3.example.com",
        "track-4.example.com",
        "track-5.example.com",
    }

    patterns = generate_regex_patterns(domains)
    assert any("adsc[0-9]+" in p for p in patterns)
    assert any("track" in p for p in patterns)


def test_write_regex_file(tmp_path: Path) -> None:
    output = tmp_path / "regex.txt"
    count = write_regex_file(output, ["(\\.|^)ad[0-9]+\\.example\\.com$"])
    assert count == 1
    content = output.read_text(encoding="utf-8")
    assert "Pi-hole Regex Blocklist" in content
    assert "ad[0-9]+" in content

    output_empty = tmp_path / "regex-empty.txt"
    count_empty = write_regex_file(output_empty, [])
    assert count_empty == 0
    assert not output_empty.exists()
