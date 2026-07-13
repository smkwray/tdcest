from __future__ import annotations

import pandas as pd
import pytest

from tdc_estimator.tier2_regression_series import (
    build_tier2_regression_series,
    validate_regression_backcast_modern_splice,
)


def test_tier2_regression_series_combines_base_fed_and_backcast():
    dates = pd.to_datetime(["2002-03-31", "2022-03-31"])
    estimates = pd.DataFrame(
        {
            "date": dates,
            "tdc_base_bank_only_ru_flow": [100.0, 200.0],
            "tdc_base_broad_depository_np_cu_ru_flow": [110.0, 220.0],
            "tdc_domestic_bank_only_ru_flow": [70.0, 90.0],
        }
    )
    components = pd.DataFrame(
        {
            "date": dates,
            "fed_tsy_coupon_interest_proxy": [5.0, 8.0],
            "mmf_rrp_adjustment_lb": [0.0, 3.0],
            "mmf_rrp_adjustment_prop": [0.0, 5.0],
            "mmf_rrp_adjustment_ub": [0.0, 7.0],
        }
    )
    backcast = pd.DataFrame(
        {
            "date": dates,
            "bank_tier2_regression_interest_proxy": [10.0, 12.0],
            "row_tier2_regression_interest_proxy": [20.0, 25.0],
            "credit_union_tier2_regression_interest_proxy": [1.0, 2.0],
            "bank_row_tier2_regression_interest_proxy": [30.0, 37.0],
            "di_tier2_regression_interest_proxy": [31.0, 39.0],
            "bank_method_tier": ["pre_component_h15_scaled_backcast", "constrained_component"],
            "row_method_tier": ["pre_component_h15_scaled_backcast", "constrained_component"],
            "credit_union_method_tier": ["pre_component_h15_scaled_backcast", "constrained_component"],
        }
    )

    out = build_tier2_regression_series(
        estimates=estimates,
        components=components,
        regression_backcast_wide=backcast,
    )

    first = out.loc[out["date"].eq(pd.Timestamp("2002-03-31"))].iloc[0]
    assert first["tdc_tier2_regression_domestic_bank_only_ru_flow"] == 55.0
    assert first["tdc_tier2_regression_bank_only_ru_flow"] == 65.0
    assert first["tdc_tier2_regression_broad_depository_np_cu_ru_flow"] == 75.0
    assert first["tdc_tier2_regression_depository_institution_np_cu_ru_flow"] == 74.0
    assert first["tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow"] == 65.0
    assert first["tier2_regression_bank_row_method_tier"] == "pre_component_h15_scaled_backcast"

    latest = out.loc[out["date"].eq(pd.Timestamp("2022-03-31"))].iloc[0]
    assert latest["tdc_tier2_regression_bank_only_ru_flow"] == 155.0
    assert latest["tdc_tier2_regression_mmf_rrp_lb_bank_only_ru_flow"] == 158.0
    assert latest["tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow"] == 160.0
    assert latest["tdc_tier2_regression_mmf_rrp_ub_bank_only_ru_flow"] == 162.0
    assert latest["tdc_tier2_regression_mmf_rrp_prop_depository_institution_np_cu_ru_flow"] == 178.0


def _splice_backcast_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2022-03-31", "2022-06-30"]),
            "bank_tier2_regression_interest_proxy": [12.0, 13.0],
            "row_tier2_regression_interest_proxy": [25.0, 26.0],
            "credit_union_tier2_regression_interest_proxy": [2.0, 2.5],
            "bank_row_tier2_regression_interest_proxy": [37.0, 39.0],
            "di_tier2_regression_interest_proxy": [39.0, 41.5],
        }
    )


def _write_support(tmp_path, filename: str, values: list[float]) -> None:
    frame = pd.DataFrame({"date": ["2022-03-31", "2022-06-30"], "value": values})
    frame.to_csv(tmp_path / filename, index=False)


def test_modern_splice_validation_passes_on_exact_match(tmp_path):
    _write_support(tmp_path, "support__bank_tier2_component_interest_proxy.csv", [12.0, 13.0])
    _write_support(tmp_path, "support__row_tier2_component_interest_proxy.csv", [25.0, 26.0])
    _write_support(
        tmp_path, "support__credit_union_tier2_component_interest_proxy.csv", [2.0, 2.5]
    )
    validate_regression_backcast_modern_splice(_splice_backcast_frame(), tmp_path)


def test_modern_splice_validation_fails_closed_on_stale_backcast(tmp_path):
    _write_support(tmp_path, "support__bank_tier2_component_interest_proxy.csv", [12.0, 14.1])
    with pytest.raises(ValueError, match="bank: stale modern splice"):
        validate_regression_backcast_modern_splice(_splice_backcast_frame(), tmp_path)


def test_modern_splice_validation_fails_closed_on_no_overlap(tmp_path):
    frame = pd.DataFrame({"date": ["2010-03-31"], "value": [1.0]})
    frame.to_csv(tmp_path / "support__row_tier2_component_interest_proxy.csv", index=False)
    with pytest.raises(ValueError, match="no date overlap"):
        validate_regression_backcast_modern_splice(_splice_backcast_frame(), tmp_path)


def test_modern_splice_validation_skips_absent_support_files(tmp_path):
    validate_regression_backcast_modern_splice(_splice_backcast_frame(), tmp_path)
