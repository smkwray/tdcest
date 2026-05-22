from __future__ import annotations

import argparse

from tdc_estimator.bank_corp_tax_receipts_bridge import write_bank_corp_tax_receipts_bridge


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Tier 3 research extended bank corporate-tax receipts bridge from stitched MTS cash and extended IRS shares."
    )
    parser.add_argument("--mts-receipts", default="data/raw/treasury__mts_receipts_stitched_targets.csv")
    parser.add_argument("--irs-shares", default="data/raw/irs__soi_bank_tax_shares_extended.csv")
    parser.add_argument("--out", default="data/processed/tdc_bank_corp_tax_receipts_bridge_extended.csv")
    parser.add_argument("--markdown-out", default="data/processed/tdc_bank_corp_tax_receipts_bridge_extended.md")
    parser.add_argument("--start", default="2003-03-31")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_bank_corp_tax_receipts_bridge(
        mts_receipts_path=args.mts_receipts,
        irs_soi_bank_tax_shares_path=args.irs_shares,
        csv_path=args.out,
        markdown_path=args.markdown_out,
        start=args.start,
    )
    print(f"Wrote extended bank corporate-tax receipts bridge to {csv_path}")
    print(f"Wrote extended bank corporate-tax receipts bridge summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
