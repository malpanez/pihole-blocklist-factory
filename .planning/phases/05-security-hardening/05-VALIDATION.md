---
phase: 5
slug: security-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_fetch.py tests/test_build.py tests/test_parallel_extra.py -x -q` |
| **Full suite command** | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_fetch.py tests/test_build.py -x -q`
- **After every plan wave:** Run `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/`
- **Before `/gsd:verify-work`:** Full suite must be green + ruff clean
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | SEC-01, SEC-05 | unit | `uv run pytest tests/test_fetch.py -x -q` | ✅ | ⬜ pending |
| 5-01-02 | 01 | 1 | SEC-02 | unit | `uv run pytest tests/test_parallel_extra.py -x -q` | ✅ | ⬜ pending |

| 5-01-03 | 01 | 1 | SEC-03, SEC-04 | unit | `uv run pytest tests/test_build.py -x -q` | ✅ | ⬜ pending |
| 5-01-04 | 01 | 2 | SEC-01..05 | coverage | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing test files cover phase requirements. New test functions only — no new test files needed.

- [ ] `tests/test_fetch.py` — add `test_fetch_to_cache_traversal_rejected` and `test_compute_hash_not_cached`
- [ ] `tests/test_build.py` — add `test_build_file_traversal_rejected` and `test_build_http_emits_warning`
- [ ] `tests/test_parallel_extra.py` — add `test_resolve_local_sources_traversal_rejected`

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
