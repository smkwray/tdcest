from __future__ import annotations

import argparse

from tdc_estimator.bea_row_receipts_benchmark import write_bea_row_receipts_benchmark_from_fred_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the historical BEA/NIPA ROW federal receipts anchor from verified Table 3.2 series.")
    parser.add_argument("--taxes", default="data/raw/fred__bea_row_taxes_received_saar.csv")
    parser.add_argument("--social-insurance", default="data/raw/fred__bea_row_social_insurance_received_saar.csv")
    parser.add_argument("--current-transfers", default="data/raw/fred__bea_row_current_transfer_receipts_received_saar.csv")
    parser.add_argument("--out", default="data/processed/tdc_bea_row_receipts_anchor_extended.csv")
    parser.add_argument("--markdown-out", default="data/processed/tdc_bea_row_receipts_anchor_extended.md")
    parser.add_argument("--start", default="2003-03-31")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_bea_row_receipts_benchmark_from_fred_paths(
        taxes_path=args.taxes,
        social_insurance_path=args.social_insurance,
        current_transfers_path=args.current_transfers,
        csv_path=args.out,
        markdown_path=args.markdown_out,
        start=args.start,
    )
    print(f"Wrote extended BEA ROW receipts anchor to {csv_path}")
    print(f"Wrote extended BEA ROW receipts anchor summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
