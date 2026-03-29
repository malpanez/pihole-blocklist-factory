---
phase: 06-ci-cd-fixes
plan: 01
subsystem: infra
tags: [github-actions, ci-cd, yaml, sha256sum, releases]

requires:
  - phase: 05-security-hardening
    provides: Clean, hardened codebase that CI runs against

provides:
  - update.yml with hash-based dist/ change detection (sha256sum) replacing broken git diff
  - update.yml with setup-uv@v5 single-step pattern, no setup-python
  - update.yml with peter-evans/create-pull-request@v8
  - build-lists.yml with fixed tag_name: latest preventing unbounded release accumulation

affects: [ci-cd, github-releases, weekly-update-workflow]

tech-stack:
  added: []
  patterns:
    - "Hash dist/ contents before/after build with find+sha256sum for gitignored path change detection"
    - "Fixed tag_name: latest with make_latest: true for rolling GitHub releases"

key-files:
  created: []
  modified:
    - .github/workflows/update.yml
    - .github/workflows/build-lists.yml

key-decisions:
  - "Use sha256sum hash comparison (not git diff) for dist/ change detection -- dist/ is gitignored so git diff always returns 0"
  - "Use tag_name: latest (not lists-$run_id) for rolling single release -- prevents unbounded release accumulation"
  - "Bump create-pull-request from v5 to v8 -- two major versions behind, core inputs unchanged"

patterns-established:
  - "Hash-based change detection: find dist -type f | sort | xargs sha256sum | sha256sum -- stable, deterministic, works on gitignored paths"

requirements-completed: [CICD-01, CICD-02, CICD-03]

duration: 5min
completed: 2026-03-29
---

# Phase 6 Plan 01: CI/CD Fixes Summary

**Three GitHub Actions workflow bugs fixed: hash-based dist/ change detection in update.yml replaces broken git-diff-on-gitignored-path, build-lists.yml now uses a fixed `latest` release tag instead of per-run unique tags, and update.yml setup-uv bumped to @v5 to match ci.yml and build-lists.yml.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-29T17:00:00Z
- **Completed:** 2026-03-29T17:05:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Fixed CICD-01: update.yml now hashes dist/ contents before and after build using sha256sum; git diff was silently always returning 0 because dist/ is gitignored
- Fixed CICD-02: build-lists.yml now uses tag_name: latest with make_latest: "true"; softprops/action-gh-release@v2 updates the existing release in-place instead of creating a new one per run
- Fixed CICD-03: update.yml consolidated from two-step setup (setup-python@v5 + setup-uv@v3) to single-step (setup-uv@v5), consistent with ci.yml and build-lists.yml
- Bumped peter-evans/create-pull-request from v5 to v8

## Task Commits

1. **Task 1: Fix update.yml -- hash-based change detection and setup-uv@v5** - `80e744a` (fix)
2. **Task 2: Fix build-lists.yml -- fixed latest release tag** - `d212531` (fix)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `.github/workflows/update.yml` - Replaced broken git-diff change detection with sha256sum hash comparison; upgraded to setup-uv@v5; bumped create-pull-request to v8
- `.github/workflows/build-lists.yml` - Changed tag_name from per-run unique to fixed `latest`; added make_latest: "true"

## Decisions Made

- Used `find dist -type f | sort | xargs sha256sum | sha256sum` pattern per research recommendation -- sort ensures deterministic ordering, the outer sha256sum produces a single comparable value
- Guard before-build hash with `if [ -d dist ]` to handle first-run case where dist/ does not yet exist (outputs `hash=none`, which differs from any real hash, correctly signaling changes)
- `make_latest: "true"` added to ensure GitHub marks the overwritten release as the repository's latest release

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three CI/CD bugs (CICD-01, CICD-02, CICD-03) resolved
- update.yml will now correctly detect weekly blocklist changes and create PRs
- build-lists.yml will maintain a single rolling `latest` release, overwriting assets on each run
- Remaining work: Phase 07 (code quality cleanup -- YAML injection in firebog.py, env var at module scope, TLD regex, stub commands)

---
*Phase: 06-ci-cd-fixes*
*Completed: 2026-03-29*
