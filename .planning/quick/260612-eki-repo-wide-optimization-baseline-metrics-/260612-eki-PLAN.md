---
phase: quick-260612-eki
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/baseline.md
  - src/blocklist_builder/build.py
  - src/blocklist_builder/parallel.py
  - src/blocklist_builder/parse.py
  - src/blocklist_builder/sanitize.py
  - src/blocklist_builder/classify.py
  - src/blocklist_builder/analyze.py
  - src/blocklist_builder/recommend.py
  - src/blocklist_builder/fetch.py
  - src/blocklist_builder/firebog.py
  - pyproject.toml
  - .github/workflows/ci.yml
  - .github/workflows/build-lists.yml
  - .github/workflows/update.yml
  - README.md
  - tests/test_build.py
  - tests/test_build_internal.py
  - tests/test_parallel_extra.py
  - tests/test_parse.py
  - tests/test_sanitize.py
  - tests/test_classify.py
  - tests/test_analyze.py
  - tests/test_recommend.py
  - tests/test_fetch.py
  - tests/test_fetch_http.py
  - tests/test_firebog.py
autonomous: true
requirements: [QUICK-OPT-P0, QUICK-OPT-P1, QUICK-OPT-P2, QUICK-OPT-P3]

must_haves:
  truths:
    - "docs/baseline.md records pre-change domain counts, peak RSS, wall time, and sha256 of dist/all.txt"
    - "After Phase 1, dist/all.txt sha256 is byte-identical to baseline"
    - "After Phase 2, added domains vs baseline are explainable as IDN punycode TLDs or extra hostnames from multi-host lines"
    - "Downloads larger than 64MB are aborted; 4xx HTTP errors are not retried; non-https Firebog entries are skipped"
    - "All GitHub Actions are pinned to full commit SHAs; update.yml is deleted; coverage gate --cov-fail-under=99 enforced in CI"
  artifacts:
    - path: "docs/baseline.md"
      provides: "Baseline + per-phase comparison metrics"
    - path: "dist/reports/provenance.jsonl.gz"
      provides: "Streamed gzipped JSONL provenance (replaces provenance.json)"
    - path: "docs/archive/"
      provides: "Archived one-off optimization markdown files"
  key_links:
    - from: "src/blocklist_builder/build.py"
      to: "parallel.parallel_fetch_sources"
      via: "fetch path in _resolve_all_source_paths"
      pattern: "parallel_fetch_sources"
    - from: "src/blocklist_builder/analyze.py"
      to: "dist/reports/ aggregates file"
      via: "build-time overlap/marginal aggregates (no full provenance load)"
      pattern: "aggregates"
---

<objective>
Repo-wide optimization in 4 sequential phases, each an atomic commit: (0) baseline metrics, (1) behavior-preserving perf/memory work with byte-identical dist/all.txt, (2) parsing correctness changes with justified output deltas, (3) security hardening + CI cleanup.

Purpose: Cut peak RSS and wall time (3.2M provenance dataclasses + 545MB JSON loads today), fix parser correctness gaps, and harden fetch/CI — without breaking the stable dist/ contract (all.txt, categories/, profiles/ unchanged; provenance format change explicitly approved).
Output: docs/baseline.md with before/after metrics, 4 conventional commits, all quality gates green after each.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.claude/CLAUDE.md
@src/blocklist_builder/build.py
@src/blocklist_builder/parallel.py
@src/blocklist_builder/parse.py
@src/blocklist_builder/sanitize.py
@src/blocklist_builder/fetch.py
@src/blocklist_builder/classify.py
@src/blocklist_builder/analyze.py
@src/blocklist_builder/recommend.py
@src/blocklist_builder/firebog.py
@pyproject.toml

Executor notes:
- Task 1 needs network and a full fetch build — may take several minutes. Tasks 2-3 rebuild with `--no-fetch` against the `.cache/sources/` populated in Task 1.
- Quality gates after EVERY task, before its commit: `PYTHONPATH=src uv run pytest --cov=blocklist_builder` (coverage ≥99%), `uv run ruff check . && uv run ruff format --check .`, and `uvx mypy --strict src/blocklist_builder` (mypy is NOT a project dep — run ad-hoc, REPORT results; pre-existing strict errors are not blockers, but new code must not add errors).
- Conventional commits, NO Co-Authored-By trailer. Never push without confirmation.
- Constraints: Python 3.11+, stdlib only, NO new runtime dependencies. dist/ output format stable except provenance.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Phase 0 — capture baseline metrics</name>
  <files>docs/baseline.md</files>
  <action>
