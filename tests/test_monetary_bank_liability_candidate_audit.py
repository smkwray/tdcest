from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_bank_liability_candidate_audit import (
    build_monetary_bank_liability_candidate_audit,
    render_monetary_bank_liability_candidate_audit_markdown,
    write_monetary_bank_liability_candidate_audit,
)


def test_build_monetary_bank_liability_candidate_audit_computes_loaded_context_residual() -> None:
    stage0 = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_nonbank_depository_bridge_level_mil": [70.0],
            "delta_large_time_deposits_all_commercial_banks_level_mil": [50.0],
            "delta_other_deposits_all_commercial_banks_level_mil": [210.0],
        }
    )
    decomposition = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_minus_liquid_target_wedge_mil": [180.0],
        }
    )

    out = build_monetary_bank_liability_candidate_audit(stage0=stage0, decomposition=decomposition)
    latest = out.iloc[0]

    assert round(float(latest["loaded_liability_context_total_mil"]), 3) == 120.0
    assert round(float(latest["residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil"]), 3) == 60.0
    assert round(float(latest["loaded_liability_context_share_of_bank_minus_liquid_wedge"]), 6) == round(120.0 / 180.0, 6)
    assert round(float(latest["other_deposits_share_of_bank_minus_liquid_wedge"]), 6) == round(210.0 / 180.0, 6)


def test_write_monetary_bank_liability_candidate_audit_outputs_files(tmp_path: Path) -> None:
    stage0 = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_nonbank_depository_bridge_level_mil": [70.0],
            "delta_large_time_deposits_all_commercial_banks_level_mil": [50.0],
            "delta_other_deposits_all_commercial_banks_level_mil": [210.0],
        }
    )
    decomposition = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_minus_liquid_target_wedge_mil": [180.0],
        }
    )
    csv_path = tmp_path / "liability_audit.csv"
    md_path = tmp_path / "liability_audit.md"

    _, _, audit = write_monetary_bank_liability_candidate_audit(
        monetary_stage0_diagnostics=stage0,
        monetary_target_definition_decomposition=decomposition,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(audit)
    markdown = render_monetary_bank_liability_candidate_audit_markdown(audit)
    assert "Monetary Bank Liability Candidate Audit" in markdown
    assert "Loaded liability context total" in markdown
    assert "Other deposits" in markdown
