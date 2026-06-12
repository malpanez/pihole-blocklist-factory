import re

from blocklist_builder.parse import parse_lines


def test_parse_hosts_and_domain_and_abp():
    """Test parsing of hosts, domain-only, and ABP simple formats."""
    lines = [
        "0.0.0.0 ads.example.com",
        "bad.example.io",
        "||annoying.example.com^",
        "||complex.example.com/path^",
    ]
    out = list(parse_lines(lines))
    ok = [x.domain for x in out if x.reason == "ok"]
    assert "ads.example.com" in ok
    assert "bad.example.io" in ok
    assert "annoying.example.com" in ok
    # complex ABP rule should be unsupported
    assert any(x.reason == "unsupported" for x in out)


def test_parse_with_drop_patterns():
    """Test drop_patterns filter."""
    lines = [
        "0.0.0.0 good.com",
        "0.0.0.0 analytics.bad.com",
        "0.0.0.0 example.com",
    ]
    drop_patterns = [re.compile(r"analytics|tracking")]
    out = list(parse_lines(lines, drop_patterns=drop_patterns))
    dropped = [x for x in out if x.reason == "pattern_drop"]
    ok_domains = [x.domain for x in out if x.reason == "ok"]

    assert len(dropped) == 1  # analytics.bad.com
    assert "good.com" in ok_domains
    assert "example.com" in ok_domains


def test_parse_comments_and_empty():
    """Test that comments and empty lines are filtered."""
    lines = ["# Comment", "", "  ", "example.com", "! another comment"]
    out = list(parse_lines(lines))
    ok = [x.domain for x in out if x.reason == "ok"]
    comments = [x for x in out if x.reason == "comment"]
    empty = [x for x in out if x.reason == "empty"]

    assert len(ok) == 1
    assert "example.com" in ok
    assert len(comments) == 2
    assert len(empty) == 2


def test_classify_line_single():
    from blocklist_builder.parse import classify_line

    assert classify_line("0.0.0.0 ads.example.com", ()) == ("ads.example.com", "ok")
    assert classify_line("# comment", ()) == (None, "comment")
    assert classify_line("", ()) == (None, "empty")
    assert classify_line("garbage line here", ()) == (None, "unsupported")
    assert classify_line("bad.com", [re.compile(r"^bad")]) == (None, "pattern_drop")
