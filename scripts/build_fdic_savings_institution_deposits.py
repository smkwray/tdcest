from __future__ import annotations

import argparse
from pathlib import Path

from tdc_estimator.fdic_savings_institution import write_fdic_savings_institution_deposit_bridge


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download FDIC quarterly savings-institution financial snapshots and normalize a thrift deposit bridge."
    )
    parser.add_argument("--out", default="data/raw/fdic__savings_institution_deposit_bridge.csv")
    parser.add_argument("--support-out", default="data/raw/support__thrift_deposits.csv")
    parser.add_argument("--cache-dir", default="data/raw/_cache_fdic_financials")
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path, support_path, _ = write_fdic_savings_institution_deposit_bridge(
        out_path=Path(args.out),
        support_out_path=Path(args.support_out),
        cache_dir=Path(args.cache_dir),
        start_year=args.start_year,
        end_year=args.end_year,
    )
    print(f"Wrote FDIC savings-institution bridge to {out_path}")
    print(f"Wrote support series to {support_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
