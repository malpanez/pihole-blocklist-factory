---
phase: quick-261030-hnt
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/blocklist_builder/types.py
  - src/blocklist_builder/config.py
  - src/blocklist_builder/parallel.py
  - src/blocklist_builder/build.py
  - src/blocklist_builder/gate.py
  - src/blocklist_builder/cli.py
  - config/sources.yml
  - inputs/current_overrides/must_not_block.txt
  - .forgejo/workflows/build-lists.yml
  - tests/test_parallel_extra.py
  - tests/test_config.py
  - tests/test_build.py
  - tests/test_sources_config.py
  - tests/test_gate.py
  - CLI_GUIDE.md
  - CHANGELOG.md
autonomous: true
requirements:
  - QUICK-261030-hnt

must_haves:
  truths:
    - "A full build reports no source_missing: discarded.source_missing is absent or 0 in dist/reports/stats.json"
    - "hagezi_pro, hagezi_tif, urlhaus_filter and metamask_phishing all contribute domains to dist/all.txt"
    - "MetaMask contributes only its blacklist array; a path entry such as sites.google.com/view/x never blocks sites.google.com"
    - "A malformed JSON source or a missing key counts as source_missing, logs a warning, and the build still finishes"
    - "blocklist-factory gate exits 1 on source_missing, on a drop above max-drop, or on a must-not-block name or parent in all.txt, and prints each failure"
    - "When the gate fails in the workflow the release is not replaced and a high-priority ntfy alert names the repo and the run URL"
    - "dist/ output format is unchanged and no new dependency is added"
  artifacts:
    - path: "src/blocklist_builder/gate.py"
      provides: "Post-build gate checks, no printing and no exit"
      exports: ["GateResult", "run_gate", "check_drop", "check_must_not_block", "blocking_entry"]
    - path: "inputs/current_overrides/must_not_block.txt"
      provides: "26 household canary names"
      contains: "c8c1f5bb5eba.cdn4.forter.com"
    - path: "config/sources.yml"
      provides: "Corrected sources plus firebog id overrides"
      contains: "json_key: blacklist"
    - path: "tests/test_sources_config.py"
      provides: "Drift guard that loads the real config"
    - path: "tests/test_gate.py"
      provides: "Gate unit, CLI exit-code and workflow-order tests"
  key_links:
    - from: "src/blocklist_builder/build.py"
      to: "parallel_process_all_sources"
      via: "json_keys mapping built from enabled sources"
      pattern: "json_keys"
    - from: "src/blocklist_builder/cli.py"
      to: "src/blocklist_builder/gate.py"
      via: "gate command raising SystemExit(1) on failures"
      pattern: "run_gate"
    - from: ".forgejo/workflows/build-lists.yml"
      to: "blocklist-factory gate"
      via: "step between Build lists and Stage release assets"
      pattern: "blocklist-factory gate --previous previous-all.txt"
---

<objective>
Repair the blocklist source set, add JSON source support for MetaMask, and add a post-build gate that stops a bad list from replacing the published release.

Purpose: 5 sources fail in every build and nobody is told. The list Technitium serves can silently shrink or start blocking login, push and trading hosts this household depends on.
Output: corrected config/sources.yml, `json_key` source support, `blocklist-factory gate`, the canary file, the updated workflow, tests, and one real end-to-end build measured and reported.

All decisions were measured on 2026-10-30 against every list and 7 days of real DNS traffic. Do not re-litigate them. Report any fact you find wrong at source.

