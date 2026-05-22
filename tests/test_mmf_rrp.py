from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from tdc_estimator.mmf_rrp import (
    aggregate_mmf_rrp_to_quarter,
    build_mmf_rrp_scale_audit,
    build_mmf_rrp_source_comparison,
    build_sec_nmfp_fund_month_support,
    compute_mmf_rrp_monthly_adjustments,
    discover_sec_nmfp_dataset_links,
    normalize_sec_nmfp_zip,
)


def test_compute_mmf_rrp_monthly_adjustments_allocates_runoff_by_fund_month():
    raw = pd.DataFrame(
        {
            "date": [
                "2024-01-31",
                "2024-02-29",
                "2024-03-31",
                "2024-01-31",
                "2024-02-29",
            ],
            "fund_id": ["a", "a", "a", "b", "b"],
            "fed_rrp": [100.0, 60.0, 50.0, 20.0, 10.0],
            "treasury_bills": [10.0, 30.0, 30.0, 5.0, 6.0],
            "treasury_other": [0.0, 10.0, 15.0, 0.0, 2.0],
            "non_treasury_non_fed_rrp_assets": [50.0, 60.0, 65.0, 10.0, 14.0],
            "nav": [160.0, 160.0, 155.0, 35.0, 34.0],
        }
    )

    monthly = compute_mmf_rrp_monthly_adjustments(raw)

    fund_a_feb = monthly.loc[
        (monthly["fund_id"].eq("a")) & (monthly["date"].eq(pd.Timestamp("2024-02-29")))
    ].iloc[0]
    assert round(float(fund_a_feb["rrp_runoff"]), 6) == 40.0
    assert round(float(fund_a_feb["treasury_increase"]), 6) == 30.0
    assert round(float(fund_a_feb["other_uses"]), 6) == 10.0
    assert round(float(fund_a_feb["mmf_rrp_adjustment_prop"]), 6) == 30.0
    assert round(float(fund_a_feb["mmf_rrp_adjustment_lb"]), 6) == 30.0
    assert round(float(fund_a_feb["mmf_rrp_adjustment_ub"]), 6) == 30.0

    fund_a_mar = monthly.loc[
        (monthly["fund_id"].eq("a")) & (monthly["date"].eq(pd.Timestamp("2024-03-31")))
    ].iloc[0]
    assert round(float(fund_a_mar["rrp_runoff"]), 6) == 10.0
    assert round(float(fund_a_mar["treasury_increase"]), 6) == 5.0
    assert round(float(fund_a_mar["other_uses"]), 6) == 10.0
    assert round(float(fund_a_mar["mmf_rrp_adjustment_prop"]), 6) == round(10.0 * 5.0 / 15.0, 6)
    assert round(float(fund_a_mar["mmf_rrp_adjustment_lb"]), 6) == 0.0
    assert round(float(fund_a_mar["mmf_rrp_adjustment_ub"]), 6) == 5.0

    quarterly = aggregate_mmf_rrp_to_quarter(monthly)
    row = quarterly.loc[pd.Timestamp("2024-03-31")]
    assert round(float(row["mmf_rrp_adjustment_prop"]), 6) == round(30.0 + 10.0 * 5.0 / 15.0 + 3.0, 6)
    assert round(float(row["mmf_rrp_adjustment_lb"]), 6) == 33.0
    assert round(float(row["mmf_rrp_adjustment_ub"]), 6) == 38.0


def test_mmf_rrp_proportional_adjustment_is_capped_at_upper_bound():
    raw = pd.DataFrame(
        {
            "date": ["2024-01-31", "2024-02-29"],
            "fund_id": ["aggregate", "aggregate"],
            "fed_rrp": [200.0, 0.0],
            "treasury_total": [10.0, 30.0],
            "treasury_bills": [10.0, 30.0],
            "non_treasury_non_fed_rrp_assets": [50.0, 50.0],
            "nav": [260.0, 260.0],
        }
    )

    monthly = compute_mmf_rrp_monthly_adjustments(raw)
    row = monthly.loc[monthly["date"].eq(pd.Timestamp("2024-02-29"))].iloc[0]

    assert round(float(row["mmf_rrp_adjustment_ub"]), 6) == 20.0
    assert round(float(row["mmf_rrp_adjustment_prop"]), 6) == 20.0


