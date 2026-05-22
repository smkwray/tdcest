from __future__ import annotations

import argparse

from tdc_estimator.bank_corp_tax_receipts_bridge import write_bank_corp_tax_receipts_bridge_guardrail_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit guardrails for the extended bank corporate-tax receipts bridge.")
    parser.add_argument("--bridge", default="data/processed/tdc_bank_corp_tax_receipts_bridge_extended.csv")
    parser.add_argument("--out", default="data/processed/tdc_bank_corp_tax_receipts_bridge_guardrail_audit.csv")
    parser.add_argument("--markdown-out", default="data/processed/tdc_bank_corp_tax_receipts_bridge_guardrail_audit.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_bank_corp_tax_receipts_bridge_guardrail_audit(
        bridge_path=args.bridge,
        csv_path=args.out,
        markdown_path=args.markdown_out,
    )
    print(f"Wrote bank corporate-tax receipts bridge guardrail audit to {csv_path}")
    if markdown_path is not None:
        print(f"Wrote bank corporate-tax receipts bridge guardrail audit summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
