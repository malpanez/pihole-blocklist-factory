---
phase: quick-261030-hnt
plan: 01
subsystem: blocklist-builder
tags: [sources, json-source, gate, workflow]
requires: []
provides:
  - json_key source support (MetaMask blacklist array)
  - blocklist-factory gate command and gate module
  - corrected source set and household canary file
affects: [build, cli, forgejo-workflow]
key-files:
  created:
    - src/blocklist_builder/gate.py
    - inputs/current_overrides/must_not_block.txt
    - tests/test_gate.py
    - tests/test_sources_config.py
  modified:
    - src/blocklist_builder/types.py
    - src/blocklist_builder/config.py
    - src/blocklist_builder/parallel.py
    - src/blocklist_builder/build.py
    - src/blocklist_builder/cli.py
    - config/sources.yml
    - .forgejo/workflows/build-lists.yml
    - tests/test_parallel_extra.py
    - tests/test_config.py
    - tests/test_build.py
    - CLI_GUIDE.md
    - CHANGELOG.md
metrics:
  completed: 2026-10-30
  tests: 219 passed
  coverage: 100%
---

# Quick 261030-hnt: Blocklist source review, JSON sources and publish gate

Fixed the source set (HaGeZi wildcard URLs, 7 dead or redundant sources and 5 Firebog ids disabled, urlhaus_filter and metamask_phishing added), added `json_key` JSON sources, and added a `gate` command plus workflow steps that stop a bad list from replacing the published release. All changes are uncommitted in the main tree.

## What was done

- `Source.json_key` read from YAML (default None). The worker args tuple gained a fourth element; all 4 call sites in `parallel_process_all_sources` pass `keys.get(src_id)`. The text path and JSON path share `_process_lines`.
- A malformed JSON file, non-object top level, missing key, non-list value, empty or all-non-string array, unreadable file or `RecursionError` returns `[]` with `source_missing: 1`, logs one warning naming file and key, and does not crash. `SOURCE_MISSING_REASON` is defined in parallel.py and imported by build.py.
- `gate.py` (no printing, no exit): `blocking_entry`, `check_must_not_block`, `check_drop`, `run_gate`, `GateResult`. Missing or invalid stats.json, missing or empty all.txt, and a missing or empty canary file fail closed. `cli.gate_cmd` raises `SystemExit(1)`; tests assert on `cli.main` return value and on `CliRunner`.
- Workflow: `allow_drop` dispatch input, "Fetch previous release" (curl `--fail`, `.part` then rename), "Gate" (input via `env:`), "Alert on failure" (ntfy, high priority, run URL by `github.run_number`). Stage step untouched.
- `config/sources.firebog.yml` and `pyproject.toml` unchanged; no new dependency.

## Verification (observed)

- `pytest --cov-fail-under=99`: 221 passed (baseline 141), coverage 100%, gate.py 100%.
- `ruff check --no-fix .` clean, `ruff format --check .` clean, `mypy --strict src/blocklist_builder` clean, `blocklist-factory validate` ok (48 sources, rerun after the driver follow-ups), `blocklist-factory gate --help` ok.
- shellcheck `-s sh` clean on the 3 new `run:` blocks (`${{ }}` replaced by placeholders in a scratch copy, removed).
- Real build: exit 0, 3:06.78 wall, max RSS 1,980,236 KB (1.9 GiB). 2,513,302 unique domains, `source_missing` absent (0).
- Real gate against the published list (1,313,585 domains): exit 0, `domains=2513302 previous=1313585 delta=+91.33%`.
- Negative proofs through the installed console script: canary child-of-listed-entry exit 1 naming both; 15% padded previous exit 1 (`list shrank from 2890297 to 2513302 domains (13.0% drop, limit 10.0%)`); same with `--allow-drop` exit 0 printing the skip note; empty `--dist` exit 1 with two failures.
- Not verified: the workflow itself (not dispatched, by instruction), the ntfy alert, and a Forgejo run of the gate.

## Deviations from Plan

None to code behavior. Two facts in `verified_at_planning` turned out wrong at source, reported below as findings.

### Assumption Drift (advisory)

1. **urlhaus_filter is mostly IPs.** Planned: "18,009 domains, 0 star lines". Actual: 18,015 lines, 16,142 rejected as `sanitize_ip`, 1,867 domains contribute. Why: the filter lists hosts of malware URLs, most of which are bare IPs. Cost if wrong: the source contributes about 10% of what the plan implied; still non-zero and correct.
2. **MetaMask discard count.** Planned gap 1,107 (114,053 raw vs 112,946). Actual: 114,054 lines, 112,845 sanitized, 1,209 discarded (1,143 `not_fqdn` path entries, 35 `ip`, 31 `invalid`). The upstream file moved slightly; behavior is as designed. `sites.google.com` is not in dist/all.txt.

## Driver follow-ups (applied after review)

1. `urlhaus_filter` notes (and CHANGELOG) now say it yields about 1.9k domains because most of the file is bare IPs rejected by the sanitizer. The SUMMARY's Assumption Drift entry already carried the measured numbers.
2. Disabled the two zero-contribution sources with a one-line reason each: `openphish` (full-URL feed, every line rejected, hosts from URL feeds unsafe to block whole) and `firebog_malicious_5_quidsup_malicious` (id override in the Firebog overrides block, id/name/url/category copied from `sources.firebog.yml`; 125 of 136 lines `parse_unsupported`). Both added to `DISABLED_IDS` in `tests/test_sources_config.py`; the Firebog override check now derives its ids from the `firebog_` prefix. CHANGELOG updated. No parsing code changed, so no rebuild was done.
3. `.pre-commit-config.yaml`: ruff-pre-commit `rev` v0.9.21 (does not exist upstream) changed to `v0.14.14`, matching `ruff 0.14.14` locked in uv.lock; `git ls-remote --tags` confirms the tag. `pre-commit run --files` over the 17 changed and new files (not uv.lock, .vscode or .planning): `ruff (legacy alias)` Passed, `ruff format` Passed. These are the only two hooks configured. No hook modified any file (`git status --short` identical before and after).

## Findings (pre-existing, not touched)

- `openphish` and `firebog_malicious_5_quidsup_malicious` contributed 0 domains in the build; both are now disabled (see follow-ups).
- `dist/reports/provenance.json` (570 MB, Feb 2026) predates this work and was left in place.
- dist/ went from 1.4G to 733M across the build; not investigated.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model.

## Self-Check: PASSED

Created files exist (gate.py, must_not_block.txt, test_gate.py, test_sources_config.py, this summary); nothing staged (`git diff --cached --stat` empty); no commits made, per the owner's rule.
