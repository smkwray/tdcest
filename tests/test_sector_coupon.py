from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.sector_coupon import (
    estimate_quarterly_bank_bill_discount_interest_proxy,
    estimate_quarterly_bank_coupon_interest_proxy,
    estimate_quarterly_credit_union_coupon_interest_proxy,
    estimate_quarterly_row_coupon_interest_proxy,
    resolve_wamest_artifact_paths,
    write_quarterly_tier2_coupon_interest_proxies,
)


def test_estimate_quarterly_sector_coupon_proxies_from_wamest_style_inputs():
    sector_maturity = pd.DataFrame(
        {
            "date": [
                "2025-03-31",
                "2025-03-31",
                "2025-03-31",
                "2025-03-31",
                "2025-06-30",
                "2025-06-30",
                "2025-06-30",
                "2025-06-30",
            ],
            "sector_key": [
                "bank_us_chartered",
                "bank_foreign_banking_offices_us",
                "bank_us_affiliated_areas",
                "foreigners_total",
                "bank_us_chartered",
                "bank_foreign_banking_offices_us",
                "bank_us_affiliated_areas",
                "foreigners_total",
            ],
            "coupon_share": [0.90, 0.80, 0.70, 0.85, 0.92, 0.75, 0.72, 0.88],
            "coupon_only_maturity_years": [4.0, 2.0, 1.0, 10.0, 4.0, 2.0, 1.0, 10.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": sector_maturity["date"],
            "sector_key": sector_maturity["sector_key"],
            "level": [100.0, 20.0, 10.0, 200.0, 110.0, 22.0, 12.0, 210.0],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "1y": [1.0, 1.2],
            "2y": [2.0, 2.2],
            "3y": [3.0, 3.2],
            "5y": [5.0, 5.2],
            "10y": [6.0, 6.4],
        }
    )

    bank = estimate_quarterly_bank_coupon_interest_proxy(sector_maturity, sector_panel, curves)
    row = estimate_quarterly_row_coupon_interest_proxy(sector_maturity, sector_panel, curves)

    assert round(float(bank.loc[pd.Timestamp("2025-03-31")]), 6) == round(0.90 + 0.08 + 0.0175, 6)
    assert round(float(row.loc[pd.Timestamp("2025-03-31")]), 6) == round(200.0 * 0.85 * 0.06 / 4.0, 6)
    assert round(float(bank.loc[pd.Timestamp("2025-06-30")]), 6) == round(110.0 * 0.92 * 0.042 / 4.0 + 22.0 * 0.75 * 0.022 / 4.0 + 12.0 * 0.72 * 0.012 / 4.0, 6)
    assert round(float(row.loc[pd.Timestamp("2025-06-30")]), 6) == round(210.0 * 0.88 * 0.064 / 4.0, 6)


def test_estimate_quarterly_bill_discount_proxy_uses_bill_share_and_bill_wam():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["bank_us_chartered"],
            "bill_share": [0.25],
            "coupon_only_maturity_years": [4.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["bank_us_chartered"],
            "level": [100.0],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "3m": [4.0],
            "1y": [5.0],
        }
    )
    bill_wam = pd.DataFrame({"date": ["2025-03-31"], "bill_wam_years": [0.25]})

    bank = estimate_quarterly_bank_bill_discount_interest_proxy(
        sector_maturity,
        sector_panel,
        curves,
        bill_wam_support=bill_wam,
    )

    assert round(float(bank.loc[pd.Timestamp("2025-03-31")]), 6) == round(100.0 * 0.25 * 0.04 / 4.0, 6)


def test_estimate_quarterly_credit_union_coupon_proxy_from_wamest_sector_key():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["credit_unions_marketable_proxy"],
            "coupon_share": [0.60],
            "coupon_only_maturity_years": [2.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["credit_unions_marketable_proxy"],
            "level": [50.0],
        }
    )
    curves = pd.DataFrame({"date": ["2025-03-31"], "2y": [4.0]})

    credit_union = estimate_quarterly_credit_union_coupon_interest_proxy(sector_maturity, sector_panel, curves)

    assert round(float(credit_union.loc[pd.Timestamp("2025-03-31")]), 6) == round(50.0 * 0.60 * 0.04 / 4.0, 6)


