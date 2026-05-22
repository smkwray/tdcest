from __future__ import annotations

import argparse

from tdc_estimator.tier3_pre2003_feasibility import write_tier3_pre2003_feasibility_panel_from_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the partial 1999-2002 Tier 3 feasibility bridge.")
    parser.add_argument("--mts-outlays", default="data/raw/treasury__mts_outlays_previous_targets_1999_2002.csv")
    parser.add_argument("--mts-receipts", default="data/raw/treasury__mts_receipts_previous_targets_1999_2002.csv")
    parser.add_argument("--bea-row-anchor", default="data/processed/tdc_bea_row_receipts_anchor_1999_2002.csv")
    parser.add_argument("--out", default="data/processed/tdc_tier3_pre2003_feasibility.csv")
    parser.add_argument("--markdown-out", default="data/processed/tdc_tier3_pre2003_feasibility.md")
    parser.add_argument("--start", default="1999-03-31")
    parser.add_argument("--end", default="2002-12-31")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_tier3_pre2003_feasibility_panel_from_paths(
        mts_outlays_path=args.mts_outlays,
        mts_receipts_path=args.mts_receipts,
        bea_row_anchor_path=args.bea_row_anchor,
        csv_path=args.out,
        markdown_path=args.markdown_out,
        start=args.start,
        end=args.end,
    )
    print(f"Wrote Tier 3 pre-2003 feasibility panel to {csv_path}")
    print(f"Wrote Tier 3 pre-2003 feasibility summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
