# Phase 1: Core Pipeline Bugs - Research

**Researched:** 2026-03-29
**Domain:** Python pipeline refactoring — Counter semantics, dead code removal, test coverage
**Confidence:** HIGH

## Summary

This phase fixes four concrete bugs in the build pipeline: a redundant HTTP fetch call, a `total_lines` counter that sums wrong values, a `discarded` Counter that mixes ok-counts with discard-reason counts, and a dead function that has extensive tests but is never called from production code. All bugs are localized to two files (`build.py` and `parallel.py`) and their corresponding test files. No library changes, no new dependencies, and no output format changes are required.

The fixes are surgical: one line removal (double-fetch), two arithmetic corrections (stats), one function block deletion (dead code), and deletion of the tests that covered that dead function. The primary risk is the stats fix, which requires updating `test_build.py` — an existing integration test asserts `stats.total_lines == sum(stats.discarded.values())`, which is precisely the buggy behavior we are removing.

**Primary recommendation:** Fix in order — dead code first (lowest risk, no behavior change), then stats (requires test update), then double-fetch last (functional change, easiest to verify).

## Project Constraints (from CLAUDE.md)

- Python 3.11+ — `match/case`, `slots=True`, `tomllib` in use
- Test coverage must be ≥99% after each phase
- `ruff check` must pass clean after each phase
- `dist/` output format must not change
- No new dependencies — stdlib only

## Standard Stack

No library changes in this phase. Existing stack is sufficient.

| Module | Role | Relevant to This Phase |
|--------|------|----------------------|
| `collections.Counter` | Accumulates discard reason counts | Bug is in how its values are summed |
| `concurrent.futures.ProcessPoolExecutor` | Parallel source processing | Dead function uses this; production path uses `parallel_process_all_sources` |
| `concurrent.futures.ThreadPoolExecutor` | Parallel HTTP fetch | Used by `parallel_fetch_sources` (the redundant call to remove) |
| `dataclasses` | `Stats`, `SourceMetadata`, `Source` | `Stats` in `report.py` defines the output schema |

**Installation:** No changes needed.

## Architecture Patterns

### Pipeline Flow (current, with bug annotated)

```
build()
├── parallel_fetch_sources()      ← BUG: result discarded with `_ =`; fetches all HTTP sources
├── _collect_domains()
│   ├── _resolve_all_source_paths()
│   │   └── _resolve_source_path() → fetch_to_cache()  ← fetches again for every HTTP source
│   └── parallel_process_all_sources()  ← actual production parse/sanitize path
├── Stats construction
│   ├── total_lines = sum(discarded.values())  ← BUG: includes parse_ok + sanitize_ok
│   └── discarded = dict(discarded)            ← BUG: includes parse_ok + sanitize_ok as keys
└── write_reports()
```

### Correct Flow (after fix)

```
build()
├── _collect_domains()
│   ├── _resolve_all_source_paths() → fetch_to_cache()  ← single fetch per source
│   └── parallel_process_all_sources()
├── Stats construction
│   ├── total_lines = sum(source_stats[s]["lines"] for s in source_stats)  ← actual line count
│   ├── parsed_ok = from discarded counter
│   ├── sanitized_ok = from discarded counter
│   └── discarded = {k: v for k, v in discarded.items() if not k.endswith("_ok")}
└── write_reports()
```

### Stats Data Flow (exact locations)

`parallel.py:_process_source_file_worker()` builds a `stats` dict per source:

```python
stats = dict(discarded)          # keys like parse_comment, sanitize_ip, ...
stats["lines"] = len(lines)      # raw line count
stats["parse_ok"] = parsed_ok    # domains that passed parse
stats["sanitize_ok"] = sanitized_ok  # domains that passed sanitize
stats["allowlisted"] = allowlisted
return valid, stats
```

`build.py:_collect_domains()` merges source stats into the global `discarded` Counter:

