from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.interest_source_constraints import build_interest_source_constraints, write_interest_source_constraints


def test_build_interest_source_constraints_extracts_regulatory_mmf_and_tic_rows(tmp_path: Path):
    bank = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "total_treasuries_amortized_cost": [100_000.0, 200_000.0],
            "total_treasuries_fair_value": [90_000.0, 180_000.0],
            "treasury_ladder_total": [100_000.0, 200_000.0],
            "treasury_bucket_3m_or_less": [10_000.0, 20_000.0],
            "treasury_bucket_3_12m": [5_000.0, 10_000.0],
        }
    )
    cu = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "total_treasuries_level_proxy": [50_000.0],
            "treasury_ladder_total": [50_000.0],
            "treasury_bucket_3m_or_less": [5_000.0],
            "treasury_bucket_3_12m": [5_000.0],
        }
    )
    mmf = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "treasury_total": [100.0, 300.0],
            "treasury_bills": [80.0, 120.0],
            "fed_rrp": [0.0, 0.0],
            "nav": [120.0, 320.0],
        }
    )
    tic = pd.DataFrame(
        {
            "month": ["2025-12-31"],
            "tic_foreign_total_treasury_net_flow_usd_millions": [50.0],
            "tic_foreign_official_long_treasury_net_flow_usd_millions": [30.0],
            "tic_foreign_official_short_treasury_net_flow_usd_millions": [10.0],
            "tic_foreign_private_long_treasury_net_flow_usd_millions": [20.0],
            "tic_foreign_private_short_treasury_net_flow_usd_millions": [-40.0],
        }
    )

    out = build_interest_source_constraints(
        bank_ffiec_path=None,
        credit_union_ncua_path=None,
        mmf_path=None,
        row_tic_path=None,
    )
    assert set(out["constraint_status"]) == {"missing_source"}

    bank_path = tmp_path / "bank_constraints.csv"
    cu_path = tmp_path / "cu_constraints.csv"
    mmf_path = tmp_path / "mmf_constraints.csv"
    tic_path = tmp_path / "tic_constraints.csv"
    bank.to_csv(bank_path, index=False)
    cu.to_csv(cu_path, index=False)
    mmf.to_csv(mmf_path, index=False)
    tic.to_csv(tic_path, index=False)

    out = build_interest_source_constraints(
        bank_ffiec_path=bank_path,
        credit_union_ncua_path=cu_path,
        mmf_path=mmf_path,
        row_tic_path=tic_path,
    )
    rows = out.set_index("sector_key")
    assert rows.loc["bank_broad_private_depositories_marketable_proxy", "bill_weight_proxy"] == 0.1
    assert rows.loc["credit_unions_marketable_proxy", "short_weight_proxy_le_1y"] == 0.2
    assert rows.loc["money_market_funds", "bill_weight_proxy"] == 0.5
    assert rows.loc["foreigners_total", "constraint_status"] == "diagnostic_flow_only_not_default_weight"


def test_write_interest_source_constraints(tmp_path: Path):
    out_csv = tmp_path / "constraints.csv"
    out_md = tmp_path / "constraints.md"

    written_csv, written_md, frame = write_interest_source_constraints(
        out_path=out_csv,
        markdown_out_path=out_md,
        bank_ffiec_path=None,
        credit_union_ncua_path=None,
        mmf_path=None,
        row_tic_path=None,
    )

    assert written_csv == out_csv
    assert written_md == out_md
    assert out_csv.exists()
    assert out_md.exists()
    assert len(frame) == 4


def test_build_interest_source_constraints_uses_tic_slt_positions(tmp_path: Path):
    tic_path = tmp_path / "slt_table3.txt"
    tic_path.write_text(
        "\n".join(
            [
                "header",
                "header",
                "header",
                "header",
                "header",
                "header",
                "header",
                "header",
                "country\tcountry_code\tdate\tfor_treas_pos\tfor_treas_net\tfor_lt_treas_pos\tfor_lt_treas_net\tfor_lt_treas_valchg\tfor_st_treas_pos\tfor_st_treas_net",
                "Grand Total\t99996\t2025-12\t1000\t0\t750\t0\t0\t250\t0",
            ]
        ),
        encoding="utf-8",
    )

    out = build_interest_source_constraints(
        bank_ffiec_path=None,
        credit_union_ncua_path=None,
        mmf_path=None,
        row_tic_path=tic_path,
    )

    row = out.set_index("sector_key").loc["foreigners_total"]
    assert row["constraint_status"] == "usable_constraint"
    assert row["bill_weight_proxy"] == 0.25
    assert row["coupon_weight_proxy"] == 0.75


def test_build_interest_source_constraints_marks_ncua_level_only_fallback(tmp_path: Path):
    cu = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "total_treasuries_level_proxy": [50_000_000.0],
        }
    )
    cu_path = tmp_path / "ncua.csv"
    cu.to_csv(cu_path, index=False)

    out = build_interest_source_constraints(
        bank_ffiec_path=None,
        credit_union_ncua_path=cu_path,
        mmf_path=None,
        row_tic_path=None,
    )

    row = out.set_index("sector_key").loc["credit_unions_marketable_proxy"]
    assert row["constraint_status"] == "usable_level_constraint_wamest_split_fallback"
    assert bool(row["fallback_split_accepted"])
    assert row["constraint_basis"] == "ncua_treasury_level_only_wamest_interest_contract_split_fallback"
