from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier2_live_delta_acceptance import (
    build_tier2_live_delta_acceptance,
    summarize_tier2_live_delta_acceptance,
    write_tier2_live_delta_acceptance,
)


def _delta_attribution() -> pd.DataFrame:
    rows = []
    for sector, component, component_total, current, delta in [
        ("bank", "coupon_accrual", 80.0, 100.0, -20.0),
        ("bank", "frn_accrued_interest", 10.0, 0.0, 10.0),
        ("bank", "sector_total", 90.0, 100.0, -10.0),
        ("row", "coupon_accrual", 150.0, 200.0, -50.0),
        ("row", "frn_accrued_interest", 20.0, 0.0, 20.0),
        ("row", "sector_total", 170.0, 200.0, -30.0),
        ("credit_union", "coupon_accrual", 9.0, 10.0, -1.0),
        ("credit_union", "sector_total", 9.0, 10.0, -1.0),
    ]:
        rows.append(
            {
                "date": "2025-12-31",
                "sector_group": sector,
                "component_key": component,
                "component_anchored_interest_mil": component_total,
                "current_proxy_comparable_mil": current,
                "component_minus_current_mil": delta,
            }
        )
    return pd.DataFrame(rows)


def test_build_tier2_live_delta_acceptance_accepts_attributed_deltas() -> None:
    out = build_tier2_live_delta_acceptance(_delta_attribution())

    gate = out.loc[out["sector_group"].eq("all_selected")].iloc[0]
    row = out.loc[out["sector_group"].eq("row")].iloc[0]
    assert gate["acceptance_status"] == "accepted_caveat"
    assert row["dominant_delta_component"] == "coupon_accrual"
    assert row["acceptance_status"] == "accepted_method_delta"


def test_write_tier2_live_delta_acceptance(tmp_path: Path) -> None:
    source = tmp_path / "delta.csv"
    out_csv = tmp_path / "acceptance.csv"
    out_md = tmp_path / "acceptance.md"
    _delta_attribution().to_csv(source, index=False)

    written_csv, written_md, frame = write_tier2_live_delta_acceptance(
        delta_attribution_path=source,
        out_csv_path=out_csv,
        out_markdown_path=out_md,
    )

    assert written_csv == out_csv
    assert written_md == out_md
    assert out_csv.exists()
    assert "Acceptance status" in out_md.read_text(encoding="utf-8")
    assert "accepted_caveat" in summarize_tier2_live_delta_acceptance(frame)
