from __future__ import annotations

from pathlib import Path

import pandas as pd

from .catalog import FredSeries
from .utils import parse_date_column, parse_value_column, quarterly_resample, to_float_series


def fred_raw_path(raw_dir: Path | str, key: str) -> Path:
    return Path(raw_dir) / f"fred__{key}.csv"


def treasury_raw_path(raw_dir: Path | str, key: str) -> Path:
    return Path(raw_dir) / f"treasury__{key}.csv"


def load_fred_series(path: Path | str) -> pd.Series:
    df = pd.read_csv(path)
    date_col = parse_date_column(df)
    value_col = parse_value_column(df)
    series = pd.Series(
        to_float_series(df[value_col]).values,
        index=pd.to_datetime(df[date_col]),
        name=Path(path).stem,
        dtype="float64",
    )
    series = series.sort_index()
    return series


def load_quarterly_fred_series(path: Path | str, agg: str, transform: str | None = None) -> pd.Series:
    series = load_fred_series(path)
    if transform == "clip_positive":
        series = series.clip(lower=0)
    return quarterly_resample(series, agg=agg)


def build_quarterly_frame(raw_dir: Path | str, specs: list[FredSeries]) -> tuple[pd.DataFrame, dict]:
    frame = pd.DataFrame()
    meta: dict[str, dict] = {}

    for spec in specs:
        path = fred_raw_path(raw_dir, spec.key)
        if not path.exists():
            if spec.required:
                raise FileNotFoundError(f"Missing required raw file: {path}")
            continue
        series = load_quarterly_fred_series(path, agg=spec.agg, transform=spec.transform)
        frame[spec.key] = series
        meta[spec.key] = {
            "series_id": spec.series_id,
            "description": spec.description,
            "agg": spec.agg,
            "transform": spec.transform,
            "required": spec.required,
            "raw_filename": path.name,
            "raw_relative_path": str(Path("data/raw") / path.name),
        }

    frame = frame.sort_index()
    return frame, meta


def load_treasury_table(path: Path | str) -> pd.DataFrame:
    return pd.read_csv(path)
