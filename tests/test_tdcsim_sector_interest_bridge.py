from __future__ import annotations

import pandas as pd
import pytest

from tdc_estimator.tdcsim_sector_interest_bridge import (
    MATCHED_TDCSIM_COMPONENTS,
    build_tdcsim_sector_interest_bridge,
    render_tdcsim_sector_interest_bridge_markdown,
    validate_tdcsim_sector_inputs,
)


SECTOR_SHARES = {
    "Banks": 0.20,
    "CB": 0.10,
    "Foreign": 0.30,
    "Private": 0.30,
    "Unallocated": 0.10,
}


def _allocation_rows() -> pd.DataFrame:
    components = [
        ("bill_discount", 100.0, True, True, "certified_quarterly", "official_control_certified_component", 90.0),
        ("coupon_accrual", 200.0, True, True, "certified_quarterly", "official_control_certified_component", 95.0),
        ("tips_coupon_accrual", 10.0, False, True, "candidate_timing_caveated", "official_control_uncertified_component", 80.0),
        ("frn_interest", 20.0, True, True, "certified_quarterly", "official_control_certified_component", 92.0),
        ("tips_inflation_compensation", 40.0, True, True, "certified_quarterly", "official_control_certified_component", 85.0),
    ]
    rows: list[dict[str, object]] = []
    for component_id, official, core, extended, cert_status, allocation_status, coverage in components:
        for sector, share in SECTOR_SHARES.items():
            rows.append(
                {
                    "schema_version": "test",
                    "quarter": "2025Q4",
                    "scope_id": (
                        "extended_with_timing_caveated_tips_coupon"
                        if component_id == "tips_coupon_accrual"
                        else "certified_core_ex_tips_coupon_nonbill_dp"
                    ),
                    "tdc_sector": sector,
                    "tdcsim_holder": sector,
                    "component_id": component_id,
                    "component_in_certified_core_scope": core,
                    "component_in_extended_scope": extended,
                    "weight_source": "fixture",
                    "weight_time_basis": "current" if sector in {"Banks", "CB"} else "prior",
                    "weight_model_version": "fixture",
                    "aggregate_control_basis": "official_treasury_component_pool",
                    "control_quality_tier": (
                        "uncertified_official"
                        if cert_status == "candidate_timing_caveated"
                        else "certified_official"
                    ),
                    "component_certification_status": cert_status,
                    "official_interest_mil": official,
                    "model_interest_mil": official + 1.0,
                    "raw_weight_mil": share * 1000.0,
                    "component_weight_total_mil": 1000.0,
                    "attributed_weight_mil": share * 900.0,
                    "residual_weight_mil": 100.0,
                    "attributed_weight_coverage_pct": coverage,
                    "allocation_share": share,
                    "allocated_official_interest_mil": official * share,
                    "allocated_model_interest_mil": (official + 1.0) * share,
                    "selected_allocated_interest_mil": official * share,
                    "allocation_status": allocation_status,
                }
            )
    return pd.DataFrame(rows)


def _totals_rows(allocation: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for scope, flag in [
        ("certified_core_ex_tips_coupon_nonbill_dp", "component_in_certified_core_scope"),
        ("extended_with_timing_caveated_tips_coupon", "component_in_extended_scope"),
    ]:
        subset = allocation.loc[allocation[flag].astype(bool)]
        grouped = subset.groupby("tdc_sector", as_index=False).agg(
            selected_allocated_interest_mil=("selected_allocated_interest_mil", "sum"),
            allocated_official_interest_mil=("allocated_official_interest_mil", "sum"),
            allocated_model_interest_mil=("allocated_model_interest_mil", "sum"),
            component_count=("component_id", "nunique"),
            tdcsim_holder_count=("tdcsim_holder", "nunique"),
            official_control_component_count=("component_id", "nunique"),
            certified_component_count=("component_id", "nunique"),
            min_attributed_weight_coverage_pct=("attributed_weight_coverage_pct", "min"),
        )
        grouped["quarter"] = "2025Q4"
        grouped["scope_id"] = scope
        grouped["allocation_statuses"] = "official_control_certified_component"
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True)[
        [
            "quarter",
            "scope_id",
            "tdc_sector",
            "selected_allocated_interest_mil",
            "allocated_official_interest_mil",
            "allocated_model_interest_mil",
            "component_count",
            "tdcsim_holder_count",
            "official_control_component_count",
            "certified_component_count",
            "min_attributed_weight_coverage_pct",
            "allocation_statuses",
        ]
    ]


