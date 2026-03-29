# Phase 3: Profile Features Cleanup - Research

**Researched:** 2026-03-29
**Domain:** Python dataclass cleanup, YAML config, test fixture updates
**Confidence:** HIGH

## Summary

Phase 3 removes four dead fields from two dataclasses (`Profile` and `Policies`) that are parsed from YAML but never read by the build pipeline. The fields exist across a predictable, fully enumerable set of locations: source files, YAML configs, tests, and documentation. No runtime state migration is involved — all changes are code and config edits.

The work is pure deletion: remove fields from dataclasses, remove parsing logic in `config.py`, clean YAML configs, and update test fixtures that construct `Policies(sensitive_domains=set())` or assert on `Profile.strict`. There is no behavior change to the build pipeline — output (`dist/`) is unaffected.

**Primary recommendation:** Execute as a single wave — delete fields, update all references atomically, run `pytest --cov` and `ruff check` to confirm ≥99% coverage and no lint regressions.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROF-01 | `Profile` dataclass no longer contains `include_sources`, `exclude_sources`, or `strict` fields | Fields confirmed dead in `build.py` — `_write_profiles()` reads only `include_categories`. Grep finds zero production reads of the three fields. |
| PROF-02 | `Policies` dataclass no longer contains `sensitive_domains` field | `sensitive_domains` confirmed parsed and stored only — never read in `build.py`, `analyze.py`, `recommend.py`, or any other module. |
| PROF-03 | `config/profiles.yml` and `config/policies.yml` contain no references to removed fields | Both YAMLs confirmed to reference all four fields. Both require editing. |
| PROF-04 | All existing tests pass after field removal with no behavior change in build output | Four test files construct `Policies(sensitive_domains=set())`. One test asserts `Profile.strict is True`. All must be updated. |
</phase_requirements>

## Standard Stack

No new dependencies. All work uses existing stdlib and project tooling.

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Python dataclasses | 3.11 stdlib | Dataclass field removal | Already used throughout |
| PyYAML | ≥6.0.1 | YAML parsing (existing) | Already a dependency |
| pytest + pytest-cov | ≥8.0 / ≥5.0 | Test runner + coverage | Already in dev deps |
| ruff | ≥0.5.0 | Linting + formatting | Already in dev deps |

**Test run commands:**
```bash
pytest --cov=blocklist_builder --cov-report=term-missing -x
ruff check src/ tests/
```

## Architecture Patterns

### Project Structure (relevant to this phase)
```
src/blocklist_builder/
├── types.py          # Profile dataclass — remove 3 fields
├── config.py         # Policies dataclass + parse logic — remove 1 field + 4 parse lines
config/
├── profiles.yml      # Remove include_sources, exclude_sources, strict from all 7 profiles + header comment
├── policies.yml      # sensitive_domains key absent (already not present in file)
tests/
├── test_config.py    # Remove YAML fixture lines + assertion on .strict
├── test_build.py     # Remove sensitive_domains=set() from Policies() constructor
├── test_build_internal.py  # Two Policies() calls with sensitive_domains=set()
├── test_recommend.py # One Policies() call with sensitive_domains=set()
├── test_analyze.py   # One Policies() call with sensitive_domains=set()
docs/
├── ARCHITECTURE.md   # References Profile fields in docs — update
├── DEPLOYMENT_CHECKLIST.md  # References profile YAML — update
README.md             # References strict/include_sources in example — update
USAGE_GUIDE.md        # References include_sources/exclude_sources in example — update
```

### Deletion pattern: frozen dataclass with keyword-only fields with defaults

The affected fields all have default values (`default_factory=set` or `False`). Because `Profile` uses `frozen=True, slots=True`, removing fields with defaults is safe — it cannot break positional construction because `Profile` is constructed exclusively by keyword argument in all callers. Verified: all `Profile(name=...)` instantiations in test code use only `name=` and optionally `include_categories=`.

```python
# Before (types.py)
@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    include_categories: set[str] = field(default_factory=set)
    include_sources: set[str] = field(default_factory=set)
    exclude_sources: set[str] = field(default_factory=set)
    strict: bool = False

# After
@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    include_categories: set[str] = field(default_factory=set)
```

```python
# Before (config.py) — Policies dataclass
@dataclass(frozen=True, slots=True)
class Policies:
    category_precedence: list[str]
    core_domains: set[str]
    base_allowlist: set[str]
    sensitive_domains: set[str] | None = None

# After
@dataclass(frozen=True, slots=True)
class Policies:
    category_precedence: list[str]
    core_domains: set[str]
    base_allowlist: set[str]
```

### Anti-Patterns to Avoid
- **Partial removal:** Do not remove fields from the dataclass while leaving parse lines in `config.py` — `ruff` will flag dead assignments and tests will fail to construct `Policies` with the removed keyword argument.
- **Leaving YAML keys:** YAML parser does not error on unknown keys — extra keys in `profiles.yml` would silently persist without failing, but violate PROF-03. Must explicitly verify YAML is clean after edits.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Finding all references | Manual search | `grep`/Grep tool before editing | Easy to miss test fixture helpers |
| Coverage check | Visual inspection | `pytest --cov` | Dataclass field removal can expose previously-covered lines as now unreachable |

