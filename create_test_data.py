#!/usr/bin/env python3
"""Create realistic test data (synthetic blocklists) for local testing."""

from pathlib import Path

# Create synthetic test lists
test_lists_dir = Path("/home/malpanez/repos/pihole-blocklist-factory/inputs/test_lists")
test_lists_dir.mkdir(parents=True, exist_ok=True)

# Synthetic advertising list
(test_lists_dir / "ads_synthetic.txt").write_text("""# Synthetic advertising blocklist
ads.example.com
ads2.example.net
tracker-ads.example.org
adserving.com
advertising.net
0.0.0.0 ads.double-click.net
127.0.0.1 ads.google.com
""")

# Synthetic tracking list
(test_lists_dir / "tracking_synthetic.txt").write_text("""# Synthetic tracking blocklist
tracking.example.com
analytics.example.net
metrics.example.org
pixel.example.com
""")

# Synthetic malicious list
(test_lists_dir / "malicious_synthetic.txt").write_text("""# Synthetic malicious blocklist
malware.example.com
botnet.example.net
phishing.example.org
""")

print(f"✓ Created synthetic test lists in {test_lists_dir}")
for f in test_lists_dir.glob("*.txt"):
    count = len(f.read_text().splitlines())
    print(f"  {f.name}: {count} lines")