Run a full fetch build and capture baseline metrics BEFORE any code change:

1. `/usr/bin/time -v uv run blocklist-factory build 2> /tmp/baseline-time.txt` (network required; several minutes). If the CLI exposes per-stage timing in logs/output, capture it; do NOT modify code to obtain per-stage timings — overall wall time alone is acceptable.
2. Capture: total domain count (`wc -l dist/all.txt`), per-profile counts (`wc -l dist/profiles/*.txt`), per-category counts (`wc -l dist/categories/*.txt`), peak RSS ("Maximum resident set size" from /tmp/baseline-time.txt), wall time ("Elapsed (wall clock) time"), `sha256sum dist/all.txt`.
3. Write all of it to `docs/baseline.md` with a "## Baseline (pre-optimization)" section: date, command used, counts table, peak RSS, wall time, sha256. Leave placeholder sections "## Phase 1 comparison" and "## Phase 2 comparison" to be appended later.
4. Run quality gates (no code changed — they must pass as-is; report mypy strict pre-existing error count as the mypy baseline for later tasks).
5. Commit ONLY docs/baseline.md: `docs(baseline): capture pre-optimization build metrics`.
  </action>
  <verify>
    <automated>test -f docs/baseline.md && grep -q "sha256" docs/baseline.md && git log -1 --format=%s | grep -q "docs(baseline)"</automated>
  </verify>
  <done>docs/baseline.md committed with domain counts, peak RSS, wall time, and sha256 of dist/all.txt; .cache/sources/ populated for later --no-fetch builds.</done>
</task>

<task type="auto">
  <name>Task 2: Phase 1 — behavior-preserving perf/memory optimization</name>
  <files>src/blocklist_builder/build.py, src/blocklist_builder/parallel.py, src/blocklist_builder/parse.py, src/blocklist_builder/sanitize.py, src/blocklist_builder/classify.py, src/blocklist_builder/analyze.py, src/blocklist_builder/recommend.py, docs/baseline.md, tests/test_build.py, tests/test_build_internal.py, tests/test_parallel_extra.py, tests/test_parse.py, tests/test_sanitize.py, tests/test_classify.py, tests/test_analyze.py, tests/test_recommend.py</files>
  <action>
HARD CONSTRAINT: dist/all.txt must be byte-identical to baseline (same sha256). Provenance format change is approved. Implement:

1. **Parallel fetch wiring** (build.py:86-109): replace the sequential per-source `fetch_to_cache` loop in `_resolve_all_source_paths` with `parallel_fetch_sources` (parallel.py:86). Preserve accounting: enabled sources that fail to resolve (absent from result or mapped to None — note parallel_fetch_sources stores None on fetch failure) must still increment `discarded["source_missing"]` and `source_stats[src.id]["source_missing"]` exactly as today (build.py:106-108). Preserve the http:// insecurity warning currently in `_resolve_source_path` (build.py:65-70) and the file:// traversal rejection. Filter None values out of the returned dict.

2. **Dead code removal**: delete `_process_chunk_worker` (parallel.py:51-57) and `_get_abp_pattern` (parse.py:26-29) plus their now-unused imports (`ProcessPoolExecutor` stays — used by parallel_process_all_sources; `lru_cache` import in parse.py goes). Delete/update any tests referencing them (tests/test_parallel_extra.py, tests/test_parse.py).

