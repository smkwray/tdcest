from __future__ import annotations

import argparse

from tdc_estimator.tier3_component_crosswalk import write_tier3_component_crosswalk


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the private Tier 3 historical-extension component crosswalk.")
    parser.add_argument("--out", default="data/processed/tdc_tier3_component_crosswalk.csv")
    parser.add_argument("--markdown-out", default="data/processed/tdc_tier3_component_crosswalk.md")
    parser.add_argument("--validation-out", default="data/processed/tdc_tier3_component_crosswalk_validation.csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, _ = write_tier3_component_crosswalk(
        csv_path=args.out,
        markdown_path=args.markdown_out,
        validation_path=args.validation_out,
    )
    print(f"Wrote Tier 3 component crosswalk to {csv_path}")
    print(f"Wrote Tier 3 component crosswalk summary to {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
