from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import load_treasury_table
from .utils import choose_numeric_column, parse_date_column, string_match_mask


def extract_mts_pattern_series(
    path: Path | str,
    *,
    pattern: str,
    preferred_keywords: list[str] | None = None,
    series_name: str = "mts_pattern_series",
) -> pd.Series:
    df = load_treasury_table(path)
    mask = string_match_mask(df, pattern)
    sub = df.loc[mask].copy()
    if sub.empty:
        return pd.Series(dtype="float64", name=series_name)

    date_col = parse_date_column(sub)
    value_col = choose_numeric_column(sub, preferred_keywords=preferred_keywords or ["net", "amt", "amount"])
    if value_col is None:
        return pd.Series(dtype="float64", name=series_name)

    series = pd.Series(
        pd.to_numeric(sub[value_col], errors="coerce").values,
        index=pd.to_datetime(sub[date_col]),
        name=series_name,
    ).sort_index()
    return series


def extract_mts_fed_earnings_receipts(path: Path | str) -> pd.Series:
    return extract_mts_pattern_series(
        path,
        pattern=r"deposit of earnings.*federal reserve",
        preferred_keywords=["net", "amt", "amount"],
        series_name="mts_fed_earnings_receipts",
    )


def extract_mts_net_outlays_matching(path: Path | str, pattern: str, *, series_name: str) -> pd.Series:
    return extract_mts_pattern_series(
        path,
        pattern=pattern,
        preferred_keywords=["net_outly", "net", "outly", "amt"],
        series_name=series_name,
    )


def extract_dts_operating_cash_balance(path: Path | str) -> pd.DataFrame:
    return load_treasury_table(path)
