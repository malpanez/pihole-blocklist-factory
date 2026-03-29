# Phase 6: CI/CD Fixes - Research

**Researched:** 2026-03-29
**Domain:** GitHub Actions workflow configuration
**Confidence:** HIGH

## Summary

Three discrete bugs exist across two workflow files. All three are straightforward YAML edits with no Python code changes required. The bugs are: (1) `update.yml` change-detection using `git diff dist/` which silently never fires because `dist/` is gitignored; (2) `build-lists.yml` creating a new uniquely-tagged GitHub Release every run via `lists-${{ github.run_id }}`; (3) `update.yml` pinned to `astral-sh/setup-uv@v3` while both other workflows use `@v5`.

Each fix is one or two lines of YAML. There is no Python implementation work in this phase, no new dependencies, and no test changes required (workflow files are not covered by pytest).

**Primary recommendation:** Fix all three issues in a single YAML-only commit to `.github/workflows/`. No Python source changes, no test changes.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CICD-01 | `update.yml` detects blocklist changes using a mechanism that works with gitignored `dist/` | Hash-based comparison of `dist/` contents before/after build (sha256sum or find+hash); replaces broken `git diff dist/` |
| CICD-02 | `build-lists.yml` overwrites a fixed `latest` release tag instead of creating a new release per run | Replace `tag_name: lists-${{ github.run_id }}` with `tag_name: latest`; `softprops/action-gh-release@v2` updates existing release when tag already exists |
| CICD-03 | `update.yml` uses `astral-sh/setup-uv@v5` consistent with `ci.yml` and `build-lists.yml` | Bump `@v3` to `@v5` and consolidate to single-step setup pattern (remove `actions/setup-python@v5` step) |
</phase_requirements>

## Standard Stack

### Core
| Action | Version in ci.yml / build-lists.yml | Version in update.yml | Status |
|--------|-------------------------------------|-----------------------|--------|
| `actions/checkout` | v4 | v4 | Consistent |
| `astral-sh/setup-uv` | v5 | **v3** | **MISMATCH — fix required** |
| `actions/setup-python` | Not used (uv handles it) | v5 (separate step) | Redundant in update.yml |
| `softprops/action-gh-release` | v2 | Not used | Fix tag_name |
| `peter-evans/create-pull-request` | Not used | **v5** | Stale — current is v8 |

### Action Versions (verified)
| Action | Current Version | Source |
|--------|----------------|--------|
| `softprops/action-gh-release` | v2 (v2.5.0, Dec 2025) | GitHub Marketplace |
| `peter-evans/create-pull-request` | v8 | GitHub Marketplace |
| `astral-sh/setup-uv` | v5 | Used in ci.yml + build-lists.yml |

## Architecture Patterns

### CICD-01: Change Detection Without Git Tracking

**Root cause:** `git diff --quiet dist/` on line 45 of `update.yml` always exits 0 (no changes) because `dist/` is in `.gitignore`. Git does not track gitignored paths; `git diff` only compares tracked files.

**Broken step (update.yml lines 44-49):**
```yaml
- name: Check for changes
  id: check
  run: |
    if git diff --quiet dist/ 2>/dev/null; then
      echo "has_changes=false" >> "$GITHUB_OUTPUT"
    else
      echo "has_changes=true" >> "$GITHUB_OUTPUT"
    fi
```

**Fix — hash comparison pattern:**
```yaml
- name: Hash dist before build
  id: hash_before
  run: |
    if [ -d dist ]; then
      echo "hash=$(find dist -type f | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)" >> "$GITHUB_OUTPUT"
    else
      echo "hash=none" >> "$GITHUB_OUTPUT"
    fi

# ... build step runs here ...

- name: Check for changes
  id: check
  run: |
    after=$(find dist -type f | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)
    if [ "${{ steps.hash_before.outputs.hash }}" = "$after" ]; then
      echo "has_changes=false" >> "$GITHUB_OUTPUT"
    else
      echo "has_changes=true" >> "$GITHUB_OUTPUT"
    fi
```

**Why this works:** `find dist -type f | sort | xargs sha256sum | sha256sum` hashes all file contents and is stable regardless of git tracking. The sort ensures deterministic ordering across filesystem states.

**Alternative:** Write a manifest file before build (`sha256sum dist/**/*.txt > /tmp/manifest_before.txt`) and diff after. The hash approach above is simpler and produces a single comparable value.

### CICD-02: Fixed Release Tag Overwrite

**Root cause:** `tag_name: lists-${{ github.run_id }}` on line 53 of `build-lists.yml` uses the GitHub Actions run ID — a unique integer incremented per run. Every scheduled or manual run creates a distinct new release, accumulating indefinitely.

