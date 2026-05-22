from __future__ import annotations

import argparse

from tdc_estimator.mts_previous_issues import write_mts_fas_early_window_qa


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the 2003-2004 Financial Agent Services manual-QA decision artifact.")
    parser.add_argument("--manifest", default="data/raw/treasury__mts_previous_issues_manifest.csv")
    parser.add_argument("--table5-history", default="data/raw/treasury__mts_table5_target_history.csv")
    parser.add_argument("--out", default="reports/mts_fas_2003_2004_manual_qa.csv")
    parser.add_argument("--markdown-out", default="reports/mts_fas_2003_2004_manual_qa.md")
    parser.add_argument("--start", default="2003-01-31")
    parser.add_argument("--end", default="2004-12-31")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_mts_fas_early_window_qa(
        manifest_path=args.manifest,
        table5_history_path=args.table5_history,
        csv_path=args.out,
        markdown_path=args.markdown_out,
        start=args.start,
        end=args.end,
    )
    print(f"Wrote MTS FAS early-window QA to {csv_path}")
    print(f"Wrote MTS FAS early-window QA summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
