from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.sector_coupon import (
    estimate_quarterly_bank_coupon_interest_proxy,
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


def test_resolve_wamest_artifact_paths_prefers_full_history_conventions(tmp_path: Path):
    wamest_root = tmp_path / "wamest"
    sector_maturity = wamest_root / "data" / "processed" / "sector_effective_maturity_full.csv"
    sector_panel = wamest_root / "data" / "interim" / "z1_sector_panel_full.csv"
    curve = wamest_root / "data" / "external" / "normalized" / "h15_curves_auto_nominal_treasury_constant_maturity.csv"
    curve.parent.mkdir(parents=True, exist_ok=True)
    sector_panel.parent.mkdir(parents=True, exist_ok=True)
    sector_maturity.parent.mkdir(parents=True, exist_ok=True)
    sector_maturity.write_text("date,sector_key,coupon_share,coupon_only_maturity_years\n", encoding="utf-8")
    sector_panel.write_text("date,sector_key,level\n", encoding="utf-8")
    curve.write_text("date,1y\n", encoding="utf-8")

    resolved = resolve_wamest_artifact_paths(wamest_root)

    assert resolved == (sector_maturity, sector_panel, curve)