def _candidate_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    values = {
        ("bank", "bill_amortized_discount"): 15.0,
        ("bank", "coupon_accrual"): 30.0,
        ("bank", "frn_accrued_interest"): 5.0,
        ("credit_union", "bill_amortized_discount"): 5.0,
        ("credit_union", "coupon_accrual"): 10.0,
        ("credit_union", "frn_accrued_interest"): 1.0,
        ("row", "bill_amortized_discount"): 30.0,
        ("row", "coupon_accrual"): 60.0,
        ("row", "frn_accrued_interest"): 6.0,
    }
    pools = {
        "bill_amortized_discount": 100.0,
        "coupon_accrual": 210.0,
        "frn_accrued_interest": 20.0,
    }
    for (sector, component), value in values.items():
        rows.append(
            {
                "date": "2025-12-31",
                "sector_group": sector,
                "sector_keys": sector,
                "component_key": component,
                "component_family": component,
                "official_component_pool_mil": pools[component],
                "component_anchored_interest_mil": value,
            }
        )
    return pd.DataFrame(rows)


def _fed_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2025-12-31",
                "fed_tsy_coupon_interest_proxy": 70.0,
                "fed_tsy_bill_discount_interest_proxy": 5.0,
                "fed_tsy_frn_interest_proxy": 2.0,
                "fed_tsy_tips_coupon_interest_proxy": 3.0,
                "fed_tsy_tips_inflation_comp_proxy": 4.0,
            }
        ]
    )


def _bridge_frame() -> pd.DataFrame:
    allocation = _allocation_rows()
    totals = _totals_rows(allocation)
    frame, _manifest = build_tdcsim_sector_interest_bridge(
        allocation=allocation,
        totals=totals,
        component_certification=pd.DataFrame({"quarter": ["2025Q4"]}),
        scope_certification=pd.DataFrame({"quarter": ["2025Q4"]}),
        candidate=_candidate_rows(),
        fed_support=_fed_rows(),
        hashes={},
        expected_release=None,
    )
    return frame


def test_validate_inputs_allows_multiple_weight_time_basis_but_reconciles_totals():
    allocation = _allocation_rows()
    totals = _totals_rows(allocation)

    validate_tdcsim_sector_inputs(allocation, totals, expected_release=None)


def test_bridge_uses_component_matched_cash_set_and_excludes_tips_inflation():
    frame = _bridge_frame()

    assert len(frame) == 5
    assert set(MATCHED_TDCSIM_COMPONENTS) == {
        "bill_discount",
        "coupon_accrual",
        "tips_coupon_accrual",
        "frn_interest",
    }
    assert frame["tdcsim_interest_mil"].sum() == pytest.approx(330.0)
    assert "tips_inflation_compensation" not in frame["tdcsim_component_ids"].iloc[0]
    assert frame["required_component_count"].iloc[0] == 4
    assert frame["timing_caveated_component_count"].iloc[0] == 1


def test_banks_mapping_uses_bank_plus_credit_union_and_does_not_put_cu_under_private():
    frame = _bridge_frame()

    banks = frame.loc[frame["tdcsim_sector"].eq("Banks")].iloc[0]
    private = frame.loc[frame["tdcsim_sector"].eq("Private")].iloc[0]
    assert banks["tdcest_sector_groups"] == "bank;credit_union"
    assert banks["tdcsim_interest_mil"] == pytest.approx(66.0)
    assert banks["tdcest_support_interest_mil"] == pytest.approx(66.0)
    assert banks["delta_eligible"]
    assert banks["delta_tdcsim_minus_tdcest_mil"] == pytest.approx(0.0)
    assert pd.isna(private["tdcest_support_interest_mil"])
    assert private["comparison_status"] == "blocked_unmatched_private"


def test_foreign_cb_and_unallocated_are_blocked_by_default():
    frame = _bridge_frame()

    foreign = frame.loc[frame["tdcsim_sector"].eq("Foreign")].iloc[0]
    cb = frame.loc[frame["tdcsim_sector"].eq("CB")].iloc[0]
    unallocated = frame.loc[frame["tdcsim_sector"].eq("Unallocated")].iloc[0]
    assert not foreign["delta_eligible"]
    assert foreign["comparison_status"] == "blocked_foreign_row_crosswalk_pending"
    assert pd.isna(foreign["delta_tdcsim_minus_tdcest_mil"])
    assert cb["tdcest_support_interest_mil"] == pytest.approx(77.0)
    assert not cb["delta_eligible"]
    assert cb["comparison_status"] == "blocked_fed_component_crosswalk_pending"
    assert unallocated["tdcsim_interest_mil"] == pytest.approx(33.0)
    assert unallocated["comparison_status"] == "report_only_unallocated"
    assert not unallocated["unallocated_redistributed"]


def test_render_markdown_states_diagnostic_boundary():
    frame = _bridge_frame()
    rendered = render_tdcsim_sector_interest_bridge_markdown(
        frame,
        {
            "bridge_version": "test",
            "comparison_set_id": "test_set",
            "row_count": len(frame),
            "quarter_min": "2025Q4",
            "quarter_max": "2025Q4",
        },
    )

    assert "diagnostic only" in rendered
    assert "TIPS inflation compensation is excluded" in rendered
    assert "bank plus credit union" in rendered
    assert "Unallocated redistribution: prohibited" in rendered
