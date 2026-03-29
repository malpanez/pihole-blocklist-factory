---
phase: 07-code-quality-cleanup
plan: 01
subsystem: testing
tags: [python, yaml, regex, config, sanitize, firebog]

requires:
  - phase: 06-ci-cd-fixes
    provides: clean codebase baseline for quality cleanup

provides:
  - BLOCKLIST_SOURCES env var read at call time inside load_settings()
  - yaml.dump-based YAML generation in firebog.py (no injection risk)
  - Stricter TLD regex rejecting numeric-only TLDs (e.g. foo.123)

affects: [08-any-future-phase-using-config, firebog-sync-users]

tech-stack:
  added: []
  patterns:
    - "Read env vars inside functions, not at module import time"
    - "Use yaml.dump for YAML generation instead of string interpolation"

key-files:
  created: []
  modified:
    - src/blocklist_builder/config.py
    - tests/test_config.py
    - src/blocklist_builder/firebog.py
    - tests/test_firebog.py
    - src/blocklist_builder/sanitize.py
    - tests/test_sanitize.py

key-decisions:
  - "Read BLOCKLIST_SOURCES inside load_settings() so monkeypatch.setenv works without importlib.reload"
  - "Use yaml.dump with default_flow_style=False to eliminate YAML injection risk in firebog output"
  - "TLD segment changed from [a-z0-9-]{2,63} to [a-z]{2,63} to reject numeric and hyphenated TLDs"

patterns-established:
  - "Env var reads belong in functions, not at module scope"
  - "Structured data serialization via yaml.dump, not f-string construction"

requirements-completed: [QUAL-01, QUAL-02, QUAL-03]

duration: 12min
completed: 2026-03-29
---

# Phase 7 Plan 01: Code Quality Cleanup Summary

**Moved BLOCKLIST_SOURCES env read into load_settings(), replaced manual YAML string construction with yaml.dump, and tightened TLD regex to reject numeric-only TLDs**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-29T00:00:00Z
- **Completed:** 2026-03-29
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Eliminated module-scope env var capture that required importlib.reload in tests (QUAL-02)
- Replaced f-string YAML construction in firebog.py with yaml.dump, eliminating YAML injection risk (QUAL-01)
- Tightened _DOMAIN_RE TLD segment from `[a-z0-9-]{2,63}` to `[a-z]{2,63}`, rejecting domains like `foo.123` (QUAL-03)
- Full test suite passes at 100% coverage, ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Move env var read into load_settings and rewrite test (QUAL-02)** - `a058f5e` (fix)
2. **Task 2: Replace manual YAML construction with yaml.dump (QUAL-01) and tighten TLD regex (QUAL-03)** - `7612f78` (fix)

## Files Created/Modified

- `src/blocklist_builder/config.py` - Removed module-scope `_BLOCKLIST_SOURCES_MODE`; added `mode = os.environ.get(...)` as first line of `load_settings()`
- `tests/test_config.py` - Removed `import importlib`; rewrote `test_load_settings_test_mode` to use `monkeypatch.setenv` only
- `src/blocklist_builder/firebog.py` - Added `import yaml`; replaced `yaml_lines` block with `yaml.dump({"sources": sources_data}, ...)`
- `tests/test_firebog.py` - Added YAML parse validation (`_yaml.safe_load`) to `test_sync_firebog_writes_file`
- `src/blocklist_builder/sanitize.py` - Changed TLD regex from `[a-z0-9-]{2,63}$` to `[a-z]{2,63}$`
- `tests/test_sanitize.py` - Added `test_sanitize_reject_numeric_tld` test

## Decisions Made

- Read `BLOCKLIST_SOURCES` inside `load_settings()` on each call — env var capture at module import time made the variable immutable for the process lifetime, requiring the fragile `importlib.reload` workaround in tests
- `yaml.dump` with `default_flow_style=False, allow_unicode=True` produces clean block-style YAML and handles special characters in source names/URLs safely
- TLD-only change (not labels): `[a-z0-9-]{2,63}` → `[a-z]{2,63}` — labels can still have digits/hyphens; only the final TLD segment is restricted to alpha-only

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- QUAL-01, QUAL-02, QUAL-03 all resolved
- Plan 07-02 (stub commands cleanup) is ready to execute
- Full test suite at 100% coverage, ruff clean — solid baseline for next plan

---
*Phase: 07-code-quality-cleanup*
*Completed: 2026-03-29*
