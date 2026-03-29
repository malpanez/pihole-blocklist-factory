# Phase 4: HTTP Conditional Fetching - Research

**Researched:** 2026-03-29
**Domain:** Python HTTP conditional requests (ETag / If-Modified-Since / HTTP 304)
**Confidence:** HIGH

## Summary

The infrastructure for conditional fetching already exists in this codebase. `SourceMetadata` has `etag` and `last_modified` fields, `_load_metadata` / `_save_metadata` already read and write a JSON sidecar per source, and the sidecar path is deterministic (`{sha256(url)[:32]}.json`). The only missing pieces are: (1) loading prior metadata before a fetch, (2) sending conditional headers when prior values exist, (3) handling HTTP 304 by reusing the cached `.txt` file without rewriting it, and (4) capturing `ETag` / `Last-Modified` headers from 200 responses and persisting them.

`_fetch_http` currently returns `str` (content only). The cleanest change is to return a named tuple or dataclass so callers can also receive the response headers — or to restructure so `fetch_to_cache` handles the conditional logic directly via the `requests` response object before `_fetch_http` discards headers. The latter is cleaner because `fetch_to_cache` already owns the cache path and metadata lifecycle.

**Primary recommendation:** Restructure `_fetch_http` to return `tuple[str, str | None, str | None]` (content, etag, last_modified) and add prior-metadata loading and 304 handling in `fetch_to_cache`. No new dependencies required.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NET-01 | HTTP fetch uses `If-None-Match` / `If-Modified-Since` when prior metadata exists | `_load_metadata` + `requests` headers dict already supports this |
| NET-02 | HTTP 304 response reuses cached file without re-writing | `requests` exposes `.status_code`; cached `.txt` path is already deterministic |
| NET-03 | `SourceMetadata.etag` and `last_modified` are populated on successful fetches | Response headers accessible via `r.headers.get("ETag")` / `r.headers.get("Last-Modified")` |
| NET-04 | Tests cover first-fetch, 304 (unchanged), and 200 (updated) scenarios | Existing `monkeypatch` pattern on `fetch.requests.get` supports all three |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11+ (`match/case`, `slots=True`, `tomllib`)
- Test coverage must remain ≥99% after changes
- `ruff check` must pass clean after changes
- `dist/` output format must not change
- No new dependencies — use stdlib + existing `requests` library

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | ≥2.32.0 (already installed) | HTTP client with full header access | Already the project's HTTP library; `r.headers`, `r.status_code` cover all needs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` (stdlib) | built-in | Persist etag/last_modified to sidecar JSON | Already used in `_save_metadata` |
| `pathlib.Path` (stdlib) | built-in | Cached file read on 304 | Already used throughout |

No new packages required.

## Architecture Patterns

### Recommended Project Structure

No structural changes to the module layout are needed. All changes are confined to:

```
src/blocklist_builder/
├── fetch.py     # All changes here: _fetch_http signature + fetch_to_cache logic
tests/
├── test_fetch_http.py  # Extend with conditional fetch tests (304, 200-with-headers, first-fetch)
```

### Pattern 1: `_fetch_http` returns (content, etag, last_modified)

**What:** Change return type from `str` to `tuple[str, str | None, str | None]`.
**When to use:** Caller (`fetch_to_cache`) needs ETag and Last-Modified from the response to persist to metadata.
**Example:**

```python
# Source: requests library docs + HTTP/1.1 RFC 7232
def _fetch_http(
    url: str,
    timeout_s: int = _REQUESTS_TIMEOUT_DEFAULT,
    user_agent: str = _USER_AGENT,
    conditional_headers: dict[str, str] | None = None,
) -> tuple[str, str | None, str | None]:
    headers = {"User-Agent": user_agent}
    if conditional_headers:
        headers.update(conditional_headers)
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            r = requests.get(url, timeout=timeout_s, headers=headers)
            if r.status_code == 304:
                return "", r.headers.get("ETag"), r.headers.get("Last-Modified")
            r.raise_for_status()
            return r.text, r.headers.get("ETag"), r.headers.get("Last-Modified")
        except requests.RequestException:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(2**attempt)
    return "", None, None  # pragma: no cover
```

**Caller side — `fetch_to_cache` conditional logic:**

```python
# Before calling _fetch_http in the HTTP branch:
prior = _load_metadata(metadata_path)
cond: dict[str, str] = {}
if prior:
    if prior.get("etag"):
        cond["If-None-Match"] = prior["etag"]
    if prior.get("last_modified"):
        cond["If-Modified-Since"] = prior["last_modified"]

content, etag, last_modified = _fetch_http(url, timeout_s=timeout_s, conditional_headers=cond)

if not content and target.exists():
    # HTTP 304 — reuse cached file
    # Reload existing metadata and return without rewriting
    existing_meta = SourceMetadata(
        source_id=source_id,
        hash=prior["hash"],
        size_bytes=prior["size_bytes"],
        line_count=prior["line_count"],
        parsed_ok=prior.get("parsed_ok", 0),
        sanitized_ok=prior.get("sanitized_ok", 0),
        etag=etag or prior.get("etag"),
        last_modified=last_modified or prior.get("last_modified"),
        fetch_timestamp=time.time(),
    )
    _save_metadata(metadata_path, existing_meta)
    return target, existing_meta
```

