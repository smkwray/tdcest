#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from tdc_estimator.tdcsim_sector_interest_bridge import write_tdcsim_sector_interest_bridge


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TDCSIM_VALIDATION = ROOT.parent / "tdcsim" / "data/historical_replay/validation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the TDCSIM/TDC-est sector-interest diagnostic bridge.")
    parser.add_argument(
        "--allocation",
        default=str(DEFAULT_TDCSIM_VALIDATION / "historical_replay_sector_interest_allocation.csv"),
    )
    parser.add_argument(
        "--totals",
        default=str(DEFAULT_TDCSIM_VALIDATION / "historical_replay_sector_interest_totals.csv"),
    )
    parser.add_argument(
        "--component-certification",
        default=str(DEFAULT_TDCSIM_VALIDATION / "historical_replay_interest_component_certification.csv"),
    )
    parser.add_argument(
        "--scope-certification",
        default=str(DEFAULT_TDCSIM_VALIDATION / "historical_replay_interest_scope_certification.csv"),
    )
    parser.add_argument(
        "--candidate",
        default=str(ROOT / "data/processed/tier2_interest_component_candidate.csv"),
    )
    parser.add_argument(
        "--fed-support",
        default=str(ROOT / "data/raw/support__fed_treasury_interest_components.csv"),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data/processed/tdc_tdcsim_sector_interest_bridge.csv"),
    )
    parser.add_argument(
        "--markdown-output",
        default=str(ROOT / "data/processed/tdc_tdcsim_sector_interest_bridge.md"),
    )
    parser.add_argument(
        "--manifest-output",
        default=str(ROOT / "data/processed/tdc_tdcsim_sector_interest_bridge_manifest.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, manifest_path, frame, _manifest = write_tdcsim_sector_interest_bridge(
        allocation_path=args.allocation,
        totals_path=args.totals,
        component_certification_path=args.component_certification,
        scope_certification_path=args.scope_certification,
        candidate_path=args.candidate,
        fed_support_path=args.fed_support,
        csv_path=args.output,
        markdown_path=args.markdown_output,
        manifest_path=args.manifest_output,
        canonical_immutability_paths=[
            ROOT / "data/processed/tdc_estimates.csv",
            ROOT / "data/processed/tdc_components.csv",
            ROOT / "data/processed/method_meta.json",
        ],
    )
    print(f"wrote {csv_path}")
    print(f"wrote {markdown_path}")
    print(f"wrote {manifest_path}")
    latest = frame.loc[frame["quarter"].eq(frame["quarter"].max())]
    print(latest[["quarter", "tdcsim_sector", "tdcsim_interest_mil", "tdcest_support_interest_mil", "comparison_status"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