3. **Provenance streaming** (replaces `_write_provenance` build.py:193-206 and `build_provenance` classify.py:32-67): do NOT materialize Provenance dataclasses (currently ~3.2M). Stream-write `dist/reports/provenance.jsonl.gz` directly from `domain_to_sources` + `partition` results: open `gzip.open(path, "wt", encoding="utf-8")`, write one JSON object per line per domain ({domain, source_ids sorted, categories sorted, assigned}) using a generator loop. In the SAME single pass, accumulate aggregates: total_unique, overlap_2 count, overlap_3_plus count, and per-source {total_contributions, unique_domains} (a domain with sset == {src_id} is unique to that source). Write aggregates to `dist/reports/provenance_aggregates.json` (small file). Remove `build_provenance` from classify.py and the `Provenance` type usage if now dead (check types.py; keep it only if still referenced). Stop writing `provenance.json`.

4. **analyze.py / recommend.py off full provenance**: analyze.py `_load_provenance_and_stats` (analyze.py:11-33) and `_compute_overlap_findings` (analyze.py:66-88) must read `provenance_aggregates.json` instead of json.loads on the 545MB provenance.json; total_unique comes from aggregates. recommend.py `_load_provenance_and_marginal` (recommend.py:12-29) and `_compute_source_metrics` (recommend.py:32-67) likewise read per-source aggregates — this also fixes the O(sources × domains) scan: metrics are now a single dict lookup per source. Keep `marginal.json` fallback semantics. Error messages referencing provenance.json should reference the new files. Update tests/test_analyze.py and tests/test_recommend.py fixtures to write aggregates files.

5. **Remove @cache from sanitize.py** `_is_ipv4` (sanitize.py:31-34) and `_validate_domain_regex` (sanitize.py:45-48) — regexes are precompiled; caches grow unbounded over ~unique domains. Either inline the fullmatch calls or keep the functions uncached.

6. **Line-by-line workers**: `_process_source_file_worker` (parallel.py:144) replaces `Path.read_text(...).splitlines()` with `with open(path, encoding="utf-8", errors="ignore") as f:` iterating the file object; count lines during iteration for stats["lines"]. Counter-based parse path: refactor `_process_chunk_local` (parallel.py:26-48) to tally counters without creating one ParsedLine per line — extract the per-line classification from `parse_lines` into a helper returning (domain | None, reason) tuples, or have _process_chunk_local call the `_try_parse_*` helpers directly. Keep `parse_lines` public and behavior-identical for its existing tests.

7. **Generator writes**: replace `"\n".join(list)` on multi-million-element lists with `writelines()` over a generator in: all.txt (build.py:298-300), `_write_categories` (build.py:119-121), `_write_profiles` (build.py:132-134), `_write_allowlist` (build.py:352-353). Pattern: open file, writelines(f"{d}\n" for d in sorted_domains). Preserve exact byte output incl. trailing newline semantics (current code: trailing newline only when non-empty; allowlist has header lines).

