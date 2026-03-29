---
phase: 01-core-pipeline-bugs
verified: 2026-03-29T11:00:00Z
status: passed
score: 6/6 must-haves verified
gaps: []
---

# Phase 1: Core Pipeline Bugs Verification Report

**Phase Goal:** The build pipeline fetches each source exactly once and `stats.json` reflects actual input volumes
**Verified:** 2026-03-29T11:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `parallel_parse_and_sanitize` function does not exist in production code | VERIFIED | `grep -rn parallel_parse_and_sanitize src/ tests/` returns 0 matches |
| 2 | No test imports or calls `parallel_parse_and_sanitize` | VERIFIED | `tests/test_parallel.py` deleted; `grep` across `tests/` returns 0 matches |
| 3 | `build()` does not call `parallel_fetch_sources` — each source fetched exactly once via `_resolve_source_path` | VERIFIED | `grep parallel_fetch_sources src/blocklist_builder/build.py` returns 0 matches; import line is `from .parallel import parallel_process_all_sources` only |
| 4 | `stats.total_lines` equals sum of per-source line counts, not sum of discarded values | VERIFIED | `build.py:308`: `total_lines = sum(s.get("lines", 0) for s in source_stats.values())`; `test_build.py:107`: `assert stats.total_lines == 15` |
| 5 | `stats.discarded` dict contains only discard-reason keys — no `parse_ok` or `sanitize_ok` | VERIFIED | `build.py:310-316`: `_ok_keys` set defined and filtered inline at Stats construction; `test_build.py:108-109`: `assert "parse_ok" not in stats.discarded` and `assert "sanitize_ok" not in stats.discarded` |
| 6 | `ruff check` passes clean and `pytest` reports all 93 tests passing | VERIFIED | `uv run ruff check src/` exits 0; `uv run pytest -q` reports `93 passed in 1.47s` |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/blocklist_builder/parallel.py` | Parallel processing without dead `parallel_parse_and_sanitize`; contains `parallel_process_all_sources` | VERIFIED | 230 lines; `parallel_parse_and_sanitize` and `_merge_chunk_result` absent; `parallel_process_all_sources` present at line 162 |
| `src/blocklist_builder/build.py` | Build pipeline with single-fetch and correct stats; contains `source_stats.values()` | VERIFIED | Import line 16 has only `parallel_process_all_sources`; `total_lines` computed from `source_stats.values()` at line 308; `_ok_keys` filter at lines 310-316 |
| `tests/test_build.py` | Updated stats assertions matching correct behavior; contains `stats.total_lines == 15` | VERIFIED | Lines 107-109: `assert stats.total_lines == 15`, `assert "parse_ok" not in stats.discarded`, `assert "sanitize_ok" not in stats.discarded` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/blocklist_builder/build.py` | `src/blocklist_builder/parallel.py` | `from .parallel import parallel_process_all_sources` only | VERIFIED | Line 16 imports `parallel_process_all_sources` exclusively; `parallel_fetch_sources` absent |
| `src/blocklist_builder/build.py` | `source_stats` | `total_lines` computed from `source_stats` lines values | VERIFIED | `sum(s.get("lines", 0) for s in source_stats.values())` at line 308 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `build.py` stats construction | `total_lines` | `source_stats` dict populated by `_process_source_file_worker` via `parallel_process_all_sources` | Yes — `stats["lines"] = len(lines)` set from actual file read in worker | FLOWING |
| `build.py` Stats `discarded` | `discarded` Counter | Accumulated from per-source worker stats in `_collect_domains`; filtered by `_ok_keys` | Yes — keys are real discard reasons from parse/sanitize results | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `parallel_parse_and_sanitize` absent from all code | `grep -rn parallel_parse_and_sanitize src/ tests/` | 0 matches | PASS |
| `parallel_fetch_sources` absent from `build.py` | `grep -n parallel_fetch_sources src/blocklist_builder/build.py` | 0 matches | PASS |
| `total_lines` uses `source_stats.values()` | `grep -n "total_lines = sum" src/blocklist_builder/build.py` | line 308: `sum(s.get("lines", 0) for s in source_stats.values())` | PASS |
| `_ok_keys` filter present | `grep -n "_ok_keys" src/blocklist_builder/build.py` | lines 310 and 316 | PASS |
| All 93 tests pass | `uv run pytest -q` | `93 passed in 1.47s` | PASS |
| `ruff check src/` clean | `uv run ruff check src/` | `All checks passed!` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PIPE-01 | 01-01-PLAN.md | Build pipeline fetches each HTTP source exactly once per run | SATISFIED | `parallel_fetch_sources` removed from `build.py`; single-fetch path via `_resolve_source_path` in `_resolve_all_source_paths` |
| PIPE-02 | 01-01-PLAN.md | `stats.json` `total_lines` reflects actual input line count (~4.5M, not ~9.1M) | SATISFIED | `total_lines = sum(s.get("lines", 0) for s in source_stats.values())` at `build.py:308`; test asserts `== 15` for 10+5 fixture lines |
| PIPE-03 | 01-01-PLAN.md | `stats.json` separates processing-ok counters from discard-reason counters | SATISFIED | `_ok_keys` set filters `parse_ok`/`sanitize_ok` from `stats.discarded`; test asserts both absent |
| PIPE-04 | 01-01-PLAN.md | Dead function `parallel_parse_and_sanitize` removed from production code and tests | SATISFIED | Function and `_merge_chunk_result` helper deleted from `parallel.py`; `tests/test_parallel.py` deleted; 4 test functions removed from `test_parallel_extra.py` |

No orphaned requirements: REQUIREMENTS.md Traceability table maps PIPE-01 through PIPE-04 exclusively to Phase 1, all accounted for.

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, empty implementations, or hardcoded stub patterns found in modified files.

### Human Verification Required

None. All success criteria are programmatically verifiable and confirmed.

### Gaps Summary

No gaps. All six must-have truths verified, all artifacts substantive and wired, all four Phase 1 requirements satisfied, test suite fully green, linting clean.

---

_Verified: 2026-03-29T11:00:00Z_
_Verifier: Claude (gsd-verifier)_
