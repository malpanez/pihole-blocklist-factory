# Phase 7: Code Quality Cleanup - Research

**Researched:** 2026-03-29
**Domain:** Python code quality — YAML generation, env var scoping, regex patterns, CLI stubs, metadata
**Confidence:** HIGH

## Summary

Phase 7 resolves seven low-severity code quality issues in the existing codebase. All issues are fully diagnosed: the exact lines, the exact current behavior, and the exact fix are known from direct source inspection. No third-party library research is needed — PyYAML is already a dependency and already imported in `config.py`. The only new import required is `import yaml` in `firebog.py`.

The most mechanically interesting change is QUAL-02 (env var scope). Moving `_BLOCKLIST_SOURCES_MODE` from module-level to inside `load_settings()` eliminates the `importlib.reload()` workaround in `test_config.py::test_load_settings_test_mode`. The test needs a rewrite using `monkeypatch.setenv` alone (no reload). The existing test structure — 3 tests covering `load_settings` and `_read_yaml` — will continue to provide 100% coverage with no new lines uncovered.

Coverage is currently 100% across all 1,048 statements. Every change in this phase must maintain that. The only coverage risk is QUAL-06: if `sync-github-catalog` command is removed, the test `test_cli_sync_github_catalog` must be removed or converted simultaneously, or coverage of `cli.py` will drop. If the command is replaced with a `NotImplemented` stub, the test assertion must match the new output.

**Primary recommendation:** Implement all seven QUAL requirements in a single plan with sequential tasks ordered by dependency: QUAL-02 first (env var scope + test rewrite), then QUAL-01 (yaml.dump + test update), then QUAL-03 (regex), then QUAL-06 (stub removal), then QUAL-04/QUAL-05/QUAL-07 (gitignore, pyproject, script) as a single cleanup task.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUAL-01 | `firebog.py` YAML generation uses `yaml.dump()` — no manual string construction | firebog.py lines 113-130 fully mapped; yaml already a dependency; `import yaml` is the only new import needed |
| QUAL-02 | `BLOCKLIST_SOURCES` env var read inside `load_settings()`, not at module import time | config.py line 21 is the exact problem; test_config.py importlib.reload pattern identified; replacement approach documented |
| QUAL-03 | `_DOMAIN_RE` TLD segment rejects numeric-only TLDs (`[a-z]{2,63}` not `[a-z0-9-]{2,63}`) | sanitize.py line 10 is the exact change; no existing tests assert numeric TLDs pass; change is additive-only |
| QUAL-04 | `create_test_data.py` and `run_build.py` added to `.gitignore` | Both files confirmed present in repo root; `.gitignore` structure identified |
| QUAL-05 | `pyproject.toml` author field updated from placeholder | Exact value: `authors = [{name = "Your Name"}]` at line 8 |
| QUAL-06 | `sync-github-catalog` CLI command removed or clearly marked as not implemented | Command is a stub (3 echo lines, no logic); test `test_cli_sync_github_catalog` must be updated simultaneously |
| QUAL-07 | `scripts/pihole-adlists-setup-v6.sh` clarified as user template or removed | File is a 9-line placeholder with a single echo; removal or header comment are both viable |
</phase_requirements>

## QUAL-01: YAML Injection in firebog.py

### Current code (lines 113-130)

The `sync_firebog()` function builds YAML by string concatenation:

```python
yaml_lines = [
    "# Auto-generated from https://v.firebog.net/hosts/csv.txt",
    "# DO NOT EDIT manually; regenerate with: blocklist-factory sync-firebog",
    "",
]
yaml_lines.append("sources:")
for src in sources:
    yaml_lines.append(f"  - id: {src.id}")
    yaml_lines.append(f'    name: "{src.name}"')
    yaml_lines.append(f'    url: "{src.url}"')
    yaml_lines.append(f"    category: {src.category}")
    yaml_lines.append(f"    enabled: {str(src.enabled).lower()}")
    if src.notes:
        yaml_lines.append(f'    notes: "{src.notes}"')
    yaml_lines.append("")

yaml_content = "\n".join(yaml_lines)
```

### Injection risk

A source `name` or `url` containing `"` or `\n` or `:` would produce syntactically invalid or semantically wrong YAML. The Firebog CSV is external input.

### Fix approach (QUAL-01)

Replace the loop with `yaml.dump()`. The output structure is a dict with a `sources` key containing a list of dicts. Preserve the two leading comment lines (yaml.dump does not emit comments, so prepend them manually).

```python
import yaml  # add to imports

# Inside sync_firebog(), replace yaml_lines block with:
sources_data = []
for src in sources:
    entry: dict = {
        "id": src.id,
        "name": src.name,
        "url": src.url,
        "category": src.category,
        "enabled": src.enabled,
    }
    if src.notes:
        entry["notes"] = src.notes
    sources_data.append(entry)

header = (
    "# Auto-generated from https://v.firebog.net/hosts/csv.txt\n"
    "# DO NOT EDIT manually; regenerate with: blocklist-factory sync-firebog\n\n"
)
yaml_content = header + yaml.dump({"sources": sources_data}, default_flow_style=False, allow_unicode=True)
```

### yaml.dump key behaviors (HIGH confidence — PyYAML docs)

- `default_flow_style=False`: block style (one key per line), not inline `{}`
- `allow_unicode=True`: pass-through unicode; relevant for internationalized titles
- Strings containing `:`, `"`, `\n`, or leading/trailing spaces are automatically quoted
- Boolean `True`/`False` serializes as `true`/`false` in YAML (correct for Pi-hole)
- Key ordering follows insertion order in Python 3.7+ dicts

### Test impact

`test_sync_firebog_writes_file` currently asserts `"sources:" in out.read_text(...)`. This assertion remains valid after the change. No test currently asserts the exact string format of individual fields, so no test assertions need updating beyond the content check.

However, `yaml.dump` will produce `true` for `enabled: true` (correct) vs the current `enabled: true` string (also correct). The `category` field — currently unquoted — will remain unquoted if the value is a plain scalar. Output is semantically identical; it is a format change only.

### yaml is already a project dependency

`pyproject.toml` declares `PyYAML>=6.0.1`. `config.py` already does `import yaml`. Adding `import yaml` to `firebog.py` requires no new package install.

---

## QUAL-02: Env Var Read at Module Scope

### Current code (config.py line 21)

```python
_BLOCKLIST_SOURCES_MODE: Final = os.environ.get("BLOCKLIST_SOURCES", "sources")
```

This is evaluated once at module import time. Changing `BLOCKLIST_SOURCES` after import has no effect.

### How load_settings() uses it (lines 59-70)

```python
match _BLOCKLIST_SOURCES_MODE:
    case "test":
        sources_yml = _read_yaml(config_dir / "sources.test.yml")
        sources_firebog_yml = {}
        sources_local_yml = {}
    case _:
        ...
```

### Fix

Move the `os.environ.get()` call inside `load_settings()` as a local variable. Remove the module-level `_BLOCKLIST_SOURCES_MODE` constant. The `match` statement stays identical but references the local variable.

```python
# Remove line 21 entirely.
# Inside load_settings(), first line:
mode = os.environ.get("BLOCKLIST_SOURCES", "sources")
match mode:
    ...
```

The `Final` annotation is not appropriate for a local variable; drop it.

### Test impact — the importlib.reload workaround

`test_config.py::test_load_settings_test_mode` currently does:

```python
monkeypatch.setenv("BLOCKLIST_SOURCES", "test")
cfg = importlib.reload(config_mod)
settings = cfg.load_settings(config_dir)
...
monkeypatch.delenv("BLOCKLIST_SOURCES", raising=False)
importlib.reload(config_mod)
```

After the fix, the env var is read on each `load_settings()` call. The test becomes:

```python
monkeypatch.setenv("BLOCKLIST_SOURCES", "test")
settings = config_mod.load_settings(config_dir)
assert len(settings.sources) == 1
assert settings.sources[0].id == "test1"
```

No reload needed. `monkeypatch` automatically restores env vars after the test — no manual `delenv` or second reload needed. The `import importlib` at the top of `test_config.py` can be removed.

### Coverage risk

The module-level constant `_BLOCKLIST_SOURCES_MODE` is currently covered at import time. After removal, the coverage comes from the `match` expression inside `load_settings()`. The function is already covered by existing tests. No net coverage loss.

---

## QUAL-03: TLD Regex Pattern

### Current pattern (sanitize.py line 9-12)

```python
_DOMAIN_RE: Final = re.compile(
    r"^(?=.{1,253}$)(?!-)([a-z0-9-]{1,63}(?<!-)\.)+[a-z0-9-]{2,63}$",
    re.ASCII,
)
```

The trailing segment `[a-z0-9-]{2,63}` matches numeric-only TLDs like `foo.123`. ICANN does not allocate numeric TLDs; `foo.123` is not a valid FQDN.

### Fix

Change the trailing segment from `[a-z0-9-]{2,63}` to `[a-z]{2,63}`:

```python
_DOMAIN_RE: Final = re.compile(
    r"^(?=.{1,253}$)(?!-)([a-z0-9-]{1,63}(?<!-)\.)+[a-z]{2,63}$",
    re.ASCII,
)
```

Note: The non-terminal label segment `[a-z0-9-]{1,63}` (labels before the TLD) correctly allows digits and hyphens. Only the final TLD segment changes.

### Existing test coverage

`test_sanitize.py` has 7 tests. None assert that `foo.123` passes. The regex change is additive-only — it will reject previously-accepted inputs, but no test currently asserts those inputs pass. No test assertions need changing.

`_validate_domain_regex` is decorated with `@cache`. The cache is per-process and scoped to the string input; changing the compiled pattern at module level resets the cache between test runs (each test run is a new process). No cache-invalidation issue.

### Coverage risk

The regex is compiled at module import time (a constant). The lines are covered when the module is imported. No coverage risk.

---

## QUAL-04: .gitignore Entries

### Files confirmed present in repo root

- `create_test_data.py` — present (1.1K)
- `run_build.py` — present (285B)

### Current .gitignore

The file ends at line 27 (`dist/`). Neither `create_test_data.py` nor `run_build.py` are listed.

### Fix

Append two lines to `.gitignore`:

```
# Local dev helpers
create_test_data.py
run_build.py
```

No code changes, no test changes, no coverage impact.

---

## QUAL-05: pyproject.toml Author Placeholder

### Current value (line 8)

```toml
authors = [{name = "Your Name"}]
```

This is a placeholder string. The fix is to replace it with the project owner's actual name/email or a project-appropriate value.

### Recommended value

Since this is an open-source homelab tool from Winning Concepts Limited (per global CLAUDE.md), a reasonable value is:

```toml
authors = [{name = "Winning Concepts Limited"}]
```

Or with email if desired:

```toml
authors = [{name = "Winning Concepts Limited", email = ""}]
```

No code changes, no test changes, no coverage impact.

---

## QUAL-06: sync-github-catalog CLI Stub

### Current implementation (cli.py lines 122-128)

```python
@cli.command("sync-github-catalog")
def sync_github_catalog_cmd() -> None:
    """Sync GitHub catalog of known blocklists."""
    click.echo("sync-github-catalog: Feature not fully implemented yet.")
    click.echo("To use external catalogs:")
    click.echo("  1. See config/sources.yml for structure")
    click.echo("  2. Add new sources via 'sources_local.yml' or update config/sources.yml")
```

This is pure stub output — no logic, no side effects, no network calls.

### REQUIREMENTS.md context

QUAL-06 says: "removed or clearly marked as not implemented." FEAT-01 (v2) says the full implementation is deferred. The command must not disappear silently — users who discover it should get a clear message.

### Recommended approach: replace body with NotImplementedError exit

Remove the informational echo lines and replace with a single clear "not implemented" message plus exit code 1. This makes the stub's status unambiguous and consistent with CLI conventions for unimplemented commands:

```python
@cli.command("sync-github-catalog")
def sync_github_catalog_cmd() -> None:
    """Sync GitHub catalog of known blocklists (not yet implemented)."""
    click.secho("sync-github-catalog: not implemented.", fg="yellow", err=True)
    raise SystemExit(1)
```

Alternatively, remove the command entirely. Removal is cleaner but loses discoverability. The plan should pick one approach.

### Test impact (CRITICAL)

`test_cli_sync_github_catalog` currently asserts:

```python
result = runner.invoke(cli.sync_github_catalog_cmd, [])
assert result.exit_code == 0
assert "sync-github-catalog" in result.output
```

Regardless of approach chosen:
- If command is removed: delete `test_cli_sync_github_catalog` entirely
- If command is kept as exit-1 stub: update test to assert `exit_code == 1` and check `err=True` output

Coverage of `cli.py` is currently 100%. The `sync_github_catalog_cmd` function body must remain exercised. Do not remove the test without removing or replacing the command.

---

## QUAL-07: scripts/pihole-adlists-setup-v6.sh

### Current content

```bash
#!/usr/bin/env bash
set -euo pipefail

# Skeleton placeholder:
# Mantén aquí tu script de bootstrap (groups + adlists) para Pi-hole v6.
# Recomendación: mover la "verdad" (sources/profiles) al repo y generar estas URLs desde dist/.

echo "This is a placeholder. Copy your working v6 script here if you want to keep it versioned."
```

This is a 9-line placeholder with no implementation. It is not referenced from any source code, test, CI workflow, or README.

### Recommended approach

Remove the file. It adds no value as a placeholder (it only tells users to copy their own script here — that instruction is better placed in README or a comment in a proper template). Removing it avoids confusion about whether this script does anything.

If retention is preferred: add a `# TEMPLATE - NOT IMPLEMENTED` header and leave as-is, but update the echo message to match the header.

No code changes, no test changes, no coverage impact (scripts/ is not measured by pytest-cov).

---

## Architecture Patterns

### Pattern: env var read at call site, not module scope

Reading environment variables at module import time is an anti-pattern in Python because it makes the behavior impossible to test without `importlib.reload()`. The standard pattern is to read inside the function that uses the value:

```python
def load_settings(config_dir: Path) -> Settings:
    mode = os.environ.get("BLOCKLIST_SOURCES", "sources")
    match mode:
        ...
```

`monkeypatch.setenv()` from pytest sets the env var before the function is called, and pytest restores it automatically after the test. No `importlib.reload()` needed.

### Pattern: yaml.dump for YAML generation

Never build YAML by string concatenation. `yaml.dump()` handles quoting, escaping, and multiline strings correctly. For structured data with a known schema, build a Python dict/list and pass to `yaml.dump()`. Preserve handwritten comments by prepending them as a string.

### Pattern: CLI stub handling

Stub commands should either: (a) exit non-zero with a clear "not implemented" message, or (b) be removed from the CLI entirely. A stub that exits 0 with informational text is confusing because it appears to succeed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML string escaping | Manual quote/escape logic | `yaml.dump()` | Handles colons, quotes, newlines, unicode — edge cases are infinite |
| Test env var isolation | `importlib.reload()` | `monkeypatch.setenv()` | Reload has side effects on module state; monkeypatch is scoped to the test |

---

## Common Pitfalls

### Pitfall 1: yaml.dump key ordering differs from hand-built YAML

**What goes wrong:** `yaml.dump` serializes dict keys in insertion order (Python 3.7+). If tests assert exact YAML string content, they may break if key order differs from the original hand-built output.

**How to avoid:** Tests should parse the output with `yaml.safe_load()` and assert on the parsed structure, not on raw string content. The existing test only checks `"sources:" in content` — no order-sensitive assertion exists.

### Pitfall 2: yaml.dump serializes True as true, but also handles None

**What goes wrong:** `src.enabled` is a Python `bool`. `yaml.dump` serializes `True` as `true` and `False` as `false` — correct for YAML. `src.notes` can be `None` — `yaml.dump` serializes `None` as `null`. If `notes: null` appears in the output and the YAML loader later reads it back, `notes` will be `None` (correct). No issue.

**How to avoid:** The `if src.notes:` guard in the original code can be preserved when building the dict — only include `notes` key if it's truthy.

### Pitfall 3: Removing sync-github-catalog without updating its test

**What goes wrong:** Removing the command from `cli.py` leaves `test_cli_sync_github_catalog` referencing `cli.sync_github_catalog_cmd` which no longer exists. Test collection will fail with `AttributeError`.

**How to avoid:** Remove command and test in the same commit.

### Pitfall 4: QUAL-02 leaves stale `import importlib` in test_config.py

**What goes wrong:** After removing `importlib.reload()` from the test, the `import importlib` at the top of `test_config.py` becomes unused. `ruff check` will flag `F401 imported but unused`.

**How to avoid:** Remove `import importlib` from `test_config.py` in the same change.

---

## Environment Availability

Step 2.6: SKIPPED — phase is purely source code and configuration changes with no external dependencies beyond the existing Python + PyYAML stack (already verified present).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (dependency-groups.dev) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_config.py tests/test_firebog.py tests/test_sanitize.py tests/test_cli.py -x -q` |
| Full suite command | `python -m pytest --cov=src/blocklist_builder --cov-report=term-missing --cov-fail-under=99 -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUAL-01 | yaml.dump produces valid YAML for names/URLs with special chars | unit | `pytest tests/test_firebog.py -x` | Yes — `test_sync_firebog_writes_file` covers write path; add special-char assertion |
| QUAL-02 | BLOCKLIST_SOURCES env var read at call time | unit | `pytest tests/test_config.py::test_load_settings_test_mode -x` | Yes — rewrite existing test |
| QUAL-03 | Numeric-only TLD `foo.123` rejected | unit | `pytest tests/test_sanitize.py -x` | Yes — add one test case |
| QUAL-04 | create_test_data.py / run_build.py in .gitignore | manual-only | n/a | — |
| QUAL-05 | pyproject.toml author updated | manual-only | n/a | — |
| QUAL-06 | sync-github-catalog removed/stubbed; test updated | unit | `pytest tests/test_cli.py::test_cli_sync_github_catalog -x` | Yes — update existing test |
| QUAL-07 | scripts/pihole-adlists-setup-v6.sh removed/clarified | manual-only | n/a | — |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_config.py tests/test_firebog.py tests/test_sanitize.py tests/test_cli.py -x -q`
- **Per wave merge:** `python -m pytest --cov=src/blocklist_builder --cov-report=term-missing --cov-fail-under=99 -q`
- **Phase gate:** Full suite green (100% coverage) before marking phase complete

### Wave 0 Gaps

None — existing test infrastructure covers all phase requirements. New assertions are additions to existing test files, not new files.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | >=6.0.1 (already declared) | `yaml.dump()` for YAML generation | Already a project dependency; `yaml.safe_load` already used in config.py |
| pytest | >=9.0.2 (already declared) | Test framework | Already in use |

No new dependencies required.

**Installation:** None — all required packages are already installed.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `importlib.reload()` for env var test isolation | `monkeypatch.setenv()` only | Phase 7 | Tests are simpler, no module side-effects |
| Manual YAML string building | `yaml.dump()` | Phase 7 | Injection-safe, handles edge cases |

---

## Open Questions

1. **QUAL-05: Author field value**
   - What we know: Current value is `Your Name` placeholder
   - What's unclear: Whether the owner wants personal name, company name, or a generic value
   - Recommendation: Use `Winning Concepts Limited` per global CLAUDE.md identity; planner should confirm with user if in doubt

2. **QUAL-06: Remove vs stub with exit-1**
   - What we know: Command is a pure stub with no logic; FEAT-01 is deferred to v2
   - What's unclear: Whether discoverability (the command appearing in `--help`) matters
   - Recommendation: Remove entirely — cleaner CLI, simpler test cleanup; FEAT-01 will re-add when implemented

3. **QUAL-07: Remove vs keep as template**
   - What we know: File is a 9-line echo placeholder; not referenced anywhere
   - Recommendation: Remove — it adds noise. If a template is wanted later, it can be created with real content

---

## Sources

### Primary (HIGH confidence)

- Direct source inspection: `src/blocklist_builder/firebog.py` (lines 113-130), `src/blocklist_builder/config.py` (line 21), `src/blocklist_builder/sanitize.py` (lines 9-12), `src/blocklist_builder/cli.py` (lines 122-128)
- Direct test inspection: `tests/test_config.py`, `tests/test_firebog.py`, `tests/test_sanitize.py`, `tests/test_cli.py`
- Coverage report: `python -m coverage report` — 100% coverage confirmed
- `pyproject.toml` — PyYAML>=6.0.1 confirmed as existing dependency

### Secondary (MEDIUM confidence)

- PyYAML behavior (`default_flow_style`, `allow_unicode`, bool serialization) — from PyYAML documentation; consistent with observed behavior in `config.py` which already uses `yaml.safe_load`

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new dependencies; yaml already in use
- Architecture: HIGH — all files directly inspected; no inference needed
- Pitfalls: HIGH — identified from direct code reading and test structure analysis

**Research date:** 2026-03-29
**Valid until:** 2026-06-29 (stable stdlib domain; no version-sensitive APIs)