```python
for k, v in stats.items():
    if k != "lines":             # "lines" excluded from discarded
        discarded[k] += v        # parse_ok and sanitize_ok ARE included here
```

This is the root of PIPE-02 and PIPE-03: `parse_ok` and `sanitize_ok` end up inside `discarded`, and `total_lines = sum(discarded.values())` counts them alongside actual discard reasons.

### Stats.discarded semantics (current vs target)

**Current:** `discarded` dict in `Stats` contains both ok-counters and discard-reason counters:
```json
{
  "parse_ok": 4577697,
  "sanitize_ok": 4575447,
  "parse_comment": 123456,
  "sanitize_ip": 98765,
  ...
}
```

**Target:** `discarded` contains only discard reasons:
```json
{
  "parse_comment": 123456,
  "sanitize_ip": 98765,
  ...
}
```

And `total_lines` is computed from `source_stats["lines"]` values, not from `discarded`.

### Dead Code Scope

`parallel_parse_and_sanitize` (lines 138-188 of `parallel.py`) is fully self-contained. It is:
- Never imported by `build.py` (only `parallel_fetch_sources` and `parallel_process_all_sources` are imported)
- Only imported in `tests/test_parallel.py` (1 test) and `tests/test_parallel_extra.py` (5 tests that call it directly)
- Not referenced anywhere else in the codebase

Tests to delete:
- `tests/test_parallel.py` — entire file (1 test, imports only `parallel_parse_and_sanitize`)
- `tests/test_parallel_extra.py` — 5 tests that call `parallel_parse_and_sanitize` directly:
  - `test_parallel_parse_and_sanitize_processpool_success`
  - `test_parallel_parse_and_sanitize_processpool_future_error`
  - `test_parallel_parse_and_sanitize_processpool_success_discard`
  - `test_parallel_parse_and_sanitize_processpool_ctor_error`
  - `test_parallel_parse_and_sanitize_counts` (in `test_parallel.py`)

The remaining tests in `test_parallel_extra.py` (those covering `parallel_fetch_sources`, `parallel_process_all_sources`, `_process_source_file_worker`, `get_optimal_workers`, `_process_chunk_worker`) are for live production code and MUST be kept.

### Anti-Patterns to Avoid

- **Do not pass the `parallel_fetch_sources` result into `_collect_domains`.** The analysis notes this as a possible fix approach, but the simpler and correct fix is just removing the redundant call. `_collect_domains` already fetches via `_resolve_all_source_paths`.
- **Do not remove `parse_ok`/`sanitize_ok` from `source_stats`.** These fields in `source_stats.json` (per-source) are correct and used by Phase 2 analysis. Only remove them from the global `discarded` Counter used by `Stats`.
- **Do not change `Stats` dataclass fields.** `total_lines`, `parsed_ok`, `sanitized_ok`, `unique_domains`, `discarded` all remain. Only the values change.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Counting actual input lines | Custom line counter | `source_stats[src_id]["lines"]` already populated by `_process_source_file_worker` |
| Separating ok vs discard counters | New accumulator class | Filter existing `discarded` Counter by key suffix at Stats construction time |

## Common Pitfalls

### Pitfall 1: Breaking the existing integration test assertion
**What goes wrong:** `test_build.py:107` asserts `stats.total_lines == sum(stats.discarded.values())`. This assertion is correct given the current buggy behavior but will fail after the fix.
**Why it happens:** The test was written to match observed behavior, not correct behavior.
**How to avoid:** Update the assertion to `stats.total_lines == 15` (sum of source1 lines=10 and source2 lines=5 from the test fixtures). Also remove `parse_ok` and `sanitize_ok` from `stats.discarded` assertions.
**Warning signs:** Test failure on `test_build_writes_stats_and_source_stats` after stats fix — expected, must update the test.

