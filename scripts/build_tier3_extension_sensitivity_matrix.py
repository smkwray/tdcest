from __future__ import annotations

import argparse

from tdc_estimator.tier3_sensitivities_figures import write_tier3_extension_sensitivity_matrix_from_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Tier 3 historical research-extension sensitivity matrix.")
    parser.add_argument("--vintages", default="data/processed/tdc_tier3_historical_vintages.csv")
    parser.add_argument("--bank-receipts", default="data/processed/tdc_bank_corp_tax_receipts_bridge_extended.csv")
    parser.add_argument("--out", default="reports/tdc_tier3_extension_sensitivity_matrix.csv")
    parser.add_argument("--markdown-out", default="reports/tdc_tier3_extension_sensitivity_matrix.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_tier3_extension_sensitivity_matrix_from_paths(
        vintages_path=args.vintages,
        bank_receipts_bridge_path=args.bank_receipts,
        csv_path=args.out,
        markdown_path=args.markdown_out,
    )
    print(f"Wrote Tier 3 extension sensitivity matrix to {csv_path}")
    print(f"Wrote Tier 3 extension sensitivity matrix summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
