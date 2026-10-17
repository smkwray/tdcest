"""Export monthly TRC (last-Wednesday clock, money-fund route term) from a processed vintage directory."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tdc_estimator.trc_monthly import export


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=ROOT / "data/refresh_2026q2/data/processed")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/refresh_2026q2_monthly/trc_monthly_v1")
    args = parser.parse_args(argv)
    receipt = export(args.processed, args.out_dir)
    print(json.dumps(receipt["outputs"] | {"coverage": receipt["coverage"], "checks": receipt["checks"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
