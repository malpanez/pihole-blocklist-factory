---
phase: quick-260612-eki
plan: 01
subsystem: build-pipeline
tags: [performance, memory, parsing, security, ci]
requires: []
provides:
  - docs/baseline.md with baseline + Phase 1 + Phase 2 comparison metrics
  - dist/reports/provenance.jsonl.gz (streamed, replaces provenance.json)
  - dist/reports/provenance_aggregates.json (small summary for analyze/recommend)
  - 64MB download cap, 4xx-no-retry policy, path containment, SHA-pinned actions
affects: [build, parallel, parse, sanitize, classify, analyze, recommend, fetch, firebog, ci]
tech-stack:
  added: []
  patterns:
    - streamed gzip JSONL writing with single-pass aggregates
    - generator-based writelines for multi-million-line outputs
    - fail-closed path containment under repo_root
key-files:
  created:
    - docs/baseline.md
    - docs/archive/ (9 archived one-off optimization docs)
  modified:
    - src/blocklist_builder/{build,parallel,parse,sanitize,classify,analyze,recommend,fetch,firebog,types}.py
    - .github/workflows/{ci,build-lists}.yml (update.yml deleted)
    - pyproject.toml, README.md, Makefile, uv.lock
    - tests/* (10 test files)
decisions:
  - "--no-fetch now resolves http(s) sources from .cache/sources via cache-key lookup — pre-existing gap meant no-fetch builds silently produced only local-file domains"
  - "Provenance streamed as gzipped JSONL + aggregates JSON; Provenance dataclass and build_provenance removed (format change approved in plan)"
  - "Local-path sources fail closed: rejected when repo_root/allowed_base is None or path escapes it"
  - "DownloadTooLargeError is a ValueError subclass so it bypasses the RequestException retry path by construction"
metrics:
  duration: 78 minutes
  completed: 2026-06-12
  tasks: 4
  commits: 5
---

# Quick Task 260612-eki: Repo-Wide Optimization (Baseline + 3 Phases) Summary

One-liner: Cut build peak RSS 12.55 GiB -> 3.41 GiB and provenance artifact 794 MiB -> 46 MiB with byte-identical dist/all.txt, then IDN punycode + multi-hostname parsing (+1,992 justified domains), then 64MB download cap / retry policy / path containment / SHA-pinned CI.

## Commits

| Task | Commit | Message |
|---|---|---|
| pre-Task 1 (deviation) | 4f72161 | style(quick-260612-eki): fix pre-existing E402 and format drift |
| 1 (Phase 0) | 3786274 | docs(baseline): capture pre-optimization build metrics |
| 2 (Phase 1) | ed5f746 | perf(build): parallel fetch, streaming provenance, generator writes |
| 3 (Phase 2) | a831ac0 | feat(parse): IDN punycode TLDs and multi-hostname hosts lines |
| 4 (Phase 3) | aa79454 | fix(security): download cap, retry policy, path containment; ci: pin actions, coverage gate |

## Results

### Phase 0 — baseline (full fetch, 43 enabled sources, none failed)
- 4,803,099 unique domains; wall 9:47.58; peak RSS 13,158,740 KB (~12.55 GiB)
- sha256(all.txt) = 301b4628e1621f6e83fe467a2c1363bad34df5795f03883f3e6c4b13e7976461
- provenance.json = 832,869,800 bytes

### Phase 1 — behavior-preserving (HARD GATE PASSED)
- dist/all.txt sha256 **byte-identical** to baseline
- Peak RSS 3,578,712 KB (~3.41 GiB) = **-72.8%**; no-fetch wall 4:40.81
- provenance.jsonl.gz 48 MB + provenance_aggregates.json 5 KB replace 794 MiB JSON
- analyze/recommend verified working against aggregates on the real build

### Phase 2 — parsing correctness (justified delta)
- **+1,992 added, 0 removed** (4,805,091 total); 100% of added domains contain xn-- labels
- 20-domain sample traced to cached sources (hagezi_tif, pyenb_blocklist, oisd_big,
  notracking_tracker) — all punycode TLDs (.xn--p1ai/.рф, .xn--hxt814e, .xn--node)
- sanitize_not_fqdn 4,073 -> 1,428; no multi-host/wildcard lines in current sources
  (those paths covered by unit tests)

### Phase 3 — security + CI
- 64MB cap (header + streamed); 4xx never retried, 5xx/network retried with backoff
- Non-https Firebog entries skipped with warning; CSV parsed via stdlib csv.reader
- file:// and bare-path sources contained under repo_root, fail closed
- All 5 actions pinned to full commit SHAs (resolved via git ls-remote, peeled tags)
- update.yml deleted; dev deps consolidated into [dependency-groups]; CI gate
  --cov-fail-under=99; 9 one-off docs archived to docs/archive/

## Quality gates (after every task)

| Gate | Result |
|---|---|
| pytest --cov | 129 passed, **100% coverage** (was 108 tests at baseline) |
| ruff check + format --check | clean |
| mypy --strict (report-only) | 56 errors (baseline 60) — **no new errors**, net -4 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing lint/format failures blocked the quality gates**
- **Found during:** Task 1 (gates must pass before any commit)
- **Issue:** E402 mid-file import in tests/test_analyze.py; format drift in
  src/blocklist_builder/analyze.py and 3 test files (ruff 0.14.14)
- **Fix:** Moved imports to top; applied ruff format
- **Files modified:** tests/test_analyze.py, src/blocklist_builder/analyze.py, tests/test_fetch.py, tests/test_fetch_http.py, tests/test_firebog.py
- **Commit:** 4f72161 (separate commit to keep Task 1 docs-only)

**2. [Rule 3 - Blocking] --no-fetch never resolved http(s) sources from cache**
- **Found during:** Task 2 verification (no-fetch build produced only 5 domains)
- **Issue:** Pre-existing gap: neither old `_resolve_source_path` nor
  `_resolve_local_sources` mapped http(s) URLs to `.cache/sources/{key}.txt`,
  making the plan's no-fetch verification (and the documented no-fetch workflow)
  impossible
- **Fix:** `_resolve_local_sources` now does a cache-key lookup for http(s) URLs
  (warns when uncached); covered by new tests
- **Files modified:** src/blocklist_builder/parallel.py, tests/test_parallel_extra.py
- **Commit:** ed5f746 (part of Task 2)

**3. [Rule 2 - Missing critical] Inline-comment truncation in multi-hostname parsing**
- **Found during:** Task 3 design
- **Issue:** Plain `parts[1:]` would treat inline `# comment` tokens on hosts lines
  as hostnames, inflating parse stats with garbage tokens
- **Fix:** `_try_parse_hosts_format` truncates the hostname list at the first
  `#`/`!` token
- **Files modified:** src/blocklist_builder/parse.py, tests/test_parse.py
- **Commit:** a831ac0 (part of Task 3)

**4. [Rule 1 - Consistency] README/Makefile referenced removed extras and workflow**
- **Found during:** Task 4
- **Fix:** `uv sync --all-extras` -> `uv sync` in README + Makefile; removed
  "Update workflow" bullets (EN + ES) for the deleted update.yml
- **Commit:** aa79454 (part of Task 4)

## Deferred Issues

- Stale references to `update.yml` / `--all-extras` remain in docs/ARCHITECTURE.md,
  docs/DEPLOYMENT_CHECKLIST.md, docs/IMPLEMENTATION_SUMMARY.md (pre-existing
  narrative docs, out of scope; README/Makefile were corrected)
- mypy --strict still reports 56 pre-existing errors (not a project gate; recorded
  in docs/baseline.md as the report-only baseline)

## Known Stubs

None.

## Threat Flags

None — all new surface was anticipated by the plan's threat model; mitigations
T-q01-01..06 implemented (T-q01-SC accepted: zero new dependencies).

## Self-Check: PASSED
- docs/baseline.md: FOUND
- docs/archive/ (9 files): FOUND
- .github/workflows/update.yml: ABSENT (intended)
- Commits 4f72161, 3786274, ed5f746, a831ac0, aa79454: FOUND in git log
- dist/reports/provenance.jsonl.gz + provenance_aggregates.json: FOUND (gitignored dist/)
