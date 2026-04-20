from __future__ import annotations

from pathlib import Path

import pandas as pd

from .catalog import all_fred_series
from .io import build_quarterly_frame, support_raw_path

TIER3_SUPPORT_KEYS = [
    "bank_noninterest_outlay_proxy",
    "row_noninterest_outlay_proxy",
    "bank_nonborrow_receipt_proxy",
    "row_nonborrow_receipt_proxy",
    "mint_cb_cash_factor_proxy",
]


def derive_quarterly_date_spine(raw_dir: Path | str) -> pd.DatetimeIndex:
    quarterly, _ = build_quarterly_frame(raw_dir, all_fred_series(include_optional=True), local_specs=[])
    return pd.DatetimeIndex(quarterly.index)


def load_tier3_quarterly_input_table(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError("Tier 3 quarterly input table must contain a 'date' column.")
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.set_index("date").sort_index()
    return frame


def build_tier3_support_table(
    *,
    dates: pd.DatetimeIndex,
    quarterly_input: pd.DataFrame | None = None,
    fill_value: float = 0.0,
) -> pd.DataFrame:
    table = pd.DataFrame(index=pd.DatetimeIndex(dates).sort_values().unique())
    for key in TIER3_SUPPORT_KEYS:
        table[key] = fill_value
        if quarterly_input is not None and key in quarterly_input.columns:
            table[key] = quarterly_input[key].reindex(table.index).fillna(fill_value)
    return table


def write_tier3_support_files(
    *,
    raw_dir: Path | str,
    table: pd.DataFrame,
    overwrite: bool = False,
) -> dict[str, str]:
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for key in TIER3_SUPPORT_KEYS:
        path = support_raw_path(raw_dir, key)
        if path.exists() and not overwrite:
            written[key] = str(path)
            continue
        df = pd.DataFrame({"date": pd.to_datetime(table.index), "value": table[key].astype("float64").values})
        df.to_csv(path, index=False)
        written[key] = str(path)
    return written