**Broken step (build-lists.yml lines 51-64):**
```yaml
- name: Create release
  uses: softprops/action-gh-release@v2
  with:
    tag_name: lists-${{ github.run_id }}
    name: "Blocklists ${{ github.run_id }}"
    body: "Automated build from workflow run ${{ github.run_id }}"
    files: |
      dist/all.txt
      ...
```

**Fix — fixed `latest` tag:**
```yaml
- name: Create release
  uses: softprops/action-gh-release@v2
  with:
    tag_name: latest
    name: "Blocklists (latest)"
    body: "Latest automated blocklist build. Run: ${{ github.run_id }}"
    make_latest: "true"
    files: |
      dist/all.txt
      dist/allowlist.txt
      dist/regex.txt
      dist/categories/*.txt
      dist/profiles/*.txt
      dist/reports/*.json
      dist/reports/*.md
```

**How `softprops/action-gh-release@v2` handles existing tags:** When a release with `tag_name: latest` already exists, the action updates the existing release in place — overwriting assets and metadata. The `overwrite_files` option defaults to `true`, so existing attached files are replaced. The `make_latest: "true"` option ensures GitHub marks this as the repository's latest release.

**Note:** The `latest` tag will be force-pushed to HEAD of the default branch on each run. This is standard practice for rolling "latest" releases and is intentional.

### CICD-03: setup-uv Version Consistency

**Root cause:** `update.yml` uses the old two-step pattern (separate `actions/setup-python@v5` + `astral-sh/setup-uv@v3`) while `ci.yml` and `build-lists.yml` use the newer single-step pattern (`astral-sh/setup-uv@v5` with `python-version` embedded).

**Broken setup in update.yml (lines 22-31):**
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.12"

- name: Install uv
  uses: astral-sh/setup-uv@v3
```

**Fix — match ci.yml and build-lists.yml pattern:**
```yaml
- name: Set up uv
  uses: astral-sh/setup-uv@v5
  with:
    python-version: "3.12"
```

This removes one step and aligns `update.yml` with the rest of the workflow files.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Release overwrite | Custom git tag force-push + API calls | `softprops/action-gh-release@v2` with fixed `tag_name` | Action handles asset cleanup, draft/prerelease state, API retries |
| Change detection | Custom git-tracked sentinel file | Hash comparison of `dist/` output | Simpler, no index mutation, works on gitignored paths |

**Key insight:** The `softprops/action-gh-release@v2` action already supports update-in-place semantics for fixed tags. No custom release management scripts are needed.

## Common Pitfalls

### Pitfall 1: `git diff` on Gitignored Paths
**What goes wrong:** `git diff --quiet dist/` exits 0 even when `dist/` files changed — silently suppressing PRs.
**Why it happens:** Git does not stage or track gitignored paths. `git diff` (staged or unstaged) never sees them.
**How to avoid:** Use filesystem-level comparison (hash, checksum, find+diff) instead of git commands for gitignored outputs.
**Warning signs:** The `Create PR` step never runs despite actual blocklist changes.

### Pitfall 2: `sha256sum` on Empty/Missing dist/
**What goes wrong:** If `dist/` does not exist before the first build, `find dist -type f` returns nothing and `xargs sha256sum` may error or produce empty input to the outer `sha256sum`.
**How to avoid:** Guard with `if [ -d dist ]; then ... else echo "hash=none"; fi` before the build step. The after-build hash will always be a real hash, so `none != real_hash` correctly signals changes.

### Pitfall 3: `latest` Tag Push Permissions
**What goes wrong:** The `latest` tag force-push may fail if the workflow's `GITHUB_TOKEN` lacks write permission.
**How to avoid:** `build-lists.yml` already has `permissions: contents: write` — this covers tag creation and release management. No change needed.

### Pitfall 4: `peter-evans/create-pull-request@v5` Major Version Gap
**What goes wrong:** v5 is two major versions behind current (v8). Breaking changes in v6 and v7 may affect behavior or introduce deprecation warnings.
**How to avoid:** Bump to `@v8` in the same commit. The core inputs (`commit-message`, `title`, `body`, `branch`, `delete-branch`) are unchanged between v5 and v8.

## Code Examples

### Complete Fixed update.yml
```yaml
name: Update

