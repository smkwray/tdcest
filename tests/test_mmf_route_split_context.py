from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from tdc_estimator.mmf_route_split_context import (
    build_mmf_route_split_context,
    render_mmf_route_split_context_markdown,
    write_mmf_route_split_context,
)


def _write_tsv_zip(path: Path) -> None:
    submission = "\n".join(
        [
            "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tREPORTDATE\tSERIESID",
            "A1\t15-Apr-2025\tN-MFP2\t31-Mar-2025\tR1",
            "A2\t15-Apr-2025\tN-MFP2\t31-Mar-2025\tI1",
        ]
    )
    series = "\n".join(
        [
            (
                "ACCESSION_NUMBER\tFEEDERFUNDFLAG\tNETASSETOFSERIES\t"
                "MONEYMARKETFUNDCATEGORY\tFUNDRETAILMONEYMARKETFLAG\t"
                "GOVMONEYMRKTFUNDFLAG"
            ),
            "A1\tN\t1000000000\tGovernment\tY\tY",
            "A2\tN\t2000000000\tGovernment\tN\tY",
        ]
    )
    securities = "\n".join(
        [
            (
                "ACCESSION_NUMBER\tNAMEOFISSUER\tTITLEOFISSUER\t"
                "INVESTMENTCATEGORY\tINCLUDINGVALUEOFANYSPONSORSUPP\t"
                "EXCLUDINGVALUEOFANYSPONSORSUPP"
            ),
            "A1\tUS Treasury\tTreasury Bill\tU.S. Treasury Debt\t300000000\t300000000",
            (
                "A1\tFederal Reserve Bank of New York\tFed Reverse Repo\t"
                "Repurchase Agreement\t100000000\t100000000"
            ),
            "A2\tUS Treasury\tTreasury Note\tU.S. Treasury Debt\t700000000\t700000000",
            (
                "A2\tFederal Reserve Bank of New York\tFed Reverse Repo\t"
                "Repurchase Agreement\t400000000\t400000000"
            ),
        ]
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("NMFP_SUBMISSION.tsv", submission + "\n")
        archive.writestr("NMFP_SERIESLEVELINFO.tsv", series + "\n")
        archive.writestr("NMFP_SCHPORTFOLIOSECURITIES.tsv", securities + "\n")


def test_build_mmf_route_split_context_keeps_split_context_only(tmp_path: Path) -> None:
    zip_path = tmp_path / "202503_nmfp.zip"
    _write_tsv_zip(zip_path)

    rows = build_mmf_route_split_context([zip_path])

    assert len(rows) == 4
    by_route = {row["route_id"]: row for _, row in rows.iterrows()}

    retail_treasury = by_route["retail_mmf_treasury_holdings_context"]
    assert retail_treasury["quarter"] == "2025Q1"
    assert retail_treasury["m2_scope"] == "true"
    assert retail_treasury["deposit_pass_through_scope"] == "false"
    assert retail_treasury["treasury_total_bil"] == "0.3"
    assert retail_treasury["fed_onrrp_bil"] == "0.1"

    institutional_treasury = by_route[
        "institutional_or_nonretail_mmf_treasury_holdings_context"
    ]
    assert institutional_treasury["m2_scope"] == "false"
    assert institutional_treasury["treasury_total_bil"] == "0.7"
    assert institutional_treasury["treasury_coupons_bil"] == "0.7"

    onrrp = by_route["institutional_or_nonretail_mmf_onrrp_plumbing_context"]
    assert onrrp["ratewall_treatment"] == "fed_onrrp_plumbing_context_only"
    assert onrrp["current_demand_eligible"] == "false"

    assert {row["canonical_tdc_math_change"] for _, row in rows.iterrows()} == {
        "false"
    }


def test_write_mmf_route_split_context_outputs_files(tmp_path: Path) -> None:
    zip_path = tmp_path / "202503_nmfp.zip"
    _write_tsv_zip(zip_path)
    csv_path = tmp_path / "context.csv"
    md_path = tmp_path / "context.md"

    _, _, frame = write_mmf_route_split_context(
        zip_paths=[zip_path],
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(frame)
    markdown = render_mmf_route_split_context_markdown(frame)
    assert "MMF Route Split Context" in markdown
    assert "context-only" in markdown