8. **Single-pass `_write_marginal`** (build.py:220-245): currently O(sources × domains) — one full domain_to_sources scan per source. Replace with one pass building a Counter of src_id for domains whose source set has exactly one element; initialize all source_map keys to 0 so output keys are unchanged. (If the per-source unique counts from step 3's aggregates are available at this call site, reuse them instead of re-scanning.) recommend.py `_compute_source_metrics` single-pass fix is covered by step 4.

VERIFY before commit: `uv run blocklist-factory build --no-fetch` (uses Task 1 cache) → `sha256sum dist/all.txt` MUST equal baseline sha256 from docs/baseline.md. If it differs, debug until identical — do not commit. Re-run `/usr/bin/time -v uv run blocklist-factory build --no-fetch` and append "## Phase 1 comparison" to docs/baseline.md (new peak RSS, wall time, sha256 match confirmation; note baseline used full fetch so compare wall time qualitatively, RSS directly). Run quality gates. Commit: `perf(build): parallel fetch, streaming provenance, generator writes`.
  </action>
  <verify>
    <automated>uv run blocklist-factory build --no-fetch && sha256sum dist/all.txt && grep -q "Phase 1 comparison" docs/baseline.md && PYTHONPATH=src uv run pytest --cov=blocklist_builder -q</automated>
  </verify>
  <done>dist/all.txt sha256 matches baseline byte-for-byte; provenance.jsonl.gz + provenance_aggregates.json written; analyze/recommend work without loading full provenance; dead code gone; coverage ≥99%, ruff clean; Phase 1 metrics appended to docs/baseline.md; single commit.</done>
</task>

<task type="auto">
  <name>Task 3: Phase 2 — parsing correctness changes (justified output deltas)</name>
  <files>src/blocklist_builder/sanitize.py, src/blocklist_builder/parse.py, README.md, docs/baseline.md, tests/test_sanitize.py, tests/test_parse.py</files>
  <action>
Output WILL change; every delta must be justified and recorded.

1. **IDN fix** (sanitize.py:9-12): `_DOMAIN_RE` final label `[a-z]{2,63}` rejects punycode TLDs (e.g. xn--p1ai). Extend the pattern so the final label also accepts `xn--[a-z0-9-]+` (punycode), e.g. alternation `(xn--[a-z0-9-]{1,59}|[a-z]{2,63})` as the final label — keep the 253-char lookahead and ASCII flag. Note: `_apply_idna` already converts unicode to punycode, so this lets legitimately-encoded IDN TLDs through. Add tests: `xn--80ak6aa92e.com`-style domains and a punycode TLD domain (e.g. `пример.рф` → `xn--e1afmkfd.xn--p1ai`) now pass; numeric/hyphen-leading garbage TLDs still rejected (preserve Phase 07 decision rejecting numeric TLDs for non-punycode labels).

2. **Multi-hostname hosts lines** (parse.py:37-41): `_try_parse_hosts_format` returns only `parts[1]`; hosts files allow `0.0.0.0 a.com b.com c.com`. Change it to return `parts[1:]` (all hostnames) and adapt the caller in `parse_lines` (parse.py:92-99) — and the counter-based path from Task 2 — to emit one result per hostname on the line. Keep stats semantics sensible: each extracted hostname counts toward parse_ok individually (document the choice in the test). Update domain-only/ABP paths to remain single-domain.

3. **Wildcards** (`*.example.com`): do NOT map to base domain. Ensure they remain rejected; count them under a distinct counter if cheap (e.g. reason "wildcard" in the counter-based path when line/hostname starts with `*.`), otherwise leave them in the existing "unsupported" counter. Do not alter matching behavior.

4. **Underscores**: do NOT change matching. Add a "Known limitations" note to README.md stating domains containing underscores (technically invalid hostnames but seen in tracking lists) are rejected by the validator.

VERIFY before commit: save a copy of baseline all.txt first (`cp dist/all.txt /tmp/all-phase1.txt` BEFORE rebuilding), then `uv run blocklist-factory build --no-fetch`, then `comm -13 /tmp/all-phase1.txt dist/all.txt > /tmp/added.txt` (both files are sorted) and `comm -23` for removed (expected: none or explainable). Sample 20 added domains (`shuf -n 20 /tmp/added.txt` or head) and confirm each is plausible: punycode (xn--) labels or extra hostnames from multi-host lines (grep the cached source files in .cache/sources/ to confirm origin for the sample). Record added/removed delta counts and the 20-domain sample with justification in a "## Phase 2 comparison" section of docs/baseline.md. Run quality gates. Commit: `feat(parse): IDN punycode TLDs and multi-hostname hosts lines`.
  </action>
  <verify>
    <automated>uv run blocklist-factory build --no-fetch && grep -q "Phase 2 comparison" docs/baseline.md && grep -qi "underscore" README.md && PYTHONPATH=src uv run pytest --cov=blocklist_builder -q</automated>
  </verify>
  <done>Punycode TLD domains accepted; all hostnames on multi-host lines extracted; wildcards counted but unsupported; underscore limitation documented in README; delta counts + 20-domain justified sample in docs/baseline.md; coverage ≥99%; single commit.</done>
</task>

<task type="auto">
  <name>Task 4: Phase 3 — security hardening + CI cleanup</name>
  <files>src/blocklist_builder/fetch.py, src/blocklist_builder/firebog.py, src/blocklist_builder/build.py, pyproject.toml, .github/workflows/ci.yml, .github/workflows/build-lists.yml, .github/workflows/update.yml, tests/test_fetch.py, tests/test_fetch_http.py, tests/test_firebog.py, tests/test_build_internal.py</files>
  <action>
1. **Download cap 64MB** (fetch.py:59-80 `_fetch_http`): switch to `requests.get(..., stream=True)`. Reject when Content-Length header exceeds 64*1024*1024; also enforce while reading (`iter_content`) since Content-Length can be absent/lying — abort and raise a ValueError (or custom exception) once accumulated bytes exceed the cap. Decode accumulated bytes to text preserving current behavior (r.encoding/apparent fallback to utf-8 with errors ignored is acceptable; keep return contract (text, etag, last_modified)).

2. **Retry only transient errors** (fetch.py:69-79): currently any `requests.RequestException` is retried, including 4xx from `raise_for_status` (HTTPError is a RequestException subclass). Catch `requests.HTTPError` separately: if `e.response.status_code` is 4xx → raise immediately, no retry; 5xx → retry with backoff. `requests.ConnectionError`/`Timeout` (network) → retry. The 64MB-cap exception must NOT be retried.

3. **firebog https enforcement** (firebog.py:74 `sync_firebog` / `fetch_firebog_csv`): skip entries whose url does not start with `https://`, logging/printing a warning with the skipped url.

4. **Path containment**: local-path resolution must resolve under repo_root, reject otherwise.
   - build.py `_resolve_source_path` (build.py:60-83): for file:// and bare local-path cases, resolve and verify the result `is_relative_to(repo_root)`; reject (return None → counts as source_missing) otherwise. This requires passing repo_root down (build() at build.py:248 has it; thread through `_collect_domains` → `_resolve_all_source_paths` → `_resolve_source_path`, and the parallel no-fetch path `_resolve_local_sources` in parallel.py:69-83 if still in use after Task 2 wiring).
   - fetch.py `fetch_to_cache` local-path cases (fetch.py:108-116): same containment check; raise ValueError on escape. Add a repo_root (or allowed_base) parameter with the call sites updated; default behavior must fail closed for paths outside the base.
   - Add tests: file:// and bare path escaping repo_root rejected; contained path accepted.

5. **Pin GitHub Actions to full commit SHAs** (keep version as trailing comment, e.g. `uses: actions/checkout@<sha> # v4`): ci.yml lines 17, 20, 37 (actions/checkout, astral-sh/setup-uv, codecov/codecov-action); build-lists.yml lines 25, 28, 44, 51 (checkout, setup-uv, upload-artifact, softprops/action-gh-release). Resolve SHAs via `gh api repos/{owner}/{repo}/git/ref/tags/{tag}` (dereference annotated tags to commit SHA via `gh api repos/{owner}/{repo}/git/tags/{sha}` when the ref points to a tag object) or `git ls-remote https://github.com/{owner}/{repo} refs/tags/{tag}^{}`. Do not guess SHAs.

6. **firebog csv.reader** (firebog.py:41-53): replace the manual `split('","')` parsing with stdlib `csv.reader(io.StringIO(resp.text))`; keep the ≥5-fields and status=="tick" filters.

7. **pyproject.toml**: remove `[project.optional-dependencies].dev` (lines 15-21); merge needed dev deps into `[dependency-groups].dev` (lines 48-52) so it contains pytest, pytest-cov, pre-commit, ruff (keep the newer version floors already in dependency-groups where higher). Then fix workflows that rely on extras: ci.yml:25 and build-lists.yml:33 use `uv sync --all-extras` — change to `uv sync` (uv installs the dev dependency group by default), since there are no extras left.

8. **ci.yml coverage gate** (ci.yml:34): add `--cov-fail-under=99` to the pytest invocation.

9. **Delete .github/workflows/update.yml** — broken: dist/ is gitignored so its PR is always empty (build-lists.yml already handles scheduled builds via releases).

10. **Archive one-off docs**: `mkdir -p docs/archive && git mv FIXES_APPLIED.md VERIFICATION.md OPTIMIZATIONS_APPLIED.md OPTIMIZATION_CHECKLIST.md OPTIMIZATION_SUMMARY.md PYTHON_OPTIMIZATIONS.md QUICKSTART_PERF.md PERFORMANCE_TUNING.md IMPLEMENTATION_SUMMARY.md docs/archive/` (root IMPLEMENTATION_SUMMARY.md; docs/IMPLEMENTATION_SUMMARY.md stays where it is).

Add tests for new behavior: download cap (mock response with oversized Content-Length and oversized streamed body), 4xx-no-retry vs 5xx-retry, https enforcement skip, path containment. Validate workflows with `gh workflow list` syntax errors are not checkable offline — at minimum run a YAML parse (python -c with yaml.safe_load) on both workflow files. Run quality gates. Commit everything as one commit: `fix(security): download cap, retry policy, path containment; ci: pin actions, coverage gate`.
  </action>
  <verify>
    <automated>test ! -f .github/workflows/update.yml && grep -q "cov-fail-under=99" .github/workflows/ci.yml && ! grep -rn "uses: .*@v[0-9]" .github/workflows/ && test -d docs/archive && grep -q "import csv" src/blocklist_builder/firebog.py && PYTHONPATH=src uv run pytest --cov=blocklist_builder -q && uv run ruff check . && uv run ruff format --check .</automated>
  </verify>
  <done>64MB cap enforced (header + streamed); 4xx not retried; non-https firebog entries skipped; local paths confined to repo_root; all actions SHA-pinned with version comments; update.yml deleted; dev deps only in [dependency-groups]; CI coverage gate at 99; one-off docs in docs/archive/; coverage ≥99%; single commit.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HTTP fetch → parser | Remote blocklist content (untrusted) enters parse/sanitize pipeline |
| Firebog catalog → config | Remote CSV controls which URLs get fetched |
| Source URL config → filesystem | file:// and bare-path sources resolve to local file reads |
| CI supply chain | Third-party GitHub Actions run with repo write permissions |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-q01-01 | DoS | fetch.py _fetch_http | mitigate | 64MB cap via stream=True + Content-Length + streamed-byte enforcement (Task 4.1) |
| T-q01-02 | DoS | fetch.py retry loop | mitigate | No retry on 4xx; retry only network errors and 5xx (Task 4.2) |
| T-q01-03 | Tampering | firebog.py catalog URLs | mitigate | Enforce https:// on catalog entries, skip with warning (Task 4.3) |
| T-q01-04 | Information disclosure | build.py/fetch.py local path resolution | mitigate | Containment under repo_root, fail closed (Task 4.4) |
| T-q01-05 | Tampering | .github/workflows actions | mitigate | Pin all actions to full commit SHAs with version comments (Task 4.5) |
| T-q01-06 | DoS | sanitize.py unbounded @cache | mitigate | Remove @cache from _is_ipv4/_validate_domain_regex (Task 2.5) |
| T-q01-SC | Tampering | dependency installs | accept | No new dependencies introduced in this plan (stdlib only) |
</threat_model>

<verification>
- After Task 2: `sha256sum dist/all.txt` identical to the baseline value in docs/baseline.md (hard gate — byte-identical).
- After Task 3: added-domain delta documented and sampled (20 domains traced to punycode or multi-host origins).
- After every task: pytest coverage ≥99%, ruff check + format clean, `uvx mypy --strict src/blocklist_builder` reported (no NEW errors vs the baseline count recorded in Task 1).
- Four commits total, one per task, conventional format, no Co-Authored-By trailer, no push.
</verification>

<success_criteria>
- docs/baseline.md contains baseline + Phase 1 + Phase 2 comparison sections with RSS/wall-time/sha256/delta data.
- Phase 1 commit: dist/all.txt byte-identical; provenance streamed as provenance.jsonl.gz; analyze/recommend consume small aggregates file; dead code removed; generator-based writers; single-pass marginal.
- Phase 2 commit: punycode TLDs accepted, multi-hostname lines fully parsed, wildcards counted-not-mapped, underscore limitation in README.
- Phase 3 commit: download cap, retry policy, https enforcement, path containment, SHA-pinned actions, coverage gate, update.yml deleted, docs archived, pyproject dev deps consolidated.
- All quality gates green after each of the 4 commits.
</success_criteria>

<output>
Create `.planning/quick/260612-eki-repo-wide-optimization-baseline-metrics-/260612-eki-SUMMARY.md` when done.
</output>
