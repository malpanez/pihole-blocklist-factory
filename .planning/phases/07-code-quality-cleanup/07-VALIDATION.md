---
phase: 7
slug: code-quality-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_config.py tests/test_firebog.py tests/test_sanitize.py tests/test_cli.py -x -q` |
| **Full suite command** | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command above
- **After every plan wave:** Run full suite + ruff check
- **Before `/gsd:verify-work`:** Full suite must be green at 100% coverage + ruff clean
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | QUAL-02 | unit | `uv run pytest tests/test_config.py -x -q` | ✅ | ⬜ pending |
| 7-01-02 | 01 | 1 | QUAL-01 | unit | `uv run pytest tests/test_firebog.py -x -q` | ✅ | ⬜ pending |
| 7-01-03 | 01 | 1 | QUAL-03 | unit | `uv run pytest tests/test_sanitize.py -x -q` | ✅ | ⬜ pending |
| 7-01-04 | 01 | 1 | QUAL-06 | unit | `uv run pytest tests/test_cli.py -x -q` | ✅ | ⬜ pending |
| 7-01-05 | 01 | 2 | QUAL-04, QUAL-05, QUAL-07 | manual+grep | `grep -q "create_test_data.py" .gitignore && grep -q "run_build.py" .gitignore && echo "QUAL-04 OK"` | ✅ | ⬜ pending |
| 7-01-06 | 01 | 2 | QUAL-01..07 | coverage | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing test infrastructure covers all phase requirements. No new test files needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `create_test_data.py` / `run_build.py` gitignored | QUAL-04 | File existence check only | `grep -q "create_test_data.py" .gitignore && echo "OK"` |
| `pyproject.toml` author updated | QUAL-05 | Metadata check | `grep "authors" pyproject.toml` — confirm no "Your Name" placeholder |
| `scripts/pihole-adlists-setup-v6.sh` removed/clarified | QUAL-07 | File removal check | `test ! -f scripts/pihole-adlists-setup-v6.sh && echo "removed"` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
