---
phase: 05-security-hardening
plan: 01
subsystem: security
tags: [security, path-traversal, hardening, fetch, parallel, build]
dependency_graph:
  requires: []
  provides: [path-traversal-protection, http-scheme-warning, bounded-hash-cache]
  affects: [fetch.py, parallel.py, build.py]
tech_stack:
  added: []
  patterns: [pre-resolve path traversal check, guard-before-match]
key_files:
  created: []
  modified:
    - src/blocklist_builder/fetch.py
    - src/blocklist_builder/parallel.py
    - src/blocklist_builder/build.py
    - tests/test_fetch.py
    - tests/test_build.py
    - tests/test_parallel_extra.py
decisions:
  - "Check .. in raw Path.parts before .resolve() — post-resolve check is ineffective since .resolve() eliminates .. components"
  - "Remove @cache from _compute_hash — unbounded memory growth with large content strings"
  - "Add http:// warning before match statement in _resolve_source_path — fires regardless of no_fetch"
metrics:
  duration: 21 minutes
  completed: "2026-03-29T14:50:23Z"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 6
---

# Phase 05 Plan 01: Security Hardening Summary

**One-liner:** Path traversal guards (pre-resolve) in fetch.py and parallel.py, http:// insecure scheme warning in build.py, and unbounded @cache removed from _compute_hash.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add security guards to fetch.py, parallel.py, and build.py | 8ca6cb8 | fetch.py, parallel.py, build.py, test_fetch.py, test_build.py, test_parallel_extra.py |

## What Was Built

### SEC-01: Path traversal guard in fetch_to_cache (fetch.py)
Added pre-resolve check on raw Path parts before calling `.resolve()`. A `file://` URL containing `..` raises `ValueError` with message "path traversal detected". This is correct — checking parts after `.resolve()` would never fire since `.resolve()` eliminates `..` components.

### SEC-02: Path traversal guard in _resolve_local_sources (parallel.py)
Added pre-resolve check on raw path parts. Sources with `..` in `file://` URLs are skipped with a warning log. Consistent guard pattern with fetch.py.

### SEC-03: Build.py traversal guard fixed (build.py)
The existing guard used post-resolve check (`Path(...).resolve()` then check `..` in parts) which was ineffective. Fixed to check raw parts pre-resolve, consistent with the new guards. Now `_resolve_source_path` correctly returns `None` for traversal URLs, causing `source_missing` to be incremented.

### SEC-04: HTTP scheme warning (build.py)
Added `http://` insecure scheme warning before the match statement in `_resolve_source_path`. Fires unconditionally (even in no_fetch mode) with message referencing "insecure".

### SEC-05: Remove @cache from _compute_hash (fetch.py)
Removed `@cache` decorator from `_compute_hash`. The `@cache` on `_cache_key` is retained (URL-keyed, bounded by number of unique URLs). `_compute_hash` was cached by content string — unbounded growth with arbitrary file contents.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed post-resolve traversal check in build.py**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** The existing build.py guard used `Path(...).resolve()` before checking `..` in parts. Since `.resolve()` canonicalizes paths by eliminating `..`, the check `if ".." in file_path.parts` would never be True. The traversal URL `file:///tmp/../etc/passwd` would resolve to `/etc/passwd` and pass through.
- **Fix:** Changed to check raw path parts pre-resolve, then call `.resolve()` on the clean path.
- **Files modified:** src/blocklist_builder/build.py
- **Commit:** 8ca6cb8

**2. [Rule 1 - Bug] Fixed case-sensitive regex match in ValueError message**
- **Found during:** Task 1 (GREEN phase, first run)
- **Issue:** Initial ValueError message was "Path traversal detected..." (capital P). Test matched `"path traversal"` (lowercase) which is case-sensitive in pytest.raises(match=...).
- **Fix:** Changed message to lowercase "path traversal detected...".
- **Files modified:** src/blocklist_builder/fetch.py
- **Commit:** 8ca6cb8

## Verification Results

```
uv run --active pytest --cov=blocklist_builder --cov-report=term-missing -q
103 passed in 17.05s
TOTAL: 1062 stmts, 0 miss, 100% coverage

uv run --active ruff check src/
All checks passed!

grep -c "@cache" src/blocklist_builder/fetch.py
1  (only _cache_key)
```

## Known Stubs

None.

## Self-Check: PASSED

- src/blocklist_builder/fetch.py: FOUND
- src/blocklist_builder/parallel.py: FOUND
- src/blocklist_builder/build.py: FOUND
- tests/test_fetch.py: FOUND
- tests/test_build.py: FOUND
- tests/test_parallel_extra.py: FOUND
- Commit 8ca6cb8: FOUND
