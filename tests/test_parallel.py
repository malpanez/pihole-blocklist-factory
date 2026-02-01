from __future__ import annotations

import blocklist_builder.parallel as parallel
from blocklist_builder.parallel import parallel_parse_and_sanitize


def test_parallel_parse_and_sanitize_counts(monkeypatch) -> None:
    lines = [
        "# comment",
        "",
        "0.0.0.0 1.2.3.4",
        "0.0.0.0 example.com",
        "example.org",
        "badline",
        "foo-.bar.com",
    ]

    class BoomExecutor:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(parallel, "ProcessPoolExecutor", BoomExecutor)

    valid, discarded, parsed_ok, sanitized_ok = parallel_parse_and_sanitize(lines, drop_patterns=[])

    assert parsed_ok == 4
    assert sanitized_ok == 2
    assert set(valid) == {"example.com", "example.org"}
    assert discarded["parse_comment"] == 1
    assert discarded["parse_empty"] == 1
    assert discarded["parse_unsupported"] == 1
    assert discarded["sanitize_ip"] == 1
    assert discarded["sanitize_not_fqdn"] == 1
