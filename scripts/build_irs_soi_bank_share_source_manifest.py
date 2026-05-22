from __future__ import annotations

import argparse

from tdc_estimator.irs_soi import write_publication16_bank_share_source_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write an IRS Publication 16 source manifest for historical bank-minor tax share extraction."
    )
    parser.add_argument("--out", default="data/raw/irs__soi_bank_share_source_manifest.csv")
    parser.add_argument("--start-year", type=int, default=2003)
    parser.add_argument("--end-year", type=int, default=2022)
    parser.add_argument("--cache-dir", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = write_publication16_bank_share_source_manifest(
        out_path=args.out,
        start_year=args.start_year,
        end_year=args.end_year,
        cache_dir=args.cache_dir,
    )
    print(f"Wrote IRS SOI bank-share source manifest to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
