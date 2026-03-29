---
phase: 1
slug: core-pipeline-bugs
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_build.py tests/test_parallel.py tests/test_parallel_extra.py -x -q` |
| **Full suite command** | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_build.py tests/test_parallel.py tests/test_parallel_extra.py -x -q`
- **After every plan wave:** Run `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/`
- **Before `/gsd:verify-work`:** Full suite must be green + ruff clean
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | PIPE-04 | unit | `uv run pytest tests/test_parallel.py tests/test_parallel_extra.py -x -q` | ✅ | ⬜ pending |
| 1-01-02 | 01 | 1 | PIPE-01 | unit | `uv run pytest tests/test_build.py -k "test_build" -x -q` | ✅ | ⬜ pending |
| 1-01-03 | 01 | 2 | PIPE-02, PIPE-03 | unit | `uv run pytest tests/test_build.py -k "stats" -x -q` | ✅ | ⬜ pending |
| 1-01-04 | 01 | 2 | PIPE-02, PIPE-03 | coverage | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files needed — only modifications to existing tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HTTP requests count | PIPE-01 | Requires live network or mock HTTP server | Run `uv run blocklist-factory build --no-fetch` with cached sources; verify single fetch per source via logging output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
