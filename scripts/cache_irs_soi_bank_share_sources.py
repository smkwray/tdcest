from __future__ import annotations

import argparse

from tdc_estimator.irs_soi import write_cached_publication16_bank_share_sources_from_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download/cache IRS Publication 16 bank-share source workbooks from a manifest.")
    parser.add_argument("--manifest", default="data/raw/irs__soi_bank_share_source_manifest.csv")
    parser.add_argument("--out", default=None, help="Updated manifest path. Defaults to overwriting --manifest.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = write_cached_publication16_bank_share_sources_from_manifest(
        manifest_path=args.manifest,
        out_path=args.out,
        overwrite=args.overwrite,
        continue_on_error=not args.fail_fast,
    )
    print(f"Wrote cached IRS SOI bank-share source manifest to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
