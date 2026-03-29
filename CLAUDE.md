<!-- GSD:project-start source:PROJECT.md -->
## Project

**pihole-blocklist-factory**

A Python CLI tool that builds custom Pi-hole blocklists by fetching domain lists from multiple sources (HTTP + local files), parsing and sanitizing them in parallel, categorizing domains, and writing per-profile blocklist files to `dist/`. Targets homelab/self-hosted users who want a reproducible, auditable blocklist pipeline.

**Core Value:** Produce accurate, deduplicated, correctly-categorized blocklists from multiple sources — with stats and provenance that reflect reality.

### Constraints

- **Python**: 3.11+ — uses `match/case`, `slots=True`, `tomllib`
- **Test coverage**: Must maintain ≥99% after each phase
- **Linting**: `ruff check` must pass clean after each phase
- **Backwards compatibility**: `dist/` output format must not change (Pi-hole adlist URLs are stable)
- **No new dependencies**: Fix bugs using existing stdlib; avoid adding packages
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