def test_mmf_rrp_adjustment_is_zero_without_observed_rrp_runoff():
    raw = pd.DataFrame(
        {
            "date": ["2011-01-31", "2011-02-28"],
            "fund_id": ["aggregate", "aggregate"],
            "fed_rrp": [pd.NA, pd.NA],
            "treasury_total": [10.0, 30.0],
            "treasury_bills": [10.0, 30.0],
            "non_treasury_non_fed_rrp_assets": [50.0, 50.0],
            "nav": [60.0, 80.0],
        }
    )

    monthly = compute_mmf_rrp_monthly_adjustments(raw)
    row = monthly.loc[monthly["date"].eq(pd.Timestamp("2011-02-28"))].iloc[0]

    assert round(float(row["rrp_runoff"]), 6) == 0.0
    assert round(float(row["treasury_increase"]), 6) == 20.0
    assert round(float(row["mmf_rrp_adjustment_lb"]), 6) == 0.0
    assert round(float(row["mmf_rrp_adjustment_prop"]), 6) == 0.0
    assert round(float(row["mmf_rrp_adjustment_ub"]), 6) == 0.0


def test_mmf_rrp_adjustment_ignores_pre_on_rrp_fed_repo_observations():
    raw = pd.DataFrame(
        {
            "date": ["2012-10-31", "2012-11-30", "2012-12-31"],
            "fund_id": ["aggregate", "aggregate", "aggregate"],
            "fed_rrp": [0.0, 860.0, 0.0],
            "treasury_total": [10.0, 20.0, 30.0],
            "treasury_bills": [10.0, 20.0, 30.0],
            "non_treasury_non_fed_rrp_assets": [50.0, 50.0, 50.0],
            "nav": [60.0, 70.0, 80.0],
        }
    )

    monthly = compute_mmf_rrp_monthly_adjustments(raw)
    row = monthly.loc[monthly["date"].eq(pd.Timestamp("2012-12-31"))].iloc[0]

    assert round(float(row["rrp_runoff"]), 6) == 0.0
    assert round(float(row["mmf_rrp_adjustment_prop"]), 6) == 0.0


def test_build_mmf_rrp_scale_audit_flags_aggregate_bridge_and_bounds():
    raw = pd.DataFrame(
        {
            "date": ["2024-01-31", "2024-02-29"],
            "fund_id": ["ofr_aggregate_mmf", "ofr_aggregate_mmf"],
            "fed_rrp": [100.0, 80.0],
            "treasury_total": [10.0, 25.0],
            "treasury_bills": [pd.NA, pd.NA],
            "non_treasury_non_fed_rrp_assets": [50.0, 55.0],
            "nav": [160.0, 160.0],
        }
    )
    monthly = compute_mmf_rrp_monthly_adjustments(raw)
    quarterly = aggregate_mmf_rrp_to_quarter(monthly)

    audit = build_mmf_rrp_scale_audit(raw=raw, monthly=monthly, quarterly=quarterly)

    source = audit.loc[audit["check"].eq("source_granularity")].iloc[0]
    bounds = audit.loc[audit["check"].eq("mmf_rrp_adjustment_monthly_bounds")].iloc[0]
    assert source["status"] == "warn"
    assert source["value"] == "aggregate_monthly"
    assert bounds["status"] == "pass"
    assert int(bounds["value"]) == 0


