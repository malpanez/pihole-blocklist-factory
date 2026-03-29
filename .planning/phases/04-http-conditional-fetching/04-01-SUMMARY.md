---
phase: 04-http-conditional-fetching
plan: "01"
subsystem: fetch
tags: [http, conditional-fetch, etag, cache, performance]
dependency_graph:
  requires: []
  provides: [conditional-http-fetching, etag-caching, 304-handling]
  affects: [fetch.py, test_fetch_http.py, test_fetch.py]
tech_stack:
  added: []
  patterns: [conditional-HTTP-headers, ETag/If-Modified-Since, 304-short-circuit]
key_files:
  created: []
  modified:
    - src/blocklist_builder/fetch.py
    - tests/test_fetch_http.py
    - tests/test_fetch.py
decisions:
  - "Guard conditional headers with `prior and target.exists()` to prevent stale-sidecar without cache-file edge case"
  - "Check status_code == 304 before raise_for_status() per HTTP spec (304 is not an error)"
  - "Return tuple[str, str | None, str | None] from _fetch_http to propagate ETag/Last-Modified"
  - "Install pytest/pytest-cov in worktree venv to prevent main-repo .venv leakage during test runs"
metrics:
  duration: "12m 18s"
  completed_date: "2026-03-29"
  tasks_completed: 2
  files_modified: 4
---

# Phase 04 Plan 01: HTTP Conditional Fetching Summary

**One-liner:** Conditional HTTP fetching with ETag/If-Modified-Since/304 support using requests headers dict and metadata sidecar.

## What Was Built

Modified `fetch.py` to send conditional HTTP headers on second-and-subsequent builds, reuse cached files on HTTP 304, and persist `etag`/`last_modified` values in `SourceMetadata`. Tests cover all four scenarios: first fetch, 304 cache reuse, 200 cache update, and 304 with missing cache file.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Add conditional header support to _fetch_http and 304 handling to fetch_to_cache | 3719939 | src/blocklist_builder/fetch.py, tests/test_fetch_http.py |
| 2 | Add conditional fetch tests and fix existing stubs | bc5930e | tests/test_fetch_http.py, tests/test_fetch.py, pyproject.toml, uv.lock |

## Verification Results

- `uv run pytest tests/ --cov=blocklist_builder -q` — 102 passed, 99% coverage
- `uv run ruff check src/` — all checks passed
- `grep -c "If-None-Match|If-Modified-Since|status_code == 304" fetch.py` — 3 matches
- `grep -c "304" tests/test_fetch_http.py` — 3 matches (304 test scenarios)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree venv missing pytest, causing main repo source to load**

- **Found during:** Task 2 verification
- **Issue:** `uv run pytest` resolved to `/home/malpanez/repos/pihole-blocklist-factory/.venv/bin/pytest` (main repo) because the worktree's `.venv` had no `pytest` installed. This caused the main repo's unmodified `fetch.py` to be loaded, making all new tests fail with `etag=None`.
- **Fix:** Ran `VIRTUAL_ENV="" uv add --dev pytest pytest-cov` in the worktree to install test deps. All tests pass when running with the worktree's `.venv`.
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Commit:** bc5930e

## Known Stubs

None.

## Self-Check: PASSED

- `src/blocklist_builder/fetch.py` — exists, contains `conditional_headers`, `status_code == 304`, `If-None-Match`, `If-Modified-Since`
- `tests/test_fetch_http.py` — exists, contains `test_fetch_to_cache_http_304_reuses_cache`, `test_fetch_to_cache_http_first_fetch_saves_headers`, `test_fetch_to_cache_http_200_updates_cache`, `test_fetch_to_cache_http_304_missing_cache_file`
- Commits 3719939 and bc5930e — both present in git log