def test_estimate_quarterly_sector_coupon_proxies_prefers_bill_wam_adjusted_coupon_maturity():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["foreigners_total"],
            "coupon_share": [1.0],
            "coupon_only_maturity_years": [10.0],
            "coupon_only_maturity_years_bill_wam_adjusted": [2.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["foreigners_total"],
            "level": [100.0],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "2y": [2.0],
            "10y": [10.0],
        }
    )

    row = estimate_quarterly_row_coupon_interest_proxy(sector_maturity, sector_panel, curves)

    assert round(float(row.loc[pd.Timestamp("2025-03-31")]), 6) == 0.5


def test_estimate_quarterly_sector_coupon_proxies_can_scale_to_observed_interest_pool():
    extra_sector_keys = [f"other_sector_{idx}" for idx in range(17)]
    sector_keys = [
        "bank_us_chartered",
        "foreigners_total",
        "households_nonprofits",
        "fed",
        *extra_sector_keys,
    ]
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"] * len(sector_keys),
            "sector_key": sector_keys,
            "coupon_share": [1.0] * len(sector_keys),
            "coupon_only_maturity_years": [2.0, 4.0, 6.0, 8.0, *([2.0] * len(extra_sector_keys))],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-03-31"] * len(sector_keys),
            "sector_key": sector_keys,
            "level": [100.0, 100.0, 100.0, 100.0, *([0.0] * len(extra_sector_keys))],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "2y": [2.0],
            "4y": [4.0],
            "6y": [6.0],
            "8y": [8.0],
        }
    )
    aggregate_interest_proxy = pd.Series([100.0], index=pd.to_datetime(["2025-03-31"]))
    exact_fed_coupon_proxy = pd.Series([10.0], index=pd.to_datetime(["2025-03-31"]))

    bank = estimate_quarterly_bank_coupon_interest_proxy(
        sector_maturity,
        sector_panel,
        curves,
        use_observed_interest_anchor=True,
        aggregate_interest_proxy=aggregate_interest_proxy,
        exact_fed_coupon_proxy=exact_fed_coupon_proxy,
    )
    row = estimate_quarterly_row_coupon_interest_proxy(
        sector_maturity,
        sector_panel,
        curves,
        use_observed_interest_anchor=True,
        aggregate_interest_proxy=aggregate_interest_proxy,
        exact_fed_coupon_proxy=exact_fed_coupon_proxy,
    )

    # Raw non-Fed weights are 0.5, 1.0, and 1.5, so bank and ROW get 1/3 and 2/3 of the 90 observed non-Fed pool.
    assert round(float(bank.loc[pd.Timestamp("2025-03-31")]), 6) == 15.0
    assert round(float(row.loc[pd.Timestamp("2025-03-31")]), 6) == 30.0


def test_estimate_quarterly_sector_coupon_proxies_falls_back_when_sector_coverage_is_too_narrow():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"] * 4,
            "sector_key": [
                "bank_us_chartered",
                "foreigners_total",
                "households_nonprofits",
                "fed",
            ],
            "coupon_share": [1.0, 1.0, 1.0, 1.0],
            "coupon_only_maturity_years": [2.0, 4.0, 6.0, 8.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-03-31"] * 4,
            "sector_key": [
                "bank_us_chartered",
                "foreigners_total",
                "households_nonprofits",
                "fed",
            ],
            "level": [100.0, 100.0, 100.0, 100.0],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "2y": [2.0],
            "4y": [4.0],
            "6y": [6.0],
            "8y": [8.0],
        }
    )
    aggregate_interest_proxy = pd.Series([100.0], index=pd.to_datetime(["2025-03-31"]))
    exact_fed_coupon_proxy = pd.Series([10.0], index=pd.to_datetime(["2025-03-31"]))

    bank = estimate_quarterly_bank_coupon_interest_proxy(
        sector_maturity,
        sector_panel,
        curves,
        use_observed_interest_anchor=True,
        aggregate_interest_proxy=aggregate_interest_proxy,
        exact_fed_coupon_proxy=exact_fed_coupon_proxy,
    )
    row = estimate_quarterly_row_coupon_interest_proxy(
        sector_maturity,
        sector_panel,
        curves,
        use_observed_interest_anchor=True,
        aggregate_interest_proxy=aggregate_interest_proxy,
        exact_fed_coupon_proxy=exact_fed_coupon_proxy,
    )

    assert round(float(bank.loc[pd.Timestamp("2025-03-31")]), 6) == 0.5
    assert round(float(row.loc[pd.Timestamp("2025-03-31")]), 6) == 1.0


