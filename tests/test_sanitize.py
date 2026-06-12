from blocklist_builder.sanitize import sanitize_domain


def test_sanitize_ok():
    """Test basic domain sanitization."""
    s = sanitize_domain("Example.COM.")
    assert s.reason == "ok"
    assert s.domain == "example.com"


def test_sanitize_ok_with_hyphens():
    """Test domain with hyphens."""
    s = sanitize_domain("my-ads.example.com")
    assert s.reason == "ok"
    assert s.domain == "my-ads.example.com"


def test_sanitize_reject_ip():
    """Test that IPs are rejected."""
    s = sanitize_domain("1.2.3.4")
    assert s.reason == "ip"


def test_sanitize_reject_single_label():
    """Test that single-label domains are rejected."""
    s = sanitize_domain("localhost")
    assert s.reason == "single_label"


def test_sanitize_idna():
    """Test IDNA/punycode handling."""
    # Internationalized domain
    s = sanitize_domain("münchen.de")
    assert s.reason == "ok"
    assert "xn--" in s.domain  # Should be punycode


def test_sanitize_reject_invalid():
    """Test that invalid domains are rejected."""
    s = sanitize_domain("")
    assert s.reason == "invalid"

    s = sanitize_domain("   ")
    assert s.reason == "invalid"


def test_sanitize_idna_failure():
    """Test IDNA encoding failure branch."""
    s = sanitize_domain("\ud800.com")
    assert s.reason == "invalid"


def test_sanitize_reject_numeric_tld():
    """Test that numeric-only TLDs are rejected."""
    s = sanitize_domain("foo.123")
    assert s.reason == "not_fqdn"


def test_sanitize_punycode_label():
    """Pre-encoded punycode labels with an ASCII TLD pass."""
    s = sanitize_domain("xn--80ak6aa92e.com")
    assert s.reason == "ok"
    assert s.domain == "xn--80ak6aa92e.com"


def test_sanitize_punycode_tld():
    """Unicode domains with IDN TLDs encode to punycode TLDs and pass."""
    s = sanitize_domain("пример.рф")
    assert s.reason == "ok"
    assert s.domain == "xn--e1afmkfd.xn--p1ai"


def test_sanitize_punycode_tld_preencoded():
    """Pre-encoded punycode TLDs pass directly."""
    s = sanitize_domain("example.xn--p1ai")
    assert s.reason == "ok"
    assert s.domain == "example.xn--p1ai"


def test_sanitize_reject_garbage_tlds():
    """Numeric and hyphen-leading non-punycode TLDs remain rejected."""
    assert sanitize_domain("foo.42").reason == "not_fqdn"
    assert sanitize_domain("foo.a1b").reason == "not_fqdn"