## Runtime State Inventory

Step 2.5 SKIPPED — this is a code cleanup phase, not a rename/refactor affecting stored data, external service config, OS state, secrets, or build artifacts. No data migration required. All changes are source file edits.

## Common Pitfalls

### Pitfall 1: `Policies()` keyword argument in test fixtures
**What goes wrong:** After removing `sensitive_domains` from `Policies`, all four test files that pass `sensitive_domains=set()` to `Policies(...)` will raise `TypeError: __init__() got an unexpected keyword argument 'sensitive_domains'`.
**Why it happens:** `frozen=True` dataclasses generate `__init__` with one parameter per field.
**How to avoid:** Remove `sensitive_domains=set()` from every `Policies(...)` call in tests before running pytest.
**Warning signs:** `TypeError` on first `pytest` run — caught immediately.

### Pitfall 2: YAML comment block still references removed fields
**What goes wrong:** `config/profiles.yml` has a multi-line comment block at the top (lines 1–6) documenting `include_sources`, `exclude_sources`, and `strict`. If only the data keys are removed and the comment is left, PROF-03 technically still fails (the fields are "referenced").
**Why it happens:** Grep confirms the comment block explicitly names the fields.
**How to avoid:** Remove or rewrite the comment block to match the remaining fields (`include_categories` only).
**Warning signs:** Grep for `include_sources` after editing still returns a hit in `profiles.yml`.

### Pitfall 3: `typing` imports becoming unused after field removal
**What goes wrong:** After removing `strict: bool` from `Profile`, if no other field uses `bool` type annotation, ruff may flag an unused import. In this case no stdlib imports are solely used for these fields, but `from __future__ import annotations` and `field` from `dataclasses` should be verified.
**Why it happens:** `field` is still used for `include_categories`; `dataclasses.field` import is safe. No extra imports are orphaned.
**How to avoid:** Run `ruff check` after edits.
**Warning signs:** `ruff` reports `F401 unused import`.

### Pitfall 4: `test_config.py` asserts on `Profile.strict`
**What goes wrong:** `test_load_settings_merges_sources` passes `strict: true` in the YAML fixture (line 80) and then asserts `settings.profiles.by_name["default"].strict is True` (line 91). After removing `strict` from `Profile`, both the YAML line and the assertion are dead — the assertion will `AttributeError`.
**Why it happens:** The test was written to verify a field that is now being removed.
**How to avoid:** Remove the `include_sources`, `exclude_sources`, `strict` lines from the inline YAML string and remove the `assert settings.profiles.by_name["default"].strict is True` line.
**Warning signs:** `AttributeError: 'Profile' object has no attribute 'strict'` on pytest run.

### Pitfall 5: `sensitive_domains` in test YAML fixture vs. in actual policies.yml
**What goes wrong:** `test_config.py` line 66 passes `sensitive_domains: [sensitive.example]` in the inline `policies.yml` YAML fixture. If the parse code is removed from `config.py` but the YAML fixture still includes it — or vice versa — the test may silently pass (YAML ignores unknown keys) while the assertion is gone.
**Why it happens:** PyYAML `safe_load` does not error on unknown keys; `policies_data.get("sensitive_domains", [])` being removed means the key is simply ignored.
**How to avoid:** Remove the `sensitive_domains` line from the test YAML fixture when removing the parse line in `config.py`.

## Code Examples

### Complete change set — `types.py`
```python
# Remove lines 52-54 (include_sources, exclude_sources, strict fields)
# Result:
@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    include_categories: set[str] = field(default_factory=set)
```

### Complete change set — `config.py`
```python
# Remove sensitive_domains field from Policies (line 30)
# Remove sensitive_domains parse line (line 111)
# Remove include_sources parse line (line 121)
# Remove exclude_sources parse line (line 122)
# Remove strict parse line (line 123)
# Profile() constructor call becomes:
profiles_dict[str(pname)] = Profile(
    name=str(pname),
    include_categories=set(pconf.get("include_categories", []) or []),
)
```

### Test fixture update pattern (applies to all 4 test files)
```python
# Before (test_build.py:17-31, test_build_internal.py:11-26, etc.)
policies = Policies(
    category_precedence=[...],
    core_domains=set(),
    base_allowlist=set(),
    sensitive_domains=set(),   # REMOVE THIS LINE
)

# After
policies = Policies(
    category_precedence=[...],
    core_domains=set(),
    base_allowlist=set(),
)
```

### YAML cleanup — `config/profiles.yml`
Remove comment block lines 1–6, then for each profile remove `include_sources`, `exclude_sources`, and `strict` keys. Result per profile:
```yaml
profiles:
  base:
    include_categories: ["advertising", "tracking", "malicious"]
```

## Environment Availability

