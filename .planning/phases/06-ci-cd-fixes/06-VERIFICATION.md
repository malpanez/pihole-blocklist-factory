---
phase: 06-ci-cd-fixes
verified: 2026-03-29T17:30:00Z
status: passed
score: 3/3 must-haves verified
re_verification: false
gaps: []
human_verification: []
---

# Phase 6: CI/CD Fixes Verification Report

**Phase Goal:** The update workflow reliably detects blocklist changes and releases do not accumulate unboundedly
**Verified:** 2026-03-29T17:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `update.yml` detects blocklist changes via hash comparison, not git diff | VERIFIED | Lines 34, 45: `find dist -type f \| sort \| xargs sha256sum \| sha256sum` before and after build; `git diff` absent |
| 2 | `build-lists.yml` uses a fixed `latest` release tag, not a per-run unique tag | VERIFIED | Line 53: `tag_name: latest`; line 56: `make_latest: "true"`; no `lists-${{ github.run_id }}` pattern |
| 3 | `update.yml` uses `astral-sh/setup-uv@v5` with embedded `python-version`, no separate `setup-python` step | VERIFIED | Line 23: `uses: astral-sh/setup-uv@v5` with `python-version: "3.12"`; no `setup-python` step present |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.github/workflows/update.yml` | Weekly update workflow with hash-based change detection | VERIFIED | Exists, substantive (65 lines), wired — `sha256sum` present, `git diff` absent, `setup-uv@v5` present |
| `.github/workflows/build-lists.yml` | Build workflow with fixed latest release tag | VERIFIED | Exists, substantive (65 lines), wired — `tag_name: latest` and `make_latest: "true"` present, no per-run tag |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `.github/workflows/update.yml` | `dist/` | `find + sha256sum` hash comparison before/after build | VERIFIED | `hash_before` step (lines 30-37) + `check` step (lines 42-50) — pattern `sha256sum` found at lines 34 and 45 |
| `.github/workflows/build-lists.yml` | GitHub Releases | `softprops/action-gh-release@v2` with `tag_name: latest` | VERIFIED | `tag_name: latest` at line 53; `make_latest: "true"` at line 56 |

### Data-Flow Trace (Level 4)

Not applicable — phase artifacts are CI/CD YAML workflows, not components rendering dynamic data.

### Behavioral Spot-Checks

Step 7b: SKIPPED — workflow files require GitHub Actions runner execution; not runnable locally without a server/external service.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CICD-01 | 06-01-PLAN.md | `update.yml` detects blocklist changes using a mechanism that works with gitignored `dist/` | SATISFIED | `sha256sum` hash comparison in `hash_before` and `check` steps; `git diff` absent |
| CICD-02 | 06-01-PLAN.md | `build-lists.yml` overwrites a fixed `latest` release tag instead of creating a new release per run | SATISFIED | `tag_name: latest` + `make_latest: "true"` in Create release step |
| CICD-03 | 06-01-PLAN.md | `update.yml` uses `astral-sh/setup-uv@v5` (consistent with `ci.yml` and `build-lists.yml`) | SATISFIED | Single `astral-sh/setup-uv@v5` step with `python-version: "3.12"` — no `setup-python@v5`, no `setup-uv@v3` |

REQUIREMENTS.md traceability table marks CICD-01, CICD-02, CICD-03 as Complete for Phase 6. No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No anti-patterns found |

Both workflow files parse as valid YAML (verified with `python3 -c "import yaml; yaml.safe_load(...)`).

The `peter-evans/create-pull-request` action was also bumped from v5 to v8 — not a required fix but a noted improvement from the plan.

### Human Verification Required

None — all three requirements are verifiable by static inspection of YAML files. No visual output, real-time behavior, or external service integration is required to confirm the fixes.

### Gaps Summary

No gaps. All three must-haves are satisfied by the actual file contents:

- `update.yml`: hash-based change detection is implemented with `sha256sum` in two steps (`hash_before` before build, `check` after build); first-run guard (`if [ -d dist ]`) handles missing `dist/` correctly; `git diff` is absent.
- `build-lists.yml`: `tag_name: latest` with `make_latest: "true"` ensures a single rolling release is maintained; no per-run unique tag (`lists-${{ github.run_id }}`) remains.
- `update.yml`: consolidated to `astral-sh/setup-uv@v5` with `python-version: "3.12"` — consistent with `ci.yml` and `build-lists.yml`; no separate `actions/setup-python` step.

---

_Verified: 2026-03-29T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
