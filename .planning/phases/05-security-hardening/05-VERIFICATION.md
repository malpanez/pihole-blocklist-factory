---
phase: 05-security-hardening
verified: 2026-03-29T15:10:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 05: Security Hardening Verification Report

**Phase Goal:** Path traversal protection is consistent across all `file://` code paths and memory usage is bounded
**Verified:** 2026-03-29T15:10:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                          | Status     | Evidence                                                                                              |
|----|--------------------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------------------------|
| 1  | A `file://` URL with `..` raises `ValueError` in `fetch_to_cache()`           | VERIFIED   | `fetch.py:111-112` checks `".." in raw.parts` pre-resolve; raises `ValueError` with matching message |
| 2  | A `file://` URL with `..` is skipped with warning in `_resolve_local_sources()`| VERIFIED   | `parallel.py:77-79` checks `".." in raw_path.parts` pre-resolve; calls `logging.warning` and `continue` |
| 3  | The `build.py` path traversal guard (lines 68-70) is covered by tests         | VERIFIED   | `test_build.py:176-191` `test_build_file_traversal_rejected` calls `build()` with traversal URL; asserts `source_missing == 1` |
| 4  | An `http://` source URL emits `logging.warning()` at build time               | VERIFIED   | `build.py:65-70` fires warning before `match` block; `test_build.py:194-213` asserts `any("http://" in r.message ...)` |
| 5  | `_compute_hash` is a plain function with no `@cache` memoization              | VERIFIED   | `fetch.py:28-30` has no decorator; `grep -c "@cache" fetch.py` returns `1` (only `_cache_key`); `test_fetch.py:49-50` asserts `not hasattr(_compute_hash, "cache_info")` |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                          | Expected                                              | Status   | Details                                                             |
|-----------------------------------|-------------------------------------------------------|----------|---------------------------------------------------------------------|
| `src/blocklist_builder/fetch.py`  | Path traversal guard in `file://` arm; no `@cache` on `_compute_hash` | VERIFIED | `ValueError` raised at line 112; `@cache` absent from `_compute_hash` at line 28 |
| `src/blocklist_builder/parallel.py` | Path traversal guard in `_resolve_local_sources`    | VERIFIED | Guard at lines 77-79; message contains "path traversal"             |
| `src/blocklist_builder/build.py`  | `http://` warning before `match` in `_resolve_source_path` | VERIFIED | Warning at lines 65-70; `url.startswith("http://")` check present   |
| `tests/test_fetch.py`             | Tests for SEC-01 and SEC-05                           | VERIFIED | `test_fetch_to_cache_traversal_rejected` (line 44) and `test_compute_hash_not_cached` (line 49) present |
| `tests/test_build.py`             | Tests for SEC-03 and SEC-04                           | VERIFIED | `test_build_file_traversal_rejected` (line 176) and `test_build_http_emits_warning` (line 194) present |
| `tests/test_parallel_extra.py`    | Test for SEC-02                                       | VERIFIED | `test_resolve_local_sources_traversal_rejected` (line 206) present  |

### Key Link Verification

| From                              | To                        | Via                                   | Status  | Details                                                                     |
|-----------------------------------|---------------------------|---------------------------------------|---------|-----------------------------------------------------------------------------|
| `src/blocklist_builder/fetch.py`  | `tests/test_fetch.py`     | `ValueError` on `file://` with `..`   | WIRED   | Test imports `fetch_to_cache` and exercises `file:///tmp/../etc/passwd` path |
| `src/blocklist_builder/build.py`  | `tests/test_build.py`     | `http://` warning and `file://` traversal skip | WIRED | Both `test_build_http_emits_warning` and `test_build_file_traversal_rejected` exercise live code paths |

### Data-Flow Trace (Level 4)

Not applicable — this phase modifies security guards and a hash utility, not data-rendering components. No Level 4 trace required.

### Behavioral Spot-Checks

| Behavior                                             | Command                                                                                   | Result          | Status |
|------------------------------------------------------|-------------------------------------------------------------------------------------------|-----------------|--------|
| All 5 SEC test functions pass                        | `uv run pytest tests/test_fetch.py tests/test_build.py tests/test_parallel_extra.py -x -q` | 23 passed       | PASS   |
| Full test suite passes at 100% coverage              | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q`                      | 108 passed, 100% | PASS  |
| `ruff check src/` clean                              | `uv run ruff check src/`                                                                  | All checks passed | PASS |
| Only one `@cache` in `fetch.py` (only `_cache_key`)  | `grep -c "@cache" src/blocklist_builder/fetch.py`                                         | 1               | PASS   |

### Requirements Coverage

| Requirement | Source Plan  | Description                                                                    | Status    | Evidence                                               |
|-------------|-------------|--------------------------------------------------------------------------------|-----------|--------------------------------------------------------|
| SEC-01      | 05-01-PLAN  | `file://` URLs with `..` rejected in `fetch_to_cache()`                       | SATISFIED | `fetch.py:111-112`; `test_fetch.py:44-46`             |
| SEC-02      | 05-01-PLAN  | `file://` URLs with `..` rejected in `_resolve_local_sources()`               | SATISFIED | `parallel.py:77-79`; `test_parallel_extra.py:206-215` |
| SEC-03      | 05-01-PLAN  | Tests cover path traversal rejection in `build.py`                            | SATISFIED | `test_build.py:176-191` covers `build.py:74-76`       |
| SEC-04      | 05-01-PLAN  | `http://` source URLs emit `logging.warning()` at build time                  | SATISFIED | `build.py:65-70`; `test_build.py:194-213`             |
| SEC-05      | 05-01-PLAN  | `@cache` removed from `_compute_hash` (bounded memory)                        | SATISFIED | `fetch.py:28` has no decorator; `test_fetch.py:49-50` |

No orphaned requirements — REQUIREMENTS.md traceability table marks SEC-01 through SEC-05 complete and maps them to Phase 5.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

No TODOs, placeholders, empty handlers, or stub returns detected in modified files. `_compute_hash` removal of `@cache` is intentional and documented.

### Human Verification Required

None. All behaviors are fully verifiable programmatically: guard logic is inspected in source, tests exercise each guard path, test suite passes at 100% coverage.

### Gaps Summary

No gaps. All five must-haves are implemented, tested, and verified against the actual codebase. The phase goal — consistent `file://` path traversal protection and bounded memory in `_compute_hash` — is achieved.

---

_Verified: 2026-03-29T15:10:00Z_
_Verifier: Claude (gsd-verifier)_
