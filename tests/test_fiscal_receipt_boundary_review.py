from __future__ import annotations

import pandas as pd

from tdc_estimator.fiscal_receipt_boundary_review import build_fiscal_receipt_boundary_review


def test_fiscal_receipt_boundary_review_maps_live_historical_and_pilot_receipt_roles() -> None:
    fiscal_quality = pd.DataFrame(
        [
            {
                "row_family": "nonborrow_receipts",
                "counterparty_column": "banks_default",
                "source": "tier3_support_file",
                "last_date": "2025-12-31",
                "latest_value_millions": 0.0,
                "notes": "Current default bank nonborrow-receipt correction. This remains zero in the live source-backed build.",
            },
            {
                "row_family": "nonborrow_receipts",
                "counterparty_column": "row_total",
                "source": "tier3_support_file",
                "last_date": "2025-12-31",
                "latest_value_millions": 0.0,
                "notes": "Current default ROW nonborrow-receipt correction. This remains zero in the live source-backed build.",
            },
            {
                "row_family": "nonborrow_receipts",
                "counterparty_column": "banks_default",
                "source": "mts_plus_irs_soi_bridge",
                "last_date": "2025-12-31",
                "latest_value_millions": 5373.2,
                "notes": "Primary bank corporate-tax default-candidate bridge using MTS quarterly cash totals and IRS Publication 16 Table 5.1 depository-plus-BHC shares.",
            },
            {
                "row_family": "nonborrow_receipts",
                "counterparty_column": "banks_default",
                "source": "mts_plus_irs_soi_bridge",
                "last_date": "2025-12-31",
                "latest_value_millions": 1363.9,
                "notes": "Bank corporate-tax receipt bridge using MTS quarterly cash totals and IRS Publication 16 Table 5.1 strict-depository shares.",
            },
            {
                "row_family": "nonborrow_receipts",
                "counterparty_column": "banks_default",
                "source": "mts_plus_irs_soi_bridge",
                "last_date": "2025-12-31",
                "latest_value_millions": 13373.1,
                "notes": "Upper benchmark only: MTS quarterly cash totals with broad finance-sector annual shares retained for scale comparison.",
            },
            {
                "row_family": "nonborrow_receipts",
                "counterparty_column": "row_total",
                "source": "bea_nipa_table_3_2",
                "last_date": "2025-12-31",
                "latest_value_millions": 12670.25,
                "notes": "BEA/NIPA ROW current-receipts benchmark. Official macro benchmark, not a Treasury cash-payer default.",
            },
        ]
    )
    receipt = pd.DataFrame(
        [
            {
                "branch_key": "bank_table51_historical_window",
                "binding_blocker": "none_within_current_policy_window",
            },
            {
                "branch_key": "bank_table51_current_window",
                "binding_blocker": "stale_share_rule",
            },
            {
                "branch_key": "row_mrv_cbsp_primary",
                "binding_blocker": "evidence_boundary",
                "latest_relevant_date": "2025-09-30",
                "latest_value_millions": 578.4,
            },
        ]
    )
    research = pd.DataFrame(
        [
            {
                "comparison_key": "latest_live_defaults",
                "reference_date": "2025-12-31",
            },
            {
                "comparison_key": "latest_historical_bank_window",
                "reference_date": "2024-12-31",
                "tier3_bank_only_mil": 96122.5299,
                "historical_bank_receipt_variant_mil": 103071.0563,
                "historical_bank_lower_bound_variant_mil": 97886.2797,
            },
        ]
    )
    gap = pd.DataFrame(
        [
            {
                "gap_key": "latest_historical_bank_receipt_overlay",
                "net_delta_millions": 6948.5,
            },
            {
                "gap_key": "latest_historical_candidate_to_lower_bound",
                "net_delta_millions": 5184.8,
            },
        ]
    )
    mrv_summary = pd.DataFrame(
        [
            {
                "strongest_nondefault_claim": "MRV cash route has supportive nondefault evidence.",
            }
        ]
    )

    frame = build_fiscal_receipt_boundary_review(
        fiscal_source_quality=fiscal_quality,
        receipt_unblock_status=receipt,
        tier3_research_comparison=research,
        downstream_estimator_gap_review=gap,
        row_mrv_nondefault_evidence_summary=mrv_summary,
    )

    keys = set(frame["boundary_key"])
    assert "bank_live_default_receipt_cell" in keys
    assert "bank_receipt_historical_overlay_candidate" in keys
    assert "row_mrv_primary_nondefault_pilot" in keys
    assert "row_bea_receipt_benchmark" in keys

    bank_live = frame.loc[frame["boundary_key"].eq("bank_live_default_receipt_cell")].iloc[0]
    assert bool(bank_live["included_in_live_tier3_headline"]) is True
    assert bank_live["binding_blocker"] == "stale_share_rule"

    bank_hist = frame.loc[frame["boundary_key"].eq("bank_receipt_historical_overlay_candidate")].iloc[0]
    assert bool(bank_hist["included_in_historical_overlay"]) is True
    assert round(float(bank_hist["latest_value_millions"]), 3) == 6948.526

    bank_bridge = frame.loc[frame["boundary_key"].eq("bank_receipt_bridge_depository_plus_bhc")].iloc[0]
    assert bool(bank_bridge["included_in_historical_overlay"]) is False

    bank_lower = frame.loc[frame["boundary_key"].eq("bank_receipt_historical_overlay_lower_bound")].iloc[0]
    assert round(float(bank_lower["latest_value_millions"]), 3) == 1763.750

    row_mrv = frame.loc[frame["boundary_key"].eq("row_mrv_primary_nondefault_pilot")].iloc[0]
    assert str(pd.Timestamp(row_mrv["latest_reference_date"]).date()) == "2025-09-30"