def test_write_quarterly_tier2_coupon_interest_proxies_writes_default_date_value_files(tmp_path: Path):
    sector_maturity_path = tmp_path / "sector_effective_maturity.csv"
    sector_panel_path = tmp_path / "sector_panel.csv"
    curve_path = tmp_path / "h15_curves.csv"
    bank_out = tmp_path / "support__bank_tsy_coupon_interest_proxy.csv"
    row_out = tmp_path / "support__row_tsy_coupon_interest_proxy.csv"

    pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-03-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total"],
            "bill_share": [0.10, 0.15],
            "effective_duration_years": [5.0, 10.0],
        }
    ).to_csv(sector_maturity_path, index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-03-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total"],
            "level": [100.0, 200.0],
        }
    ).to_csv(sector_panel_path, index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "5y": [4.0],
            "10y": [5.0],
        }
    ).to_csv(curve_path, index=False)

    written_bank, written_row = write_quarterly_tier2_coupon_interest_proxies(
        sector_maturity_path=sector_maturity_path,
        sector_panel_path=sector_panel_path,
        curve_path=curve_path,
        bank_out_path=bank_out,
        row_out_path=row_out,
    )

    bank_frame = pd.read_csv(written_bank)
    row_frame = pd.read_csv(written_row)

    assert written_bank == bank_out
    assert written_row == row_out
    assert list(bank_frame.columns) == ["date", "value"]
    assert list(row_frame.columns) == ["date", "value"]
    assert bank_frame.loc[0, "date"] == "2025-03-31"
    assert row_frame.loc[0, "date"] == "2025-03-31"
    assert round(float(bank_frame.loc[0, "value"]), 6) == 0.9
    assert round(float(row_frame.loc[0, "value"]), 6) == 2.125


def test_write_quarterly_tier2_coupon_interest_proxies_can_write_credit_union_file(tmp_path: Path):
    sector_maturity_path = tmp_path / "sector_effective_maturity.csv"
    sector_panel_path = tmp_path / "sector_panel.csv"
    curve_path = tmp_path / "h15_curves.csv"
    bank_out = tmp_path / "support__bank_tsy_coupon_interest_proxy.csv"
    row_out = tmp_path / "support__row_tsy_coupon_interest_proxy.csv"
    credit_union_out = tmp_path / "support__credit_union_tsy_coupon_interest_proxy.csv"

    pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-03-31", "2025-03-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total", "credit_unions_marketable_proxy"],
            "coupon_share": [1.0, 1.0, 0.5],
            "coupon_only_maturity_years": [2.0, 2.0, 2.0],
        }
    ).to_csv(sector_maturity_path, index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-03-31", "2025-03-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total", "credit_unions_marketable_proxy"],
            "level": [100.0, 200.0, 40.0],
        }
    ).to_csv(sector_panel_path, index=False)
    pd.DataFrame({"date": ["2025-03-31"], "2y": [4.0]}).to_csv(curve_path, index=False)

    written_bank, written_row, written_credit_union = write_quarterly_tier2_coupon_interest_proxies(
        sector_maturity_path=sector_maturity_path,
        sector_panel_path=sector_panel_path,
        curve_path=curve_path,
        bank_out_path=bank_out,
        row_out_path=row_out,
        credit_union_out_path=credit_union_out,
    )

    credit_union_frame = pd.read_csv(written_credit_union)

    assert written_bank == bank_out
    assert written_row == row_out
    assert written_credit_union == credit_union_out
    assert list(credit_union_frame.columns) == ["date", "value"]
    assert round(float(credit_union_frame.loc[0, "value"]), 6) == round(40.0 * 0.5 * 0.04 / 4.0, 6)


