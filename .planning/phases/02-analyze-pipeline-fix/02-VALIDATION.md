---
phase: 2
slug: analyze-pipeline-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_analyze.py -x -q` |
| **Full suite command** | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_analyze.py -x -q`
- **After every plan wave:** Run `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/`
- **Before `/gsd:verify-work`:** Full suite must be green + ruff clean
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | ANLZ-01, ANLZ-02 | unit | `uv run pytest tests/test_analyze.py -x -q` | ✅ | ⬜ pending |
| 2-01-02 | 01 | 1 | ANLZ-03 | unit+coverage | `uv run pytest tests/test_analyze.py -x -q && uv run pytest --cov=blocklist_builder -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files needed — only modifications to existing `tests/test_analyze.py`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `analyze` command produces findings on real build | ANLZ-01 | Requires a real dist/ with source_stats.json | Run `uv run blocklist-factory analyze` after a build; check output contains at least one high-discard finding |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
