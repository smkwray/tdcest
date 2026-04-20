from __future__ import annotations

import argparse
from pathlib import Path

from tdc_estimator.tier3_provisional import write_provisional_tier3_input_table


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a provisional Tier 3 quarterly input table from existing Tier 2 support files.")
    parser.add_argument("--bank-coupon-path", default="data/raw/support__bank_tsy_coupon_interest_proxy.csv")
    parser.add_argument("--row-coupon-path", default="data/raw/support__row_tsy_coupon_interest_proxy.csv")
    parser.add_argument("--out", default="examples/tier3-quarterly-input-template.csv")
    parser.add_argument("--start", default="2022-09-30")
    parser.add_argument("--bank-outlay-ratio", type=float, default=0.15)
    parser.add_argument("--row-outlay-ratio", type=float, default=0.10)
    parser.add_argument("--bank-receipt-ratio", type=float, default=0.05)
    parser.add_argument("--row-receipt-ratio", type=float, default=0.03)
    parser.add_argument("--mint-cb-cash-factor-value", type=float, default=0.25)
    args = parser.parse_args()

    written = write_provisional_tier3_input_table(
        bank_coupon_path=Path(args.bank_coupon_path),
        row_coupon_path=Path(args.row_coupon_path),
        out_path=Path(args.out),
        start=args.start,
        bank_outlay_ratio=args.bank_outlay_ratio,
        row_outlay_ratio=args.row_outlay_ratio,
        bank_receipt_ratio=args.bank_receipt_ratio,
        row_receipt_ratio=args.row_receipt_ratio,
        mint_cb_cash_factor_value=args.mint_cb_cash_factor_value,
    )
    print(f"Wrote provisional Tier 3 quarterly input table to {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
