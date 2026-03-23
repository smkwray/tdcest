from __future__ import annotations

import sys

from tdc_estimator.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["build", *sys.argv[1:]]))
