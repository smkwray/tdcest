from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from tdc_estimator.irs_soi import (
    download_publication16_table53_xlsx,
    write_publication16_table53_availability_table,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download IRS Publication 16 Table 5.3 workbooks and normalize bank minor-industry availability."
    )
    parser.add_argument("--out", default="data/raw/irs__soi_bank_minor_industry_availability.csv")
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2022)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = list(range(args.start_year, args.end_year + 1))
    with tempfile.TemporaryDirectory(prefix="tdcest-irs-soi-53-") as tmpdir:
        paths = []
        for year in years:
            path = Path(tmpdir) / f"{year}co53ccr.xlsx"
            download_publication16_table53_xlsx(year, path)
            paths.append(path)
        out_path = write_publication16_table53_availability_table(paths, out_path=args.out)
    print(f"Wrote IRS SOI bank minor-industry availability table to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
