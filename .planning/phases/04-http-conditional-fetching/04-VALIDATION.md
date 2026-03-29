---
phase: 4
slug: http-conditional-fetching
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_fetch.py -x -q` |
| **Full suite command** | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_fetch.py -x -q`
- **After every plan wave:** Run `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/`
- **Before `/gsd:verify-work`:** Full suite must be green + ruff clean
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | NET-01, NET-03 | unit | `uv run pytest tests/test_fetch.py -x -q` | ✅ | ⬜ pending |
| 4-01-02 | 01 | 1 | NET-02, NET-04 | unit | `uv run pytest tests/test_fetch.py -x -q` | ✅ | ⬜ pending |
| 4-01-03 | 01 | 2 | NET-01..04 | coverage | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Modifications to existing `tests/test_fetch.py` only — no new test files needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real server ETag round-trip | NET-01, NET-02 | Requires live HTTP server with ETag support | Run two consecutive builds and check `.cache/*.json` sidecar files for non-None `etag` and `last_modified` values |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
