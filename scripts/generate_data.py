#!/usr/bin/env python
"""Generate synthetic loyalty dataset."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from loyalty_ledger.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["generate", "--scale", "starter", "--seed", "20261022"])
    elif sys.argv[1] != "generate":
        sys.argv.insert(1, "generate")
    main()
