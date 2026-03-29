---
phase: 03-profile-features-cleanup
plan: 01
subsystem: config
tags: [python, dataclass, yaml, dead-code-removal]

requires:
  - phase: 01-core-pipeline-bugs
    provides: clean build pipeline on which profiles operate

provides:
  - Profile dataclass with only name and include_categories fields
  - Policies dataclass with only category_precedence, core_domains, and base_allowlist fields
  - config/profiles.yml with no dead include_sources, exclude_sources, or strict keys

affects: [04-conditional-fetch, any phase reading Profile or Policies dataclasses]

tech-stack:
  added: []
  patterns:
    - "Dataclass field removal: remove field + YAML key + all constructor call sites + all test fixtures atomically"

key-files:
  created: []
  modified:
    - src/blocklist_builder/types.py
    - src/blocklist_builder/config.py
    - config/profiles.yml
    - tests/test_config.py
    - tests/test_build.py
    - tests/test_build_internal.py
    - tests/test_recommend.py
    - tests/test_analyze.py

key-decisions:
  - "Remove dead fields rather than implement per-device profile differentiation - fields were parsed but never read by build pipeline"

patterns-established:
  - "Dead field removal: single atomic sweep across dataclass -> YAML -> config parser -> all test fixtures"

requirements-completed: [PROF-01, PROF-02, PROF-03, PROF-04]

duration: 3min
completed: 2026-03-29
---

# Phase 3 Plan 1: Profile Features Cleanup Summary

**Removed 4 dead fields (include_sources, exclude_sources, strict, sensitive_domains) from Profile/Policies dataclasses, config parser, YAML config, and all 5 test files**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-29T12:50:28Z
- **Completed:** 2026-03-29T12:53:30Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- Profile dataclass reduced from 5 fields to 2 (name, include_categories)
- Policies dataclass reduced from 4 fields to 3 (category_precedence, core_domains, base_allowlist)
- config/profiles.yml cleaned of all dead YAML keys across all 7 profiles
- All test fixtures updated — no test constructs Profile or Policies with removed fields

## Task Commits

1. **Task 1: Remove dead fields from dataclasses and config parser** - `7d9391f` (feat)
2. **Task 2: Clean YAML config files** - `eddcd56` (feat)
3. **Task 3: Update tests to remove dead field references** - `5cf94e1` (feat)

## Files Created/Modified
- `src/blocklist_builder/types.py` - Removed include_sources, exclude_sources, strict fields from Profile
- `src/blocklist_builder/config.py` - Removed sensitive_domains from Policies; removed 3 dead kwargs from Profile() and Policies() constructors
- `config/profiles.yml` - Removed header comment block and dead keys from all 7 profiles
- `tests/test_config.py` - Removed dead YAML fixture keys and .strict assertion
- `tests/test_build.py` - Removed sensitive_domains=set() from Policies constructor
- `tests/test_build_internal.py` - Removed sensitive_domains=set() from 2 Policies constructors
- `tests/test_recommend.py` - Removed sensitive_domains=set() from Policies constructor
- `tests/test_analyze.py` - Removed sensitive_domains=set() from Policies constructor

## Decisions Made
None - followed plan as specified. Field removal scope was pre-decided in Phase 3 research.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failures (not caused by this plan):
- `tests/test_parallel.py` and `tests/test_parallel_extra.py`: ImportError on `parallel_parse_and_sanitize` — removed in Phase 1 as dead code. Out of scope.
- `tests/test_build.py::test_build_writes_stats_and_source_stats`: Assertion on `total_lines == sum(discarded.values())` — pre-existing failure, confirmed present before this plan's changes.
- `tests/test_analyze.py::test_compute_discard_findings_triggers`: monkeypatch AttributeError on `defaultdict` — pre-existing failure.

All 4 pre-existing failures confirmed by running tests against stashed (unmodified) state.

## Known Stubs

None.

## Next Phase Readiness
- Phase 3 complete. Profile and Policies dataclasses are clean.
- Phase 4 (conditional fetch) can proceed — Profile dataclass is now minimal and correct.
- Pre-existing test failures (test_parallel, test_build stats assertion, test_analyze monkeypatch) remain deferred from earlier phases.

---
*Phase: 03-profile-features-cleanup*
*Completed: 2026-03-29*
