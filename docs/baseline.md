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

- **Date:** 2026-06-12
- **Command:** `/usr/bin/time -v uv run blocklist-factory build --no-fetch`
  (against `.cache/sources/` populated by the baseline fetch; same 43 sources)
- **sha256(dist/all.txt):** `301b4628e1621f6e83fe467a2c1363bad34df5795f03883f3e6c4b13e7976461`
  — **byte-identical to baseline** (hard gate passed)
- **Peak RSS:** 3,578,712 KB (~3.41 GiB) vs baseline 13,158,740 KB (~12.55 GiB)
  → **-72.8%** (directly comparable: same inputs, fetch I/O does not affect peak RSS,
  which is dominated by the parse/provenance phase)
- **Wall time:** 4:40.81 (no-fetch) vs baseline 9:47.58 (full fetch) — qualitative only,
  since the baseline includes ~44 network downloads
- **Pipeline stats:** identical (unique 4,803,099 / parsed_ok 6,871,067 /
  sanitized_ok 6,865,799)

### Provenance artifact change (approved format change)

| Artifact | Baseline | Phase 1 |
|---|---|---|
| provenance.json | 832,869,800 B (~794 MiB) | no longer written |
| provenance.jsonl.gz | — | 48,093,478 B (~46 MiB, streamed) |
| provenance_aggregates.json | — | 5,072 B |

analyze/recommend now consume `provenance_aggregates.json` (single dict lookup per
source) instead of loading the full provenance JSON into memory.

### Note: --no-fetch cache resolution fix

Pre-existing gap: `--no-fetch` resolved only local-path sources; http(s) sources were
never mapped to their `.cache/sources/` entries, so a no-fetch build produced only
5 domains. Fixed in `_resolve_local_sources` (cache-key lookup per URL) — required
for this comparison and for the documented no-fetch workflow to function at all.

## Phase 2 comparison

- **Date:** 2026-06-12
- **Command:** `uv run blocklist-factory build --no-fetch` (same cache as Phase 1)
- **Delta vs Phase 1 all.txt:** **+1,992 added, 0 removed** (4,805,091 vs 4,803,099)
- **All 1,992 added domains contain `xn--` labels** (`grep -c "xn--" added == 1992`) —
  these are IDN punycode TLD domains previously rejected by the `[a-z]{2,63}` final
  label and now accepted by the `(xn--[a-z0-9-]{1,59}|[a-z]{2,63})` alternation.
- **Stats shift:** `sanitize_not_fqdn` 4,073 → 1,428 (-2,645 = newly accepted punycode
  entries before dedup); `sanitized_ok` 6,865,799 → 6,868,444 (+2,645); `parsed_ok`
  unchanged (6,871,067) — no multi-hostname or wildcard lines exist in the current
  source set, so those parser changes produced no delta here (covered by unit tests).

### 20-domain sample of added entries (all traced to cached sources)

| Domain | Source | Justification |
|---|---|---|
| xn----7sbbk0auidbf2b5a.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| xn--s1afb.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| test.xn--d1abb4arh.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| www.xn--80aaaao1aure0a6a.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| xn----8sb7bjbebi.xn--p1ai | pyenb_blocklist | punycode TLD (.рф) |
| www.xn----htbbhiankkhbwvd5l.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| mail.xn--80acmblfbgosci7at.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| ftp.xn--80adcgutoavp4m.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| www.xn----rtbnabcatsu.xn--p1ai | pyenb_blocklist | punycode TLD (.рф) |
| mail.xn--80adhtqlq.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| xn----itbhqobajbjbrf.xn--p1ai | oisd_big | punycode TLD (.рф) |
| yuzhno-sahalinsk.xn----7sbbk0auidbf2b5a.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| mail.xn--80adx0bza.xn--80aphgvco4b.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| xn--174-mdd9c4b.xn--p1ai | notracking_tracker | punycode TLD (.рф) |
| autodiscover.xn--hxt814e | notracking_tracker | punycode TLD (.网店) |
| smtp.xn--b1aglfoddwe7c.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| xn--44-6kcpb8aqfhbduy.xn--p1ai | hagezi_tif | punycode TLD (.рф) |
| edevletyardim.xn--node | hagezi_tif | punycode TLD (.გე) |
| xn--80abdh8aeoadtg.xn--p1ai | pyenb_blocklist | punycode TLD (.рф) |
| xn--80aa3ac1aekp.xn--p1ai | oisd_big | punycode TLD (.рф) |

Other Phase 2 behavior changes (no delta in this dataset, covered by tests):
multi-hostname hosts lines now contribute every hostname (truncated at inline
comments); wildcard entries (`*.example.com`) are counted as `parse_wildcard` and
remain excluded; underscore limitation documented in README.
