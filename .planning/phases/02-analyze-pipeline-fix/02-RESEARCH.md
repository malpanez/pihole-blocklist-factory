# Phase 2: Analyze Pipeline Fix - Research

**Researched:** 2026-03-29
**Domain:** Python bug fix — analytics function, JSON fixture testing
**Confidence:** HIGH

## Summary

The `analyze` command's `_compute_discard_findings()` function has a logic bug that makes it permanently a no-op. It builds `source_stats` from `provenance.json` by iterating domain-to-source_ids, incrementing only `sanitized_ok` per source. The `discarded` key is initialized to 0 and is never incremented by anything — provenance.json records only successful domains, not discarded lines. Therefore `discard_rate` is always 0.0 and `findings` is always `[]`.

The fix is straightforward: replace the provenance-reconstruction approach with a direct read of `dist/reports/source_stats.json`. That file is already written by `_write_source_stats()` in `build.py` after every build and contains per-source counts for `lines`, `parse_ok`, `sanitize_ok`, and all discard reason keys (`parse_comment`, `parse_empty`, `parse_unsupported`, `sanitize_ip`, `sanitize_single_label`, `sanitize_not_fqdn`, `sanitize_invalid`, `allowlisted`). The discard count for a source is `lines - sanitize_ok`.

The test at `test_analyze.py:101-119` bypasses the real code path by monkeypatching `defaultdict` with a hardcoded `discarded: 2` value. It must be replaced with a test that writes a real `source_stats.json` fixture and calls `_compute_discard_findings` through `analyze_build`.

**Primary recommendation:** Rewrite `_compute_discard_findings` to load `source_stats.json` and compute `discard_rate = (lines - sanitize_ok) / lines`. Delete the monkeypatch test. Write two new tests: one that confirms a finding fires when discard_rate > threshold, one that confirms no finding when below threshold. Both use a real `source_stats.json` fixture file via `tmp_path`.

## Project Constraints (from CLAUDE.md)

- Python 3.11+ — uses `match/case`, `slots=True`, `tomllib`
- Test coverage: must maintain ≥99% after each phase
- Linting: `ruff check` must pass clean after each phase
- `dist/` output format must not change (Pi-hole adlist URLs are stable)
- No new dependencies: fix bugs using existing stdlib

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANLZ-01 | `analyze` command produces discard-rate findings for sources with high discard rates | `source_stats.json` contains per-source `lines` and `sanitize_ok`; discard_rate = (lines - sanitize_ok) / lines. Real data shows `sample_local` at 54.5%, `firebog_malicious_5` at 100%, `perflyst_smarttv` at 35.8% — findings will fire against real builds. |
| ANLZ-02 | `_compute_discard_findings` reads actual discard data from `source_stats.json` | `_write_source_stats` already writes `dist/reports/source_stats.json` after every build. `_load_provenance_and_stats` already loads `stats.json` but not `source_stats.json` — add a third file load or a separate helper. |
| ANLZ-03 | Tests for `_compute_discard_findings` exercise the real code path (no hardcoded bypass) | Replace `test_compute_discard_findings_triggers` with two fixture-based tests. The monkeypatch of `defaultdict` must be deleted. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| json (stdlib) | 3.11+ | Read source_stats.json | Already used in analyze.py |
| pathlib (stdlib) | 3.11+ | File path resolution | Already used throughout |
| pytest | ≥8.0.0 | Test framework | Project standard |
| pytest-cov | ≥5.0.0 | Coverage enforcement | Project standard |

No new dependencies required. The fix is pure stdlib JSON file I/O.

**Version verification:** All packages already declared in `pyproject.toml`. No new packages needed.

## Architecture Patterns

### source_stats.json Schema (verified from real build)

```json
{
  "source_id": {
    "lines": 374,
    "parse_comment": 3,
    "parse_empty": 2,
    "parse_ok": 369,
    "sanitize_ok": 240,
    "sanitize_not_fqdn": 129
  }
}
```

All keys except `lines` are optional (only present when count > 0). Keys in the real dataset:
- Metadata: `lines`
- Success: `parse_ok`, `sanitize_ok`
- Discards: `parse_comment`, `parse_empty`, `parse_unsupported`, `sanitize_ip`, `sanitize_single_label`, `sanitize_not_fqdn`, `sanitize_invalid`, `allowlisted`

**Discard rate formula:** `(lines - sanitize_ok) / lines` — uses only `lines` and `sanitize_ok`, both always present for processed sources.

### Existing Load Pattern

`_load_provenance_and_stats()` already handles the pattern of reading a JSON file with error handling. The same pattern applies for `source_stats.json`. Two options:

**Option A — Extend `_load_provenance_and_stats`:** Return a third value `source_stats_data` from the existing loader. Signature becomes `tuple[dict, dict, dict] | tuple[None, None, None]`. Requires updating all callers.

**Option B — Separate loader:** Add `_load_source_stats(dist_dir: Path) -> dict | None` following the same try/except pattern. Cleaner, no caller changes for provenance/stats.

