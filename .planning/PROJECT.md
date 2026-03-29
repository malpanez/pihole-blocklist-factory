# pihole-blocklist-factory

## What This Is

A Python CLI tool that builds custom Pi-hole blocklists by fetching domain lists from multiple sources (HTTP + local files), parsing and sanitizing them in parallel, categorizing domains, and writing per-profile blocklist files to `dist/`. Targets homelab/self-hosted users who want a reproducible, auditable blocklist pipeline.

## Core Value

Produce accurate, deduplicated, correctly-categorized blocklists from multiple sources — with stats and provenance that reflect reality.

## Requirements

### Validated

- ✓ Multi-source fetch with parallel HTTP downloads — existing
- ✓ Parse + sanitize pipeline with ProcessPoolExecutor parallelism — existing
- ✓ Per-category and per-profile blocklist output — existing
- ✓ Domain provenance tracking (source attribution) — existing
- ✓ Build stats reporting (stats.json) — existing
- ✓ Quality analysis command (analyze) — existing (broken)
- ✓ Source recommendation command (recommend) — existing
- ✓ Firebog catalog import (firebog subcommand) — existing
- ✓ 99% test coverage with ruff linting — existing

### Active

- [x] Fix double-fetch bug: HTTP sources downloaded twice per build — **Validated in Phase 1: Core Pipeline Bugs**
- [x] Remove dead code: `parallel_parse_and_sanitize` never called in production — **Validated in Phase 1: Core Pipeline Bugs**
- [x] Fix stats double-counting: `total_lines` reports ~9.1M instead of ~4.5M — **Validated in Phase 1: Core Pipeline Bugs**
- [x] Fix analyze pipeline: `_compute_discard_findings` always returns empty (discard_rate always 0%) — **Validated in Phase 2: Analyze Pipeline Fix**
- [x] Remove silently-ignored profile fields: `include_sources`, `exclude_sources`, `strict`, `sensitive_domains` — **Validated in Phase 3: Profile Features Cleanup**
- [x] Implement HTTP conditional fetching (ETag/If-Modified-Since) to avoid redundant downloads — **Validated in Phase 4: HTTP Conditional Fetching**
- [x] Consistent path traversal protection across all code paths — **Validated in Phase 5: Security Hardening**
- [ ] Fix CI/CD: `update.yml` never detects changes (dist/ gitignored), releases accumulate unboundedly
- [ ] Code quality cleanup: YAML injection in firebog.py, env var at module scope, TLD regex, stub commands

### Out of Scope

- Pi-hole v6 API integration for automated list loading — deferred, `sync-github-catalog` and setup script are stubs
- Per-device profile differentiation via `include_sources` (android/ios/windows/macos) — removing rather than implementing; implementation too complex for current scope
- SSL certificate pinning — low impact on blocklist content security
- Provenance.json scalability refactor (O(n²) recommend.py) — out of scope for this milestone

## Context

**Existing quality:** Well-structured Python 3.11+, frozen dataclasses, typed throughout, 99% coverage. Main issues are architectural (dead code, unimplemented features presented as features) and logic bugs producing incorrect output.

**Key bugs with user-visible impact:**
- Stats are misleading: 9.1M reported vs 4.5M actual total_lines
- `analyze` command never produces quality findings regardless of source quality
- Every build re-downloads all sources twice (doubles network I/O)
- Per-device profiles (android/ios/windows/macos) all produce identical output

**CI/CD state:**
- `update.yml` has been broken since `dist/` was added to `.gitignore` — auto-update PRs never fire
- `build-lists.yml` creates a new GitHub release every run (65+/year, unbounded growth)

**Analysis artifact:** `.planning/codebase/analysis.md` contains the full 22-issue breakdown with severity ratings and exact file/line references.

## Constraints

- **Python**: 3.11+ — uses `match/case`, `slots=True`, `tomllib`
- **Test coverage**: Must maintain ≥99% after each phase
- **Linting**: `ruff check` must pass clean after each phase
- **Backwards compatibility**: `dist/` output format must not change (Pi-hole adlist URLs are stable)
- **No new dependencies**: Fix bugs using existing stdlib; avoid adding packages

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Remove `include_sources`/`exclude_sources`/`strict` rather than implement | Implementation requires significant `_write_profiles()` rewrite; current profiles only differ by `include_categories` which works | — Pending |
| Fix double-fetch by removing redundant `parallel_fetch_sources()` call | Simpler than threading result through to `_collect_domains()`; `_resolve_all_source_paths()` already caches to disk | — Pending |
| Load `source_stats.json` in analyze.py instead of reconstructing from provenance | `source_stats.json` already has correct per-source counts; provenance lacks discard information | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-29 after Phase 5: Security Hardening complete*
