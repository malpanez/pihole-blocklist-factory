# Roadmap: pihole-blocklist-factory

## Overview

Systematic quality improvement of an existing, well-structured Python CLI tool. The pipeline is correct in architecture but has concrete bugs producing wrong output (doubled stats, broken analysis command, redundant HTTP fetches), dead code masquerading as features, and broken CI/CD. Phases are ordered by impact: fix output-correctness bugs first, then restore broken features, then remove dead code, then add missing efficiency and security, then repair infrastructure, then clean up low-severity issues.

## Phases

- [x] **Phase 1: Core Pipeline Bugs** - Fix double-fetch, stats double-counting, and remove dead parallel function (completed 2026-03-29)
- [x] **Phase 2: Analyze Pipeline Fix** - Restore `analyze` command so discard findings actually fire (completed 2026-03-29)
- [x] **Phase 3: Profile Features Cleanup** - Remove silently-ignored Profile/Policies fields (completed 2026-03-29)
- [x] **Phase 4: HTTP Conditional Fetching** - Implement ETag/If-Modified-Since to skip unchanged sources (completed 2026-03-29)
- [x] **Phase 5: Security Hardening** - Consistent path traversal checks, remove unbounded cache, HTTP warning (completed 2026-03-29)
- [x] **Phase 6: CI/CD Fixes** - Fix broken update workflow and unbounded release accumulation (completed 2026-03-29)
- [ ] **Phase 7: Code Quality Cleanup** - YAML injection, env var scope, TLD regex, stubs, author field

## Phase Details

### Phase 1: Core Pipeline Bugs
**Goal**: The build pipeline fetches each source exactly once and `stats.json` reflects actual input volumes
**Depends on**: Nothing (first phase)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04
**Success Criteria** (what must be TRUE):
  1. A build run with 20 HTTP sources triggers exactly 20 HTTP requests (not 40)
  2. `dist/reports/stats.json` `total_lines` matches the sum of per-source line counts (~4.5M, not ~9.1M)
  3. `stats.json` `parse_ok` and `sanitize_ok` counters are separated from the discard-reason counters
  4. `parallel_parse_and_sanitize` function and its tests no longer exist in the codebase
  5. `ruff check` passes and `pytest` reports ≥99% coverage after changes
**Plans**: 1 plan
Plans:
- [x] 01-01-PLAN.md — Remove dead code, fix double-fetch, fix stats double-counting

### Phase 2: Analyze Pipeline Fix
**Goal**: The `analyze` command produces real discard-rate findings when sources have high discard rates
**Depends on**: Phase 1
**Requirements**: ANLZ-01, ANLZ-02, ANLZ-03
**Success Criteria** (what must be TRUE):
  1. Running `analyze` on a build with known high-discard sources produces at least one finding
  2. `_compute_discard_findings` reads per-source discard data from `source_stats.json` instead of reconstructing from provenance
  3. Tests for `_compute_discard_findings` exercise the real code path without hardcoded bypasses
  4. `ruff check` passes and `pytest` reports ≥99% coverage after changes
**Plans**: 1 plan
Plans:
- [x] 02-01-PLAN.md — Fix _compute_discard_findings to use source_stats.json, rewrite tests

### Phase 3: Profile Features Cleanup
**Goal**: Profile and Policies dataclasses contain only fields the build pipeline actually uses
**Depends on**: Phase 2
**Requirements**: PROF-01, PROF-02, PROF-03, PROF-04
**Success Criteria** (what must be TRUE):
  1. `Profile` dataclass no longer contains `include_sources`, `exclude_sources`, or `strict` fields
  2. `Policies` dataclass no longer contains `sensitive_domains` field
  3. `config/profiles.yml` and `config/policies.yml` contain no references to removed fields
  4. All existing tests pass after field removal with no behavior change in build output
  5. `ruff check` passes and `pytest` reports ≥99% coverage after changes
**Plans**: 1 plan
Plans:
- [x] 03-01-PLAN.md — Remove dead fields from dataclasses, clean YAML config, update tests