Option B is recommended: minimal diff, no change to existing function contracts, easy to test in isolation.

### Revised `_compute_discard_findings` Signature

Current signature: `(provenance: dict, source_map: dict, high_discard_threshold: float = 0.5) -> list[str]`

Required change: Remove `provenance` dependency, add `source_stats: dict`. `source_map` still needed for human-readable source name in the finding message.

New signature: `(source_stats: dict, source_map: dict, high_discard_threshold: float = 0.5) -> list[str]`

Caller in `analyze_build()` already has `source_map`. It needs to call `_load_source_stats()` and pass the result.

### Graceful Degradation

`source_stats.json` may not exist if the user runs `analyze` against a pre-Phase-1 build artifact that predates the file being written. The function should return `[]` with a log warning when the file is missing, not raise. The existing `_load_provenance_and_stats` pattern (return None on error) is the right model.

In `analyze_build()`: if `_load_source_stats()` returns None, skip discard findings and log a warning.

### Anti-Patterns to Avoid

- **Reconstructing discard counts from provenance:** provenance.json only records successfully-retained domains. Discarded entries are not in provenance by definition.
- **Summing all non-`lines`, non-`sanitize_ok` keys as discards:** Fragile against new key additions. Use `lines - sanitize_ok` instead — stable regardless of what discard subcategories exist.
- **Keeping the defaultdict approach:** The new implementation should use a plain dict iteration over the loaded JSON, not a defaultdict.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON file loading with error handling | Custom retry/fallback logic | Pattern already in `_load_provenance_and_stats` | Copy the try/except → return None pattern |
| Discard rate computation | Complex per-key aggregation | `(lines - sanitize_ok) / lines` | Direct arithmetic is correct and stable |

## Common Pitfalls

### Pitfall 1: Missing `source_stats.json` not handled
**What goes wrong:** `_load_source_stats` raises `FileNotFoundError` if user runs `analyze` on a build that predates `source_stats.json` (pre-Phase-1 artifact).
**Why it happens:** Old builds written before `_write_source_stats` was added to the pipeline.
**How to avoid:** Check `.exists()` before reading, return `None` on any exception, log a `logging.warning`.
**Warning signs:** Test fails with `FileNotFoundError` in tmp_path without a fixture file.

### Pitfall 2: Division by zero for sources with `lines: 0`
**What goes wrong:** `discard_rate = (0 - 0) / 0` raises `ZeroDivisionError`.
**Why it happens:** A source entry with `lines: 0` can occur if a source file existed but was empty.
**How to avoid:** Guard: `if lines == 0: continue`.
**Warning signs:** Test with empty-source fixture raises ZeroDivisionError.

### Pitfall 3: `sanitize_ok` key absent for fully-failed sources
**What goes wrong:** `source_stats.get('sanitize_ok', 0)` returns 0 when all lines failed before sanitization (e.g., `firebog_malicious_5` has 100% parse discard — no `sanitize_ok` key at all).
**Why it happens:** Keys are only written when count > 0.
**How to avoid:** Always use `.get('sanitize_ok', 0)`. The formula `lines - sanitize_ok` handles this correctly.
**Warning signs:** KeyError in test with a fixture that has only `parse_unsupported` and no `sanitize_ok`.

### Pitfall 4: Test coverage regression from deleting the monkeypatch test
**What goes wrong:** Deleting `test_compute_discard_findings_triggers` removes the only test covering the discard-findings code path. If the two replacement tests do not also cover the `source_map` lookup (src_id present vs absent in source_map), lines go uncovered.
**Why it happens:** The source name lookup `source_map.get(src_id, {}).name if ...` has two branches.
**How to avoid:** Write one test with a populated source_map and one where the source_id is not in source_map, confirming the fallback to `src_id` in the finding string.

### Pitfall 5: `analyze_build` test `test_analyze_build_reports` will break
**What goes wrong:** `analyze_build` now calls `_load_source_stats`, which looks for `source_stats.json`. The existing `test_analyze_build_reports` fixture does not write this file.
**Why it happens:** The new code path is triggered on every `analyze_build` call.
**How to avoid:** Update `test_analyze_build_reports` to also write a `source_stats.json` fixture, OR ensure `_load_source_stats` returning None simply skips discard findings gracefully (so the test still passes without the file).
**Warning signs:** `test_analyze_build_reports` fails with `high_discard_sources` assertion or unexpected behavior.

## Code Examples

### Correct discard_rate formula
```python
# Source: verified against dist/reports/source_stats.json real data
for src_id, stats in source_stats_data.items():
    lines = stats.get("lines", 0)
    if lines == 0:
        continue
    sanitize_ok = stats.get("sanitize_ok", 0)
    discard_rate = (lines - sanitize_ok) / lines
    if discard_rate > high_discard_threshold:
        src_name = source_map.get(src_id)
        name = src_name.name if src_name else src_id
        findings.append(
            f"High discard rate for {src_id} ({name}): {discard_rate:.1%} "
            f"({lines - sanitize_ok}/{lines} entries)"
        )
```

