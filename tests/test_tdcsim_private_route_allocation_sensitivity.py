from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tdc_estimator.tdcsim_private_route_allocation_sensitivity import (
    build_tdcsim_private_route_allocation_sensitivity,
    render_tdcsim_private_route_allocation_sensitivity_markdown,
    write_tdcsim_private_route_allocation_sensitivity,
)


def _flow_source() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "quarter": [
                "2025-03-31",
                "2025-06-30",
                "2025-09-30",
                "2025-12-31",
            ],
            "z1_component_households_nonprofits_treasuries_residual_holder_bn": [
                39.138,
                139.376,
                -13.005,
                54.416,
            ],
            "z1_component_nonfinancial_corporate_treasuries_bn": [
                -1.051,
                2.337,
                4.384,
                3.729,
            ],
            "z1_component_nonfinancial_noncorporate_us_government_securities_bn": [
                -1.613,
                0.175,
                -0.147,
                0.84,
            ],
            "z1_component_state_local_governments_treasuries_ex_slgs_bn": [
                17.569,
                -21.88,
                49.859,
                -21.174,
            ],
            "z1_component_security_brokers_dealers_treasuries_net_bn": [
                21.897,
                24.971,
                -25.444,
                49.779,
            ],
            "z1_component_government_sponsored_enterprises_treasuries_bn": [
                2.984,
                25.115,
                -5.568,
                -8.424,
            ],
            "z1_component_insurance_pensions_total_treasuries_bn": [
                83.374,
                -19.656,
                119.924,
                0.361,
            ],
            "z1_component_mutual_funds_treasuries_bn": [
                -1.241,
                -5.263,
                87.249,
                37.911,
            ],
            "z1_component_closed_end_funds_treasuries_bn": [
                0.015,
                -0.035,
                -0.006,
                0.054,
            ],
            "z1_component_exchange_traded_funds_treasuries_bn": [
                36.497,
                33.408,
                34.575,
                36.43,
            ],
            "z1_component_asset_backed_securities_issuers_treasuries_bn": [
                -3.664,
                -2.205,
                -1.327,
                0.133,
            ],
            "z1_component_holding_companies_treasuries_bn": [
                4.749,
                -6.625,
                -5.586,
                -5.783,
            ],
            "z1_component_central_clearing_counterparties_treasuries_bn": [
                -2.675,
                3.017,
                3.329,
                12.509,
            ],
            "z1_component_money_market_funds_total_treasuries_bn": [
                -114.28,
                -266.537,
                618.32,
                285.458,
            ],
        }
    )


def _stock_source() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2025-12-31"] * 9,
            "sector": [
                "households_residual",
                "nonfinancial_corporates",
                "state_local_governments",
                "dealers",
                "insurers",
                "mutual_funds_etfs",
                "other_financial",
                "pensions",
                "money_market_funds",
            ],
            "instrument": ["all_treasuries"] * 9,
            "holdings": [
                2_944_570.0,
                224_710.0,
                1_553_261.0,
                542_458.0,
                639_409.0,
                2_381_908.0,
                490_774.0,
                1_157_536.0,
                3_517_812.0,
            ],
        }
    )


def _mmf_context() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "quarter": ["2025Q4"] * 4,
            "route_id": [
                "retail_mmf_treasury_holdings_context",
                "retail_mmf_onrrp_plumbing_context",
                "institutional_or_nonretail_mmf_treasury_holdings_context",
                "institutional_or_nonretail_mmf_onrrp_plumbing_context",
            ],
            "fund_scope": [
                "retail_mmf",
                "retail_mmf",
                "institutional_or_nonretail_mmf",
                "institutional_or_nonretail_mmf",
            ],
            "treasury_total_bil": [83.118827, 83.118827, 3434.668061, 3434.668061],
            "fed_onrrp_bil": [2.9, 2.9, 69.692966, 69.692966],
        }
    )


