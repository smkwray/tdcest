from __future__ import annotations

from pathlib import Path

import pandas as pd


def _load_support(path: Path | str) -> pd.Series:
    df = pd.read_csv(path)
    if "date" not in df.columns or "value" not in df.columns:
        raise ValueError(f"Support file {path} must contain date and value columns.")
    return pd.Series(df["value"].astype("float64").values, index=pd.to_datetime(df["date"]), dtype="float64")


def build_provisional_tier3_input_table(
    *,
    bank_coupon_path: Path | str,
    row_coupon_path: Path | str,
    start: str = "2022-09-30",
    bank_outlay_ratio: float = 0.15,
    row_outlay_ratio: float = 0.10,
    bank_receipt_ratio: float = 0.05,
    row_receipt_ratio: float = 0.03,
    mint_cb_cash_factor_value: float = 0.25,
) -> pd.DataFrame:
    bank_coupon = _load_support(bank_coupon_path)
    row_coupon = _load_support(row_coupon_path)
    index = bank_coupon.index.union(row_coupon.index)
    frame = pd.DataFrame(index=index.sort_values())
    frame["bank_coupon"] = bank_coupon.reindex(frame.index).fillna(0.0)
    frame["row_coupon"] = row_coupon.reindex(frame.index).fillna(0.0)
    frame = frame.loc[pd.to_datetime(frame.index) >= pd.Timestamp(start)].copy()
    frame["bank_noninterest_outlay_proxy"] = frame["bank_coupon"] * bank_outlay_ratio
    frame["row_noninterest_outlay_proxy"] = frame["row_coupon"] * row_outlay_ratio
    frame["bank_nonborrow_receipt_proxy"] = frame["bank_coupon"] * bank_receipt_ratio
    frame["row_nonborrow_receipt_proxy"] = frame["row_coupon"] * row_receipt_ratio
    frame["mint_cb_cash_factor_proxy"] = mint_cb_cash_factor_value
    return frame[
        [
            "bank_noninterest_outlay_proxy",
            "row_noninterest_outlay_proxy",
            "bank_nonborrow_receipt_proxy",
            "row_nonborrow_receipt_proxy",
            "mint_cb_cash_factor_proxy",
        ]
    ]


def write_provisional_tier3_input_table(
    *,
    bank_coupon_path: Path | str,
    row_coupon_path: Path | str,
    out_path: Path | str,
    start: str = "2022-09-30",
    bank_outlay_ratio: float = 0.15,
    row_outlay_ratio: float = 0.10,
    bank_receipt_ratio: float = 0.05,
    row_receipt_ratio: float = 0.03,
    mint_cb_cash_factor_value: float = 0.25,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = build_provisional_tier3_input_table(
        bank_coupon_path=bank_coupon_path,
        row_coupon_path=row_coupon_path,
        start=start,
        bank_outlay_ratio=bank_outlay_ratio,
        row_outlay_ratio=row_outlay_ratio,
        bank_receipt_ratio=bank_receipt_ratio,
        row_receipt_ratio=row_receipt_ratio,
        mint_cb_cash_factor_value=mint_cb_cash_factor_value,
    )
    to_write = table.copy()
    to_write.index.name = "date"
    to_write.to_csv(out_path)
    return out_path
