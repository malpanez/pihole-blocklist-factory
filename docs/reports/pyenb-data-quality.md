# Data quality issue: multiple domains concatenated on single lines (missing newlines)

**Repo:** Pyenb/Pi-hole-blocklist — `blocklist.txt` (main)
**Reported by:** a downstream consumer (pihole-blocklist-factory)

## Summary

A subset of lines in `blocklist.txt` contain **two or more domains concatenated with no
separator** (no newline, no space). Because the concatenation produces a string that is
still a *syntactically valid* FQDN, it silently passes most parsers and lands in the final
blocklist as a single bogus entry that resolves to nothing — inflating counts and polluting
every downstream list.

## Evidence

Byte-level inspection of the raw file (pure `\n` line endings, no `\r`) shows runs like:

```
images-na.ssl-images-amazon.cominit.itunes.apple.comjs.moatads.com
```

which is three separate domains run together with zero delimiter:

- `images-na.ssl-images-amazon.com`
- `init.itunes.apple.com`
- `js.moatads.com`

More examples (each is a single physical line in the file):

```
api-glb-ash.smoot.apple.comat1.listrakbi.com
xp.apple.com131788053.log.optimizely.comaccounts.google.comad.sxp.smartclip.net
0.0.0.0kryptonchain.org            # sink IP glued to the host, also no space
```

Longest single line observed — 128 chars, several phishing domains concatenated:

```
paypal.de-signin-sicherheit-7295.paypal.de-signin-sicherheit-3339.amazon.de-signin-meinkundenservice-4630.amazon.de-signin-siche...
```

Line-length distribution (2,658,759 lines total): ~25,800 lines are 51–80 chars and ~767
lines exceed 80 chars — well beyond a single domain, consistent with concatenation.

## Impact on consumers

These entries cannot be safely repaired downstream: because `apple.comjs` is a valid DNS
label and the whole string ends in a real TLD, a consumer cannot tell `apple.com`+`js...`
from a single legitimate domain without risking deletion of real domains (we measured a
PSL-based splitter at up to ~37% false positives on legitimate domains). So the only robust
fix is **at the source** — i.e. here.

## Likely cause

A generation/merge step is dropping line separators when concatenating chunks or sources
(e.g. writing records without a trailing `\n`, or joining lists without a separator). The
host-IP cases (`0.0.0.0kryptonchain.org`) suggest the same when emitting hosts-format lines.

## Suggested fix

- Ensure exactly **one domain per line** with a trailing newline on every record.
- A cheap CI guard: reject any output line that, after stripping a leading sink IP, contains
  more than one registrable domain (validate against the Public Suffix List), or simply flag
  lines whose length/label-count is implausible for a single FQDN.

Happy to share the full list of affected lines if useful. Thanks for maintaining the list!
