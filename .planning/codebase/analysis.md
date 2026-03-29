# Codebase Analysis: pihole-blocklist-factory

**Analysis Date:** 2026-03-29
**Analyst:** Claude Sonnet 4.6

---

## Executive Summary

A well-structured Python CLI tool for building Pi-hole blocklists from multiple sources. Code quality is generally high: 99% test coverage, ruff linting passes clean, typed throughout, and Python 3.11+ idioms used correctly. The main concerns are architectural (dead code, unimplemented features presented as features, stats semantics), one logic bug in the quality analyzer, and infrastructure issues in the CI/CD workflows.

---

## 1. Architecture and Design Quality

**Pattern:** Pipeline architecture — fetch → parse → sanitize → classify → write.

**Strengths:**
- Clean module separation: each concern in its own file
- Immutable dataclasses with `frozen=True, slots=True` throughout
- Parallel processing at two levels (HTTP fetch via ThreadPoolExecutor, domain processing via ProcessPoolExecutor)
- Graceful fallback to sequential on worker failures

**Weaknesses:**
- Redundant fetch step in `build.py` (see §2)
- Profile filtering for `include_sources`/`exclude_sources` is silently dropped (see §2)
- `parallel_parse_and_sanitize` is a dead code path in production (see §2)

---

## 2. Code Quality Issues

### [HIGH] Dead Function: `parallel_parse_and_sanitize` never called in production

`src/blocklist_builder/parallel.py:138` — `parallel_parse_and_sanitize()` is defined and tested, but never imported or called from any production code path. The build pipeline exclusively uses `parallel_process_all_sources()`. This creates confusion about the intended parallelism model and inflates tested-but-unused surface area.

**Impact:** ~50 lines of code + ~10 test cases are testing a function the system never uses.
**Fix:** Remove the function and its tests, or wire it into the build pipeline if intended.

### [HIGH] Double-fetch: `parallel_fetch_sources` result is discarded

`src/blocklist_builder/build.py:261-265` — `parallel_fetch_sources()` is called and its return value assigned to `_` (explicitly discarded). Then `_collect_domains()` → `_resolve_all_source_paths()` → `_resolve_source_path()` calls `fetch_to_cache()` again for every HTTP source. Every HTTP source is downloaded twice per build.

```python
# build.py:261
_ = parallel_fetch_sources(...)   # fetches all sources, discards result
# then:
domain_to_categories, domain_to_sources = _collect_domains(...)  # fetches again
```

**Impact:** Doubles network I/O and time for HTTP sources. For a 3.2M-domain build pulling from 20+ sources, this is significant.
**Fix:** Use the returned `dict[str, Path]` from `parallel_fetch_sources()` and pass it directly to `_collect_domains()`, skipping `_resolve_all_source_paths()` for already-fetched sources.

### [HIGH] Unimplemented Profile Features Silently Ignored

`src/blocklist_builder/types.py:52-53` and `src/blocklist_builder/build.py:118-128` — `Profile.include_sources` and `Profile.exclude_sources` are parsed from config (YAML support, dataclass fields) but never read anywhere in the build pipeline. `_write_profiles()` only checks `include_categories`.

Similarly, `Profile.strict` (used in `policies.yml` to describe which profiles can block telemetry) is never read in `build.py`. A `strict=false` profile currently receives the same domains as `strict=true`.

And `Policies.sensitive_domains` (`src/blocklist_builder/config.py:30`) is parsed and stored but never used anywhere in the codebase.

**Impact:** Users reading `profiles.yml` or the README who configure `include_sources`, `exclude_sources`, or expect `strict` to mean something will get unexpected behavior with no warning.
**Fix:** Either implement these features or remove them from the types, config parsing, and YAML schema.

### [MEDIUM] Stats Semantics Bug: `total_lines` double-counts domains

`src/blocklist_builder/build.py:315` — `total_lines = sum(discarded.values())` where `discarded` is a `Counter` that includes both `parse_ok` and `sanitize_ok` keys alongside actual discard reasons. A domain that parses and sanitizes successfully is counted twice (once in `parse_ok`, once in `sanitize_ok`), and it is also counted by the discard reasons.

