# Phase 5: Security Hardening - Research

**Researched:** 2026-03-29
**Domain:** Python security — path traversal guards, memory safety, HTTP hygiene
**Confidence:** HIGH

## Summary

Phase 5 is a pure code-hardening phase. No new libraries are required; all five requirements are targeted, surgical changes to existing source files. The codebase currently has exactly ONE location that correctly checks for path traversal (`build.py:68-70`) and TWO locations that do NOT (`fetch.py` file:// branch, `parallel.py` `_resolve_local_sources`). Coverage data confirms `build.py:69-70` are the only uncovered lines in the entire suite (2 misses out of 1040 statements, 99%). Adding traversal guards to fetch.py and parallel.py plus tests for all three rejection branches will achieve the ≥99% coverage gate.

The `@cache` decorator on `_compute_hash` in `fetch.py` causes every unique content blob seen during a build run to be retained in memory permanently for the life of the process. For a build processing millions of domains, this is unbounded growth. Removing the decorator has zero functional impact — `_compute_hash` is called once per source file and the result is immediately stored in `SourceMetadata`; memoization buys nothing.

The `http://` warning belongs in `_resolve_source_path` in `build.py` — it is the single entry point for all source URL dispatch and has `logging` already imported. Placing it there means both fetch-mode and no-fetch-mode builds emit the warning, and there is no duplication.

**Primary recommendation:** Three targeted code edits (fetch.py, parallel.py, build.py) plus two new test functions; no new dependencies, no refactoring of call sites.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | `file://` URLs with `..` rejected in `fetch_to_cache()` | Add guard to `fetch.py` file:// match arm before `src.read_text()` |
| SEC-02 | `file://` URLs with `..` rejected in `_resolve_local_sources()` | Add guard to `parallel.py` after `src_path` construction |
| SEC-03 | Tests cover all three path traversal rejection branches | Add tests for fetch.py guard, parallel.py guard; build.py branch currently 0% covered |
| SEC-04 | `http://` (non-HTTPS) source URLs emit `logging.warning()` at build time | Add check in `_resolve_source_path` in build.py before dispatching to fetch |
| SEC-05 | `@cache` removed from `_compute_hash` | Remove `@cache` decorator on line 29 of fetch.py; `cache` import may become unused |
</phase_requirements>

## Standard Stack

No new libraries required. All changes use stdlib only.

### Core (existing)
| Module | Purpose | Notes |
|--------|---------|-------|
| `pathlib.Path` | Path resolution and traversal check | `.parts` already used in build.py guard |
| `logging` | Warning emission | Already imported in build.py and parallel.py; NOT imported in fetch.py |
| `functools.cache` | Decorator to REMOVE from `_compute_hash` | Import remains for `_cache_key` — do not remove the import entirely |

**Installation:** None required.

## Architecture Patterns

### Pattern 1: Path Traversal Guard (build.py reference implementation)

The existing guard in `build.py:66-70` is the canonical pattern:

```python
# Source: build.py lines 66-70 (existing, verified)
case url if url.startswith("file://"):
    file_path = Path(url.removeprefix("file://")).resolve()
    if ".." in file_path.parts:
        logging.warning("Rejected file:// URL with path traversal: %s", url)
        return None
    return file_path
```

Key implementation detail: The existing build.py guard calls `.resolve()` first, then checks `.parts`. After `.resolve()`, `..` components are canonicalized away — so on most systems, `Path("/tmp/../etc/passwd").resolve()` becomes `Path("/etc/passwd")` which has NO `..` in `.parts`. The build.py guard still works in practice because the resolved path will not exist as an expected source, causing a `source_missing` increment downstream.

**IMPORTANT — corrected approach for new guards (fetch.py, parallel.py):** The new guards in fetch.py and parallel.py MUST check `..` in the RAW path parts BEFORE calling `.resolve()`. This is because: (1) fetch.py raises `ValueError` and the test asserts it fires, and (2) after `.resolve()` the `..` is gone so the guard would never trigger. Example: `Path("/tmp/../etc/passwd").parts` = `('/', 'tmp', '..', 'etc', 'passwd')` — contains `..`. After `.resolve()`: `Path("/etc/passwd").parts` = `('/', 'etc', 'passwd')` — no `..`.

**For fetch.py:** The guard must raise `ValueError` (or equivalent) rather than returning `None`, because `fetch_to_cache` returns `(Path, SourceMetadata)` — there is no sentinel return path. A `ValueError` is the appropriate signal for an invalid URL argument.

**For parallel.py `_resolve_local_sources`:** Can silently skip (continue) the entry, mirroring the build.py pattern (returns `None` → source omitted from dict). No logging module is currently imported in parallel.py — but `parallel.py` already imports `logging` (line 12), so a `logging.warning()` call is available.

### Pattern 2: HTTP Warning in `_resolve_source_path`

```python
# Target location: build.py _resolve_source_path, before match statement
# build.py already has: import logging (line 4)
```

The match/case in `_resolve_source_path` handles three arms: `file://`, non-file with `not no_fetch`, and plain path. The `http://` warning should be emitted before the match, or as a guard inside the non-file fetch arm. Placing it before the match is cleaner — it fires regardless of fetch mode.

The check is: `if url.startswith("http://") and not url.startswith("https://")` — equivalently `url.startswith("http://")` since HTTPS starts with `http` only if checked as `https://`.

### Pattern 3: Removing `@cache` from `_compute_hash`

```python
# fetch.py lines 28-31 (current)
@cache
def _compute_hash(content: str) -> str:
    """Compute SHA256 hash of content (cached)."""
    return hashlib.sha256(content.encode(_HASH_ENCODING)).hexdigest()
```

Remove the `@cache` decorator on line 29. The `from functools import cache` import on line 6 MUST be retained — `_cache_key` (line 22) also uses `@cache`. Removing the `cache` import would break `_cache_key`.

### Anti-Patterns to Avoid

- **Checking `..` AFTER `.resolve()` in fetch.py/parallel.py:** After `.resolve()`, `..` components are canonicalized away (e.g., `Path("/tmp/../etc/passwd").resolve()` becomes `Path("/etc/passwd")` with no `..` in `.parts`). The new fetch.py and parallel.py guards MUST check `..` in the raw path parts BEFORE calling `.resolve()`. The existing build.py guard uses post-resolve checking, which works only because it relies on the downstream `source_missing` path — do NOT replicate that pattern for the new guards.
- **Removing the `cache` import from fetch.py:** `_cache_key` also uses `@cache`. Only remove the decorator from `_compute_hash`, not the import.
- **Adding `logging` import to fetch.py just for SEC-04:** The `http://` warning belongs in `build.py` where `logging` is already imported, not in `fetch.py` which has no logging at all.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Path traversal detection | Custom regex or string splitting | `Path.parts` check (pre-resolve for new guards) |
| Memory-bounded hashing | Ring buffer cache with LRU eviction | Simply remove `@cache` — no replacement needed |

## Common Pitfalls

### Pitfall 1: fetch.py traversal check return type
**What goes wrong:** Adding a guard that returns `None` from `fetch_to_cache`, which violates the return type `tuple[Path, SourceMetadata]` and causes a `TypeError` at the call site.
**Why it happens:** The build.py guard returns `None` cleanly because `_resolve_source_path` has `Optional[Path]` return type. `fetch_to_cache` does not.
**How to avoid:** Raise `ValueError` with a descriptive message from the file:// guard in `fetch_to_cache`.
**Warning signs:** Test for the guard passes but integration tests break with `TypeError: cannot unpack non-iterable NoneType object`.

### Pitfall 2: parallel.py `_resolve_local_sources` — no logging import needed
**What goes wrong:** Assuming `logging` is not available in parallel.py.
**Why it happens:** fetch.py has no logging import, so the assumption spreads. But parallel.py imports `logging` on line 12.
**How to avoid:** Check the import before assuming — parallel.py already has it.

### Pitfall 3: `@cache` on `_cache_key` also in fetch.py
**What goes wrong:** Removing the `@cache` import entirely from fetch.py because `_compute_hash` no longer needs it.
**Why it happens:** Grepping for `@cache` finds two uses; only one is being removed.
**How to avoid:** Only remove the decorator line `@cache` above `_compute_hash`, not the `from functools import cache` import on line 6.

### Pitfall 4: build.py path traversal test — indirect coverage gap
**What goes wrong:** Tests for SEC-03 are written for fetch.py and parallel.py but the requirement also says build.py lines 69-70 (currently 0% covered) must be covered.
**Why it happens:** The requirement text says "all three code paths" — fetch.py, parallel.py, AND build.py. The existing build.py guard exists but has no test.
**How to avoid:** The test plan must include a test that calls `build()` with a `file://` URL containing `..` and asserts the source is skipped (source_missing counter incremented or domain not in output).

### Pitfall 5: `http://` warning test must use `no_fetch=True`
**What goes wrong:** A test for SEC-04 that uses an actual `http://` URL will trigger a real HTTP request.
**Why it happens:** The `_resolve_source_path` non-file arm calls `fetch_to_cache` when `not no_fetch`.
**How to avoid:** Use `no_fetch=True` in tests for the warning — the URL `http://example.com/list.txt` will reach the match arm `case url: p = Path(url)` when `no_fetch=True`, so the warning check must come before the match or be in the `not no_fetch` arm explicitly. Alternatively, use `monkeypatch` to mock `fetch_to_cache`. The cleanest approach: emit the warning before the match statement so it fires regardless of `no_fetch`.

## Code Examples

### Exact location of existing build.py guard (verified)
```python
# build.py lines 65-71
match src.url:
    case url if url.startswith("file://"):
        file_path = Path(url.removeprefix("file://")).resolve()
        if ".." in file_path.parts:
            logging.warning("Rejected file:// URL with path traversal: %s", url)
            return None
        return file_path
```

### fetch.py — where to add SEC-01 guard (pre-resolve check)
```python
# fetch.py lines 109-112 (current)
match url:
    case url if url.startswith("file://"):
        src = Path(url.removeprefix("file://"))
        content = src.read_text(encoding=_HASH_ENCODING, errors="ignore")
```
Guard goes between `src = Path(...)` and `content = src.read_text(...)`. Check `..` in `src.parts` BEFORE calling `.resolve()`, then resolve for the read. Raise `ValueError`.

### parallel.py — where to add SEC-02 guard (pre-resolve check)
```python
# parallel.py lines 75-77 (current)
src_path = Path(url.removeprefix("file://")) if url.startswith("file://") else Path(url)
if src_path.exists():
    result[src.id] = src_path
```
Guard goes after `src_path` construction. Check `..` in `src_path.parts` BEFORE calling `.resolve()`, then resolve for the exists check. Skip the source with a warning.

### fetch.py — SEC-05 decorator removal
```python
# Current (fetch.py line 28-31)
@cache
def _compute_hash(content: str) -> str:

# After (remove @cache only, keep import)
def _compute_hash(content: str) -> str:
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-cov 5.x |
| Config file | pyproject.toml (no `[tool.pytest]` section — pytest finds `tests/` by convention) |
| Quick run command | `python3 -m pytest tests/test_fetch.py tests/test_build.py -x -q` |
| Full suite command | `python3 -m pytest tests/ --cov=src/blocklist_builder --cov-report=term-missing` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | `fetch_to_cache("file:///tmp/../etc/passwd", ...)` raises `ValueError` | unit | `python3 -m pytest tests/test_fetch.py::test_fetch_to_cache_traversal_rejected -x` | Wave 0 |
| SEC-02 | `_resolve_local_sources` with `file:///../` URL skips source (not in result dict) | unit | `python3 -m pytest tests/test_parallel_extra.py::test_resolve_local_sources_traversal_rejected -x` | Wave 0 |
| SEC-03 | `build()` with `file://` traversal URL skips source (no domains, source_missing counter) | integration | `python3 -m pytest tests/test_build.py::test_build_file_traversal_rejected -x` | Wave 0 |
| SEC-04 | `build()` with `http://` URL emits `logging.warning` | unit | `python3 -m pytest tests/test_build.py::test_build_http_emits_warning -x` | Wave 0 |
| SEC-05 | `_compute_hash` function object has no `__wrapped__` or `cache_info` attribute | unit | `python3 -m pytest tests/test_fetch.py::test_compute_hash_not_cached -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_fetch.py tests/test_build.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ --cov=src/blocklist_builder --cov-report=term-missing`
- **Phase gate:** Full suite ≥99% coverage and `ruff check` clean before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fetch.py` — add `test_fetch_to_cache_traversal_rejected` and `test_compute_hash_not_cached`
- [ ] `tests/test_build.py` — add `test_build_file_traversal_rejected` and `test_build_http_emits_warning`
- [ ] `tests/test_parallel_extra.py` — add `test_resolve_local_sources_traversal_rejected` (file exists, needs new test function)

## State of the Art

| Area | Current State | After Phase 5 |
|------|---------------|---------------|
| Path traversal | Guarded in build.py only | Guarded in all three file:// code paths |
| Hash caching | `_compute_hash` retains every content blob in memory | Plain function, GC-eligible after each call |
| HTTP scheme check | None | `logging.warning()` emitted for `http://` sources at build time |
| Test coverage | 99% (build.py:69-70 uncovered) | 99%+ (all three traversal branches covered) |

## Open Questions

1. **Should fetch.py raise `ValueError` or `PermissionError` for traversal?**
   - What we know: build.py uses `return None` (no exception). fetch.py has no sentinel return.
   - What's unclear: Project has no explicit policy on which exception type to use for security rejections.
   - Recommendation: Use `ValueError("Path traversal detected in file:// URL: ...")` — it is the standard Python signal for "argument value is invalid", matches what the caller would expect from a URL validation failure, and is easy to assert in tests.

2. **Does `parallel.py _resolve_local_sources` need to emit a warning or silently skip?**
   - What we know: `parallel_fetch_sources` already logs `logging.warning("Failed to fetch source %s", ...)` for other errors. Consistency suggests a warning.
   - What's unclear: SEC-02 requirement text says "rejected" without specifying logging.
   - Recommendation: Emit `logging.warning("Rejected file:// URL with path traversal: %s", url)` to match the build.py message format, then `continue`.

## Environment Availability

Step 2.6: SKIPPED — phase is purely code/config changes with no external dependencies beyond the existing Python 3.11+ environment and installed dev dependencies (`pytest`, `ruff`, `pytest-cov` all present and confirmed working).

## Project Constraints (from CLAUDE.md)

- Python 3.11+ required (`match/case`, `slots=True`, `tomllib`)
- Test coverage must remain ≥99% after phase completion
- `ruff check` must pass clean after phase completion
- `dist/` output format must not change (this phase has no output impact)
- No new dependencies — all fixes must use existing stdlib
- GSD workflow required before file edits

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `src/blocklist_builder/fetch.py` — full file read, confirmed `@cache` on both `_cache_key` and `_compute_hash`, no `logging` import
- Direct code inspection: `src/blocklist_builder/parallel.py` — full file read, confirmed `logging` imported line 12, no traversal guard in `_resolve_local_sources`
- Direct code inspection: `src/blocklist_builder/build.py` lines 60-77 — confirmed exact traversal guard pattern at lines 68-70
- Coverage run: `python3 -m pytest tests/ --cov=src/blocklist_builder --cov-report=term-missing` — confirmed 99% coverage with exactly lines 69-70 uncovered in build.py, all other modules at 100%

### Secondary (MEDIUM confidence)
- Python docs: `functools.cache` semantics — unbounded LRU with no eviction policy; confirmed behavior matches the concern in SEC-05

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all stdlib
- Architecture: HIGH — all patterns derived from direct code inspection of current source
- Pitfalls: HIGH — confirmed via coverage output and code tracing
- Test mapping: HIGH — all test commands verified against existing test infrastructure

**Research date:** 2026-03-29
**Valid until:** Phase execution (code is static between research and plan execution)
