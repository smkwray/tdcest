from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import load_treasury_table
from .utils import choose_numeric_column, parse_date_column, string_match_mask


def extract_mts_fed_earnings_receipts(path: Path | str) -> pd.Series:
    df = load_treasury_table(path)
    mask = string_match_mask(df, r"deposit of earnings.*federal reserve")
    sub = df.loc[mask].copy()
    if sub.empty:
        return pd.Series(dtype="float64", name="mts_fed_earnings_receipts")

    date_col = parse_date_column(sub)
    value_col = choose_numeric_column(sub, preferred_keywords=["net", "amt", "amount"])
    if value_col is None:
        return pd.Series(dtype="float64", name="mts_fed_earnings_receipts")

    series = pd.Series(
        pd.to_numeric(sub[value_col], errors="coerce").values,
        index=pd.to_datetime(sub[date_col]),
        name="mts_fed_earnings_receipts",
    ).sort_index()
    return series


def extract_dts_operating_cash_balance(path: Path | str) -> pd.DataFrame:
    return load_treasury_table(path)