### Pattern 2: Test the three scenarios with `monkeypatch`

**What:** The existing `test_fetch_http.py` uses a `_Resp` stub class and `monkeypatch.setattr(fetch.requests, "get", fake_get)`. The same pattern covers 304.
**When to use:** All NET-04 test scenarios.

```python
# 304 scenario — fake_get must NOT call raise_for_status (304 is not an error)
class _Resp304:
    status_code = 304
    headers = {"ETag": '"abc123"'}

    def raise_for_status(self) -> None:
        return None


def test_fetch_to_cache_http_304_reuses_cache(tmp_path: Path, monkeypatch) -> None:
    # Pre-seed cache file and metadata sidecar so 304 path has something to return
    ...
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **kw: _Resp304())
    cache_path, metadata = fetch.fetch_to_cache("http://example.com/list.txt", cache_dir, source_id="s1")
    assert metadata.etag == '"abc123"'
    # confirm target was NOT rewritten (mtime unchanged)
```

### Anti-Patterns to Avoid

- **Returning `None` content to signal 304:** Callers checking `if content is None` vs `if not content` are fragile because an empty list file is valid. Use `status_code` to distinguish 304 from empty 200. The empty-string-from-304 pattern only works because the cache-hit check (`target.exists()`) guards it.
- **Raising an exception on 304:** `requests` does not raise on 304 by default; `raise_for_status()` only raises on 4xx/5xx. Calling `raise_for_status()` after a 304 is safe — it is a no-op.
- **Re-calling `_compute_hash` on 304:** Avoids re-reading the cached file. Reuse prior `hash` from loaded metadata.
- **Modifying `SourceMetadata` fields:** The dataclass is `frozen=True` — always construct a new instance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Header case normalization | Custom dict wrapper | `requests` `CaseInsensitiveDict` (used automatically via `r.headers`) | HTTP headers are case-insensitive; `requests` handles this correctly |
| ETag quoting | String manipulation | Store/compare verbatim — `requests` returns the raw header value | ETags include surrounding quotes; store as-is and send as-is |
| 304 detection | Custom status check logic | `r.status_code == 304` | Single integer comparison; no abstraction needed |

## Common Pitfalls

### Pitfall 1: `raise_for_status()` called before checking `status_code`
**What goes wrong:** `raise_for_status()` does not raise on 304 (it is a 3xx redirect-class but not an error). However, if the code checks status_code only in the exception path, 304 may fall through without being handled and return an empty body as if it were valid content.
**Why it happens:** Developers assume `raise_for_status()` handles all non-200 codes.
**How to avoid:** Check `r.status_code == 304` before `r.raise_for_status()`. The current retry loop calls `r.raise_for_status()` immediately — the 304 check must be inserted before that call.
**Warning signs:** 304 responses result in an empty cached file (content is overwritten with `""`).

### Pitfall 2: `_fetch_http` return type change breaks existing test stubs
**What goes wrong:** `test_fetch_http.py` has a `_Resp` stub with only `.text` and `.raise_for_status`. Adding `status_code` and `.headers` to the return handling requires updating all existing stub objects.
**Why it happens:** The current stubs don't expose `status_code` or `headers`.
**How to avoid:** Update `_Resp` in `test_fetch_http.py` to include `status_code = 200` and `headers = {}` as defaults. New 304 test stubs add `status_code = 304` and `headers = {"ETag": "..."}`.

### Pitfall 3: First-fetch with no prior metadata
**What goes wrong:** If `_load_metadata` returns `None` (no sidecar yet) and code unconditionally accesses `prior["etag"]`, a `TypeError` or `KeyError` is raised.
**Why it happens:** Missing null-guard on `prior`.
**How to avoid:** Guard with `if prior:` before building conditional headers. The `_load_metadata` function already returns `None` when file is missing or invalid.