def test_build_mmf_rrp_scale_audit_compares_support_to_z1_when_available():
    raw = pd.DataFrame(
        {
            "date": ["2024-01-31", "2024-02-29", "2024-03-31"],
            "fund_id": ["ofr_aggregate_mmf"] * 3,
            "fed_rrp": [100.0, 90.0, 80.0],
            "treasury_total": [1000.0, 1050.0, 1100.0],
            "treasury_bills": [600.0, 650.0, 700.0],
            "non_treasury_non_fed_rrp_assets": [50.0, 55.0, 60.0],
            "nav": [1600.0, 1700.0, 1800.0],
        }
    )
    monthly = compute_mmf_rrp_monthly_adjustments(raw)
    quarterly = aggregate_mmf_rrp_to_quarter(monthly)
    z1_total = pd.Series([1110.0], index=pd.to_datetime(["2024-03-31"]))
    z1_bills = pd.Series([705.0], index=pd.to_datetime(["2024-03-31"]))

    audit = build_mmf_rrp_scale_audit(
        raw=raw,
        monthly=monthly,
        quarterly=quarterly,
        z1_mmf_treasury_level=z1_total,
        z1_mmf_treasury_bills_level=z1_bills,
    )

    total = audit.loc[audit["check"].eq("z1_mmf_treasury_total_level_match")].iloc[0]
    bills = audit.loc[audit["check"].eq("z1_mmf_treasury_bills_level_match")].iloc[0]
    assert total["status"] == "pass"
    assert bills["status"] == "pass"
    assert round(float(total["value"]), 6) == round(abs(1100.0 - 1110.0) / 1110.0, 6)


