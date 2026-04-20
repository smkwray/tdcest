from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.fdic_savings_institution_deposit_bridge import (
    build_fdic_savings_institution_deposit_bridge,
    render_fdic_savings_institution_deposit_bridge_markdown,
    write_fdic_savings_institution_deposit_bridge,
)


def test_build_fdic_savings_institution_deposit_bridge_adds_bank_and_nonbank_ratios() -> None:
    raw_bridge = pd.DataFrame(
        {
            "date": ["2025-09-30", "2025-12-31"],
            "source_api_url": ["u1", "u2"],
            "source_cache_file": ["a.json", "b.json"],
            "total_savings_institution_deposits_mil": [540.0, 550.0],
            "federal_savings_bank_deposits_mil": [210.0, 200.0],
            "state_savings_bank_deposits_mil": [280.0, 300.0],
            "state_savings_and_loan_deposits_mil": [50.0, 50.0],
            "total_savings_institution_count": [3, 3],
            "federal_savings_bank_count": [1, 1],
            "state_savings_bank_count": [1, 1],
            "state_savings_and_loan_count": [1, 1],
        }
    )
    quarterly = pd.DataFrame(
        {
            "commercial_bank_deposits": [6.8, 7.0],
            "credit_union_deposits": [900.0, 1000.0],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )

    bridge = build_fdic_savings_institution_deposit_bridge(raw_bridge=raw_bridge, quarterly=quarterly)
    latest = bridge.iloc[-1]

    assert round(float(latest["commercial_bank_deposits_level_mil"]), 3) == 7000.0
    assert round(float(latest["credit_union_deposits_level_mil"]), 3) == 1000.0
    assert round(float(latest["savings_institution_to_bank_deposit_ratio"]), 6) == round(550.0 / 7000.0, 6)
    assert round(float(latest["nonbank_depository_bridge_level_mil"]), 3) == 1550.0


def test_write_fdic_savings_institution_deposit_bridge_outputs_files(tmp_path: Path) -> None:
    raw_bridge = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "source_api_url": ["u2"],
            "source_cache_file": ["b.json"],
            "total_savings_institution_deposits_mil": [550.0],
            "federal_savings_bank_deposits_mil": [200.0],
            "state_savings_bank_deposits_mil": [300.0],
            "state_savings_and_loan_deposits_mil": [50.0],
            "total_savings_institution_count": [3],
            "federal_savings_bank_count": [1],
            "state_savings_bank_count": [1],
            "state_savings_and_loan_count": [1],
        }
    )
    raw_path = tmp_path / "fdic__savings_institution_deposit_bridge.csv"
    raw_bridge.to_csv(raw_path, index=False)
    csv_path = tmp_path / "fdic_bridge.csv"
    md_path = tmp_path / "fdic_bridge.md"
    quarterly = pd.DataFrame(
        {
            "commercial_bank_deposits": [7.0],
            "credit_union_deposits": [1.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    _, _, bridge = write_fdic_savings_institution_deposit_bridge(
        raw_bridge_path=raw_path,
        quarterly=quarterly,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(bridge)
    markdown = render_fdic_savings_institution_deposit_bridge_markdown(bridge)
    assert "FDIC Savings Institution Deposit Bridge" in markdown
    assert "nonbank-depository-bridge-to-bank-deposit ratio" in markdown
