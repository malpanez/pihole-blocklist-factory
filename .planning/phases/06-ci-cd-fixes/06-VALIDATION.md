---
phase: 6
slug: ci-cd-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | YAML lint + manual review (no automated test framework for workflow files) |
| **Config file** | N/A — GitHub Actions YAML only |
| **Quick run command** | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/update.yml'))" && python3 -c "import yaml; yaml.safe_load(open('.github/workflows/build-lists.yml'))" && echo "YAML valid"` |
| **Full suite command** | `uv run pytest --cov=blocklist_builder --cov-report=term-missing -q && uv run ruff check src/` |
| **Estimated runtime** | ~5 seconds (YAML parse) + ~15 seconds (full suite regression) |

---

## Sampling Rate

- **After every task commit:** Run YAML parse validation above
- **After every plan wave:** Run full pytest suite (regression guard — no Python changes in this phase)
- **Before `/gsd:verify-work`:** Full suite must be green, YAML files must parse cleanly
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 1 | CICD-01 | yaml-parse | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/update.yml'))" && grep -q "sha256sum" .github/workflows/update.yml && echo "CICD-01 OK"` | ✅ | ⬜ pending |
| 6-01-02 | 01 | 1 | CICD-02 | yaml-parse | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/build-lists.yml'))" && grep -q "tag_name: latest" .github/workflows/build-lists.yml && echo "CICD-02 OK"` | ✅ | ⬜ pending |
| 6-01-03 | 01 | 1 | CICD-03 | yaml-parse | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/update.yml'))" && grep -q "setup-uv@v5" .github/workflows/update.yml && echo "CICD-03 OK"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No new test files needed. YAML parse validation uses stdlib only.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| update.yml actually creates PR on changed dist/ | CICD-01 | Requires live GitHub Actions run | Push a change that produces different dist/ output; verify PR is created |
| build-lists.yml overwrites existing release | CICD-02 | Requires live GitHub release | Trigger build-lists workflow twice; verify only one `latest` release exists |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