on:
  schedule:
    - cron: '0 3 * * 1'
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  update-build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up uv
        uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Hash dist before build
        id: hash_before
        run: |
          if [ -d dist ]; then
            echo "hash=$(find dist -type f | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)" >> "$GITHUB_OUTPUT"
          else
            echo "hash=none" >> "$GITHUB_OUTPUT"
          fi

      - name: Build (with fetch)
        run: uv run blocklist-factory build

      - name: Check for changes
        id: check
        run: |
          after=$(find dist -type f | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)
          if [ "${{ steps.hash_before.outputs.hash }}" = "$after" ]; then
            echo "has_changes=false" >> "$GITHUB_OUTPUT"
          else
            echo "has_changes=true" >> "$GITHUB_OUTPUT"
          fi

      - name: Create PR
        if: steps.check.outputs.has_changes == 'true'
        uses: peter-evans/create-pull-request@v8
        with:
          commit-message: "chore: update blocklists"
          title: "chore: weekly blocklist update"
          body: "Automated weekly blocklist update. Review stats in dist/reports/stats.md"
          branch: chore/weekly-update
          delete-branch: true

      - name: Done
        if: steps.check.outputs.has_changes == 'false'
        run: echo "No changes in blocklists"
```

### Fixed release step for build-lists.yml (lines 51-64 replacement)
```yaml
      - name: Create release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: latest
          name: "Blocklists (latest)"
          body: "Latest automated blocklist build. Run: ${{ github.run_id }}"
          make_latest: "true"
          files: |
            dist/all.txt
            dist/allowlist.txt
            dist/regex.txt
            dist/categories/*.txt
            dist/profiles/*.txt
            dist/reports/*.json
            dist/reports/*.md
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest --cov=blocklist_builder -x -q` |
| Full suite command | `PYTHONPATH=src uv run pytest --cov=blocklist_builder --cov-report=term-missing` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CICD-01 | Hash comparison detects dist/ changes | manual-only | N/A — workflow YAML only, no Python code | N/A |
| CICD-02 | Fixed `latest` tag used in release | manual-only | N/A — workflow YAML only, no Python code | N/A |
| CICD-03 | setup-uv@v5 used in update.yml | manual-only | N/A — workflow YAML only, no Python code | N/A |

**Rationale for all manual-only:** This phase is entirely GitHub Actions YAML edits. There is no Python implementation to unit-test. Validation is by inspection: grep the fixed YAML for the correct values.

### Verification commands (grep-based)
```bash
grep "astral-sh/setup-uv" .github/workflows/update.yml
grep "tag_name" .github/workflows/build-lists.yml
grep "git diff" .github/workflows/update.yml
```

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements (no new Python code, no new tests needed).

## Environment Availability

Step 2.6: SKIPPED — this phase modifies only YAML workflow files. No external tools beyond git and a text editor are required.

## Open Questions

1. **`find dist -type f | sort | xargs sha256sum` on large dist/**
   - What we know: `dist/` contains ~10-20 text files; this command is fast
   - What's unclear: Whether `xargs sha256sum` handles zero files gracefully when dist/ is empty (not missing)
   - Recommendation: Add `|| true` after `xargs sha256sum` to handle empty case, or use `find dist -type f -exec sha256sum {} \; | sort | sha256sum`

2. **`peter-evans/create-pull-request@v5` vs `@v8` input compatibility**
   - What we know: `commit-message`, `title`, `body`, `branch`, `delete-branch` inputs exist in both versions
   - What's unclear: Whether any previously undocumented defaults changed between v5 and v8
   - Recommendation: Bump to `@v8`; all used inputs are stable. Changelog confirms no breaking changes to these core inputs.

## Sources

### Primary (HIGH confidence)
- Direct inspection of `.github/workflows/update.yml` — line 28 (`@v3`), line 45 (`git diff dist/`)
- Direct inspection of `.github/workflows/build-lists.yml` — line 53 (`lists-${{ github.run_id }}`)
- Direct inspection of `.github/workflows/ci.yml` — line 20 (`@v5`)
- Direct inspection of `.gitignore` — confirms `dist/` is gitignored (last line)

### Secondary (MEDIUM confidence)
- [softprops/action-gh-release GitHub](https://github.com/softprops/action-gh-release) — confirmed `overwrite_files` defaults true, `make_latest` option exists, v2 is current
- [peter-evans/create-pull-request GitHub](https://github.com/peter-evans/create-pull-request) — confirmed v8 is current major version

## Metadata

**Confidence breakdown:**
- Root cause analysis (CICD-01, 02, 03): HIGH — direct code inspection of workflow files
- Fix approach (hash comparison): HIGH — standard CI pattern, no library dependency
- Action behavior (softprops overwrite): MEDIUM — confirmed via official README, not Context7
- peter-evans v8 inputs: MEDIUM — confirmed via official README

**Research date:** 2026-03-29
**Valid until:** 2026-06-29 (GitHub Actions action versions are stable; action APIs change slowly)
