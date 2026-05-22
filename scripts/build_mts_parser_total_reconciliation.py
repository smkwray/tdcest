from __future__ import annotations

import argparse

from tdc_estimator.mts_previous_issues import write_mts_parser_total_reconciliation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile parsed previous-issue MTS printed total lines against summary totals.")
    parser.add_argument("--manifest", default="data/raw/treasury__mts_previous_issues_manifest.csv")
    parser.add_argument("--table4-history", default="data/raw/treasury__mts_table4_target_history.csv")
    parser.add_argument("--out", default="reports/mts_parser_total_reconciliation.csv")
    parser.add_argument("--markdown-out", default="reports/mts_parser_total_reconciliation.md")
    parser.add_argument("--tolerance-mil", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_mts_parser_total_reconciliation(
        manifest_path=args.manifest,
        table4_history_path=args.table4_history,
        csv_path=args.out,
        markdown_path=args.markdown_out,
        tolerance_mil=args.tolerance_mil,
    )
    print(f"Wrote MTS parser total reconciliation to {csv_path}")
    print(f"Wrote MTS parser total reconciliation summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
