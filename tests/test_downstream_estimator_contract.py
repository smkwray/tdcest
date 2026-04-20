from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_estimator_contract import build_downstream_estimator_contract


def test_downstream_estimator_contract_builds_key_rows():
    index = pd.to_datetime(["2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [100.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [80.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [75.0],
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow": [77.0],
        },
        index=index,
    )
    method_meta = {
        "method_descriptions": {
            "tdc_base_bank_only_ru_flow": "Base bank-only headline.",
            "tdc_tier2_interest_corrected_bank_only_ru_flow": "Tier 2 bank-only.",
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": "Tier 3 bank-only.",
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow": "Tier 3 broad depository.",
        },
        "method_formulas": {
            "tdc_base_bank_only_ru_flow": "base formula",
            "tdc_tier2_interest_corrected_bank_only_ru_flow": "tier2 formula",
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": "tier3 formula",
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow": "broad formula",
        },
    }
    receipt = pd.DataFrame(
        [
            {
                "branch_key": "bank_table51_historical_window",
                "latest_relevant_date": "2024-12-31",
                "summary_note": "Historical bank view.",
            },
            {
                "branch_key": "bank_table51_current_window",
                "binding_blocker": "stale_share_rule",
            },
            {
                "branch_key": "row_mrv_cbsp_primary",
                "latest_relevant_date": "2025-09-30",
                "latest_value_millions": 12.0,
                "binding_blocker": "evidence_boundary",
                "summary_note": "MRV pilot.",
            },
        ]
    )
    goals = pd.DataFrame(
        [
            {
                "goal_key": "fiscal_flow_tdc_equation",
                "latest_relevant_date": "2025-12-31",
                "strongest_live_surface": "Fiscal reconciliation shell",
                "binding_blocker": "receipt_cells_still_partial",
                "summary_note": "Fiscal shell note.",
            },
            {
                "goal_key": "monetary_disaggregated_tdc_equation",
                "latest_relevant_date": "2025-12-31",
                "binding_blocker": "stop_at_perimeter_stress_test",
                "summary_note": "Monetary note.",
            },
        ]
    )
    research = pd.DataFrame(
        [
            {
                "comparison_key": "latest_historical_bank_window",
                "reference_date": "2024-12-31",
                "historical_bank_receipt_variant_mil": 88.0,
            }
        ]
    )
    bea_row_benchmark = pd.DataFrame(
        {"bea_row_current_receipts_total_q_mil": [99.0]},
        index=pd.to_datetime(["2025-12-31"]),
    )
    mrv_summary = pd.DataFrame(
        [
            {
                "binding_default_blocker": "legal_remitter_or_debited_account_proof",
            }
        ]
    )
    monetary = pd.DataFrame(
        [
            {
                "latest_quarter": "2025-12-31",
                "depository_residual_after_expanded_mil": 10.0,
                "commercial_bank_residual_after_expanded_mil": 20.0,
            }
        ]
    )
    workstreams = pd.DataFrame(
        [
            {
                "workstream_key": "bank_receipt_historical_window",
                "next_finite_push": "Push historical bank.",
            },
            {
                "workstream_key": "row_mrv_primary_pilot",
                "next_finite_push": "Push MRV carefully.",
            },
            {
                "workstream_key": "fiscal_reconciliation_shell",
                "next_finite_push": "Keep shell aligned.",
            },
            {
                "workstream_key": "monetary_branch",
                "next_finite_push": "Keep as cross-check.",
            },
        ]
    )

    contract = build_downstream_estimator_contract(
        estimates=estimates,
        method_meta=method_meta,
        receipt_unblock_status=receipt,
        project_goal_status_review=goals,
        tier3_research_comparison=research,
        bea_row_receipts_benchmark=bea_row_benchmark,
        row_mrv_nondefault_evidence_summary=mrv_summary,
        monetary_target_preference_review=monetary,
        workstream_end_state_map=workstreams,
    )

    keys = set(contract["artifact_key"])
    assert "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in keys
    assert "bank_receipt_historical_default_view" in keys
    assert "tdc_bea_row_receipts_benchmark" in keys
    assert "row_mrv_primary_nondefault_pilot" in keys
    assert "fiscal_reconciliation_shell" in keys
    assert "monetary_depository_crosscheck" in keys
    assert contract["latest_reference_date"].astype(str).str.contains("T").sum() == 0
