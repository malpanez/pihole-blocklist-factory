# Requirements: pihole-blocklist-factory

**Defined:** 2026-03-29
**Core Value:** Produce accurate, deduplicated, correctly-categorized blocklists from multiple sources — with stats and provenance that reflect reality.

## v1 Requirements

### Pipeline Correctness

- [x] **PIPE-01**: Build pipeline fetches each HTTP source exactly once per run
- [x] **PIPE-02**: `stats.json` `total_lines` reflects actual input line count (~4.5M, not ~9.1M)
- [x] **PIPE-03**: `stats.json` separates processing-ok counters from discard-reason counters
- [x] **PIPE-04**: Dead function `parallel_parse_and_sanitize` removed from production code and tests

### Analysis Quality

- [x] **ANLZ-01**: `analyze` command produces discard-rate findings for sources with high discard rates
- [x] **ANLZ-02**: `_compute_discard_findings` reads actual discard data from `source_stats.json`
- [x] **ANLZ-03**: Tests for `_compute_discard_findings` exercise the real code path (no hardcoded bypass)

### Profile Integrity

- [x] **PROF-01**: `Profile` dataclass contains only fields that are actually used by the build pipeline
- [x] **PROF-02**: `Policies` dataclass contains only fields that are actually used
- [x] **PROF-03**: `config/profiles.yml` and `config/policies.yml` do not reference removed fields
- [x] **PROF-04**: All tests pass after field removal

### Network Efficiency

- [x] **NET-01**: HTTP fetch uses `If-None-Match` / `If-Modified-Since` when prior metadata exists
- [x] **NET-02**: HTTP 304 response reuses cached file without re-writing
- [x] **NET-03**: `SourceMetadata.etag` and `last_modified` are populated on successful fetches
- [x] **NET-04**: Tests cover first-fetch, 304 (unchanged), and 200 (updated) scenarios

### Security

- [x] **SEC-01**: `file://` URLs with `..` path traversal rejected in `fetch_to_cache()`
- [x] **SEC-02**: `file://` URLs with `..` path traversal rejected in `_resolve_local_sources()`
- [x] **SEC-03**: Tests cover path traversal rejection paths (currently 0 coverage on `build.py:69-70`)
- [x] **SEC-04**: `http://` (non-HTTPS) source URLs emit a `logging.warning()` at build time
- [x] **SEC-05**: `@cache` decorator removed from `_compute_hash` (eliminates unbounded memory retention)

### CI/CD

- [ ] **CICD-01**: `update.yml` detects blocklist changes using a mechanism that works with gitignored `dist/`
- [ ] **CICD-02**: `build-lists.yml` overwrites a fixed `latest` release tag instead of creating a new release per run
- [ ] **CICD-03**: `update.yml` uses `astral-sh/setup-uv@v5` (consistent with `ci.yml` and `build-lists.yml`)

### Code Quality

- [ ] **QUAL-01**: `firebog.py` YAML generation uses `yaml.dump()` — no manual string construction
- [ ] **QUAL-02**: `BLOCKLIST_SOURCES` env var read inside `load_settings()`, not at module import time
- [ ] **QUAL-03**: `_DOMAIN_RE` TLD segment rejects numeric-only TLDs (`[a-z]{2,63}` not `[a-z0-9-]{2,63}`)
- [ ] **QUAL-04**: `create_test_data.py` and `run_build.py` added to `.gitignore`
- [ ] **QUAL-05**: `pyproject.toml` author field updated from placeholder
- [ ] **QUAL-06**: `sync-github-catalog` CLI command removed or clearly marked as not implemented
- [ ] **QUAL-07**: `scripts/pihole-adlists-setup-v6.sh` clarified as user template or removed

## v2 Requirements

### Performance

- **PERF-01**: Provenance.json replaced with SQLite or streaming format for >5M domain builds
- **PERF-02**: `recommend.py` O(n²) metrics computation replaced with O(n) streaming

### Features

- **FEAT-01**: `sync-github-catalog` command implemented (fetch and merge upstream blocklist catalogs)
- **FEAT-02**: Pi-hole v6 API integration for automated adlist loading
- **FEAT-03**: Per-device profile differentiation via `include_sources` (android/ios/windows/macos)

## Out of Scope

| Feature | Reason |
|---------|--------|
| SSL certificate pinning | Low impact on blocklist content security; blocklist content is not secret |
| OAuth / API auth for fetch | Sources are public; not needed |
| Web UI | CLI tool; out of scope for this project |
| `include_sources`/`exclude_sources` implementation | Deferred to v2; removing broken fields is safer than partial implementation |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-01 | Phase 1 | Complete |
| PIPE-02 | Phase 1 | Complete |
| PIPE-03 | Phase 1 | Complete |
| PIPE-04 | Phase 1 | Complete |
| ANLZ-01 | Phase 2 | Complete |
| ANLZ-02 | Phase 2 | Complete |
| ANLZ-03 | Phase 2 | Complete |
| PROF-01 | Phase 3 | Complete |
| PROF-02 | Phase 3 | Complete |
| PROF-03 | Phase 3 | Complete |
| PROF-04 | Phase 3 | Complete |
| NET-01 | Phase 4 | Complete |
| NET-02 | Phase 4 | Complete |
| NET-03 | Phase 4 | Complete |
| NET-04 | Phase 4 | Complete |
| SEC-01 | Phase 5 | Complete |
| SEC-02 | Phase 5 | Complete |
| SEC-03 | Phase 5 | Complete |
| SEC-04 | Phase 5 | Complete |
| SEC-05 | Phase 5 | Complete |
| CICD-01 | Phase 6 | Pending |
| CICD-02 | Phase 6 | Pending |
| CICD-03 | Phase 6 | Pending |
| QUAL-01 | Phase 7 | Pending |
| QUAL-02 | Phase 7 | Pending |
| QUAL-03 | Phase 7 | Pending |
| QUAL-04 | Phase 7 | Pending |
| QUAL-05 | Phase 7 | Pending |
| QUAL-06 | Phase 7 | Pending |
| QUAL-07 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 31
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 after roadmap finalization*
