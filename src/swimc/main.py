#!/usr/bin/env python3
"""Entry point for the Swim compiler when run from a checkout."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swimc.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
