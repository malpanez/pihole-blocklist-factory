# Quick Task 260624-jmc: Strip glued host-IP prefixes from domain-only tokens

## Background (verified)

Some upstream feeds (Firebog cryptojacking list, pyenb) ship hosts-format lines with **no
space** between the sink IP and the hostname, e.g. `0.0.0.0kryptonchain.org`. The current
parser takes the whole thing as one domain-only token; it passes the FQDN regex (labels
`0`,`0`,`0`,`0kryptonchain`,`org`) and lands in the output as garbage. Verified count in the
current build: **4,798** such entries, and **100%** strip to a domain that is **already in
the output** (so removing them is zero-loss dedup).

This task fixes ONLY this unambiguous, zero-false-positive class. It deliberately does NOT
attempt to split genuine no-delimiter multi-FQDN concatenations
(`init.itunes.apple.comjs.moatads.com`) — verification proved that cannot be done without
mangling legitimate domains. That class is documented as a known limitation.

## Task 1 — strip glued host-IP (commit: `fix(parse): strip glued host-IP prefixes from domain-only tokens`)

### Code — `src/blocklist_builder/parse.py`
1. Add a module constant and helper:
   ```python
   _GLUED_HOST_IP_RE: Final = re.compile(
       r"^(?:0\.0\.0\.0|127\.0\.0\.1|255\.255\.255\.255)(?=[a-z0-9])", re.ASCII
   )

   def _strip_glued_host_ip(token: str) -> str:
       """Strip a sink IP glued (no separator) to a hostname: 0.0.0.0kryptonchain.org -> kryptonchain.org."""
       return _GLUED_HOST_IP_RE.sub("", token)
   ```
   - The lookahead `(?=[a-z0-9])` ensures we only strip when the IP is glued to a hostname
     start (never `0.0.0.0` alone, never `0.0.0.0.example.com` where a dot follows).
2. In `_try_parse_domain_only`, apply the strip before the dot check:
   ```python
   def _try_parse_domain_only(parts: Sequence[str]) -> str | None:
       if len(parts) == 1 and not parts[0].startswith("||"):
           token = _strip_glued_host_ip(parts[0])
           if "." in token:
               return token
       return None
   ```
   Keep behaviour identical for all tokens without a glued IP prefix (the regex sub is a
   no-op then). Type hints required; mypy --strict clean; no new deps.

### Tests — `tests/test_parse.py` (and reuse existing patterns)
Add cases covering the user's required scenarios plus the new fix:
- `0.0.0.0kryptonchain.org` (domain-only, glued IP) -> `classify_line` yields `("kryptonchain.org",), "ok"`.
- `127.0.0.1evil.example.com` -> recovers `evil.example.com`.
- `0.0.0.0` alone -> NOT stripped (stays `0.0.0.0`, reason ok as a token but sanitize rejects as ip; assert classify returns it unchanged).
- `0.0.0.0.example.com` (dot after IP) -> NOT stripped (assert token unchanged, still parses to `0.0.0.0.example.com`).
- Standard hosts format with space `0.0.0.0 example.com` -> still yields `example.com` (regression).
- Multi-hostname hosts line `0.0.0.0 a.com b.com` -> yields `a.com`, `b.com` (regression).
- Individually-presented domains accepted: `metrics.apple.com`, `init.itunes.apple.com`, `js.moatads.com` each classify to `(d,), "ok"`.
- KNOWN-LIMITATION pin: `init.itunes.apple.comjs.moatads.com` (no delimiter, no host IP) is STILL
  returned as a single token `("init.itunes.apple.comjs.moatads.com",), "ok"` — assert this
  current behaviour with a comment noting it is an accepted, documented limitation (safe
  de-concatenation is not achievable; see README Known limitations).

### Tests — `tests/test_parallel_extra.py` (worker / file-level, for newline handling)
Add a test that writes a temp file and runs `_process_source_file_worker` to confirm:
- Two domains separated only by `\r` (carriage return, no `\n`) are both parsed
  (universal-newline file reading already handles this — regression lock).
- A file with no trailing newline still yields its last domain.
- A glued `0.0.0.0kryptonchain.org` line in the file produces valid `kryptonchain.org`.

### Docs — `README.md` "Known limitations" (after the wildcard bullet, line ~205)
Add:
```
- Some upstream feeds occasionally concatenate multiple domains with no delimiter
  (e.g. `init.itunes.apple.comjs.moatads.com`). These are structurally valid FQDNs, so
  they cannot be split or rejected without risking removal of legitimate domains; they are
  passed through as-is (a cosmetic, non-functional artifact — Pi-hole never resolves them).
  Host-IP-glued lines (`0.0.0.0host`) ARE repaired by stripping the sink IP.
```

### Gates (record results, fix before commit)
- `PYTHONPATH=src uv run pytest --cov=blocklist_builder --cov-fail-under=99 -q`
- `uv run ruff check . && uv run ruff format --check .`
- `uv run mypy --strict src/blocklist_builder` (0 errors)

Do NOT run a full build (no .cache in the worktree). Do NOT commit dist/ or .cache/.
Create SUMMARY at `.planning/quick/260624-jmc-strip-glued-host-ip-prefixes-from-domain/260624-jmc-SUMMARY.md`
(do not commit it — orchestrator handles the docs commit). Do not touch ROADMAP.md/STATE.md.
