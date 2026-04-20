from __future__ import annotations

import argparse
from pathlib import Path

from tdc_estimator.state_visa_issuances import write_state_visa_monthly_issuances


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and normalize monthly State NIV/IV issuance totals.")
    parser.add_argument("--out", default="data/raw/state__visa_issuances_monthly.csv")
    parser.add_argument("--cache-dir", default="data/raw/_cache_state_visa")
    parser.add_argument("--fiscal-year-start", type=int, default=2023)
    parser.add_argument("--fiscal-year-end", type=int, default=2025)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    write_state_visa_monthly_issuances(
        out_path=Path(args.out),
        cache_dir=Path(args.cache_dir),
        fiscal_year_start=args.fiscal_year_start,
        fiscal_year_end=args.fiscal_year_end,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
