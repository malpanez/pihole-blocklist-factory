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

    assert classify_line("0.0.0.0 ads.example.com", ()) == (("ads.example.com",), "ok")
    assert classify_line("# comment", ()) == ((), "comment")
    assert classify_line("", ()) == ((), "empty")
    assert classify_line("garbage line here", ()) == ((), "unsupported")
    assert classify_line("bad.com", [re.compile(r"^bad")]) == ((), "pattern_drop")


def test_classify_line_multi_hostname():
    from blocklist_builder.parse import classify_line

    domains, reason = classify_line("0.0.0.0 a.example.com b.example.com c.example.com", ())
    assert reason == "ok"
    assert domains == ("a.example.com", "b.example.com", "c.example.com")


def test_classify_line_multi_hostname_inline_comment():
    from blocklist_builder.parse import classify_line

    domains, reason = classify_line("0.0.0.0 a.example.com # inline note", ())
    assert reason == "ok"
    assert domains == ("a.example.com",)


def test_parse_multi_hostname_hosts_line():
    """Each hostname on a multi-host hosts line counts toward parse_ok individually."""
    out = list(parse_lines(["0.0.0.0 a.example.com b.example.com"]))
    ok = [x.domain for x in out if x.reason == "ok"]
    assert ok == ["a.example.com", "b.example.com"]
    # one ParsedLine per hostname, same raw line
    assert all(x.raw == "0.0.0.0 a.example.com b.example.com" for x in out)


def test_parse_wildcard_rejected():
    """Wildcards are counted as wildcard, never mapped to base domain."""
    out = list(parse_lines(["*.example.com", "0.0.0.0 *.tracker.example.com good.example.com"]))
    wildcards = [x for x in out if x.reason == "wildcard"]
    ok = [x.domain for x in out if x.reason == "ok"]
    assert len(wildcards) == 2
    assert ok == ["good.example.com"]
