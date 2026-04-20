from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.ncua_credit_union_deposit_bridge import (
    build_ncua_credit_union_deposit_bridge,
    render_ncua_credit_union_deposit_bridge_markdown,
    write_ncua_credit_union_deposit_bridge,
)


def test_build_ncua_credit_union_deposit_bridge_adds_bank_ratio() -> None:
    raw_bridge = pd.DataFrame(
        {
            "date": ["2025-09-30", "2025-12-31"],
            "source_zip_url": ["u1", "u2"],
            "source_zip_file": ["z1", "z2"],
            "total_credit_union_shares_and_deposits_mil": [1020.0, 1050.0],
            "federally_insured_credit_union_shares_and_deposits_mil": [1000.0, 1030.0],
            "nonfederally_insured_credit_union_shares_and_deposits_mil": [20.0, 20.0],
            "total_credit_union_member_shares_mil": [960.0, 990.0],
            "federally_insured_credit_union_member_shares_mil": [950.0, 980.0],
            "nonfederally_insured_credit_union_member_shares_mil": [10.0, 10.0],
            "total_credit_union_implied_nonmember_deposits_mil": [60.0, 60.0],
            "federally_insured_credit_union_implied_nonmember_deposits_mil": [50.0, 50.0],
            "nonfederally_insured_credit_union_implied_nonmember_deposits_mil": [10.0, 10.0],
            "total_credit_union_count": [110, 111],
            "federally_insured_credit_union_count": [100, 101],
            "nonfederally_insured_credit_union_count": [10, 10],
        }
    )
    quarterly = pd.DataFrame(
        {"commercial_bank_deposits": [6.8, 6.9]},
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )

    bridge = build_ncua_credit_union_deposit_bridge(raw_bridge=raw_bridge, quarterly=quarterly)
    latest = bridge.iloc[-1]
    assert round(float(latest["commercial_bank_deposits_level_mil"]), 3) == 6900.0
    assert round(float(latest["federally_insured_credit_union_to_bank_deposit_ratio"]), 6) == round(1030.0 / 6900.0, 6)


def test_write_ncua_credit_union_deposit_bridge_outputs_files(tmp_path: Path) -> None:
    raw_path = tmp_path / "ncua__credit_union_deposit_bridge.csv"
    pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "source_zip_url": ["u1"],
            "source_zip_file": ["z1"],
            "total_credit_union_shares_and_deposits_mil": [1050.0],
            "federally_insured_credit_union_shares_and_deposits_mil": [1030.0],
            "nonfederally_insured_credit_union_shares_and_deposits_mil": [20.0],
            "total_credit_union_member_shares_mil": [990.0],
            "federally_insured_credit_union_member_shares_mil": [980.0],
            "nonfederally_insured_credit_union_member_shares_mil": [10.0],
            "total_credit_union_implied_nonmember_deposits_mil": [60.0],
            "federally_insured_credit_union_implied_nonmember_deposits_mil": [50.0],
            "nonfederally_insured_credit_union_implied_nonmember_deposits_mil": [10.0],
            "total_credit_union_count": [111],
            "federally_insured_credit_union_count": [101],
            "nonfederally_insured_credit_union_count": [10],
        }
    ).to_csv(raw_path, index=False)
    quarterly = pd.DataFrame({"commercial_bank_deposits": [6.9]}, index=pd.to_datetime(["2025-12-31"]))

    csv_path = tmp_path / "bridge.csv"
    md_path = tmp_path / "bridge.md"
    _, _, bridge = write_ncua_credit_union_deposit_bridge(
        raw_bridge_path=raw_path,
        quarterly=quarterly,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(bridge)
    markdown = render_ncua_credit_union_deposit_bridge_markdown(bridge)
    assert "NCUA Credit Union Deposit Bridge" in markdown
    assert "FDIC-insured savings institutions are still required" in markdown
