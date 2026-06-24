---
task: 260624-jmc
type: quick
subsystem: parse
tags: [parser, hosts-format, sanitization, bugfix]
commit: 8c59ebe
key-files:
  modified:
    - src/blocklist_builder/parse.py
    - tests/test_parse.py
    - tests/test_parallel_extra.py
    - README.md
completed: 2026-06-24
---

# Quick Task 260624-jmc: Strip glued host-IP prefixes from domain-only tokens Summary

Repaired no-delimiter sink-IP-glued hosts lines (`0.0.0.0kryptonchain.org` -> `kryptonchain.org`) inside the domain-only parser, while deliberately leaving genuine no-delimiter multi-FQDN concatenations untouched as a documented, accepted limitation.

## What changed

- **`src/blocklist_builder/parse.py`**
  - Added module constant `_GLUED_HOST_IP_RE` matching `0.0.0.0` / `127.0.0.1` / `255.255.255.255` at line start, with a `(?=[a-z0-9])` lookahead (compiled `re.ASCII`).
  - Added helper `_strip_glued_host_ip(token: str) -> str` that returns the token with a glued sink IP removed (no-op when no glued IP is present).
  - `_try_parse_domain_only` now applies the strip before the `.` check. Behavior is identical for every token without a glued host-IP prefix (the `re.sub` is a no-op then).
- **`tests/test_parse.py`** — added 6 `classify_line` tests:
  - Glued IP recovery for all three sink IPs.
  - Bare `0.0.0.0` NOT stripped (lookahead fails, stays a token; sanitize later rejects as IP).
  - `0.0.0.0.example.com` (dot after IP) NOT stripped.
  - Space-delimited hosts regression (`0.0.0.0 example.com`, `0.0.0.0 a.com b.com`).
  - Individual FQDNs (`metrics.apple.com`, `init.itunes.apple.com`, `js.moatads.com`) classify ok.
  - **KNOWN-LIMITATION pin**: `init.itunes.apple.comjs.moatads.com` (no delimiter, no host IP) is STILL returned as a single `("init.itunes.apple.comjs.moatads.com",), "ok"` token, with a comment documenting it as an accepted limitation.
- **`tests/test_parallel_extra.py`** — added 3 worker/file-level tests:
  - Two domains separated only by bare `\r` are both parsed (universal-newline regression lock).
  - File with no trailing newline still yields its last domain.
  - A glued `0.0.0.0kryptonchain.org` line in a file produces a valid `kryptonchain.org`.
- **`README.md`** — "Known limitations" now documents that no-delimiter multi-FQDN concatenations are passed through as-is (cosmetic, non-functional — Pi-hole never resolves them) and that host-IP-glued lines ARE repaired.

## Edge-case reasoning (verified)

- `0.0.0.0` alone: lookahead `(?=[a-z0-9])` fails (nothing follows the IP) -> no strip -> token `0.0.0.0` -> `classify_line` returns `(("0.0.0.0",), "ok")`; downstream `sanitize_domain` rejects it (`reason="ip"`).
- `0.0.0.0.example.com`: the `.` after the IP fails the lookahead -> no strip -> token unchanged.
- `kryptonchain.org` / `evil.example.com` after strip both `sanitize_domain` to `ok` (verified empirically).

## Gates (all passed)

| Gate | Command | Result |
| ---- | ------- | ------ |
| Tests + coverage | `PYTHONPATH=src uv run pytest --cov=blocklist_builder --cov-fail-under=99 -q` | 141 passed, **100.00%** coverage (parse.py 100%) |
| Lint | `uv run ruff check .` | All checks passed |
| Format | `uv run ruff format --check .` | 30 files already formatted |
| Types | `uv run mypy --strict src/blocklist_builder` | Success: no issues found in 15 source files |

No full build was run (no `.cache/` in the worktree). `dist/` and `.cache/` untouched.

## Deviations from Plan

None of substance. One mechanical adjustment: `ruff format` moved the new `_strip_glued_host_ip` helper above the `ReasonType` definition (formatter ordering of top-level defs) — semantically identical, format gate now clean.

## Self-Check: PASSED

- Commit `8c59ebe` exists in `git log`.
- All four modified files present and contain the changes.
- `git diff --diff-filter=D HEAD~1 HEAD`: no deletions.
- Only untracked file is `.planning/HANDOFF.json` (orchestrator artifact, intentionally not committed).
