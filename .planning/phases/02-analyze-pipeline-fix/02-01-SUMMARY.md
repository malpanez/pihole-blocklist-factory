---
phase: 02-analyze-pipeline-fix
plan: 01
subsystem: analyze
tags: [bug-fix, tdd, analyze, source-stats]
dependency_graph:
  requires: []
  provides: [working-discard-findings]
  affects: [analyze_build, _compute_discard_findings, _load_source_stats]
tech_stack:
  added: []
  patterns: [TDD red-green, fixture-based tests, graceful degradation]
key_files:
  created: []
  modified:
    - src/blocklist_builder/analyze.py
    - tests/test_analyze.py
decisions:
  - Load source_stats.json in analyze.py instead of reconstructing from provenance (pre-phase decision confirmed)
  - Remove defaultdict import — no longer needed after rewrite
  - Use src_id as fallback name when source not in source_map
metrics:
  duration: 104s
  completed: 2026-03-29
  tasks_completed: 2
  files_modified: 2
---

# Phase 2 Plan 1: Fix _compute_discard_findings Summary

**One-liner:** Fixed analyze pipeline to read pre-computed per-source stats from source_stats.json instead of reconstructing discard data from provenance (which only contains retained domains), making discard findings functional.

## What Was Done

The `analyze` command's discard-rate findings were a permanent no-op: `_compute_discard_findings` was reading provenance.json (retained domains only), building a per-source sanitized count, but `discarded` was always 0 because discarded entries never appear in provenance. The fix redirects the function to read `source_stats.json` (written by the build pipeline) which already contains the accurate per-source raw line counts.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix _compute_discard_findings and add _load_source_stats | 9ab5762 | src/blocklist_builder/analyze.py, tests/test_analyze.py |
| 2 | Full suite validation and lint check | (no code changes) | - |

## Changes Made

### src/blocklist_builder/analyze.py

- Removed `from collections import defaultdict` import
- Added `_load_source_stats(dist_dir)` — loads `dist/reports/source_stats.json`, returns None on missing/invalid
- Rewrote `_compute_discard_findings` — new signature `(source_stats_data: dict, source_map: dict, ...)`, computes `discard_rate = (lines - sanitize_ok) / lines`, handles `lines=0` safely, uses `src_id` as fallback name when source not in map
- Updated `analyze_build` caller to call `_load_source_stats(dist_dir)` and pass result to `_compute_discard_findings` (skips if None)

### tests/test_analyze.py

- Deleted `test_compute_discard_findings_triggers` (monkeypatch bypass — injected `discarded: 2` via `FakeDefaultDict`, never tested real code)
- Added 7 new fixture-based tests: `test_compute_discard_findings_fires`, `test_compute_discard_findings_no_finding`, `test_compute_discard_findings_zero_lines`, `test_compute_discard_findings_source_not_in_map`, `test_load_source_stats_missing`, `test_load_source_stats_valid`, `test_load_source_stats_invalid_json`

## Verification Results

- 99 tests passed, 0 failures
- Coverage: 99% (analyze.py at 100%)
- `ruff check src/` — zero diagnostics

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED
