# Technical Architecture & Advanced Features

## Overview

Pi-hole Blocklist Factory is a **production-grade** blocklist builder with the following design principles:

1. **Deterministic builds**: Same input → identical output (byte-for-byte reproducible)
2. **Strict validation**: Domain sanitization, IDNA support, provenance tracking
3. **Flexible composition**: Mix sources by category, tier, or custom rules
4. **CI-first**: All workflows verify reproducibility and quality
5. **No external state**: No timestamps, hashes, or non-deterministic data in outputs

---

## Architecture

### Core Modules

#### `types.py` - Data Models

Frozen dataclasses for immutability:

- **`Source`**: A blocklist source with metadata (id, category, url, tier, license)
- **`SourceMetadata`**: Tracking (hash, size, line_count, etag, timestamp)
- **`Provenance`**: Domain's origin (source_ids, categories, assigned_category)
- **`Profile`**: Composition rule (include_categories, include_sources, exclude_sources, strict)

#### `config.py` - Configuration Loading

```python
load_settings(config_dir: Path) -> Settings
```

Loads YAML configs:
- `sources.yml` - public sources (versionable)
- `sources.local.yml` - private sources (gitignored)
- `policies.yml` - precedence rules and core domains
- `profiles.yml` - profile definitions

**Key features**:
- Merges public + local sources (local doesn't override, extends)
- Returns strongly-typed `Settings` object
- Lazy validation (errors during load, not during build)

#### `fetch.py` - HTTP + Cache

```python
fetch_to_cache(url: str, cache_dir: Path, source_id: str) -> (Path, SourceMetadata)
```

Features:
- Handles `http(s)://`, `file://`, and relative paths
- ETag/Last-Modified ready (not implemented yet, but structure is there)
- Exponential backoff retries (3 attempts)
- User-Agent header
- Metadata saved to `.json` for audit trail
- Deterministic: no timestamps in outputs

#### `parse.py` - Multi-Format Parser

Supported formats:
- **Hosts**: `0.0.0.0 domain`, `127.0.0.1 domain`, `:: domain`, `0 domain`
- **Domain-only**: `example.com` (single word)
- **ABP simple**: `||domain^` (ONLY if no paths/wildcards/modifiers)

Features:
- `drop_patterns`: regex filters to reject lines before parse
- Comments (`#`, `!`) and empty lines tracked
- Generates `ParsedLine(domain, reason)` for each input
- Reasons: `ok`, `comment`, `empty`, `unsupported`, `pattern_drop`

#### `sanitize.py` - Strict Validation

```python
sanitize_domain(domain: str) -> Sanitized
```

Pipeline:
1. Normalize: `.strip()`, `.lower()`, remove trailing dots
2. Reject: IPs (IPv4), single-label domains
3. IDNA: Apply punycode encoding (`münchen.de` → `xn--mnchen-3ya.de`)
4. Validate: Strict regex on ASCII domain (1-253 chars, labels 1-63 chars)

Reasons: `ok`, `invalid`, `ip`, `single_label`, `not_fqdn`

#### `classify.py` - Categorization

```python
partition_by_precedence(domain_to_cats: dict[str, set[Category]], precedence: list[str]) -> dict[str, Category]
build_provenance(...) -> dict[str, Provenance]
```

Features:
- Assigns each domain to **single** category by precedence order
- Example precedence: malicious > tracking > advertising > suspicious > other > telemetry
- Provenance tracks: domain → source_ids → categories

#### `build.py` - Orchestration

Main entry point:

```python
build(repo_root: Path, settings: Settings, no_fetch: bool = False) -> Stats
```

Pipeline:
1. Load overrides (allow/deny/drop_patterns)
2. Process each enabled source:
   - Fetch (or use local path if `--no-fetch`)
   - Parse lines
   - Sanitize domains
3. Classify by category (using precedence)
4. Write outputs:
   - `dist/all.txt` (sorted, newline-terminated)
   - `dist/categories/{category}.txt`
   - `dist/profiles/{profile}.txt`
5. Generate reports
6. Return Stats

**Key: All outputs are sorted deterministically.**

#### `report.py` - Reporting

Generates:
- `stats.json` - machine-readable stats (counts by reason)
- `stats.md` - human-readable summary

Stats structure:
```python
@dataclass(frozen=True)
class Stats:
    total_lines: int
    parsed_ok: int
    sanitized_ok: int
    unique_domains: int
    discarded: dict[str, int]  # discard reason → count
```

#### `cli.py` - Command Line

Commands:

- **`build`** - Build blocklist (with `--no-fetch` for offline, `--json` for stats)
- **`validate`** - Check config validity
- **`report`** - Show latest build stats
- **`sync-firebog`** - Fetch Firebog catalog (TODO)
- **`sync-github-catalog`** - Fetch GitHub catalog (TODO)

---

## Workflows & CI

### CI Workflow (`.github/workflows/ci.yml`)

On **push to main** or **pull request**:

1. **Lint & Format** (Python 3.11, 3.12)
   - `ruff check .`
   - `ruff format --check .`
   - `pytest tests/`

2. **Build (offline)**
   - `blocklist-factory build --no-fetch`
   - Save SHA256 hash of `dist/*`

3. **Rebuild (reproducibility check)**
   - Remove `dist/`, rebuild
   - Compare SHA256 hashes
   - **Fail if hashes differ** ❌

4. **Build Artifacts** (on main)
   - Upload `dist/` as artifact (7-day retention)

### Update Workflow (`.github/workflows/update.yml`)

Weekly schedule (Monday 03:00 UTC) or on-demand:

1. Checkout latest main
2. Build **with fetch** (downloads all sources)
3. Check if `dist/` changed
4. If yes: Create PR with updates
5. If no: Skip (no changes in blocklists)

---

## Configuration Examples

### `config/sources.yml` (Public Catalog)

```yaml
sources:
  - id: firebog_malware
    name: "Firebog Malware"
    category: malicious
    url: "https://v.firebog.net/hosts/RPiList-Malware.txt"
    enabled: true
    tier: stable
    license: "MIT"
    notes: "Curated list of malicious domains"

  - id: stalkerware_blocklist
    name: "Stalkerware Indicators"
    category: malicious
    url: "https://raw.githubusercontent.com/AssoEchap/stalkerware-indicators/master/generated/hosts"
    enabled: true
    tier: stable
```

### `config/sources.local.yml` (Private/Local - Gitignored)

```yaml
sources:
  - id: my_internal_ads
    name: "My Internal Ad List"
    category: advertising
    url: "file:///home/user/my-ads.txt"
    enabled: true
    tier: stable
    license: "internal"

  - id: experimental_test
    name: "Experimental List"
    category: tracking
    url: "https://example.com/experimental.txt"
    enabled: false
    tier: edge
```

### `config/policies.yml` (Governance)

```yaml
policies:
  category_precedence:
    - malicious
    - tracking
    - advertising
    - suspicious
    - other
    - telemetry

  # Domains never blocked in non-strict profiles
  core_domains:
    - apple.com
    - google.com
    - microsoft.com
    - github.com
    - cloudflare.com

  # Global allowlist
  base_allowlist: []
```

### `config/profiles.yml` (Profiles)

```yaml
profiles:
  base:
    include_categories: [advertising, tracking, malicious]
    include_sources: []
    exclude_sources: []
    strict: false  # respects core_domains

  aggressive:
    include_categories: [advertising, tracking, malicious, telemetry]
    strict: true  # allows blocking telemetry even if core_domains

  android:
    include_categories: [advertising, tracking, malicious]
    include_sources: []  # can restrict to specific sources
    exclude_sources: []
    strict: false
```

### Overrides

- **`inputs/current_overrides/allowlist.txt`** - Domains NEVER to block (highest priority)
- **`inputs/current_overrides/denylist_extra.txt`** - Domains ALWAYS to block (force into "other" category)
- **`inputs/current_overrides/drop_patterns.txt`** - Regex patterns to skip lines during parsing

Example `drop_patterns.txt`:
```regex
^#
tracking\|
sponsored
```

---

## Determinism Guarantees

### How We Ensure Reproducibility

1. **No timestamps** in output files (not in `dist/`)
2. **Sorted output** - all lists sorted alphabetically
3. **No randomness** - deterministic category assignment
4. **No external state** - cache is side-effect, not part of output
5. **Frozen dataclasses** - immutable, hashable

### Verification

```bash
# First build
uv run blocklist-factory build --no-fetch
sha256sum dist/all.txt > /tmp/hash1.txt

# Second build (same conditions)
uv run blocklist-factory build --no-fetch
sha256sum dist/all.txt > /tmp/hash2.txt

# Should match bit-for-bit
diff /tmp/hash1.txt /tmp/hash2.txt  # ✓ PASS
```

---

## Future Roadmap

### Provenance Tracking (Phase 2)

Store per-domain metadata:
```python
provenance: dict[str, Provenance] = {
    "ads.example.com": Provenance(
        domain="ads.example.com",
        source_ids=frozenset(["firebog_malware", "stalkerware"]),
        categories=frozenset(["malicious"]),
        assigned_category="malicious",
    )
}
```

Enables:
- **Overlap reports**: Matrix of domains by source
- **Marginal contribution**: Unique domains per source
- **Churn tracking**: What changed since last build

### Release Channels (Phase 3)

- **`dist/stable/`** - Only tier=stable sources
- **`dist/edge/`** - Includes tier=edge (experimental)
- Separate URLs for different risk profiles

### Firebog Integration (Phase 4)

```bash
uv run blocklist-factory sync-firebog
```

Fetches Firebog CSV, parses ticked status, generates `config/sources.firebog.yml`.

### GitHub Catalog (Phase 5)

```bash
uv run blocklist-factory sync-github-catalog
```

Maintains `config/catalog.yml` with curated GitHub blocklist repos.

---

## Performance

Current implementation:
- **Parse**: ~100k lines/sec (simple regex)
- **Sanitize**: ~50k domains/sec (IDNA encoding is the bottleneck)
- **Build**: Typically <5 seconds for 10k unique domains

With fetch:
- Network timeout: 30 seconds per source
- Retry backoff: 1s, 2s, 4s (exponential)

---

## Security Considerations

### Input Validation

- **Domains**: Strict regex, reject IPs, single-label
- **IDNA**: Python's built-in encoder (safe)
- **YAML**: `yaml.safe_load()` only (no arbitrary code execution)

### Private Sources

- `config/sources.local.yml` is gitignored
- Can point to `file://` URLs (local paths)
- Allows non-public lists without compromising repo

### Core Domains

- Non-strict profiles must respect `core_domains`
- Prevents accidental blocking of critical services
- Configurable per-deployment

---

## Integration with Pi-hole v6

### Import Blocklists

Pi-hole Admin Panel > Settings > Adlists:

```
https://raw.githubusercontent.com/yourusername/pihole-blocklist-factory/main/dist/all.txt
https://raw.githubusercontent.com/yourusername/pihole-blocklist-factory/main/dist/profiles/base.txt
https://raw.githubusercontent.com/yourusername/pihole-blocklist-factory/main/dist/profiles/android.txt
```

Or local (if repo is on Pi-hole server):

```
file:///home/pi/blocklist-factory/dist/all.txt
http://localhost:8000/profiles/base.txt
```

### Map Profiles to Groups

Use Pi-hole API to assign adlists to groups:

```bash
# Get adlist IDs
curl "http://pihole.local/api/adlists" \
  -H "Authorization: Bearer $API_KEY" | jq '.[] | {id, address}'

# Assign to group 1 (Default)
curl -X PUT "http://pihole.local/api/adlists/42" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"groups": [1]}'
```

---

## Troubleshooting

### Build shows "Connection refused"

Use `--no-fetch` to use local paths only:
```bash
uv run blocklist-factory build --no-fetch
```

### Inconsistent outputs

Check for timestamps or non-deterministic elements. Rebuild and verify hashes:
```bash
find dist -type f ! -name ".gitkeep" -exec cat {} \; | sha256sum
```

### Domains disappearing from profiles

Check:
1. Is source enabled in `sources.yml`?
2. Is category in profile's `include_categories`?
3. Is domain allowlisted in `inputs/current_overrides/allowlist.txt`?
4. Does domain match a drop pattern?

---

## Contributing

When adding features:
1. **Maintain determinism**: No timestamps, no hashes in outputs
2. **Add tests**: Every parser/sanitizer change needs a test
3. **Keep it simple**: Prefer composability over monolithic functions
4. **Document config**: Update README for new config options
5. **Frozen dataclasses**: Use `@dataclass(frozen=True)` for thread-safety

---

## References

- Pi-hole v6 API: https://docs.pi-hole.com/api/overview/
- Firebog: https://v.firebog.net/hosts/
- IDNA Standard: RFC 3490, RFC 5890
- Blocklist Formats:
  - Hosts: https://en.wikipedia.org/wiki/Hosts_(file)
  - Domain-only: Simple list of FQDNs
  - ABP: https://adblockplus.org/filter-cheatsheet
