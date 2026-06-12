---
created: 2026-06-12T11:49:15.082Z
title: Deduplicate byte-identical profile outputs (symlinks or manifest)
area: general
files:
  - src/blocklist_builder/build.py
  - config/profiles.yml
---

## Problem

Six profiles (base, aggressive, android, ios, macos, windows) currently produce byte-identical 4.8M-domain files (4,805,001 lines each) because no per-device divergence exists yet. That is ~570 MB of duplicated artifacts per release upload (build-lists.yml attaches all profiles). Note: ROADMAP Phase 3 "Profile Features Cleanup" (completed 2026-03-29) removed silently-ignored fields but did not address output duplication — this is follow-up work, not part of that phase.

## Solution

Until profiles actually diverge, the cheap fix is one of:
- Write the unique content once and emit symlinks for identical profiles (verify GitHub release upload follows symlinks), or
- Emit a small manifest (profiles.json) mapping profile name -> canonical file, and only upload unique files.

Constraint: dist/ output format is consumed by Pi-hole adlist URLs — if any published profile URL changes, it breaks subscribers; prefer a solution that keeps existing URLs working (e.g. release assets deduped but same filenames).