### Fixture pattern for new tests
```python
# Source: existing test pattern in test_analyze.py
def test_compute_discard_findings_fires(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    source_stats = {
        "s1": {"lines": 100, "parse_ok": 100, "sanitize_ok": 20, "sanitize_ip": 80},
        "s2": {"lines": 100, "parse_ok": 100, "sanitize_ok": 90},
    }
    (dist_dir / "reports").mkdir(parents=True)
    (dist_dir / "reports" / "source_stats.json").write_text(
        json.dumps(source_stats), encoding="utf-8"
    )
    source_map = {"s1": type("S", (), {"name": "Source One"})(), "s2": type("S", (), {"name": "Source Two"})()}
    findings = _compute_discard_findings(source_stats, source_map, high_discard_threshold=0.5)
    assert len(findings) == 1
    assert "s1" in findings[0]
    assert "80.0%" in findings[0]
```

### Safe file load pattern (matches existing style)
```python
def _load_source_stats(dist_dir: Path) -> dict | None:
    source_stats_file = dist_dir / "reports" / "source_stats.json"
    if not source_stats_file.exists():
        return None
    try:
        return json.loads(source_stats_file.read_text(encoding="utf-8"))
    except Exception:
        return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Reconstruct discard counts from provenance | Read pre-computed source_stats.json | Phase 2 (this phase) | Discard findings actually fire |
| Monkeypatch defaultdict to inject discarded=2 | Real source_stats.json fixture | Phase 2 (this phase) | Test exercises real code path |

## Open Questions

1. **Should `_compute_discard_findings` signature change break `analyze_build` caller?**
   - What we know: `analyze_build` calls `_compute_discard_findings(provenance, source_map)` — provenance must be removed from args.
   - What's unclear: Whether to load `source_stats` inside `_compute_discard_findings` (passing `dist_dir`) or outside and pass the dict.
   - Recommendation: Load outside and pass as dict — keeps the function pure and testable without filesystem. Load with `_load_source_stats(dist_dir)` in `analyze_build`, pass result to function.

2. **Should `test_analyze_build_reports` be updated or rely on graceful degradation?**
   - What we know: The test doesn't write `source_stats.json`. It asserts `result["high_discard_sources"]` is not checked (only `total_domains`, `overlap_2`, `overlap_3_plus`).
   - Recommendation: Implement graceful degradation (`_load_source_stats` returns None → `discard_findings = []`) so existing `test_analyze_build_reports` needs no changes. Then add a separate focused test that provides the fixture and validates discard findings.

## Environment Availability

Step 2.6: SKIPPED — phase is pure Python source code and test changes with no external dependencies beyond the already-installed project packages.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-cov 5.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_analyze.py -q` |
| Full suite command | `python -m pytest tests/ --cov=blocklist_builder --cov-report=term-missing -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANLZ-01 | `analyze_build` on high-discard source data returns at least one finding | unit | `python -m pytest tests/test_analyze.py::test_compute_discard_findings_fires -x` | ❌ Wave 0 |
| ANLZ-02 | `_compute_discard_findings` reads from source_stats.json, not provenance | unit | `python -m pytest tests/test_analyze.py::test_compute_discard_findings_fires -x` | ❌ Wave 0 |
| ANLZ-03 | No monkeypatch bypass — real code path exercised with fixture | unit | `python -m pytest tests/test_analyze.py -x` | ❌ Wave 0 (delete old test, add new) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_analyze.py -q`
- **Per wave merge:** `python -m pytest tests/ --cov=blocklist_builder --cov-report=term-missing -q`
- **Phase gate:** Full suite green + ≥99% coverage before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_analyze.py` — delete `test_compute_discard_findings_triggers` (monkeypatch bypass), add `test_compute_discard_findings_fires` and `test_compute_discard_findings_no_finding` with real source_stats.json fixtures
- [ ] No new config or fixtures files needed — `tmp_path` fixture covers file writes

## Sources

### Primary (HIGH confidence)
- `src/blocklist_builder/analyze.py` — full source read, bug confirmed at lines 37-60
- `src/blocklist_builder/build.py` — `_write_source_stats` at line 203, `source_stats` dict structure confirmed
- `tests/test_analyze.py` — monkeypatch bypass confirmed at lines 101-119
- `dist/reports/source_stats.json` — live build artifact, schema and all keys enumerated, discard rates verified

### Secondary (MEDIUM confidence)
- `.planning/codebase/analysis.md` — original analysis, confirmed as accurate against live code
- `pyproject.toml` — test framework versions confirmed

## Metadata

**Confidence breakdown:**
- Bug location and cause: HIGH — code read directly, behavior traced
- Fix approach: HIGH — source_stats.json schema verified against real build artifact
- Test replacement strategy: HIGH — existing test pattern studied, monkeypatch confirmed as bypass
- Discard rate formula: HIGH — verified `lines` and `sanitize_ok` present in all processed source entries

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable codebase, no fast-moving dependencies)
