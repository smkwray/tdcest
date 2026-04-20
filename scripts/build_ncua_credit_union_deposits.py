from __future__ import annotations

import argparse
from pathlib import Path

from tdc_estimator.ncua_call_report import write_ncua_credit_union_deposit_bridge


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download NCUA quarterly Call Report ZIPs and normalize a credit-union deposit bridge."
    )
    parser.add_argument("--out", default="data/raw/ncua__credit_union_deposit_bridge.csv")
    parser.add_argument("--support-out", default="data/raw/support__credit_union_deposits.csv")
    parser.add_argument("--cache-dir", default="data/raw/_cache_ncua_call_report")
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2025)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path, support_path, _ = write_ncua_credit_union_deposit_bridge(
        out_path=Path(args.out),
        support_out_path=Path(args.support_out),
        cache_dir=Path(args.cache_dir),
        start_year=args.start_year,
        end_year=args.end_year,
    )
    print(f"Wrote NCUA credit-union bridge to {out_path}")
    print(f"Wrote support series to {support_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
