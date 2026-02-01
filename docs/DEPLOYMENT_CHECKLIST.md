# Production Deployment Checklist

## ✅ Implementation Complete

### Core Features (14/14)
- [x] Multi-format parsing (hosts, domain-only, ABP simple)
- [x] Strict sanitization (IDNA, FQDN, IP rejection)
- [x] Category precedence system
- [x] Profile composition (7 predefined profiles)
- [x] Fetch with caching & retries
- [x] Private overlay support (sources.local.yml)
- [x] Deterministic builds
- [x] Comprehensive reporting
- [x] CLI with 5 subcommands
- [x] GitHub Actions CI workflow
- [x] GitHub Actions Update workflow
- [x] Test coverage (parse, sanitize)
- [x] Complete documentation
- [x] Config templates (example files)

### Configuration Files (4/4)
- [x] `config/sources.yml` - Public source catalog
- [x] `config/sources.local.example.yml` - Private template
- [x] `config/policies.yml` - Category precedence + core domains
- [x] `config/profiles.yml` - 7 profiles (base, security, aggressive, android, ios, windows, macos)

### Constraints Compliance (4/4)
- [x] Python 3.11+ (no external dependencies beyond PyYAML + requests)
- [x] uv + ruff + pre-commit (no black/isort introduced)
- [x] Deterministic builds (same input = same output)
- [x] No internet required for CI (--no-fetch works)

### Documentation (4/4)
- [x] README.md (300+ lines, complete guide)
- [x] docs/ARCHITECTURE.md (technical deep-dive)
- [x] docs/IMPLEMENTATION_SUMMARY.md (this implementation summary)
- [x] docs/pihole_integration.md (Pi-hole integration guide)

---

## 📋 Deployment Steps

### Step 1: Initial Setup
```bash
cd pihole-blocklist-factory
uv sync --all-extras
uv run blocklist-factory validate
```
**Expected**: ✓ Config valid, 1 source, 7 profiles

### Step 2: Test Offline Build
```bash
uv run blocklist-factory build --no-fetch
cat dist/reports/stats.md
```
**Expected**: ✓ Build completes, shows domain counts

