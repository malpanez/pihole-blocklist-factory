# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-06-24

### Added
- IDN support: punycode (`xn--`) TLD labels are now accepted, recovering ~2,000
  internationalized domains previously rejected by the validator.
- Multi-hostname hosts lines: every hostname on a `0.0.0.0 a.com b.com` line is parsed,
  not just the first.
- Profile output deduplication: byte-identical profiles are emitted as relative symlinks to
  a single canonical file, plus a `profiles/manifest.json` recording each profile's
  canonical target, sha256, and line count.
- Gzipped JSONL provenance (`reports/provenance.jsonl.gz`) plus a small
  `reports/provenance_aggregates.json`; `analyze` and `recommend` consume the aggregates
  instead of loading the full provenance.
- `mypy --strict` adopted as a blocking CI gate; `--cov-fail-under=99` coverage gate in CI.

### Changed
- Parallel source fetching wired into the build path.
- Memory: streaming provenance and removal of unbounded sanitize caches cut peak RSS from
  ~12.5 GiB to ~3.4 GiB on a full build.
- All GitHub Actions pinned to commit SHAs.
- Dev dependencies consolidated under `[dependency-groups]`.

### Fixed
- Strip sink-IP prefixes glued to hostnames in domain-only tokens
  (`0.0.0.0kryptonchain.org` -> `kryptonchain.org`), removing 4,798 garbage duplicate
  entries with zero legitimate-domain loss.
- Download safety: 64 MB cap with `stream=True` and a `Content-Length` check; retries are
  limited to network errors and 5xx (4xx no longer retried).
- `--no-fetch` now resolves http(s) sources from the cache (previously produced near-empty
  output).
- Firebog sync enforces `https://` source URLs and parses the catalog with `csv.reader`.
- Local source paths are constrained under the repository root.

### Removed
- Broken `update.yml` workflow (its PR was always empty because `dist/` is gitignored).

### Known limitations
- Some upstream feeds occasionally concatenate multiple domains with no delimiter
  (e.g. `init.itunes.apple.comjs.moatads.com`). These are structurally valid FQDNs, so they
  cannot be split or rejected without risking removal of legitimate domains; they are passed
  through as a cosmetic artifact and reported upstream
  (see `docs/reports/pyenb-data-quality.md`).

## [0.1.0] - 2026-01-31

### Added
- Initial release: fetch, parse, sanitize, categorize, and partition Pi-hole blocklists
  with per-profile outputs, regex generation, allowlist, and stats/provenance reports.
