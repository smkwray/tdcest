from __future__ import annotations

import argparse

from tdc_estimator.irs_soi import write_publication16_bank_tax_share_table_from_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse cached IRS Publication 16 bank-share sources into a historical/current share table."
    )
    parser.add_argument("--manifest", default="data/raw/irs__soi_bank_share_source_manifest.csv")
    parser.add_argument("--out", default="data/raw/irs__soi_bank_tax_shares_extended.csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = write_publication16_bank_tax_share_table_from_manifest(
        manifest_path=args.manifest,
        out_path=args.out,
    )
    print(f"Wrote extended IRS SOI bank-tax share table to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
