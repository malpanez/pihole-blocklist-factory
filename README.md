# Pi-hole Blocklist Factory

[![CI](https://github.com/malpanez/pihole-blocklist-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/malpanez/pihole-blocklist-factory/actions/workflows/ci.yml)
[![Build Lists](https://github.com/malpanez/pihole-blocklist-factory/actions/workflows/build-lists.yml/badge.svg)](https://github.com/malpanez/pihole-blocklist-factory/actions/workflows/build-lists.yml)
[![Codecov](https://codecov.io/gh/malpanez/pihole-blocklist-factory/branch/main/graph/badge.svg)](https://codecov.io/gh/malpanez/pihole-blocklist-factory)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://github.com/malpanez/pihole-blocklist-factory)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/malpanez/pihole-blocklist-factory)

Production-grade tooling to build, sanitize, and distribute custom **Pi-hole v6** blocklists from multiple sources.

## Features

- **Multiple parsers**: hosts (`0.0.0.0 domain`, `127.0.0.1 domain`, `::`) | domain-only | ABP simple (`||domain^`)
- **Strict sanitization**: IDNA/punycode, FQDN validation, IP and single-label rejection
- **Categorization**: malicious > tracking > advertising > suspicious > other > telemetry (configurable precedence)
- **Profiles**: base, security, aggressive, android, ios, windows, macos
- **Strict/non-strict mode**: protects core domains in non-strict profiles
- **Cached fetch**: retries, timeouts, metadata
- **Private overlays**: gitignored `sources.local.yml`, allowlist/denylist, drop_patterns
- **Reports**: stats, provenance, overlap, marginal contribution, source stats
- **Deterministic output**: same input -> same output
- **Ruff + pre-commit**

## Requirements

- Python 3.11+ (3.12 recommended)
- `uv` package manager

## Local setup

```bash
git clone https://github.com/malpanez/pihole-blocklist-factory.git
cd pihole-blocklist-factory

uv sync

uv run ruff check .
uv run ruff format .

uv run pytest
```

## Usage

### Build

```bash
# Build using local sources only
uv run blocklist-factory build --no-fetch

# Build with fetch (downloads URLs)
uv run blocklist-factory build

# JSON stats
uv run blocklist-factory build --json
```

Outputs:
- `dist/all.txt`
- `dist/categories/{advertising,tracking,malicious,suspicious,other,telemetry}.txt`
- `dist/profiles/{base,security,aggressive,android,ios,windows,macos}.txt`
- `dist/reports/stats.json` and `stats.md`

### Validate config

```bash
uv run blocklist-factory validate
```

### Reports

```bash
uv run blocklist-factory report
```

## Configuration

### 1) Sources (`config/sources.yml`)

```yaml
sources:
  - id: firebog_malware
    name: "Firebog Malware List"
    category: malicious
    url: https://v.firebog.net/hosts/RPiList-Malware.txt
    enabled: true
    tier: stable
    license: "MIT"
    notes: "Curated malware blocklist"
```

### 2) Private sources (`config/sources.local.yml` - gitignored)

```yaml
sources:
  - id: my_internal_list
    name: "My Internal List"
    category: tracking
    url: file:///path/to/my/list.txt
    enabled: true
    tier: stable
```

### 3) Policies (`config/policies.yml`)

```yaml
policies:
  category_precedence:
    - malicious
    - tracking
    - advertising
    - suspicious
    - other
    - telemetry

  core_domains:
    - apple.com
    - google.com
    - microsoft.com

  base_allowlist: []
```

### 4) Profiles (`config/profiles.yml`)

```yaml
profiles:
  base:
    include_categories: [advertising, tracking, malicious]
    include_sources: []
    exclude_sources: []
    strict: false

  aggressive:
    include_categories: [advertising, tracking, malicious, telemetry]
    strict: true
```

### 5) Overrides

- `inputs/current_overrides/allowlist.txt`
- `inputs/current_overrides/denylist_extra.txt`
- `inputs/current_overrides/drop_patterns.txt`

## Import from Pi-hole v6

```bash
curl "http://pihole.local/api/adlists" \
  -H "Authorization: Bearer YOUR_API_KEY" | jq -r '.[] | .address' > inputs/sources_current.txt
```

## GitHub Actions

- **CI**: lint + tests + coverage on every push/PR.
- **Build Lists**: manual + weekly/monthly schedules. Generates `dist/` and publishes a GitHub Release with the `.txt` assets.

## Download lists (Releases)

```
https://github.com/malpanez/pihole-blocklist-factory/releases/download/lists-<RUN_ID>/all.txt
https://github.com/malpanez/pihole-blocklist-factory/releases/download/lists-<RUN_ID>/profiles/base.txt
```

To find `<RUN_ID>`, open the latest workflow run and use the release tag created by that run.

## Code coverage (Codecov)

1. Create a Codecov account and activate the repo.
2. Add `CODECOV_TOKEN` in GitHub → Settings → Secrets and variables → Actions.

## Architecture

```
src/blocklist_builder/
├── types.py
├── config.py
├── fetch.py
├── parse.py
├── sanitize.py
├── classify.py
├── build.py
├── report.py
└── cli.py
```

## Roadmap

- [x] Multiple parsers (hosts, domain-only, ABP simple)
- [x] Strict sanitization (IDNA, FQDN)
- [x] Profiles and category precedence
- [x] Cached fetch
- [x] Private overlays
- [x] Provenance + marginal reports
- [x] CI workflows
- [ ] Churn report (delta vs previous build)
- [ ] Release channels (stable/edge)

## Known limitations

- Domains containing underscores (e.g. `tracker_metrics.example.com`) are rejected by
  the validator. Underscores are technically invalid in hostnames (RFC 952/1123), but
  they do appear in some tracking lists; such entries are counted under
  `sanitize_not_fqdn` and excluded from the output.
- Wildcard entries (`*.example.com`) are not expanded or mapped to their base domain;
  they are counted under `parse_wildcard` and excluded from the output.

## License

- Code: MIT (see `LICENSE`)
- External lists: keep their own licenses (see `CREDITS.md`)

---

# Pi-hole Blocklist Factory (ES)

Herramienta de producción para construir, sanitizar y distribuir listas personalizadas para **Pi-hole v6** desde múltiples fuentes.

## Características

- **Múltiples parsers**: hosts (`0.0.0.0 domain`, `127.0.0.1 domain`, `::`) | domain-only | ABP simple (`||domain^`)
- **Sanitización estricta**: IDNA/punycode, validación FQDN, rechazo de IPs y single-label
- **Categorización**: malicious > tracking > advertising > suspicious > other > telemetry (configurable)
- **Perfiles**: base, security, aggressive, android, ios, windows, macos
- **Modo strict/non-strict**: protege dominios core en perfiles no-strict
- **Fetch con caché**: reintentos, timeouts, metadata
- **Overlays privados**: `sources.local.yml`, allowlist/denylist, drop_patterns
- **Reportes**: stats, provenance, overlap, marginal contribution, source stats
- **Salida determinista**

## Requisitos

- Python 3.11+ (3.12 recomendado)
- `uv`

## Setup local

```bash
git clone https://github.com/malpanez/pihole-blocklist-factory.git
cd pihole-blocklist-factory

uv sync
uv run ruff check .
uv run ruff format .
uv run pytest
```

## Uso

```bash
uv run blocklist-factory build --no-fetch
uv run blocklist-factory build
uv run blocklist-factory build --json
```

## GitHub Actions

- **CI**: lint + tests + coverage en cada push/PR.
- **Build Lists**: manual + cron semanal/mensual. Genera `dist/` y publica Releases con assets `.txt`.

## Descarga de listas (Releases)

```
https://github.com/malpanez/pihole-blocklist-factory/releases/download/lists-<RUN_ID>/all.txt
```

## Cobertura (Codecov)

1. Activar el repo en Codecov.
2. Añadir `CODECOV_TOKEN` en GitHub → Settings → Secrets and variables → Actions.