From the actual build output (`dist/reports/stats.json`):
```json
{
  "total_lines": 9173670,   <- misleadingly large
  "parse_ok": 4577697,
  "sanitize_ok": 4575447   <- same ~4.5M domains counted again
}
```

The actual input line count is ~4.5M, but `total_lines` reports 9.1M. The `discarded` dict in `Stats` also contains `parse_ok` and `sanitize_ok` keys, semantically conflating "successful" with "discarded".

**Impact:** Misleading stats in reports and CLI output.
**Fix:** Separate the "ok" counters from the "discard" Counter, and compute `total_lines` as `sum of all source 'lines' stats`.

### [MEDIUM] `_compute_discard_findings` in analyze.py is always a no-op

`src/blocklist_builder/analyze.py:37-60` — This function builds `source_stats` by only incrementing `sanitized_ok` (counting domains per source from provenance). The `discarded` key in each source's stats is initialized to 0 and never incremented. Therefore `discard_rate` is always 0.0, the `high_discard_threshold` check never fires, and `findings` is always `[]`.

This means the `analyze` CLI command never produces actual discard-rate findings regardless of source quality.

**Impact:** The quality analysis report's most valuable feature (identifying low-quality sources) is broken.
**Fix:** Load `source_stats.json` (which does contain actual parse/sanitize counts per source) and compute discard rates from that, rather than reconstructing from provenance.

### [LOW] Stale root-level scripts committed

`/home/malpanez/repos/pihole-blocklist-factory/create_test_data.py` and `run_build.py` exist in the repo root but are not tracked by git (confirmed via `git ls-files`). They reference `parallel_parse_and_sanitize` and other patterns from an older design. If they were to be committed accidentally they would cause confusion.

**Fix:** Add to `.gitignore` or delete.

### [LOW] YAML generation in firebog.py uses manual string building

`src/blocklist_builder/firebog.py:114-130` — YAML is constructed by hand-joining strings rather than using `yaml.dump()`. If a source name or URL contains YAML special characters (`"`, `:`, `#`, etc.), the generated file will be malformed.

Example: a title like `Test: "ads"` would produce `name: "Test: "ads""` which is invalid YAML.

**Fix:** Use `yaml.dump()` or at minimum apply proper YAML string escaping.

### [LOW] `pyproject.toml` author placeholder not updated

`pyproject.toml:8` — `authors = [{name = "Your Name"}]`. Minor but indicates the project wasn't fully initialized.

---

## 3. Security Concerns

### [MEDIUM] Inconsistent path traversal protection across code paths

`src/blocklist_builder/build.py:67-70` — `_resolve_source_path()` checks for `..` in resolved path parts for `file://` URLs:

```python
if ".." in file_path.parts:
    logging.warning("Rejected file:// URL with path traversal: %s", url)
    return None
```

However, `src/blocklist_builder/parallel.py:76` (`_resolve_local_sources()`) and `src/blocklist_builder/fetch.py:101-103` (`fetch_to_cache()`) both handle `file://` URLs without any path traversal check:

```python
# parallel.py:76 - no traversal check
src_path = Path(url.removeprefix("file://")) if url.startswith("file://") else Path(url)

# fetch.py:101-103 - no traversal check
case url if url.startswith("file://"):
    src = Path(url.removeprefix("file://"))
    content = src.read_text(...)
```

Since `fetch_to_cache` is called from the `_resolve_source_path` non-`file://` branch, this only matters for the `parallel.py` path (used in `no_fetch` mode). A malicious `sources.yml` entry with `url: "file://../../../etc/passwd"` in no-fetch mode would read the file unimpeded.

**Fix:** Apply the same traversal check consistently in `fetch_to_cache()` and `_resolve_local_sources()`.

### [LOW] No SSL certificate pinning or HTTPS validation override protection

`src/blocklist_builder/fetch.py:67` — `requests.get()` uses default SSL verification (correct) but there is no mechanism to enforce HTTPS for remote sources. A `sources.yml` entry using `http://` would fetch over plaintext. The blocklist content could be MITM'd.

