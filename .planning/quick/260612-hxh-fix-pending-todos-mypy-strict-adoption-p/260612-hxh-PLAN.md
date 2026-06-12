# Quick Task 260612-hxh: Fix pending todos (mypy strict + profile dedup)

Two pending todos, one atomic commit each, in order. Source todos:
- `.planning/todos/pending/2026-06-12-adopt-mypy-strict-fix-errors-add-dep-ci-gate.md`
- `.planning/todos/pending/2026-06-12-phase-3-profile-redundancy-symlinks-or-manifest-until-profil.md`

## Task 1 — Adopt mypy strict (commit: `chore(types): adopt mypy --strict with CI gate`)

Order matters:
1. Add `mypy` plus needed stubs (`types-PyYAML`, `types-requests`) to `[dependency-groups]` dev in pyproject.toml (NO runtime deps). Add a `[tool.mypy]` section: `strict = true`, `files = ["src/blocklist_builder"]`, python_version 3.11.
2. Run `uv sync` then `PYTHONPATH=src uv run mypy --strict src/blocklist_builder`. NOTE: the recorded "56 errors" came from `uvx mypy` (isolated env, deps invisible); the real count with deps installed will differ — fix whatever the in-env run reports, down to **0 errors**. Typical fixes expected: click decorator typing, `dict`/`Any` returns in analyze/recommend/firebog, untyped json loads, Counter/defaultdict annotations in build.py, fetch.py header dicts.
3. Behavior must not change: no logic edits beyond what typing requires (e.g. narrowing, explicit casts, TypedDicts/dataclasses where cheap). dist/ output format untouched.
4. Add a blocking step to .github/workflows/ci.yml after Lint: `uv run mypy --strict src/blocklist_builder` (uv sync already installs the dev group).
5. Gates before commit: `PYTHONPATH=src uv run pytest --cov=blocklist_builder --cov-fail-under=99` (coverage stays ≥99; currently 100%), `uv run ruff check . && uv run ruff format --check .`, `uv run mypy --strict src/blocklist_builder` → 0 errors. Commit pyproject.toml, uv.lock, ci.yml, and source changes.

## Task 2 — Deduplicate byte-identical profile outputs (commit: `feat(build): dedup identical profile outputs via symlinks + manifest`)

Context: six profiles (base, aggressive, android, ios, macos, windows) are byte-identical 4.8M-line files (~67 MB each) because no per-device divergence exists yet; `security` differs. Published profile URLs must keep working.

1. In `_write_profiles` (src/blocklist_builder/build.py): group profiles by content (hash of the selected domain list, computed without materializing extra copies). Write the first profile of each group as a real file; for the others create **relative symlinks** to that canonical file (`Path.symlink_to`). Remove any pre-existing regular file/symlink at the target first (idempotent rebuilds; current dist/ has real files from past builds).
2. Write `dist/profiles/manifest.json`: `{profile: {"canonical": "<name>.txt", "sha256": "...", "lines": N}}` for every profile.
3. Release safety: `softprops/action-gh-release` follows symlinks when uploading, so asset names/URLs are unchanged. Do not modify build-lists.yml beyond (optionally) adding manifest.json to the release files list.
4. Tests: new tests asserting (a) identical-content profiles become symlinks resolving to the canonical file with identical content, (b) differing profiles stay regular files, (c) manifest.json structure. Keep coverage ≥99%.
5. Gates before commit: pytest+cov, ruff check/format, mypy --strict (now blocking — new code must keep it at 0).

## Verification (after both tasks)

- `BLOCKLIST_SOURCES=test uv run blocklist-factory build --no-fetch` (or test sources) runs green end-to-end.
- Full gates one final time; report results.