def test_private_route_sensitivity_keeps_proxy_fail_closed() -> None:
    rows = build_tdcsim_private_route_allocation_sensitivity(
        z1_flow=_flow_source(),
        z1_stock=_stock_source(),
        mmf_route_split_context=_mmf_context(),
        source_inputs="test_flow;test_stock;test_mmf",
    )

    assert set(rows["object_family"]) == {
        "stock_interest_quarter_end",
        "flow_absorption_trailing_4q",
    }
    assert set(rows["current_demand_eligible"]) == {"false"}
    assert set(rows["canonical_tdc_math_change"]) == {"false"}
    assert set(rows["source_backed_private_bucket_split_status"]) == {
        "not_source_backed_private_bucket_split"
    }
    assert set(rows["evidence_mode_enabled"]) == {"false"}
    assert set(rows["holder_allocation_enabled"]) == {"false"}
    assert set(rows["pricing_output_enabled"]) == {"false"}
    assert set(rows["sensitivity_label"]) == {"mechanical_midpoint_not_estimate"}

    for _, group in rows.groupby(["ref_quarter", "object_family"]):
        for column in ("share_lambda_0", "share_lambda_0_5", "share_lambda_1"):
            total = pd.to_numeric(group[column], errors="raise").sum()
            assert total == pytest.approx(1.0, abs=2e-6)


def test_private_route_sensitivity_separates_stock_flow_and_mmf_memo() -> None:
    rows = build_tdcsim_private_route_allocation_sensitivity(
        z1_flow=_flow_source(),
        z1_stock=_stock_source(),
        mmf_route_split_context=_mmf_context(),
    )

    flow = rows.loc[rows["object_family"].eq("flow_absorption_trailing_4q")]
    stock = rows.loc[rows["object_family"].eq("stock_interest_quarter_end")]
    assert set(flow["z1_table"]) == {"F.210"}
    assert set(stock["z1_table"]) == {"L.210"}

    flow_by_class = {row["route_class"]: row for _, row in flow.iterrows()}
    mmf = flow_by_class["mmf_onrrp_like_intermediated"]
    assert mmf["mmf_split_status"] == (
        "z1_mmf_aggregate_replaced_by_sec_nmfp_treasury_split"
    )
    assert mmf["onrrp_treatment"] == "memo_only_not_additive"
    assert float(mmf["raw_amount_bil"]) == pytest.approx(903.778)
    assert float(mmf["onrrp_stock_bil"]) == pytest.approx(72.592966)

    denominator = float(mmf["denominator_bil"])
    included_raw = sum(float(value) for value in flow["raw_amount_bil"])
    assert denominator == pytest.approx(included_raw)
    assert denominator == pytest.approx(1833.882)

    deposit = flow_by_class["deposit_funded_domestic_nonbank_possible"]
    assert float(deposit["raw_amount_bil"]) == pytest.approx(244.395)
    assert float(deposit["share_lambda_0"]) == 0.0
    assert float(deposit["share_lambda_0_5"]) == pytest.approx(0.066633, abs=1e-6)


def test_write_private_route_sensitivity_outputs_files(tmp_path: Path) -> None:
    flow_path = tmp_path / "flow.csv"
    stock_path = tmp_path / "stock.csv"
    mmf_path = tmp_path / "mmf.csv"
    csv_path = tmp_path / "out.csv"
    md_path = tmp_path / "out.md"
    _flow_source().to_csv(flow_path, index=False)
    _stock_source().to_csv(stock_path, index=False)
    _mmf_context().to_csv(mmf_path, index=False)

    _, _, frame = write_tdcsim_private_route_allocation_sensitivity(
        z1_flow_path=flow_path,
        z1_stock_path=stock_path,
        mmf_route_split_context_path=mmf_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(frame)
    markdown = render_tdcsim_private_route_allocation_sensitivity_markdown(frame)
    assert "bounded noncanonical proxy" in markdown
    assert "memo-only" in markdown
