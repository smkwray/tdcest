from __future__ import annotations

import pandas as pd

from tdc_estimator.tier3_provisional import build_provisional_tier3_input_table


def test_build_provisional_tier3_input_table_scales_coupon_supports(tmp_path):
    bank_path = tmp_path / "bank.csv"
    row_path = tmp_path / "row.csv"
    pd.DataFrame(
        {"date": ["2022-06-30", "2022-09-30", "2022-12-31"], "value": [5.0, 10.0, 20.0]}
    ).to_csv(bank_path, index=False)
    pd.DataFrame(
        {"date": ["2022-09-30", "2022-12-31"], "value": [50.0, 100.0]}
    ).to_csv(row_path, index=False)

    table = build_provisional_tier3_input_table(
        bank_coupon_path=bank_path,
        row_coupon_path=row_path,
        start="2022-09-30",
        bank_outlay_ratio=0.2,
        row_outlay_ratio=0.1,
        bank_receipt_ratio=0.05,
        row_receipt_ratio=0.02,
        mint_cb_cash_factor_value=0.25,
    )

    assert list(table.index) == list(pd.to_datetime(["2022-09-30", "2022-12-31"]))
    assert round(table.loc[pd.Timestamp("2022-09-30"), "bank_noninterest_outlay_proxy"], 6) == 2.0
    assert round(table.loc[pd.Timestamp("2022-09-30"), "row_noninterest_outlay_proxy"], 6) == 5.0
    assert round(table.loc[pd.Timestamp("2022-12-31"), "bank_nonborrow_receipt_proxy"], 6) == 1.0
    assert round(table.loc[pd.Timestamp("2022-12-31"), "row_nonborrow_receipt_proxy"], 6) == 2.0
    assert round(table.loc[pd.Timestamp("2022-12-31"), "mint_cb_cash_factor_proxy"], 6) == 0.25