### Pitfall 2: Leaving dead imports after removing parallel_parse_and_sanitize
**What goes wrong:** `ruff check` fails on unused imports.
**Why it happens:** After deleting `parallel_parse_and_sanitize`, the import in any remaining test file that references it will fail both Python import and ruff.
**How to avoid:** `test_parallel.py` imports only `parallel_parse_and_sanitize` — delete the whole file. `test_parallel_extra.py` imports it at the top (line 8) alongside other used imports — remove just that import line and the 5 test functions.
**Warning signs:** `ImportError` or `ruff` F401 (unused import) after deletion.

### Pitfall 3: Coverage drop from test deletion
**What goes wrong:** Deleting dead function tests drops coverage of lines that become uncovered.
**Why it happens:** The dead function `parallel_parse_and_sanitize` (lines 138-188) currently has 100% coverage from tests. After deletion of both function and tests, coverage of the remaining file should stay 100%.
**How to avoid:** Delete both function and tests together. Do not delete tests without deleting the function first.
**Warning signs:** Coverage report showing `parallel.py` below 100% means tests were deleted but function was not, or vice versa.

### Pitfall 4: total_lines computation when no sources resolve
**What goes wrong:** `sum(source_stats[s]["lines"] for s in source_stats)` raises `KeyError` if a source failed to resolve (has `source_missing` in stats but no `lines` key).
**Why it happens:** Failed sources get `{source_missing: 1}` in `source_stats` without a `lines` key.
**How to avoid:** Use `source_stats[s].get("lines", 0)` for safe access.
**Warning signs:** `KeyError: 'lines'` when a source fails to resolve.

### Pitfall 5: Double-fetch fix scope
**What goes wrong:** Removing `parallel_fetch_sources` call from `build()` without checking `parallel_fetch_sources` is still imported.
**Why it happens:** `build.py` line 16: `from .parallel import parallel_fetch_sources, parallel_process_all_sources`. After removing the call, `parallel_fetch_sources` becomes an unused import.
**How to avoid:** Remove `parallel_fetch_sources` from the import line in `build.py` when removing the call.
**Warning signs:** `ruff check` F401 on `parallel_fetch_sources` after removing the call but not the import.

## Code Examples

### Current buggy stats computation (build.py:313-323)
```python
# Source: build.py lines 313-323
parsed_ok = discarded.get(f"{_PARSE_PREFIX}ok", 0)
sanitized_ok = discarded.get(f"{_SANITIZE_PREFIX}ok", 0)
total_lines = sum(discarded.values())  # BUG: includes parse_ok + sanitize_ok

stats = Stats(
    total_lines=total_lines,
    parsed_ok=parsed_ok,
    sanitized_ok=sanitized_ok,
    unique_domains=len(all_domains),
    discarded=dict(discarded),  # BUG: includes parse_ok + sanitize_ok keys
)
```

### Fixed stats computation
```python
parsed_ok = discarded.get(f"{_PARSE_PREFIX}ok", 0)
sanitized_ok = discarded.get(f"{_SANITIZE_PREFIX}ok", 0)
total_lines = sum(s.get("lines", 0) for s in source_stats.values())

_ok_keys = {f"{_PARSE_PREFIX}ok", f"{_SANITIZE_PREFIX}ok"}
stats = Stats(
    total_lines=total_lines,
    parsed_ok=parsed_ok,
    sanitized_ok=sanitized_ok,
    unique_domains=len(all_domains),
    discarded={k: v for k, v in discarded.items() if k not in _ok_keys},
)
```

### Current double-fetch (build.py:260-265)
```python
# Source: build.py lines 260-265
# Parallel fetch all sources first
_ = parallel_fetch_sources(          # fetches all HTTP sources, result discarded
    [s for s in settings.sources if s.enabled],
    cache_dir,
    no_fetch=no_fetch,
)
```

