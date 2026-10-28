#!/usr/bin/env python
"""Export dataset to CSV, JSON, and SQL formats."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from loyalty_ledger.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["export", "--scale", "starter"])
    elif sys.argv[1] != "export":
        sys.argv.insert(1, "export")
    main()