**Impact:** Low in practice (blocklist content is not secret), but a MITM could inject malicious domains into the allowlist file.
**Fix:** Warn or reject `http://` source URLs at config load time.

### [LOW] `_compute_hash` caches full content strings in memory (unbounded)

`src/blocklist_builder/fetch.py:28-31` — `@cache` on `_compute_hash(content: str)` means every fetched source's full text is retained in the cache for the process lifetime. For the actual build (9M+ lines total), this holds ~500MB+ of source text in memory beyond what's needed.

**Impact:** Memory pressure on constrained build environments. The `@cache` here provides negligible benefit (the function is only called once per source).
**Fix:** Remove the `@cache` decorator from `_compute_hash`.

---

## 4. Testing

### Coverage
- 99% line coverage (2 uncovered lines in `build.py:69-70` — the path traversal rejection branch)
- 98 tests across 16 test files
- All tests are unit tests; no integration or end-to-end tests against real sources

### Quality Observations

**Good:**
- ProcessPoolExecutor failure fallback paths are tested via monkeypatching
- CLI error paths (missing files, JSON errors, exception propagation) are well covered
- `test_build.py` validates the full pipeline with realistic multi-source fixture data

**Gaps:**

**[MEDIUM] No test for the path traversal security check**
`build.py:68-70` — The 2 uncovered lines are the path traversal rejection. There is no test that provides a `file://` URL with `..` components to confirm the security check functions. This should be the highest-priority coverage gap given it is a security path.

**[MEDIUM] `_compute_discard_findings` bug not caught by tests**
The existing test (`test_analyze.py:101-119`) monkeypatches `defaultdict` with pre-set `discarded: 2` values to force a finding. This masks the production bug where `discarded` is never incremented from actual data. The test passes precisely because it bypasses the broken logic.

**[LOW] No test for YAML injection in `firebog.py`**
No test verifies behavior when source titles/URLs contain YAML special characters. The `test_firebog.py` tests use only simple ASCII strings.

**[LOW] `parallel_parse_and_sanitize` extensively tested but never used**
11 tests in `test_parallel.py` and `test_parallel_extra.py` cover this dead function. These tests will never catch a regression in production behavior.

**[LOW] No test for HTTP→HTTPS downgrade or HTTP source warnings**
No tests validate behavior with insecure `http://` source URLs.

---

## 5. Performance

### [MEDIUM] Double-fetch of all HTTP sources (see §2)

Every HTTP source is downloaded twice per build: once via `parallel_fetch_sources()` (discarded) and once via `_resolve_source_path()` → `fetch_to_cache()`. For a build with 20 remote sources this doubles network time.

### [LOW] `provenance.json` grows to 570MB at 3.2M domains

`dist/reports/provenance.json` is 570MB for the current 3.2M-domain build. This is written during every build (`build.py:294`) and read back by both `analyze` and `recommend` commands. At this scale:
- JSON serialization/deserialization is slow (~seconds)
- The file is too large for reasonable git commit (though currently gitignored)
- The `recommend.py` iterates the full provenance dict O(sources × domains) which is O(n²) for computing `_compute_source_metrics`

**Impact:** With more sources, provenance grows unbounded and the O(n²) metrics computation in `recommend.py:38-50` becomes a bottleneck.

### [LOW] `@cache` on `_compute_hash` retains all source content in memory

As noted in §3, unbounded cache holding full source file text. For a 3M-domain build, this could retain hundreds of MB of source text past their useful lifetime.

---

## 6. Maintainability

### [MEDIUM] CI/CD: `update.yml` workflow is broken by design

`.github/workflows/update.yml:45` — The "Check for changes" step does `git diff --quiet dist/`. Since `dist/` is gitignored (`line 26` of `.gitignore`), `git diff` will never report changes in `dist/`. The update workflow will always report `has_changes=false` and never create a PR, regardless of whether blocklists changed.

**Fix:** Either remove `dist/` from `.gitignore` selectively, or change the update mechanism to compare against a committed artifact (e.g., hash file).

### [MEDIUM] CI/CD: `build-lists.yml` creates a new GitHub release on every run