### Phase 4: HTTP Conditional Fetching
**Goal**: Builds skip re-downloading sources that have not changed since the last run
**Depends on**: Phase 1
**Requirements**: NET-01, NET-02, NET-03, NET-04
**Success Criteria** (what must be TRUE):
  1. A second build run sends `If-None-Match` and/or `If-Modified-Since` headers for sources fetched previously
  2. A server returning HTTP 304 results in the cached file being reused without rewriting
  3. `SourceMetadata.etag` and `last_modified` are non-None after a successful fetch that returns those headers
  4. Tests cover first-fetch, 304 (unchanged), and 200 (updated) code paths
  5. `ruff check` passes and `pytest` reports ≥99% coverage after changes
**Plans**: 1 plan
Plans:
- [x] 04-01-PLAN.md — Add conditional HTTP headers and 304 handling to fetch pipeline

### Phase 5: Security Hardening
**Goal**: Path traversal protection is consistent across all `file://` code paths and memory usage is bounded
**Depends on**: Phase 1
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05
**Success Criteria** (what must be TRUE):
  1. A `file://` URL containing `..` components is rejected in both `fetch_to_cache()` and `_resolve_local_sources()`
  2. Tests cover the path traversal rejection branches in all three code paths (currently 0 coverage for two of them)
  3. A source URL using `http://` (not HTTPS) emits a `logging.warning()` at build time
  4. `_compute_hash` no longer carries the `@cache` decorator
  5. `ruff check` passes and `pytest` reports ≥99% coverage after changes
**Plans**: 1 plan
Plans:
- [x] 05-01-PLAN.md — Add path traversal guards, http:// warning, remove @cache from _compute_hash

### Phase 6: CI/CD Fixes
**Goal**: The update workflow reliably detects blocklist changes and releases do not accumulate unboundedly
**Depends on**: Phase 1
**Requirements**: CICD-01, CICD-02, CICD-03
**Success Criteria** (what must be TRUE):
  1. `update.yml` detects blocklist changes using a mechanism that works with `dist/` gitignored (e.g., hash comparison)
  2. `build-lists.yml` overwrites a fixed `latest` release tag instead of creating a new uniquely-tagged release each run
  3. `update.yml` uses `astral-sh/setup-uv@v5` consistent with `ci.yml` and `build-lists.yml`
**Plans**: 1 plan
Plans:
- [x] 06-01-PLAN.md — Fix update workflow and release tag strategy

### Phase 7: Code Quality Cleanup
**Goal**: Low-severity code quality issues resolved — no YAML injection risk, correct env var scoping, tighter domain validation, no stub commands
**Depends on**: Phase 6
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06, QUAL-07
**Success Criteria** (what must be TRUE):
  1. `firebog.py` YAML generation uses `yaml.dump()` — source names/URLs with special characters produce valid YAML
  2. `BLOCKLIST_SOURCES` env var is read inside `load_settings()`, eliminating the fragile `importlib.reload()` test workaround
  3. `_DOMAIN_RE` TLD segment uses `[a-z]{2,63}` — numeric-only TLDs like `foo.123` are rejected
  4. `create_test_data.py` and `run_build.py` are added to `.gitignore`
  5. `sync-github-catalog` CLI command is removed or clearly marked stub; `scripts/pihole-adlists-setup-v6.sh` clarified; `pyproject.toml` author updated
  6. `ruff check` passes and `pytest` reports ≥99% coverage after changes
**Plans**: 1 plan
Plans:
- [ ] 07-01-PLAN.md — YAML injection fix, env var scope, TLD regex, stubs cleanup

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Pipeline Bugs | 0/TBD | Complete    | 2026-03-29 |
| 2. Analyze Pipeline Fix | 1/1 | Complete    | 2026-03-29 |
| 3. Profile Features Cleanup | 1/1 | Complete    | 2026-03-29 |
| 4. HTTP Conditional Fetching | 1/1 | Complete   | 2026-03-29 |
| 5. Security Hardening | 1/1 | Complete   | 2026-03-29 |
| 6. CI/CD Fixes | 1/1 | Complete   | 2026-03-29 |
| 7. Code Quality Cleanup | 0/TBD | Not started | - |
