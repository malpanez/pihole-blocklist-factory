# Optimization Baseline Metrics

Reference metrics for the repo-wide optimization work (quick task 260612-eki).
All builds use the default source set (`BLOCKLIST_SOURCES` unset → sources.yml +
sources.firebog.yml + sources.local.yml; 46 configured sources, 43 enabled).

## Baseline (pre-optimization)

- **Date:** 2026-06-12
- **Command:** `/usr/bin/time -v uv run blocklist-factory build` (full fetch, network)
- **Wall time:** 9:47.58 (587.58 s elapsed; user 544.35 s, sys 136.67 s, 115% CPU)
- **Peak RSS:** 13,158,740 KB (~12.55 GiB)
- **sha256(dist/all.txt):** `301b4628e1621f6e83fe467a2c1363bad34df5795f03883f3e6c4b13e7976461`
- **Failed source downloads:** none (no `source_missing` recorded)

### Domain counts

| Output | Lines |
|---|---|
| dist/all.txt | 4,803,099 |
| categories/advertising.txt | 2,636,037 |
| categories/malicious.txt | 1,779,380 |
| categories/suspicious.txt | 230 |
| categories/tracking.txt | 387,452 |
| profiles/aggressive.txt | 4,802,869 |
| profiles/android.txt | 4,802,869 |
| profiles/base.txt | 4,802,869 |
| profiles/ios.txt | 4,802,869 |
| profiles/macos.txt | 4,802,869 |
| profiles/security.txt | 1,779,380 |
| profiles/windows.txt | 4,802,869 |

### Pipeline stats (dist/reports/stats.json)

- total_lines: 6,928,647
- parsed_ok: 6,871,067
- sanitized_ok: 6,865,799
- unique_domains: 4,803,099
- discarded: parse_comment 37,270 / parse_empty 20,144 / parse_unsupported 166 /
  sanitize_ip 1,165 / sanitize_not_fqdn 4,073 / sanitize_invalid 25 /
  sanitize_single_label 5 / allowlisted 4

### Report artifact sizes (pre-optimization)

- dist/reports/provenance.json: 832,869,800 bytes (~794 MiB)

### Quality gate baseline

- pytest: 108 passed, coverage 100%
- ruff check + format: clean (after fixing pre-existing E402 in tests/test_analyze.py
  and format drift in 4 files — commit `style(quick-260612-eki)`)
- `uvx mypy --strict src/blocklist_builder`: **60 pre-existing errors in 8 files**
  (cli.py 16, build.py 13, recommend.py 9, firebog.py 8, fetch.py 8, analyze.py 8,
  config.py 4, parallel.py 2). mypy is not a project dependency; this count is the
  report-only baseline — later phases must not add new errors.

## Phase 1 comparison

_To be appended after the behavior-preserving perf/memory phase._

## Phase 2 comparison

_To be appended after the parsing correctness phase._