### Fix: delete lines 260-265 entirely, remove `parallel_fetch_sources` from import on line 16.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (uv run pytest) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/test_build.py tests/test_parallel_extra.py -x -q` |
| Full suite command | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | `parallel_fetch_sources` not called in `build()` | unit | `uv run pytest tests/test_build.py -x -q` | Yes |
| PIPE-02 | `stats.total_lines` equals sum of source `lines` counts | unit | `uv run pytest tests/test_build.py::test_build_writes_stats_and_source_stats -x` | Yes (assertion needs update) |
| PIPE-03 | `stats.discarded` does not contain `parse_ok` or `sanitize_ok` keys | unit | `uv run pytest tests/test_build.py::test_build_writes_stats_and_source_stats -x` | Yes (assertion needs update) |
| PIPE-04 | `parallel_parse_and_sanitize` does not exist in `parallel.py` | unit | `uv run pytest tests/test_parallel_extra.py -x -q` | Yes (affected tests to delete) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_build.py tests/test_parallel_extra.py -x -q`
- **Per wave merge:** `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q`
- **Phase gate:** Full suite ≥99% coverage, `ruff check` clean before verify

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements. Wave 0 test updates are part of the fix tasks, not prerequisites.

## Open Questions

1. **Should `parse_ok`/`sanitize_ok` be excluded from `discarded` Counter accumulation entirely, or only filtered at Stats construction?**
   - What we know: `_collect_domains` feeds both ok-keys and discard-reason keys into `discarded` Counter together. Phase 2 does not use the global `discarded` Counter directly (it reads `source_stats.json`).
   - What's unclear: Whether any code between `_collect_domains` and Stats construction inspects `discarded` and would break if ok-keys were absent.
   - Recommendation: Filter at Stats construction (safest — one-line change, no upstream side effects). Do not change `_collect_domains` logic.

2. **Does `test_build.py::test_build_source_missing_and_drop_patterns` also assert total_lines?**
   - What we know: That test only asserts `stats.discarded["source_missing"]` and `stats.discarded["parse_pattern_drop"]`. It does not assert `total_lines`.
   - Resolution: No change needed in that test.

## Environment Availability

Step 2.6: SKIPPED — phase is purely code/config changes with no external dependencies beyond the existing Python/uv toolchain.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | Test runner | Yes | (system installed) | — |
| pytest | Test framework | Yes | via uv | — |
| ruff | Linting | Yes | via uv | — |

## Sources

### Primary (HIGH confidence)
- Direct source code inspection: `build.py`, `parallel.py`, `fetch.py`, `report.py`
- Direct test inspection: `test_build.py`, `test_parallel.py`, `test_parallel_extra.py`
- `.planning/codebase/analysis.md` — prior analysis with exact line references
- Coverage run: 98 tests, 99% coverage, 2 uncovered lines at `build.py:69-70`

### Secondary (MEDIUM confidence)
- None required — all findings based on direct code reading

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Bug locations: HIGH — verified by direct code reading with line numbers
- Fix approach: HIGH — straightforward deletions and arithmetic corrections
- Test impact: HIGH — exact assertions identified that require updating
- Coverage impact: HIGH — coverage run confirms current state; deletion plan verified against import graph

**Research date:** 2026-03-29
**Valid until:** Until any of `build.py`, `parallel.py`, `report.py`, `test_build.py`, or `test_parallel*.py` are modified

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | Build pipeline fetches each HTTP source exactly once per run | Double-fetch identified at `build.py:261-265`; fix is removal of those lines + import cleanup |
| PIPE-02 | `stats.json` `total_lines` reflects actual input line count (~4.5M, not ~9.1M) | Root cause: `sum(discarded.values())` includes ok-counts; fix uses `source_stats[s]["lines"]` |
| PIPE-03 | `stats.json` separates processing-ok counters from discard-reason counters | Root cause: `parse_ok`/`sanitize_ok` keys in `discarded` Counter; fix filters them at Stats construction |
| PIPE-04 | Dead function `parallel_parse_and_sanitize` removed from production code and tests | Function at `parallel.py:138-188`; tests at `test_parallel.py` (whole file) and 5 functions in `test_parallel_extra.py` |
</phase_requirements>