def _write_nmfp_zip(path: Path) -> None:
    submission = "\n".join(
        [
            "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tREPORTDATE\tSERIESID\tSERIES_NAME",
            "old\t05-APR-2024\tN-MFP2\t31-MAR-2024\tS1\tFund One",
            "new\t08-APR-2024\tN-MFP2/A\t31-MAR-2024\tS1\tFund One",
            "fund2\t05-APR-2024\tN-MFP2\t31-MAR-2024\tS2\tFund Two",
        ]
    )
    series = "\n".join(
        [
            "ACCESSION_NUMBER\tFEEDERFUNDFLAG\tMASTERFUNDFLAG\tCASH\tTOTALVALUEPORTFOLIOSECURITIES\tTOTALVALUEOTHERASSETS\tNETASSETOFSERIES",
            "old\tN\tN\t0\t100000000\t0\t100000000",
            "new\tN\tN\t1000000\t180000000\t2000000\t181000000",
            "fund2\tN\tN\t0\t80000000\t0\t80000000",
        ]
    )
    securities = "\n".join(
        [
            "ACCESSION_NUMBER\tNAMEOFISSUER\tTITLEOFISSUER\tINVESTMENTCATEGORY\tINCLUDINGVALUEOFANYSPONSORSUPP\tEXCLUDINGVALUEOFANYSPONSORSUPP",
            "old\tU.S. Treasury Bill\tU.S. Treasury Bill\tU.S. Treasury Debt\t100000000\t100000000",
            "new\tU.S. Treasury Bill\tU.S. Treasury Bill\tU.S. Treasury Debt\t100000000\t100000000",
            "new\tU.S. Treasury Note\tU.S. Treasury Note\tU.S. Treasury Debt\t50000000\t50000000",
            "new\tFederal Reserve Bank of New York Tri Party Repo\tFederal Reserve Bank of New York Tri Party Repo\tU.S. Treasury Repurchase Agreement, if collateralized only by U.S. Treasuries (including Strips) and cash\t30000000\t30000000",
            "fund2\tU.S. Treasury Bill\tU.S. Treasury Bill\tU.S. Treasury Debt\t50000000\t50000000",
        ]
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("NMFP_SUBMISSION.tsv", submission)
        zf.writestr("NMFP_SERIESLEVELINFO.tsv", series)
        zf.writestr("NMFP_SCHPORTFOLIOSECURITIES.tsv", securities)


def test_normalize_sec_nmfp_zip_builds_fund_month_support_and_prefers_amendment(tmp_path: Path):
    path = tmp_path / "nmfp.zip"
    _write_nmfp_zip(path)

    support = normalize_sec_nmfp_zip(path)

    assert set(support["fund_id"]) == {"S1", "S2"}
    fund = support.loc[support["fund_id"].eq("S1")].iloc[0]
    assert fund["date"] == pd.Timestamp("2024-03-31")
    assert round(float(fund["treasury_total"]), 6) == 150.0
    assert round(float(fund["treasury_bills"]), 6) == 100.0
    assert round(float(fund["fed_rrp"]), 6) == 30.0
    assert round(float(fund["nav"]), 6) == 181.0
    assert round(float(fund["non_treasury_non_fed_rrp_assets"]), 6) == 3.0


def test_build_sec_nmfp_fund_month_support_deduplicates_fund_month(tmp_path: Path):
    path = tmp_path / "nmfp.zip"
    _write_nmfp_zip(path)

    support = build_sec_nmfp_fund_month_support([path, path])

    assert len(support) == 2
    assert support[["fund_id", "date"]].duplicated().sum() == 0


def test_discover_sec_nmfp_dataset_links_extracts_monthly_and_quarterly_dates():
    html = """
    <a href="/files/dera/data/form-n-mfp-data-sets/20240308-20240405_nmfp.zip" download>2024 March NMFP</a>
    <a href="/files/dera/data/form-n-mfp-data-sets/2022q1_nmfp.zip" download>2022 Q1 NMFP</a>
    """

    links = discover_sec_nmfp_dataset_links(html)

    assert links["date"].tolist() == [pd.Timestamp("2022-03-31"), pd.Timestamp("2024-03-31")]
    assert links["url"].str.startswith("https://www.sec.gov/files/dera/data/form-n-mfp-data-sets/").all()


def test_build_mmf_rrp_source_comparison_flags_material_differences(tmp_path: Path):
    preferred = pd.DataFrame(
        {
            "date": ["2024-01-31", "2024-02-29", "2024-03-31"],
            "fund_id": ["a", "a", "a"],
            "fed_rrp": [100.0, 40.0, 20.0],
            "treasury_total": [10.0, 30.0, 35.0],
            "treasury_bills": [10.0, 30.0, 35.0],
            "non_treasury_non_fed_rrp_assets": [50.0, 90.0, 95.0],
            "nav": [160.0, 160.0, 150.0],
        }
    )
    fallback = pd.DataFrame(
        {
            "date": ["2024-01-31", "2024-02-29", "2024-03-31"],
            "fund_id": ["aggregate", "aggregate", "aggregate"],
            "fed_rrp": [100.0, 20.0, 0.0],
            "treasury_total": [10.0, 50.0, 70.0],
            "treasury_bills": [10.0, 50.0, 70.0],
            "non_treasury_non_fed_rrp_assets": [50.0, 50.0, 50.0],
            "nav": [160.0, 160.0, 160.0],
        }
    )
    preferred_path = tmp_path / "preferred.csv"
    fallback_path = tmp_path / "fallback.csv"
    preferred.to_csv(preferred_path, index=False)
    fallback.to_csv(fallback_path, index=False)

    comparison = build_mmf_rrp_source_comparison(
        preferred_raw_path=preferred_path,
        fallback_raw_path=fallback_path,
        materiality_threshold_mil=10.0,
    )

    row = comparison.loc[comparison["date"].eq(pd.Timestamp("2024-03-31"))].iloc[0]
    assert round(float(row["preferred_mmf_rrp_adjustment_prop"]), 6) == 25.0
    assert round(float(row["fallback_mmf_rrp_adjustment_prop"]), 6) == 60.0
    assert round(float(row["preferred_minus_fallback_prop"]), 6) == -35.0
    assert bool(row["material_difference"]) is True
