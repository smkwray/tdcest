#!/usr/bin/env python3
from __future__ import annotations

import sys

from tdc_estimator.cli import main


if __name__ == "__main__":
    sys.exit(main(["mts-table5-target-history", *sys.argv[1:]]))
