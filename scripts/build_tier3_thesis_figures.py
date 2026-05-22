from __future__ import annotations

import argparse

from tdc_estimator.tier3_sensitivities_figures import write_tier3_thesis_figures_from_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build thesis figure drafts for the Tier 3 historical research extension.")
    parser.add_argument("--estimates", default="data/processed/tdc_estimates.csv")
    parser.add_argument("--sensitivity-matrix", default="reports/tdc_tier3_extension_sensitivity_matrix.csv")
    parser.add_argument("--out-dir", default="figures")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = write_tier3_thesis_figures_from_paths(
        estimates_path=args.estimates,
        sensitivity_matrix_path=args.sensitivity_matrix,
        out_dir=args.out_dir,
    )
    for output in outputs:
        print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