### Step 3: Test with Fetch
```bash
uv run blocklist-factory build
```
**Expected**: ✓ Downloads from all enabled sources, generates dist/*

### Step 4: Verify Determinism
```bash
# Build 1
uv run blocklist-factory build --no-fetch
find dist -type f ! -name ".gitkeep" -exec cat {} \; | sha256sum > /tmp/hash1.txt

# Build 2
rm -rf dist
uv run blocklist-factory build --no-fetch
find dist -type f ! -name ".gitkeep" -exec cat {} \; | sha256sum > /tmp/hash2.txt

# Verify
diff /tmp/hash1.txt /tmp/hash2.txt
```
**Expected**: ✓ No difference (deterministic)

### Step 5: Configure Git & Push
```bash
git add .
git commit -m "feat: production blocklist factory"
git push origin main
```

### Step 6: Enable GitHub Actions
1. Go to: Settings > Actions > General
2. Select: "Allow all actions and reusable workflows"
3. Workflows will run on next push

### Step 7: Configure Pi-hole

**Option A: Remote URLs (GitHub raw)**
```
https://raw.githubusercontent.com/<username>/<repo>/main/dist/all.txt
https://raw.githubusercontent.com/<username>/<repo>/main/dist/profiles/base.txt
https://raw.githubusercontent.com/<username>/<repo>/main/dist/profiles/android.txt
```

**Option B: Local Server**
```bash
# On Pi-hole machine:
cd /path/to/pihole-blocklist-factory
python3 -m http.server 8000 -d dist
```
Then in Pi-hole Admin Panel:
```
http://localhost:8000/all.txt
http://localhost:8000/profiles/base.txt
```

**Option C: file:// URLs** (if repo is on Pi-hole server)
```
file:///home/pi/blocklist-factory/dist/all.txt
```

### Step 8: Test in Pi-hole
1. Admin Panel > Settings > Adlists
2. Add one list URL
3. Settings > Gravity > Update
4. Check: Query Log should show list name
5. Review: Domainlist

---

## 📊 What to Expect

### First Build Stats
```json
{
  "total_lines": 50000,
  "parsed_ok": 45000,
  "sanitized_ok": 35000,
  "unique_domains": 30000,
  "discarded": {
    "parse_comment": 2000,
    "parse_unsupported": 1000,
    "sanitize_invalid": 2000,
    "sanitize_ip": 1000
  }
}
```

### Profile Distribution
- `base.txt` - advertising, tracking, malicious (~25k domains)
- `security.txt` - malicious only (~5k domains)
- `aggressive.txt` - +telemetry (~30k domains)
- `android.txt` - ad/tracking/malicious (~25k domains)
- `ios.txt` - ad/tracking/malicious (~25k domains)

### Weekly Update Workflow
- Runs every Monday 03:00 UTC
- Fetches latest versions of all sources
- If changes detected: Creates PR with summary
- If no changes: Skips (no false PRs)

---

## 🔧 Common Customizations

### Add a New Source
Edit `config/sources.yml`:
```yaml
sources:
  - id: my_new_list
    name: "My New Blocklist"
    category: tracking
    url: "https://example.com/list.txt"
    enabled: true
    tier: stable
```

### Create a Custom Profile
Edit `config/profiles.yml`:
```yaml
profiles:
  my_profile:
    include_categories: [tracking, malicious]
    include_sources: []
    exclude_sources: []
    strict: false
```

### Add Private Source
Create `config/sources.local.yml` (from template):
```yaml
sources:
  - id: my_internal_list
    name: "Internal"
    category: tracking
    url: "file:///path/to/internal.txt"
    enabled: true
```

### Allowlist a Domain
Add to `inputs/current_overrides/allowlist.txt`:
```
example.com
subdir.example.com
```

### Reject Lines Matching Pattern
Add regex to `inputs/current_overrides/drop_patterns.txt`:
```regex
^#
^!
sponsored
tracking_service
```

---

## 🚨 Troubleshooting

### Build fails with "Connection refused"
Use `--no-fetch`:
```bash
uv run blocklist-factory build --no-fetch
```

### Config validation fails
Check:
```bash
uv run blocklist-factory validate
```
Review error, check YAML syntax

### Domains disappearing
1. Is the source enabled in `sources.yml`?
2. Is the category in the profile's `include_categories`?
3. Is the domain allowlisted?
4. Does it match a drop pattern?

### Build times increasing
Check size of sources in `.cache/sources/`:
```bash
du -sh .cache/sources/
```
Consider disabling slow sources

### Need to debug parsing
Add prints to `parse.py` or check reason in discard stats:
```bash
uv run blocklist-factory report | jq .discarded
```

---

## 📈 Monitoring

### Check Latest Stats
```bash
uv run blocklist-factory report
```

### Monitor Git Commits
```bash
git log --oneline origin/chore/weekly-update | head -10
```

### View Update PRs
GitHub > Pull Requests > Filter by branch: `chore/weekly-update`

### Monitor Download Sizes
```bash
wc -l dist/all.txt dist/profiles/*.txt
du -h dist/
```

---

## 🔐 Security Notes

### Private Sources
- `config/sources.local.yml` is gitignored
- Use for non-public lists
- Can reference local files with `file://` URLs

### Core Domains Protection
- Non-strict profiles respect `core_domains` in `policies.yml`
- Example: `apple.com`, `google.com` never blocked in base profile
- Prevents accidental outages

### IDNA/Punycode
- Internationalized domains supported
- Converted to ASCII for compatibility

### Input Validation
- All domains validated (FQDN, no IPs, no wildcards)
- YAML parsed with `safe_load()` only
- Regex patterns validated during load

---

## 📚 Documentation Files

- **README.md** - Getting started, CLI reference, troubleshooting
- **docs/ARCHITECTURE.md** - Technical details, design decisions
- **docs/IMPLEMENTATION_SUMMARY.md** - What was built and why
- **docs/pihole_integration.md** - Pi-hole-specific integration

---

## ✅ Pre-Launch Checklist

- [ ] `uv sync --all-extras` runs without errors
- [ ] `uv run blocklist-factory validate` passes
- [ ] `uv run blocklist-factory build --no-fetch` completes
- [ ] `dist/reports/stats.md` shows reasonable numbers
- [ ] Git history looks clean
- [ ] GitHub Actions UI enabled
- [ ] First source added to `config/sources.yml`
- [ ] Pushed to GitHub
- [ ] CI workflow runs successfully
- [ ] Pi-hole URLs configured
- [ ] Domain list updated in Pi-hole
- [ ] Query log shows new list in use

---

## 🎉 You're Ready!

Your production-grade blocklist factory is now:
- ✅ Fully functional
- ✅ Deterministically reproducible
- ✅ CI/CD automated
- ✅ Well documented
- ✅ Ready for Pi-hole integration
- ✅ Extensible for future enhancements

**Start building blocklists!**

```bash
uv run blocklist-factory build
```
