#!/usr/bin/env python3
"""Optimized build runner with better error handling for network."""

import os
import sys
from pathlib import Path

import urllib3

# Disable SSL verification warnings (optional, for this environment)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from blocklist_builder.cli import main  # noqa: E402

if __name__ == "__main__":
    # Try with SSL verification disabled (temporary for testing)
    os.environ["PYTHONHTTPSVERIFY"] = "0"
    
    # Run build
    sys.exit(main(["build"]))