def test_write_quarterly_tier2_coupon_interest_proxies_can_use_observed_interest_anchor_when_requested(tmp_path: Path):
    sector_maturity_path = tmp_path / "sector_effective_maturity.csv"
    sector_panel_path = tmp_path / "sector_panel.csv"
    curve_path = tmp_path / "h15_curves.csv"
    bank_out = tmp_path / "support__bank_tsy_coupon_interest_proxy.csv"
    row_out = tmp_path / "support__row_tsy_coupon_interest_proxy.csv"
    mts_outlays_path = tmp_path / "treasury__mts_outlays.csv"
    fred_interest_path = tmp_path / "fred__federal_interest_payments_nsa_q.csv"
    fed_coupon_path = tmp_path / "support__fed_tsy_coupon_interest_proxy.csv"

    extra_sector_keys = [f"other_sector_{idx}" for idx in range(17)]
    sector_keys = ["bank_us_chartered", "foreigners_total", "households_nonprofits", "fed", *extra_sector_keys]
    pd.DataFrame(
        {
            "date": ["2025-03-31"] * len(sector_keys),
            "sector_key": sector_keys,
            "coupon_share": [1.0] * len(sector_keys),
            "coupon_only_maturity_years": [2.0, 4.0, 6.0, 8.0, *([2.0] * len(extra_sector_keys))],
        }
    ).to_csv(sector_maturity_path, index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31"] * len(sector_keys),
            "sector_key": sector_keys,
            "level": [100.0, 100.0, 100.0, 100.0, *([0.0] * len(extra_sector_keys))],
        }
    ).to_csv(sector_panel_path, index=False)
    pd.DataFrame({"date": ["2025-03-31"], "2y": [2.0], "4y": [4.0], "6y": [6.0], "8y": [8.0]}).to_csv(curve_path, index=False)
    pd.DataFrame(
        {
            "record_date": ["2025-01-31", "2025-02-28", "2025-03-31"],
            "classification_desc": ["Total--Interest on Treasury Debt Securities (Gross)"] * 3,
            "current_month_net_outly_amt": [30_000_000.0, 30_000_000.0, 40_000_000.0],
        }
    ).to_csv(mts_outlays_path, index=False)
    pd.DataFrame({"date": ["2025-01-01"], "value": [999.0]}).to_csv(fred_interest_path, index=False)
    pd.DataFrame({"date": ["2025-03-31"], "value": [10.0]}).to_csv(fed_coupon_path, index=False)

    written_bank, written_row = write_quarterly_tier2_coupon_interest_proxies(
        sector_maturity_path=sector_maturity_path,
        sector_panel_path=sector_panel_path,
        curve_path=curve_path,
        bank_out_path=bank_out,
        row_out_path=row_out,
        use_observed_interest_anchor=True,
        mts_outlays_path=mts_outlays_path,
        fred_interest_path=fred_interest_path,
        fed_coupon_path=fed_coupon_path,
    )

    bank_frame = pd.read_csv(written_bank)
    row_frame = pd.read_csv(written_row)

    assert round(float(bank_frame.loc[0, "value"]), 6) == 15.0
    assert round(float(row_frame.loc[0, "value"]), 6) == 30.0


def test_wamest_style_sector_panel_levels_are_normalized_to_millions():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total"],
            "coupon_share": [0.9, 0.85],
            "coupon_only_maturity_years": [5.0, 10.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31", "2025-12-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total", "all_holders_total"],
            "level": [1652.960, 8721.721, 28800.000],
            "transactions": [16.808, 60.840, 0.0],
            "method_priority": ["direct_z1", "direct_z1", "direct_z1"],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "5y": [4.0],
            "10y": [3.8],
        }
    )

    bank = estimate_quarterly_bank_coupon_interest_proxy(sector_maturity, sector_panel, curves)
    row = estimate_quarterly_row_coupon_interest_proxy(sector_maturity, sector_panel, curves)

    assert round(float(bank.loc[pd.Timestamp("2025-12-31")]), 3) == round(1652.960 * 1000.0 * 0.9 * 0.04 / 4.0, 3)
    assert round(float(row.loc[pd.Timestamp("2025-12-31")]), 3) == round(8721.721 * 1000.0 * 0.85 * 0.038 / 4.0, 3)


def test_built_wamest_sector_panel_levels_stay_in_millions_without_extra_scaling():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total"],
            "coupon_share": [0.9, 0.85],
            "coupon_only_maturity_years": [5.0, 10.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31", "2025-12-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total", "all_holders_total"],
            "level": [1652.960, 8721.721, 28800.000],
            "method_priority": ["direct_z1", "direct_z1", "direct_z1"],
            "level_source_provider_used": ["fed_z1", "fed_z1", "fed_z1"],
            "required_for_full_coverage": [True, True, False],
            "level_units": ["millions", "millions", "millions"],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "5y": [4.0],
            "10y": [3.8],
        }
    )

    bank = estimate_quarterly_bank_coupon_interest_proxy(sector_maturity, sector_panel, curves)
    row = estimate_quarterly_row_coupon_interest_proxy(sector_maturity, sector_panel, curves)

    assert round(float(bank.loc[pd.Timestamp("2025-12-31")]), 6) == round(1652.960 * 0.9 * 0.04 / 4.0, 6)
    assert round(float(row.loc[pd.Timestamp("2025-12-31")]), 6) == round(8721.721 * 0.85 * 0.038 / 4.0, 6)


