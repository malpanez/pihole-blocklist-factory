---
created: 2026-06-12T11:49:15.082Z
title: Adopt mypy strict - fix errors, add dep, CI gate
area: tooling
files:
  - src/blocklist_builder/cli.py
  - src/blocklist_builder/build.py
  - src/blocklist_builder/recommend.py
  - src/blocklist_builder/firebog.py
  - src/blocklist_builder/fetch.py
  - src/blocklist_builder/analyze.py
  - src/blocklist_builder/config.py
  - src/blocklist_builder/parallel.py
  - pyproject.toml
  - .github/workflows/ci.yml
---

## Problem

`uvx mypy --strict src/blocklist_builder` reports 56 pre-existing errors (down from 60 at baseline; per-file counts pre-Phase-1 recorded in docs/baseline.md: cli.py 16, build.py 13, recommend.py 9, firebog.py 8, fetch.py 8, analyze.py 8, config.py 4, parallel.py 2). mypy is not a project dependency and not a CI gate, so strict-mode regressions can slip in unnoticed. Quick task 260612-eki established the 56-error report-only baseline.

## Solution

Run as a single /gsd:quick task, in this exact order:
1. Fix the 56 remaining `mypy --strict` errors (zero errors).
2. Add mypy to `[dependency-groups]` dev in pyproject.toml.
3. Add `uv run mypy --strict src/blocklist_builder` as a blocking gate in .github/workflows/ci.yml.

Constraints: no new runtime deps; keep 99%+ coverage and ruff clean.
