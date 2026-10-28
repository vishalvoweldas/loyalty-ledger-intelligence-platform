#!/usr/bin/env python
"""Validate loyalty dataset integrity."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from loyalty_ledger.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["validate", "--mode", "baseline"])
    elif sys.argv[1] != "validate":
        sys.argv.insert(1, "validate")
    main()