`.github/workflows/build-lists.yml:51-63` — `tag_name: lists-${{ github.run_id }}` generates a unique release for every workflow execution. Scheduled weekly + monthly = 65+ releases/year, growing without bound with no retention policy.

**Fix:** Use a fixed tag like `latest` with `softprops/action-gh-release@v2`'s `make_latest: true` to overwrite, or implement a release rotation policy.

### [LOW] CI/CD: `update.yml` uses `astral-sh/setup-uv@v3` vs `@v5` in other workflows

`.github/workflows/update.yml:32` — Uses `astral-sh/setup-uv@v3` while `ci.yml` and `build-lists.yml` both use `@v5`. This may cause uv version differences between the CI test environment and the update environment.

### [LOW] `BLOCKLIST_SOURCES` env var is read at module import time

`src/blocklist_builder/config.py:21` — `_BLOCKLIST_SOURCES_MODE: Final = os.environ.get("BLOCKLIST_SOURCES", "sources")` is evaluated once at import time. Changing the env var at runtime (e.g., in tests without module reload) has no effect. The `test_config.py` works around this with `importlib.reload(config_mod)`, which is fragile.

**Fix:** Read the env var inside `load_settings()` rather than at module scope.

### [LOW] `pihole-adlists-setup-v6.sh` is a placeholder stub

`scripts/pihole-adlists-setup-v6.sh` contains only an echo statement. This file serves no function and could mislead users who find it.

---

## 7. Missing Features / Obvious Gaps

### [HIGH] HTTP conditional fetching (ETag/If-Modified-Since) not implemented

`src/blocklist_builder/fetch.py:53-54` — `SourceMetadata` has `etag` and `last_modified` fields, and they are serialized to JSON metadata files, but they are always set to `None`. `_fetch_http()` sends no conditional request headers. Every build re-downloads every source fully regardless of whether the upstream has changed.

**Impact:** Significant unnecessary bandwidth and latency for weekly/monthly builds. Most blocklist providers support ETags or Last-Modified.
**Fix:** Load existing metadata, include `If-None-Match`/`If-Modified-Since` headers if available, handle HTTP 304 by reading from cache.

### [MEDIUM] Profile `include_sources`/`exclude_sources` is not implemented (see §2)

Profile-level source filtering is documented in `profiles.yml`, parsed into `Profile` objects, but the build pipeline ignores these fields entirely. Per-device profiles (android, ios, windows, macos) in `config/profiles.yml` all produce identical output since they only differ in `include_categories` which is implemented.

### [MEDIUM] `sync-github-catalog` command is a stub

`src/blocklist_builder/cli.py:122-128` — The `sync-github-catalog` command prints help text and exits. This is a visible but unimplemented feature accessible from the CLI.

### [LOW] No Pi-hole v6 API integration for automated list loading

The tool generates lists but has no automation for loading them into Pi-hole via the Pi-hole v6 API. `scripts/pihole-adlists-setup-v6.sh` is a placeholder. Users must manually copy URLs.

### [LOW] Domain regex accepts numeric-only TLDs

`src/blocklist_builder/sanitize.py:9-12` — `_DOMAIN_RE` uses `[a-z0-9-]{2,63}$` for the TLD segment, which accepts `foo.123`. All real IANA TLDs are alphabetic. This allows a small class of invalid domains through.

---

## Quick Reference: Issues by Severity

| Severity | Count | Key Issues |
|----------|-------|-----------|
| **Critical** | 0 | — |
| **High** | 4 | Dead `parallel_parse_and_sanitize`, double-fetch, silent unimplemented profile features, stats double-counting |
| **Medium** | 7 | `_compute_discard_findings` always no-op, path traversal inconsistency, update.yml broken by gitignore, unbounded release accumulation, no HTTP conditional fetch, sync-github-catalog stub, O(n²) provenance scan |
| **Low** | 11 | `create_test_data.py`/`run_build.py` untracked, YAML injection in firebog.py, `_compute_hash` unbounded cache, no path traversal test, setup-uv version inconsistency, module-level env var, numeric TLD regex, stub shell script, dead test coverage, no HTTP→HTTPS enforcement, placeholder author |

---

*Analysis: 2026-03-29*
