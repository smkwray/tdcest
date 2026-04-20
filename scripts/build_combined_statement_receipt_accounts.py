from __future__ import annotations

from pathlib import Path

from tdc_estimator.combined_statement_accounts import write_combined_statement_receipt_accounts_support


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_path = root / "data" / "raw" / "support__combined_statement_receipt_accounts.csv"
    cache_dir = root / "data" / "raw" / "_cache_combined_statement"
    written = write_combined_statement_receipt_accounts_support(
        out_path=out_path,
        cache_dir=cache_dir,
    )
    print(f"Wrote Combined Statement receipt-account support to {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