def test_resolve_wamest_artifact_paths_prefers_full_history_conventions(tmp_path: Path):
    wamest_root = tmp_path / "wamest"
    sector_maturity = wamest_root / "outputs" / "full_coverage_release" / "canonical_sector_maturity.csv"
    sector_panel = wamest_root / "data" / "external" / "normalized" / "z1_series_fred.csv"
    inventory = wamest_root / "outputs" / "full_coverage_release" / "required_sector_inventory.csv"
    curve = wamest_root / "data" / "external" / "normalized" / "h15_curves_auto_nominal_treasury_constant_maturity.csv"
    curve.parent.mkdir(parents=True, exist_ok=True)
    sector_panel.parent.mkdir(parents=True, exist_ok=True)
    sector_maturity.parent.mkdir(parents=True, exist_ok=True)
    sector_maturity.write_text("date,sector_key,coupon_share,coupon_only_maturity_years\n", encoding="utf-8")
    sector_panel.write_text("date,series_code,value\n", encoding="utf-8")
    inventory.write_text("sector_key,level_source_code\n", encoding="utf-8")
    curve.write_text("date,1y\n", encoding="utf-8")

    resolved = resolve_wamest_artifact_paths(wamest_root)

    assert resolved == (sector_maturity, sector_panel, curve)


def test_write_quarterly_tier2_coupon_interest_proxies_can_use_full_coverage_release_inputs(tmp_path: Path):
    release_dir = tmp_path / "wamest" / "outputs" / "full_coverage_release"
    release_dir.mkdir(parents=True, exist_ok=True)
    curve_path = tmp_path / "wamest" / "data" / "external" / "normalized" / "h15_curves_auto_nominal_treasury_constant_maturity.csv"
    curve_path.parent.mkdir(parents=True, exist_ok=True)

    sector_maturity_path = release_dir / "canonical_sector_maturity.csv"
    sector_panel_path = release_dir / "z1_series_auto_full.csv"
    inventory_path = release_dir / "required_sector_inventory.csv"
    bank_out = tmp_path / "support__bank_tsy_coupon_interest_proxy.csv"
    row_out = tmp_path / "support__row_tsy_coupon_interest_proxy.csv"

    pd.DataFrame(
        {
            "date": ["1945-12-31", "2002-03-31", "2002-03-31"],
            "sector_key": ["bank_us_chartered", "bank_us_chartered", "foreigners_total"],
            "coupon_share": [0.75, 0.80, 0.90],
            "coupon_only_maturity_years": [3.0, 5.0, 10.0],
            "publication_status": [
                "status_only_no_level_or_estimate",
                "history_preserving_backfill",
                "published_estimate",
            ],
        }
    ).to_csv(sector_maturity_path, index=False)
    pd.DataFrame(
        {
            "date": ["1945-12-31", "2002-03-31", "2002-03-31"],
            "series_code": ["FL763061100.Q", "FL763061100.Q", "FL263061105.Q"],
            "value": [50.0, 100.0, 200.0],
        }
    ).to_csv(sector_panel_path, index=False)
    pd.DataFrame(
        {
            "sector_key": ["bank_us_chartered", "foreigners_total"],
            "level_source_code": ["FL763061100.Q", "FL263061105.Q"],
        }
    ).to_csv(inventory_path, index=False)
    pd.DataFrame(
        {
            "date": ["2002-03-31"],
            "5y": [4.0],
            "10y": [5.0],
        }
    ).to_csv(curve_path, index=False)

    written_bank, written_row = write_quarterly_tier2_coupon_interest_proxies(
        sector_maturity_path=sector_maturity_path,
        sector_panel_path=sector_panel_path,
        curve_path=curve_path,
        bank_out_path=bank_out,
        row_out_path=row_out,
    )

    bank_frame = pd.read_csv(written_bank)
    row_frame = pd.read_csv(written_row)

    assert list(bank_frame["date"]) == ["2002-03-31"]
    assert list(row_frame["date"]) == ["2002-03-31"]
    assert round(float(bank_frame.loc[0, "value"]), 6) == round(100.0 * 0.80 * 0.04 / 4.0, 6)
    assert round(float(row_frame.loc[0, "value"]), 6) == round(200.0 * 0.90 * 0.05 / 4.0, 6)


