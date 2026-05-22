from __future__ import annotations

import argparse

from tdc_estimator.row_mrv_bea_overlay import write_row_mrv_bea_overlay_from_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the non-additive MRV overlay against the BEA ROW receipts anchor.")
    parser.add_argument("--bea-anchor", default="data/processed/tdc_bea_row_receipts_anchor_extended.csv")
    parser.add_argument("--mrv-timing", default="data/processed/tdc_row_state_visa_timing_sensitivity.csv")
    parser.add_argument("--out", default="data/processed/tdc_row_mrv_bea_overlay.csv")
    parser.add_argument("--markdown-out", default="data/processed/tdc_row_mrv_bea_overlay.md")
    parser.add_argument("--start", default="2003-03-31")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_row_mrv_bea_overlay_from_paths(
        bea_anchor_path=args.bea_anchor,
        row_state_visa_timing_sensitivity_path=args.mrv_timing,
        csv_path=args.out,
        markdown_path=args.markdown_out,
        start=args.start,
    )
    print(f"Wrote ROW MRV BEA overlay to {csv_path}")
    print(f"Wrote ROW MRV BEA overlay summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
