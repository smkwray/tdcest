#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from tdc_estimator.tdcsim_interest_certification_bridge import (
    CERTIFIED_SCOPE_ID,
    write_tdcsim_interest_certification_bridge,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TDCSIM_VALIDATION = ROOT.parent / "tdcsim" / "data/historical_replay/validation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope-certification",
        default=str(DEFAULT_TDCSIM_VALIDATION / "historical_replay_interest_scope_certification.csv"),
    )
    parser.add_argument(
        "--component-certification",
        default=str(DEFAULT_TDCSIM_VALIDATION / "historical_replay_interest_component_certification.csv"),
    )
    parser.add_argument("--estimates", default=str(ROOT / "data/processed/tdc_estimates.csv"))
    parser.add_argument(
        "--output",
        default=str(ROOT / "data/processed/tdc_tdcsim_interest_certification_bridge.csv"),
    )
    parser.add_argument(
        "--markdown-output",
        default=str(ROOT / "data/processed/tdc_tdcsim_interest_certification_bridge.md"),
    )
    parser.add_argument("--scope-id", default=CERTIFIED_SCOPE_ID)
    parser.add_argument(
        "--canonical-column",
        default="tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path, markdown_path, frame = write_tdcsim_interest_certification_bridge(
        scope_certification_path=args.scope_certification,
        component_certification_path=args.component_certification,
        estimates_path=args.estimates,
        csv_path=args.output,
        markdown_path=args.markdown_output,
        scope_id=args.scope_id,
        canonical_column=args.canonical_column,
    )
    print(f"wrote {csv_path}")
    print(f"wrote {markdown_path}")
    print(frame.tail(16).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