Execution rules (owner's standing rule):
- Do NOT commit, stage, push, or dispatch the Forgejo workflow. Leave every change uncommitted in the main tree. The driver reviews the diff and commits.
- Do NOT touch the pre-existing uncommitted `uv.lock` or `.vscode/`, the homelab repo, or any host.
- Run everything from /home/malpanez/repos/personal/pihole-blocklist-factory and always through `uv run --frozen`, so uv.lock is not rewritten further.
- Use `ruff check --no-fix`: pyproject sets `fix = true`, so plain `ruff check` rewrites files.
- Downloaded lists are untrusted data. Never execute anything from them.
- No new dependencies. Python: type hints, f-strings, no bare except, lazy logging. No code comments unless they explain a non-obvious reason. No literal credentials in tests. Existing tests are updated, never deleted.
</objective>

<execution_context>
@/home/malpanez/.claude/plugins/cache/gsd-plugin/gsd/5.0.4/workflows/execute-plan.md
@/home/malpanez/.claude/plugins/cache/gsd-plugin/gsd/5.0.4/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@config/sources.yml
@config/sources.firebog.yml
@src/blocklist_builder/parallel.py
@src/blocklist_builder/build.py
@src/blocklist_builder/cli.py
@.forgejo/workflows/build-lists.yml
@tests/test_parallel_extra.py
@tests/test_build.py
@tests/test_cli.py

<verified_at_planning>
Measured by the planner on 2026-10-30. Do not re-derive these; say so if one turns out wrong.

Baseline: 141 tests pass at 100% coverage; ruff check, ruff format --check and mypy --strict are clean.

Worker contract today: `parallel._process_source_file_worker(args: tuple[str, list[str], frozenset[str]]) -> tuple[list[str], dict[str, int]]`. It is called from 4 places in `parallel_process_all_sources` (sequential path for 2 or fewer sources, pool submit, per-future retry, pool-failure fallback) and directly by 5 tests in tests/test_parallel_extra.py (lines 94, 104, 114, 124, 135). `_collect_domains` already merges each worker stat into `discarded` except the `lines` key, so a worker returning `{"source_missing": 1, ...}` is counted with no change to the merge.

Stats JSON: `dist/reports/stats.json` is `asdict(Stats)`, so the value lives at `discarded.source_missing`. The key is ABSENT on a clean build, because it comes from a Counter. Absent means 0.

Upstream formats (downloaded and sampled):
- hagezi `wildcard/pro-onlydomains.txt`: 214,202 bare domains, 0 lines starting `*.`. The worker discards `*.` entries, and these have none, so they count normally.
- hagezi `wildcard/tif-onlydomains.txt`: 1,852,754 bare domains, 0 star lines, 32.7 MB, under the 64 MB cap.
- urlhaus-filter-domains.txt: 18,009 domains, 271 KB, 0 star lines.
- MetaMask config.json: 3.3 MB. Top-level keys are version, tolerance, fuzzylist (8), whitelist (59), blacklist (114,053, all strings). The blacklist holds PATH entries such as `sites.google.com/view/moonpay-technical/home`. `sanitize_domain` rejects these because `/` fails `_DOMAIN_RE`, so they are discarded and do not block `sites.google.com`. Task 1 pins this with a test.

Canaries: 0 of the 26 names or their parents appear in hagezi pro, TIF, urlhaus-filter, MetaMask blacklist, or the published `latest` all.txt. Expect the canary check to pass.

Published release: 1,313,585 domains, downloadable with no auth, HTTP 200 with no redirect, so no token is needed. The build is expected to grow, so the first gate run should pass the drop check.

Forgejo 16.0.6: run URLs use the per-repo number, `/actions/runs/` followed by the run number. Confirmed from the actions API: task id 692 has url `.../actions/runs/33`. Use `github.run_number`, not `github.run_id`.

Runner: `node-22` maps to `docker://node:22-bookworm` (curl and bash present). The runner bind-mounts the CA bundle at /etc/ssl/certs/ca-certificates.crt, so step-ca names verify.

Source ids: `threatfox` does NOT exist in config/sources.yml, sources.firebog.yml or the overrides. There is nothing to disable; do not add it. After the changes in this plan, no two enabled sources share a URL (today only urlhaus and easyprivacy are duplicated).

Firebog ids, taken verbatim from the generated file. They contain apostrophes, so double-quote them in YAML:
- `firebog_advertising_7_fademind's_unchecky_ads`, category advertising, https://raw.githubusercontent.com/FadeMind/hosts.extras/master/UncheckyAds/hosts
- `firebog_malicious_3_fademind's_risky_hosts`, category malicious, https://raw.githubusercontent.com/FadeMind/hosts.extras/master/add.Risk/hosts
- `firebog_suspicious_2_fademind's_spammers`, category suspicious, https://raw.githubusercontent.com/FadeMind/hosts.extras/master/add.Spam/hosts
- `firebog_tracking_3_fademind's_2o7_network_tracker`, category tracking, https://raw.githubusercontent.com/FadeMind/hosts.extras/master/add.2o7Net/hosts
- `firebog_malicious_8_urlhaus_malicious_url_blocklis`, category malicious, https://urlhaus.abuse.ch/downloads/hostfile/

Trap, verified in cli.py: the console script is `cli.py:main`, which calls `cli(argv, standalone_mode=False)`. In that mode click turns `ctx.exit(1)` and `click.exceptions.Exit(1)` into a RETURN VALUE, and `main` then returns 0. A failing gate written that way would be green in CI and would publish a bad list. The gate command MUST `raise SystemExit(1)`, as the other commands do, and the tests MUST assert on `cli.main([...])`'s return value as well as on `CliRunner`.
</verified_at_planning>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: JSON source support, source corrections and the canary file</name>
  <files>src/blocklist_builder/types.py, src/blocklist_builder/config.py, src/blocklist_builder/parallel.py, src/blocklist_builder/build.py, config/sources.yml, inputs/current_overrides/must_not_block.txt, tests/test_parallel_extra.py, tests/test_config.py, tests/test_build.py, tests/test_sources_config.py</files>
  <behavior>
    - Worker with json_key "blacklist" on a JSON file: only that array's strings reach the parse and sanitize pipeline; fuzzylist and whitelist entries in the same file are absent from the result; non-string items are skipped.
    - Worker on JSON whose array holds `evil.example`, `sites.google.com/view/x`, `*.star.example`: returns only `evil.example`, and `sites.google.com` is not in the output.
    - Worker on malformed JSON, a top-level non-object, a missing key, a non-list value, or an array with no string items: returns an empty domain list and stats holding `source_missing: 1` and `lines: 0`, logs one warning naming the file and key, raises nothing.
    - Worker on deeply nested JSON that raises RecursionError: same failure result.
    - parallel_process_all_sources with `json_keys`: honored on the sequential path (2 or fewer sources) and on the pool path (3 or more sources).
    - build() with one good JSON source and one malformed JSON source: `stats.discarded["source_missing"] == 1`, the good domains are in all.txt, no exception.
    - load_settings: reads `json_key` from YAML; defaults to None when absent.
    - Real config: drift guard listed in the action.
  </behavior>
  <action>
**JSON sources.** Add `json_key: str | None = None` as the last field of `Source` in types.py. In config.py pass `json_key=item.get("json_key")`, the same idiom as `license`.

In parallel.py, extend the worker args tuple to `tuple[str, list[str], frozenset[str], str | None]` and update the 5 direct test calls to pass `None`. Add an optional `json_keys: Mapping[str, str] | None = None` parameter to `parallel_process_all_sources`, and pass `json_keys.get(src_id)` at all 4 worker call sites. Missing one call site would make a retried source parse raw JSON as text and pass quietly.

Split the existing per-line loop into a helper that takes an iterable of lines and returns the existing `(valid, stats)`, so the text path and the JSON path share it without a behavior change. The text path keeps streaming from `open`.

Add a JSON loader using stdlib `json`, reading with `encoding="utf-8", errors="ignore"` like the text path. Catch `(OSError, ValueError, RecursionError)`: JSONDecodeError and UnicodeDecodeError are ValueError, and RecursionError covers deep nesting in untrusted data. The source fails when the top level is not a dict, when the key is missing, when the value is not a list, or when the list holds no string items. An empty array is treated as failed by planner decision, because a renamed or emptied key is the same upstream break and a loss of about 113k entries sits below the 10% drop threshold. On failure log `logging.warning` with lazy args and return `[]` plus stats with `source_missing: 1`, `lines: 0`, `parse_ok: 0`, `sanitize_ok: 0`, `allowlisted: 0`. Keep a single `source_missing` constant shared between parallel.py and build.py (define it in parallel.py and import it into build.py, since build already imports parallel).

In build.py `_collect_domains`, build the mapping from enabled sources that have a `json_key` and pass it as `json_keys=`. `_resolve_all_source_paths` is unchanged, since the cache path is the same.

**config/sources.yml.** Add a `json_key` line to the field comment at the top. Notes on entries you change are in English, one line. Do not touch `hagezi_gambling`, `1hosts_pro`, `oisd_nsfw`, the commented `hagezi_fake`, or any entry not listed here.
- `hagezi_pro` url to https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/pro-onlydomains.txt and `hagezi_tif` url to https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/tif-onlydomains.txt. Both stay `enabled: true`; TIF stays `malicious`. Update the notes: the wildcard format is right because Technitium block lists are hierarchical; jsDelivr `@latest/domains` returned 403.
- Set `enabled: false` with these notes reasons:
  - `notracking_tracker`: repo archived 2023-06.
  - `blocklistproject_ads`: repo archived.
  - `easyprivacy_hosts`: same URL as firebog_tracking_1_easyprivacy.
  - `phishing_army`: near-identical subset of the firebog extended list.
  - `pyenb_blocklist`: 4.5M entries over the 64 MB download cap, historic false-positive source.
  - `urlhaus_online`: 410, needs an Auth-Key, replaced by urlhaus_filter.
  - `1hosts_lite`: blocks anti-fraud and API hosts on household traffic (api.fraud0.com, service2.us.incognia.com, a-api.anthropic.com, mirrors.hostiserver.com); HaGeZi advises against stacking multi lists; last push 2026-09.
- Keep `ads_tracking_xorro`, `oisd_big` and `firebog_advertising_2_adguard_dns` enabled and untouched; do not add an override for them.
- Add `urlhaus_filter`: category malicious, tier stable, url https://malware-filter.gitlab.io/malware-filter/urlhaus-filter-domains.txt, license `https://gitlab.com/malware-filter/urlhaus-filter`, a one-line note.
- Add `metamask_phishing`: category malicious, tier stable, url https://raw.githubusercontent.com/MetaMask/eth-phishing-detect/main/src/config.json, `json_key: blacklist`, license `https://github.com/MetaMask/eth-phishing-detect`, and a note that it takes only the blacklist array, never fuzzylist or whitelist, for the household's exchange assets.
- Add a section with the 5 firebog overrides from verified_at_planning: double-quoted id, name, category, url, `enabled: false`, and a reason in notes (FadeMind repo archived; urlhaus 410). Add a short YAML comment saying these ids are positional and must be rechecked after `sync-firebog`, that first id wins and sources.yml loads first. Do not edit config/sources.firebog.yml; it is generated.

**inputs/current_overrides/must_not_block.txt.** Start with an English comment: these are login, push and trading dependencies of this household; failing here means an upstream list started blocking them; fix via allowlist.txt. Then exactly these 26 names, one per line:
www.binance.com, accounts.binance.com, bin.bnbstatic.com, www.kucoin.com, challenges.cloudflare.com, www.tradingview.com, data.tradingview.com, static.tradingview.com, pushstream.tradingview.com, notifications.tradingview.com, news-mediator.tradingview.com, sntp.atas.net, cfg.atas.net, img.atas.net, app.gexbot.com, www.gexbot.com, assets.revolut.com, mercury.com, email.mg.mercury.com, push.apple.com, init.push.apple.com, courier-push-apple.com.akadns.net, gateway.icloud.com, setup.icloud.com, c8c1f5bb5eba.cdn4.forter.com, addfd325e6e3.cdn4.forter.com

**tests/test_sources_config.py (new).** Load the real `config/` directory through `load_settings`, with `monkeypatch.delenv("BLOCKLIST_SOURCES", raising=False)`. Assert:
- every id in the disabled list above is `enabled=False`, including the 5 firebog ids, and those 5 ids still exist in config/sources.firebog.yml (read with `yaml.safe_load`);
- no enabled source URL contains `FadeMind/`, `urlhaus.abuse.ch` or `cdn.jsdelivr.net`. This is what catches a `sync-firebog` that shifts the positional ids and silently re-enables them;
- no two enabled sources share a URL;
- `metamask_phishing.json_key == "blacklist"` and its category is malicious;
- must_not_block.txt holds exactly 26 unique non-comment names.

Leave changes uncommitted in the main tree.
  </action>
  <verify>
    <automated>PYTHONPATH=src uv run --frozen pytest -q --cov=blocklist_builder --cov-report=term-missing --cov-fail-under=99 && uv run --frozen ruff check --no-fix . && uv run --frozen ruff format --check . && uv run --frozen mypy --strict src/blocklist_builder && uv run --frozen blocklist-factory validate</automated>
  </verify>
  <done>All checks pass at 99% coverage or above. The 5 worker test call sites are updated, none deleted. All 4 worker call sites pass the JSON key. config/sources.firebog.yml is unmodified. Changes are uncommitted.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: gate module, CLI command and workflow wiring</name>
  <files>src/blocklist_builder/gate.py, src/blocklist_builder/cli.py, .forgejo/workflows/build-lists.yml, tests/test_gate.py, CLI_GUIDE.md, CHANGELOG.md</files>
  <behavior>
    - blocking_entry: `a.b.example.com` with `example.com` in the set returns `example.com`; with the exact name in the set returns the name; with nothing listed returns None.
    - check_must_not_block: failure string contains both the canary name and the matching entry, one failure per name.
    - check_drop at previous 100: current 90 no failure (exactly 10% is not MORE than 10%); current 89 one failure; current 200 no failure.
    - run_gate: `discarded` without `source_missing` passes; `source_missing: 1` fails; a missing stats file, invalid JSON, a missing `discarded` map or a non-int value fail.
    - run_gate: a missing or empty all.txt fails; a missing or empty must-not-block file fails. These fail closed so a broken gate cannot read as green.
    - run_gate: `previous=None` or a nonexistent file gives a note and no failure; a previous file with 0 entries gives a note, no failure and no ZeroDivisionError; `allow_drop=True` skips the check with a note even when the drop is 90%.
    - run_gate: comments and blank lines are ignored in all.txt, the previous file and the must-not-block file.
    - CLI: `cli.main(["gate", ...])` returns 1 on failure and 0 on pass, each failure is printed, and the pass line shows domains, previous and delta.
    - Workflow test: gate step sits after "Build lists" and before "Stage release assets", the alert step is last with `if: failure()`, and no stage command references previous-all.txt.
  </behavior>
  <action>
**src/blocklist_builder/gate.py (new).** No printing, no exit, no click. Uses `json` and `pathlib` only.
- `GateResult`: frozen slots dataclass with `failures: list[str]`, `notes: list[str]`, `domains: int`, `previous: int | None`.
- `blocking_entry(name: str, domains: AbstractSet[str]) -> str | None`: checks the name and then every parent suffix down to and including the last label. Technitium blocks hierarchically, so a listed parent blocks the child.
- `check_must_not_block(names: Iterable[str], domains: AbstractSet[str]) -> list[str]`.
- `check_drop(current: int, previous: int, max_drop: float) -> list[str]`: compare `(previous - current) / previous > max_drop` rather than multiplying previous by (1 - max_drop), so the 10% boundary does not depend on float rounding. Precondition is `previous > 0`; run_gate handles zero.
- Private readers: names are stripped, lowercased and have the trailing dot removed, matching `build._read_overrides`; lines starting with `#` and blank lines are skipped; all.txt goes into a set.
- `run_gate(dist: Path, previous: Path | None, max_drop: float, allow_drop: bool, must_not_block: Path) -> GateResult`: reports every failure rather than stopping at the first.
  - Stats come from `dist / "reports" / "stats.json"` at `discarded.source_missing`, with absent meaning 0. Catch `(OSError, ValueError)`. A `source_missing` failure message points at `reports/source_stats.json`.
  - A previous file that exists but cannot be read is a failure.
  - Summary fields: `domains` is the unique count; `previous` is the previous count or None when the check was skipped.

**cli.py.** Add `@cli.command("gate")` with `--dist` (`click.Path(path_type=Path)`, default `Path("dist")`), `--previous` (same type, default None), `--max-drop` (`click.FloatRange(0.0, 1.0)`, default 0.10), `--allow-drop` flag, and `--must-not-block` (same type, default `Path("inputs/current_overrides/must_not_block.txt")`). Do not use `exists=True`: a click usage error prints nothing under `main`'s `standalone_mode=False`, and run_gate already reports missing files clearly.

Print notes in yellow and each failure in red to stderr with the file's `✗` idiom. On any failure `raise SystemExit(1)`. Do NOT use `ctx.exit` or `click.exceptions.Exit` (see the trap in verified_at_planning). On pass print one line with domains, previous and delta percent, or `previous=none` when skipped.

**.forgejo/workflows/build-lists.yml.** Keep both crons and every existing step. POSIX shell only in new `run:` blocks: no arrays and no `pipefail`, like the existing Build step.
- Add workflow_dispatch input `allow_drop`: type boolean, default false, with a description.
- After "Build lists", add step "Fetch previous release" that downloads `${{ github.server_url }}/malpanez/pihole-blocklist-factory/releases/download/latest/all.txt`. Use curl with `-sS -L --fail --retry 5 --retry-delay 3 --retry-all-errors --connect-timeout 15 --max-time 300`, writing to `previous-all.txt.part` and renaming to `previous-all.txt` only on success. On failure remove the `.part` file, echo a warning and exit 0. `--fail` plus the rename matter: without them a 404 page or a truncated download becomes a tiny "previous" and the drop check passes for the wrong reason.
- Then add step "Gate" with `env: ALLOW_DROP: ${{ github.event.inputs.allow_drop }}`, passing the input through env rather than interpolating it into the script. Follow the if/else shape of the Build step: `uv run blocklist-factory gate --previous previous-all.txt`, plus `--allow-drop` when `ALLOW_DROP` equals `true`. On schedule the value is empty, so the strict branch runs. A failure stops the job before "Stage release assets", so the release is not replaced.
- Leave the stage step as is: it copies named files, so previous-all.txt cannot reach `release/`.
- Last step "Alert on failure" with `if: failure()` and `env: RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_number }}`. Use curl in the upstream-watch.yml idiom (`-sS`, retries, `--connect-timeout 15`, `--max-time 60`), with headers `Title: pihole-blocklist-factory build failed`, `Priority: high`, `Tags: rotating_light`, and `--data-binary` carrying a short body saying the previous release stays published plus `${RUN_URL}`, posted to https://ntfy.homelab.test/homelab. End with `|| true`, since the failure is already recorded and this is a best-effort alert.

**tests/test_gate.py (new).** Cover the behavior list. Use `tmp_path` fixtures. Exercise the exit code through `cli.main([...])`, because that is what the console script runs, and use `CliRunner` for output text. The workflow test loads the YAML with `yaml.safe_load`.

**Docs.** Add a Gate section to CLI_GUIDE.md after the Report command, in Spanish like the rest of that file. Add an `## [Unreleased]` block to CHANGELOG.md, in English: Added gate and json_key; Changed the source set.

Leave changes uncommitted in the main tree.
  </action>
  <verify>
    <automated>PYTHONPATH=src uv run --frozen pytest -q --cov=blocklist_builder --cov-report=term-missing --cov-fail-under=99 && uv run --frozen ruff check --no-fix . && uv run --frozen ruff format --check . && uv run --frozen mypy --strict src/blocklist_builder && uv run --frozen blocklist-factory gate --help</automated>
  </verify>
  <done>gate.py has 100% coverage, including the fail-closed paths. `cli.main` returns 1 on every failure class. The workflow parses and the order test passes. shellcheck `-s sh` is clean on a scratch copy of the 3 new run blocks with `${{ }}` expressions replaced by placeholders, and that scratch copy is removed. Changes are uncommitted.</done>
</task>

<task type="auto">
  <name>Task 3: real end-to-end build, gate proof and report</name>
  <files>none (measurement only; dist/ and .cache/ are gitignored)</files>
  <action>
Create a scratch directory with `mktemp -d` outside the repo. Do not dispatch the workflow.

1. Download the published list to `$SCRATCH/previous-all.txt` with the Task 2 curl flags. This is a public read-only GET.
2. Run `/usr/bin/time -v uv run --frozen blocklist-factory build` with the Bash tool's `run_in_background`, keeping its output in a scratch log, and wait for its completion notification. Do not write a pgrep wait loop. Record wall time and max RSS: the job has a 45-minute limit and the list is growing.
3. Run the real gate and record its exit code and output: `uv run --frozen blocklist-factory gate --previous "$SCRATCH/previous-all.txt"`.
4. Prove the installed console script fails where it should. Each of these MUST exit 1 with the expected message; read the code from `$?` directly, not through a pipe:
   - `--must-not-block` pointing at a scratch file holding `child.` plus the first entry of dist/all.txt: output names both the child and the entry.
   - `--previous` pointing at a scratch copy of dist/all.txt with synthetic padding numbered `padN.invalid` lines added so that real domains are under 90% of the file. Then rerun with `--allow-drop`: this one must exit 0 and print that it skipped the check.
   - `--dist` pointing at an empty scratch directory.
5. Check results in dist/ (read with `uv run --frozen python -c`; these are JSON and text data, nothing from them is executed):
   - `discarded.source_missing` is absent or 0.
   - `dist/reports/source_stats.json` shows non-zero `sanitize_ok` for hagezi_pro, hagezi_tif, urlhaus_filter and metamask_phishing. metamask's discard count should roughly match the 1,107 gap between 114,053 raw and 112,946 stated entries.
   - `sites.google.com` is not in dist/all.txt, and no line in dist/all.txt contains `/` or starts with `*.`.
   - Format unchanged: dist/all.txt has one bare lowercase domain per line, and dist/all.txt, dist/allowlist.txt, dist/regex.txt, the categories, profiles and reports all exist.
6. Rerun the Task 2 verify command as the final state check.

If the gate fails in step 3, or `source_missing` is above 0, do NOT weaken the gate, edit allowlist.txt, or disable a source to get green. A failing gate on real data is a finding: capture the failure lines and the failing source's log warning (or, for a canary, the source ids from `dist/reports/provenance.jsonl.gz` for the matching entry) and report it for the driver to decide. The task is still complete with that report.

**Cleanup.** Remove `$SCRATCH` and any stray non-gitignored output. Leave dist/ and .cache/ in place (gitignored). `dist/reports/provenance.json` (570 MB, from February, predates this work) is not yours: do not delete it, just mention it.

**Report back:**
- `git status --short` (expected: the plan's files plus the pre-existing `uv.lock` and `.vscode/`);
- `du -sh dist .cache`;
- `pgrep -af blocklist-factory` showing nothing left running;
- total domains in dist/all.txt, published count and delta;
- per-source lines, sanitize_ok and any discard reasons from source_stats.json for every enabled source;
- `source_missing`;
- the exact gate output and exit code for steps 3 and 4;
- wall time and max RSS;
- any verified fact found wrong at source.

Leave changes uncommitted in the main tree.
  </action>
  <verify>
    <automated>uv run --frozen python -c "import json; d = json.load(open('dist/reports/stats.json')); print(d['unique_domains'], d['discarded'].get('source_missing', 0))" && PYTHONPATH=src uv run --frozen pytest -q --cov=blocklist_builder --cov-fail-under=99 && git status --short</automated>
  </verify>
  <done>A real build ran. The gate outcome is measured and reported with exit codes. All 4 negative or override proofs behaved as specified through the console script. Scratch is removed, no stray process remains, and the full report above is delivered. Nothing is committed, staged, pushed or dispatched.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Upstream list hosts to build | Downloaded lists and JSON are untrusted data that decides what the household can resolve |
| Build to published release | Whatever passes this point is served by Technitium to every device |
| workflow_dispatch input to run step | Operator-supplied value entering a shell script |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-hnt-01 | Tampering | metamask_phishing parse path | mitigate | Only the `json_key` array is read; items go through the normal classify and sanitize pipeline; path entries are rejected by `_DOMAIN_RE`, pinned by test |
| T-hnt-02 | Denial of Service | JSON loader on hostile input | mitigate | Existing 64 MB download cap applies; RecursionError, ValueError and OSError become a failed source instead of a crash |
| T-hnt-03 | Denial of Service | Upstream list starts blocking login or push hosts | mitigate | Gate walks each canary and all its parents against all.txt, and failure stops the job before the release step |
| T-hnt-04 | Tampering | Gate reports green while broken | mitigate | SystemExit(1) rather than click Exit under standalone_mode=False; missing or empty stats, all.txt or canary file all fail; tests assert on `cli.main`'s return value |
| T-hnt-05 | Tampering | Previous-file comparison poisoned by a 404 page or truncated download | mitigate | curl `--fail` writing to `.part`, renamed only on success |
| T-hnt-06 | Elevation of Privilege | Input interpolated into shell in the workflow | mitigate | `allow_drop` and the run URL pass through `env:` and are compared as strings |
| T-hnt-07 | Tampering | `sync-firebog` shifts positional ids and re-enables retired sources | mitigate | test_sources_config.py fails if any enabled URL matches a retired host or an override id disappears |
| T-hnt-08 | Information Disclosure | ntfy alert body | accept | Holds only the repo name and run URL on an internal topic, no secrets |
| T-hnt-09 | Denial of Service | Any single transient source failure now blocks publishing | accept | Owner's decision: the previous good list keeps serving and an alert fires; `_fetch_http` retries 5xx and network errors first |
</threat_model>

<verification>
- `PYTHONPATH=src uv run --frozen pytest --cov=blocklist_builder --cov-report=term-missing --cov-fail-under=99`
- `uv run --frozen ruff check --no-fix .` and `uv run --frozen ruff format --check .`
- `uv run --frozen mypy --strict src/blocklist_builder`
- Real build plus `blocklist-factory gate` through the console script, with the negative proofs from Task 3
- `git diff --stat -- config/sources.firebog.yml` is empty and no new dependency appears in pyproject.toml
- `git diff --cached --stat` is empty, because nothing is staged
</verification>

<success_criteria>
- A real build shows `source_missing` at 0, with HaGeZi Pro, TIF, urlhaus-filter and the MetaMask blacklist all contributing, or the failure is reported as a finding with evidence.
- The gate exits 1 for each failure class through the installed console script and prints every failure.
- The workflow cannot replace the release after a gate failure and alerts via ntfy with the right run URL.
- Coverage is at 99% or above, ruff and mypy are clean, the dist/ format is unchanged, and no new dependencies are added.
- All changes are uncommitted in the main tree for the driver to review.
</success_criteria>

<output>
Do not create a SUMMARY commit. Write `.planning/quick/261030-hnt-blocklist-source-review-fix-dead-sources/261030-hnt-SUMMARY.md` uncommitted, and return the Task 3 report as your final message.
</output>