### Pitfall 4: 304 returned when no cached `.txt` file exists
**What goes wrong:** A 304 with no pre-existing cached file is an inconsistent state (server thinks we have data; we don't). The cache file was deleted or never written.
**Why it happens:** Unlikely in production but possible if the cache directory is cleared between runs while metadata sidecars survive.
**How to avoid:** In the 304 branch, check `target.exists()` before reusing. If it does not exist, treat as a full fetch and re-request without conditional headers, or raise a clear error. Simplest fix: fall back to re-fetching unconditionally if `not target.exists()`.

### Pitfall 5: ETag comparison with stale values
**What goes wrong:** If the sidecar JSON exists but the `.txt` cache file does not, returning cached metadata with a stale ETag from the sidecar will confuse the server-side cache validation.
**Why it happens:** Sidecar and cache file lifecycle are managed separately.
**How to avoid:** When loading prior metadata, also verify `target.exists()`. If the cached file is missing, clear the conditional headers so a full fetch occurs.

## Code Examples

### `requests` response headers and status code access
```python
# Source: requests library (https://docs.python-requests.org/en/latest/user/quickstart/)
r = requests.get(url, headers=headers, timeout=30)
r.status_code          # int, e.g. 200 or 304
r.headers.get("ETag")  # str | None — case-insensitive lookup
r.headers.get("Last-Modified")  # str | None
r.text                 # response body as str
r.raise_for_status()   # raises HTTPError for 4xx/5xx; no-op for 304
```

### Conditional request headers (RFC 7232)
```python
# If-None-Match: send ETag value received from prior response
# If-Modified-Since: send Last-Modified value received from prior response
headers = {
    "User-Agent": "blocklist-factory/0.1",
    "If-None-Match": '"etag-value-with-quotes"',      # verbatim from prior ETag header
    "If-Modified-Since": "Wed, 29 Mar 2026 00:00:00 GMT",  # verbatim from prior Last-Modified
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Always full fetch (current state) | Conditional fetch with ETag/Last-Modified | This phase | Reduces bandwidth and latency when upstream is unchanged |

No deprecated patterns relevant to this phase.

## Open Questions

1. **What to do on 304 when cached `.txt` file is absent**
   - What we know: This is an edge case (cache cleared but sidecar survived)
   - What's unclear: Should it raise, warn, or silently re-fetch?
   - Recommendation: Check `target.exists()` in the 304 branch; if missing, clear conditional headers and re-call `_fetch_http` without them. Simple, no new exception type needed.

2. **Whether `parsed_ok` / `sanitized_ok` should be preserved on 304**
   - What we know: These fields are set to 0 at fetch time and updated later by the build pipeline caller — never stored back to the sidecar in the current code
   - What's unclear: If 304 returns a reconstructed `SourceMetadata` from the sidecar, `parsed_ok=0` is correct (will be filled by caller as before)
   - Recommendation: Preserve sidecar values as-is (treat prior values as informational, not authoritative for the current run)

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — `requests` is already installed, no new tools required)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-cov 5.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` → `testpaths = ["tests"]`) |
| Quick run command | `python3 -m pytest tests/test_fetch.py tests/test_fetch_http.py -x -q` |
| Full suite command | `python3 -m pytest tests/ --cov=blocklist_builder --cov-report=term-missing -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NET-01 | `If-None-Match` / `If-Modified-Since` headers sent when prior metadata has etag/last_modified | unit | `python3 -m pytest tests/test_fetch_http.py -x -q` | ✅ (extend existing) |
| NET-02 | HTTP 304 reuses cached file without rewriting | unit | `python3 -m pytest tests/test_fetch_http.py -x -q` | ✅ (extend existing) |
| NET-03 | `SourceMetadata.etag` and `last_modified` non-None after fetch that returns those headers | unit | `python3 -m pytest tests/test_fetch_http.py -x -q` | ✅ (extend existing) |
| NET-04 | All three scenarios (first-fetch, 304, 200-with-headers) covered | unit | `python3 -m pytest tests/test_fetch_http.py -x -q` | ✅ (extend existing) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_fetch.py tests/test_fetch_http.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ --cov=blocklist_builder --cov-report=term-missing -q`
- **Phase gate:** Full suite green, coverage ≥99% before `/gsd:verify-work`

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements. `test_fetch_http.py` already uses the correct `monkeypatch` pattern and `_Resp` stub. New tests extend this file; no new files or framework setup required.

## Sources

### Primary (HIGH confidence)
- `requests` source + installed package (2.32.0+) — `r.status_code`, `r.headers`, `raise_for_status` behavior
- `src/blocklist_builder/fetch.py` — full source read; all existing logic confirmed
- `src/blocklist_builder/types.py` — `SourceMetadata` dataclass fields confirmed
- `tests/test_fetch_http.py` — existing stub/monkeypatch pattern confirmed

### Secondary (MEDIUM confidence)
- RFC 7232 (HTTP Conditional Requests) — ETag, If-None-Match, Last-Modified, If-Modified-Since semantics; well-established standard, no ambiguity

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `requests` already installed; stdlib only
- Architecture: HIGH — full source code read; no guesswork about existing structure
- Pitfalls: HIGH — derived from direct code reading, not from web search

**Research date:** 2026-03-29
**Valid until:** 2026-09-29 (stable stdlib + requests patterns; not fast-moving)