Step 2.6: SKIPPED — purely code/config changes, no external dependencies.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-cov 5.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x` |
| Full suite command | `pytest --cov=blocklist_builder --cov-report=term-missing` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PROF-01 | `Profile` has no `include_sources`, `exclude_sources`, `strict` | unit | `pytest tests/test_config.py tests/test_build_internal.py -x` | Yes |
| PROF-02 | `Policies` has no `sensitive_domains` | unit | `pytest tests/test_config.py tests/test_build.py -x` | Yes |
| PROF-03 | YAML files contain no references to removed fields | manual grep | `grep -r "include_sources\|exclude_sources\|strict\|sensitive_domains" config/` | — |
| PROF-04 | All tests pass | regression | `pytest --cov=blocklist_builder --cov-report=term-missing` | Yes |

### Sampling Rate
- **Per edit:** `pytest tests/ -x` (fail-fast, ~seconds)
- **Phase gate:** `pytest --cov=blocklist_builder --cov-report=term-missing && ruff check src/ tests/`

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements. No new test files needed. Field removal is verified by `TypeError` absence (existing tests exercise all constructors).

## Complete Reference: All Locations Requiring Changes

### Source code (must change)
| File | Lines | Change |
|------|-------|--------|
| `src/blocklist_builder/types.py` | 52–54 | Remove `include_sources`, `exclude_sources`, `strict` fields from `Profile` |
| `src/blocklist_builder/config.py` | 30 | Remove `sensitive_domains` field from `Policies` |
| `src/blocklist_builder/config.py` | 111 | Remove `sensitive_domains=set(...)` from `Policies(...)` call |
| `src/blocklist_builder/config.py` | 121–123 | Remove `include_sources`, `exclude_sources`, `strict` from `Profile(...)` call |

### Config YAML (must change — PROF-03)
| File | What | Change |
|------|------|--------|
| `config/profiles.yml` | Lines 1–6 comment block | Remove or rewrite (references removed fields) |
| `config/profiles.yml` | `include_sources: []` × 7 profiles | Remove |
| `config/profiles.yml` | `exclude_sources: []` × 7 profiles | Remove |
| `config/profiles.yml` | `strict: false/true` × 7 profiles | Remove |
| `config/policies.yml` | No `sensitive_domains` key present | No change needed — confirmed absent |

### Tests (must change — PROF-04)
| File | Lines | Change |
|------|-------|--------|
| `tests/test_config.py` | 66 | Remove `sensitive_domains: [sensitive.example]` from inline YAML |
| `tests/test_config.py` | 78–80 | Remove `include_sources`, `exclude_sources`, `strict` from inline YAML |
| `tests/test_config.py` | 91 | Remove `assert settings.profiles.by_name["default"].strict is True` |
| `tests/test_build.py` | 28 | Remove `sensitive_domains=set()` from `Policies(...)` |
| `tests/test_build_internal.py` | 23 | Remove `sensitive_domains=set()` from `Policies(...)` |
| `tests/test_build_internal.py` | 129 | Remove `sensitive_domains=set()` from `Policies(...)` |
| `tests/test_recommend.py` | 28 | Remove `sensitive_domains=set()` from `Policies(...)` |
| `tests/test_analyze.py` | 28 | Remove `sensitive_domains=set()` from `Policies(...)` |

### Documentation (should change — not a test gate, but referenced by grep)
| File | What | Change |
|------|------|--------|
| `docs/ARCHITECTURE.md` | Line 26, 259–271 | Remove field references from `Profile` description and YAML examples |
| `docs/DEPLOYMENT_CHECKLIST.md` | Lines 180–182 | Remove `include_sources`, `exclude_sources`, `strict` from example |
| `README.md` | Lines 130–136 | Remove field lines from profile example |
| `USAGE_GUIDE.md` | Lines 204–209, 238 | Remove field references from profile customization example |

## State of the Art

This is a standard Python dead-code removal pattern. No framework or library evolution is relevant. The decision to remove rather than implement was made explicitly (see PROJECT.md Key Decisions) — `include_sources`/`exclude_sources` deferred to v2 (FEAT-03), `strict` behavior unimplemented, `sensitive_domains` purpose undefined.

## Open Questions

None. All reference locations are fully enumerated by grep. The scope is closed and well-bounded.

## Sources

### Primary (HIGH confidence)
- Direct file reads of `types.py`, `config.py`, `build.py` — verified field definitions and read/write sites
- Grep over all `*.py` and `*.yml` files — exhaustive reference enumeration
- `test_config.py`, `test_build.py`, `test_build_internal.py`, `test_recommend.py`, `test_analyze.py` — direct read of all affected test constructors

### Secondary (MEDIUM confidence)
- `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT_CHECKLIST.md`, `README.md`, `USAGE_GUIDE.md` — doc references found via grep, content confirmed by grep output (not individually read but patterns are unambiguous)

## Metadata

**Confidence breakdown:**
- Scope (which files need changing): HIGH — exhaustive grep over entire repo, all hits enumerated
- Change complexity: HIGH — pure deletion, no logic to rewrite
- Test impact: HIGH — exact test lines identified
- Build output impact: HIGH (verified none) — `_write_profiles()` only reads `include_categories`, confirmed by direct read of `build.py:118-128`

**Research date:** 2026-03-29
**Valid until:** Until any of the enumerated files are modified (stable codebase, low churn)
