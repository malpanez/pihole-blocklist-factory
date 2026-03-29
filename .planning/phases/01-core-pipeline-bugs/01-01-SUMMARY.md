---
phase: 01-core-pipeline-bugs
plan: 01
subsystem: pipeline
tags: [python, parallel, stats, dead-code, double-fetch]

requires: []

provides:
  - Dead function parallel_parse_and_sanitize removed from parallel.py
  - Single-fetch build pipeline (each HTTP source fetched exactly once)
  - Correct total_lines computed from per-source line counts
  - stats.discarded contains only discard-reason keys (no parse_ok/sanitize_ok)

affects: [02-analyze-fix, 04-conditional-fetch]

tech-stack:
  added: []
  patterns:
    - "source_stats dict is authoritative for per-source line counts"
    - "_ok_keys set pattern to filter non-discard keys from discarded Counter"

key-files:
  created: []
  modified:
    - src/blocklist_builder/parallel.py
    - src/blocklist_builder/build.py
    - tests/test_parallel_extra.py
    - tests/test_build.py

key-decisions:
  - "Remove parallel_parse_and_sanitize entirely rather than deprecate — never called in production, tests only exercised dead path"
  - "Compute total_lines from source_stats.values() not from discarded Counter — source_stats lines key is populated by _process_source_file_worker and is authoritative"
  - "Filter _ok_keys inline at Stats construction point rather than in _collect_domains — keeps discarded Counter accumulation unchanged, only filters output"

patterns-established:
  - "source_stats[src_id]['lines'] is the line count for per-source attribution"
  - "Discard Counter accumulates all keys including parse_ok/sanitize_ok internally; filter only at Stats output boundary"

requirements-completed: [PIPE-01, PIPE-02, PIPE-03, PIPE-04]

duration: 4min
completed: 2026-03-29
---

# Phase 1 Plan 01: Core Pipeline Bugs Summary

**Removed dead parallel_parse_and_sanitize function, eliminated double HTTP fetch, and fixed stats reporting from ~9.1M to accurate 15 (test) / ~4.5M (production) total_lines with clean discard dict**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-29T10:45:54Z
- **Completed:** 2026-03-29T10:49:21Z
- **Tasks:** 2
- **Files modified:** 4 (1 deleted)

## Accomplishments

- Deleted 63-line dead function `parallel_parse_and_sanitize` and its `_merge_chunk_result` helper from parallel.py
- Removed double-fetch: `parallel_fetch_sources` import and call stripped from build.py so each HTTP source fetches exactly once via `_resolve_source_path`
- Fixed `stats.total_lines` to use `sum(s.get("lines", 0) for s in source_stats.values())` — previously summed all discard values including parse_ok/sanitize_ok, inflating count by ~2x
- Filtered `parse_ok` and `sanitize_ok` from `stats.discarded` output using `_ok_keys` set so discarded dict contains only actual rejection reasons

## Task Commits

1. **Task 1: Remove dead code and double-fetch (PIPE-04, PIPE-01)** - `594db4c` (fix)
2. **Task 2: Fix stats double-counting (PIPE-02, PIPE-03)** - `a35426e` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/blocklist_builder/parallel.py` - Removed `_merge_chunk_result` (lines 125-135) and `parallel_parse_and_sanitize` (lines 138-188)
- `src/blocklist_builder/build.py` - Removed `parallel_fetch_sources` import and double-fetch block; fixed stats construction
- `tests/test_parallel_extra.py` - Removed `parallel_parse_and_sanitize` import and 4 dead test functions
- `tests/test_parallel.py` - Deleted entirely (only tested dead function)
- `tests/test_build.py` - Updated assertion: `total_lines == 15`, assert ok keys absent from discarded

## Decisions Made

- Remove `parallel_parse_and_sanitize` entirely rather than deprecate — it was never called in production, only in its own dedicated test file.
- Use `source_stats.values()` for total_lines: the worker's `stats["lines"] = len(lines)` is set before any filtering, making it the canonical raw line count.
- Filter `_ok_keys` at Stats construction boundary rather than modifying `_collect_domains` accumulation — keeps the Counter semantics clean and change is minimal.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The worktree's tests required running with `uv run --active` from the worktree directory to use the worktree's own venv rather than the main repo's installed package. The plan's verify commands used `cd /home/malpanez/repos/pihole-blocklist-factory && uv run ...` which loaded the main repo's stale build.py and produced confusing false failures. Resolved by running verification from the worktree directory with the `--active` flag.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PIPE-01 through PIPE-04 complete; pipeline is correct and clean
- Phase 4 (conditional HTTP fetch) can now proceed without double-fetch concern
- Phase 2 (analyze fix) unblocked — source_stats.json now has accurate per-source line counts

---
*Phase: 01-core-pipeline-bugs*
*Completed: 2026-03-29*