def test_full_coverage_release_input_bridge_can_reconstruct_computed_credit_union_level(tmp_path: Path):
    release_dir = tmp_path / "wamest" / "outputs" / "full_coverage_release"
    release_dir.mkdir(parents=True, exist_ok=True)
    curve_path = tmp_path / "wamest" / "data" / "external" / "normalized" / "h15_curves_auto_nominal_treasury_constant_maturity.csv"
    curve_path.parent.mkdir(parents=True, exist_ok=True)

    sector_maturity_path = release_dir / "canonical_sector_maturity.csv"
    sector_panel_path = release_dir / "z1_series_auto_full.csv"
    inventory_path = release_dir / "required_sector_inventory.csv"
    bank_out = tmp_path / "support__bank_tsy_coupon_interest_proxy.csv"
    row_out = tmp_path / "support__row_tsy_coupon_interest_proxy.csv"
    credit_union_out = tmp_path / "support__credit_union_tsy_coupon_interest_proxy.csv"

    pd.DataFrame(
        {
            "date": ["2002-03-31"],
            "sector_key": ["credit_unions_marketable_proxy"],
            "coupon_share": [0.75],
            "coupon_only_maturity_years": [2.0],
            "publication_status": ["published_estimate"],
        }
    ).to_csv(sector_maturity_path, index=False)
    pd.DataFrame(
        {
            "date": ["2002-03-31", "2002-03-31"],
            "series_code": ["FL473061103.Q", "FL473061153.Q"],
            "value": [100.0, 20.0],
        }
    ).to_csv(sector_panel_path, index=False)
    pd.DataFrame(
        {
            "sector_key": ["credit_unions_marketable_proxy"],
            "level_source_code": [None],
            "dependency_level_source_codes": ["FL473061103.Q, FL473061153.Q"],
        }
    ).to_csv(inventory_path, index=False)
    pd.DataFrame({"date": ["2002-03-31"], "2y": [4.0]}).to_csv(curve_path, index=False)

    written_bank, written_row, written_credit_union = write_quarterly_tier2_coupon_interest_proxies(
        sector_maturity_path=sector_maturity_path,
        sector_panel_path=sector_panel_path,
        curve_path=curve_path,
        bank_out_path=bank_out,
        row_out_path=row_out,
        credit_union_out_path=credit_union_out,
    )

    credit_union_frame = pd.read_csv(written_credit_union)

    assert written_bank == bank_out
    assert written_row == row_out
    assert round(float(credit_union_frame.loc[0, "value"]), 6) == round(120.0 * 0.75 * 0.04 / 4.0, 6)


def test_reconstructed_full_coverage_release_levels_stay_in_millions():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total"],
            "coupon_share": [0.9, 0.85],
            "coupon_only_maturity_years": [5.0, 10.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total"],
            "level": [1652.960, 8721.721],
            "level_units": ["millions", "millions"],
            "method_priority": [
                "full_coverage_release_level_map",
                "full_coverage_release_level_map",
            ],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "5y": [4.0],
            "10y": [3.8],
        }
    )

    bank = estimate_quarterly_bank_coupon_interest_proxy(sector_maturity, sector_panel, curves)
    row = estimate_quarterly_row_coupon_interest_proxy(sector_maturity, sector_panel, curves)

    assert round(float(bank.loc[pd.Timestamp("2025-12-31")]), 3) == round(1652.960 * 0.9 * 0.04 / 4.0, 3)
    assert round(float(row.loc[pd.Timestamp("2025-12-31")]), 3) == round(8721.721 * 0.85 * 0.038 / 4.0, 3)


def test_estimate_quarterly_sector_coupon_proxy_uses_latest_nonempty_curve_row():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2002-03-31"],
            "sector_key": ["bank_us_chartered"],
            "coupon_share": [0.80],
            "coupon_only_maturity_years": [5.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2002-03-31"],
            "sector_key": ["bank_us_chartered"],
            "level": [100.0],
        }
    )
    curves = pd.DataFrame(
        {
            "date": ["2002-03-28", "2002-03-29"],
            "5y": [4.91, None],
            "10y": [5.42, None],
        }
    )

    bank = estimate_quarterly_bank_coupon_interest_proxy(sector_maturity, sector_panel, curves)

    assert round(float(bank.loc[pd.Timestamp("2002-03-31")]), 6) == round(100.0 * 0.80 * 0.0491 / 4.0, 6)
