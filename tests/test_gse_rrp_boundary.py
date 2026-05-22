from __future__ import annotations

import pandas as pd

from tdc_estimator.gse_rrp_boundary import (
    build_gse_rrp_boundary_check,
    normalize_nyfed_reverse_repo_propositions,
    nyfed_reverse_repo_propositions_url,
)


def test_normalize_nyfed_reverse_repo_propositions_extracts_gse_millions():
    payload = {
        "repo": {
            "operations": [
                {
                    "operationDate": "2024-01-10",
                    "totalAmtAccepted": 679_961_000_000,
                    "propositions": [
                        {"counterpartyType": "bank", "amtAccepted": 0},
                        {"counterpartyType": "gse", "amtAccepted": 26_850_000_000},
                        {"counterpartyType": "mmf", "amtAccepted": 653_111_000_000},
                        {"counterpartyType": "pd", "amtAccepted": 0},
                    ],
                }
            ]
        }
    }

    support = normalize_nyfed_reverse_repo_propositions(payload)

    row = support.iloc[0]
    assert row["date"] == pd.Timestamp("2024-01-10")
    assert round(float(row["value"]), 6) == 26_850.0
    assert round(float(row["gse_on_rrp"]), 6) == 26_850.0
    assert round(float(row["total_on_rrp"]), 6) == 679_961.0


def test_build_gse_rrp_boundary_check_uses_level_diff_when_available():
    quarterly = pd.DataFrame(
        {
            "gse_tsy_tx": [5.0, 50.0, 40.0],
            "gse_tsy_level": [100.0, 130.0, 170.0],
            "gse_on_rrp": [60.0, 40.0, 10.0],
        },
        index=pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30"]),
    )

    diagnostic = build_gse_rrp_boundary_check(quarterly)

    june = diagnostic.loc[diagnostic["date"].eq(pd.Timestamp("2024-06-30"))].iloc[0]
    sept = diagnostic.loc[diagnostic["date"].eq(pd.Timestamp("2024-09-30"))].iloc[0]
    assert june["status"] == "diagnostic_only"
    assert round(float(june["gse_on_rrp_runoff"]), 6) == 20.0
    assert round(float(june["gse_treasury_increase"]), 6) == 30.0
    assert round(float(june["gse_rrp_boundary_adjustment"]), 6) == 20.0
    assert round(float(sept["gse_rrp_boundary_adjustment"]), 6) == 30.0


def test_build_gse_rrp_boundary_check_reports_missing_inputs():
    quarterly = pd.DataFrame({"gse_tsy_tx": [1.0]}, index=pd.to_datetime(["2024-03-31"]))

    diagnostic = build_gse_rrp_boundary_check(quarterly)

    assert diagnostic.iloc[0]["status"] == "missing_inputs"
    assert "gse_on_rrp" in diagnostic.iloc[0]["detail"]


def test_nyfed_reverse_repo_propositions_url_uses_date_params():
    url = nyfed_reverse_repo_propositions_url(start="2024-01-01", end="2024-01-31")

    assert "startDate=2024-01-01" in url
    assert "endDate=2024-01-31" in url
