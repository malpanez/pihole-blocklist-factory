#!/usr/bin/env python3
"""Build runner convenience script."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from blocklist_builder.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["build"]))
