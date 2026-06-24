from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tdc_estimator.tdcsim_interest_certification_bridge import (
    CERTIFIED_SCOPE_ID,
    build_tdcsim_interest_certification_bridge,
    render_tdcsim_interest_certification_bridge_markdown,
    write_tdcsim_interest_certification_bridge,
)


def _scope_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quarter": "2025Q4",
                "scope_id": CERTIFIED_SCOPE_ID,
                "scope_claim": "quarterly certified core marketable interest excluding caveated components",
                "expected_components": "bill_discount;coupon_accrual",
                "certified_components": "bill_discount;coupon_accrual",
                "excluded_components": "tips_coupon_accrual;frn_discount_premium",
                "official_scope_total_mil": 253_307.425,
                "model_scope_total_mil": 253_310.577,
                "official_excluded_amount_mil": 5_859.877,
                "gap_mil": 3.152,
                "ape_pct": 0.001244,
                "certification_status": "certified_quarterly",
            }
        ]
    )


def _component_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quarter": "2025Q4",
                "component_id": "bill_discount",
                "certification_status": "certified_quarterly",
                "included_in_scope": True,
            },
            {
                "quarter": "2025Q4",
                "component_id": "coupon_accrual",
                "certification_status": "certified_quarterly",
                "included_in_scope": True,
            },
            {
                "quarter": "2025Q4",
                "component_id": "tips_coupon_accrual",
                "certification_status": "candidate_timing_caveated",
                "included_in_scope": False,
            },
            {
                "quarter": "2025Q4",
                "component_id": "frn_discount_premium",
                "certification_status": "excluded_selected_scope",
                "included_in_scope": False,
            },
        ]
    )


def test_build_tdcsim_interest_certification_bridge_marks_crosscheck_noncanonical():
    estimates = pd.DataFrame(
        [
            {
                "date": "2025-12-31",
                "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow": 123.4,
            }
        ]
    )

    out = build_tdcsim_interest_certification_bridge(
        _scope_rows(),
        _component_rows(),
        estimates=estimates,
        component_certification_sha256="componenthash",
        scope_certification_sha256="scopehash",
        tdcest_estimates_sha256="estimateshash",
    )

    row = out.iloc[0]
    assert row["date"] == "2025-12-31"
    assert row["tdcsim_scope_certification_status"] == "certified_quarterly"
    assert row["tdcest_use_status"] == "aggregate_certified_crosscheck_available"
    assert row["tdcest_permitted_use"] == "aggregate_component_contract_crosscheck_only"
    assert "sector_interest_bounds" in row["tdcest_blocked_use"]
    assert bool(row["sector_bound_eligible"]) is False
    assert bool(row["canonical_tdc_math_change"]) is False
    assert bool(row["tdcest_canonical_row_present"]) is True
    assert row["tdcest_canonical_value_mil"] == pytest.approx(123.4)
    assert row["included_component_count"] == 2
    assert row["certified_included_component_count"] == 2
    assert row["timing_caveated_component_count"] == 1
    assert row["excluded_component_count"] == 1
    assert row["component_certification_sha256"] == "componenthash"
    assert row["scope_certification_sha256"] == "scopehash"
    assert row["tdcest_estimates_sha256"] == "estimateshash"
    assert row["tdcest_canonical_column"] == "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"


def test_write_tdcsim_interest_certification_bridge(tmp_path: Path):
    scope_path = tmp_path / "scope.csv"
    component_path = tmp_path / "component.csv"
    estimates_path = tmp_path / "estimates.csv"
    out_csv = tmp_path / "bridge.csv"
    out_md = tmp_path / "bridge.md"
    _scope_rows().to_csv(scope_path, index=False)
    _component_rows().to_csv(component_path, index=False)
    pd.DataFrame({"date": ["2025-12-31"]}).to_csv(estimates_path, index=False)

    csv_path, md_path, frame = write_tdcsim_interest_certification_bridge(
        scope_certification_path=scope_path,
        component_certification_path=component_path,
        estimates_path=estimates_path,
        csv_path=out_csv,
        markdown_path=out_md,
    )

    assert csv_path == out_csv
    assert md_path == out_md
    assert len(frame) == 1
    assert out_csv.exists()
    assert "Blocked use" in out_md.read_text(encoding="utf-8")


def test_bridge_schema_fails_loudly_on_missing_required_scope_columns():
    with pytest.raises(ValueError, match="tdcsim scope certification missing required columns"):
        build_tdcsim_interest_certification_bridge(
            pd.DataFrame({"quarter": ["2025Q4"]}),
            _component_rows(),
        )


def test_render_tdcsim_interest_certification_bridge_markdown_empty():
    rendered = render_tdcsim_interest_certification_bridge_markdown(pd.DataFrame())
    assert "No TDCSIM certification rows" in rendered
