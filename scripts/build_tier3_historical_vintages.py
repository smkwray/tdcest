from __future__ import annotations

import argparse

from tdc_estimator.tier3_historical_vintages import write_tier3_historical_vintages_from_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Tier 3 historical research vintage correction deltas.")
    parser.add_argument("--mts-outlays", default="data/raw/treasury__mts_outlays_stitched_targets.csv")
    parser.add_argument("--bank-receipts", default="data/processed/tdc_bank_corp_tax_receipts_bridge_extended.csv")
    parser.add_argument("--bea-row-anchor", default="data/processed/tdc_bea_row_receipts_anchor_extended.csv")
    parser.add_argument("--mrv-overlay", default="data/processed/tdc_row_mrv_bea_overlay.csv")
    parser.add_argument("--out", default="data/processed/tdc_tier3_historical_vintages.csv")
    parser.add_argument("--markdown-out", default="data/processed/tdc_tier3_historical_vintages.md")
    parser.add_argument("--start", default="2003-03-31")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_tier3_historical_vintages_from_paths(
        mts_outlays_path=args.mts_outlays,
        bank_receipts_bridge_path=args.bank_receipts,
        bea_row_anchor_path=args.bea_row_anchor,
        mrv_overlay_path=args.mrv_overlay,
        csv_path=args.out,
        markdown_path=args.markdown_out,
        start=args.start,
    )
    print(f"Wrote Tier 3 historical vintages to {csv_path}")
    print(f"Wrote Tier 3 historical vintages summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
