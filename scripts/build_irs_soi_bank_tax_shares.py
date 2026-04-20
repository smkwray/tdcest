from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from tdc_estimator.irs_soi import download_publication16_table51_xlsx, write_publication16_table51_share_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download IRS Publication 16 Table 5.1 workbooks and normalize annual bank-minor tax shares."
    )
    parser.add_argument("--out", default="data/raw/irs__soi_bank_tax_shares.csv")
    parser.add_argument("--start-year", type=int, default=2014)
    parser.add_argument("--end-year", type=int, default=2022)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = list(range(args.start_year, args.end_year + 1))
    with tempfile.TemporaryDirectory(prefix="tdcest-irs-soi-") as tmpdir:
        paths = []
        for year in years:
            path = Path(tmpdir) / f"{year}co51ccr.xlsx"
            download_publication16_table51_xlsx(year, path)
            paths.append(path)
        out_path = write_publication16_table51_share_table(paths, out_path=args.out)
    print(f"Wrote IRS SOI bank-tax share table to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
