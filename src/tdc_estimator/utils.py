from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path | str) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _json_safe(payload: object) -> object:
    if isinstance(payload, dict):
        return {str(key): _json_safe(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_json_safe(value) for value in payload]
    if isinstance(payload, tuple):
        return [_json_safe(value) for value in payload]
    if isinstance(payload, pd.Timestamp):
        if pd.isna(payload):
            return None
        return payload.isoformat()
    if isinstance(payload, datetime):
        return payload.isoformat()
    if payload is None:
        return None
    if isinstance(payload, (float, np.floating)):
        if math.isnan(float(payload)) or math.isinf(float(payload)):
            return None
        return float(payload)
    if isinstance(payload, (int, np.integer)):
        return int(payload)
    try:
        if pd.isna(payload):
            return None
    except Exception:
        pass
    return payload


def write_json(path: Path | str, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = _json_safe(payload)
    target.write_text(json.dumps(safe_payload, indent=2, sort_keys=False, allow_nan=False), encoding="utf-8")


def read_text(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def to_float_series(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce")


def parse_date_column(df: pd.DataFrame) -> str:
    candidates = [c for c in df.columns if c.lower() in {"date", "observation_date", "record_date"}]
    if candidates:
        return candidates[0]
    return df.columns[0]


def parse_value_column(df: pd.DataFrame, preferred: str | None = None) -> str:
    if preferred and preferred in df.columns:
        return preferred
    lowered = {c.lower(): c for c in df.columns}
    for key in ["value", "observed_value", "amount", "amt"]:
        if key in lowered:
            return lowered[key]
    non_date_cols = [c for c in df.columns if c != parse_date_column(df)]
    if not non_date_cols:
        raise ValueError("No usable value column found.")
    return non_date_cols[0]


def quarterly_resample(series: pd.Series, agg: str) -> pd.Series:
    series = series.sort_index()
    if agg == "sum":
        return series.resample("QE-DEC").sum(min_count=1)
    if agg == "last":
        return series.resample("QE-DEC").last()
    raise ValueError(f"Unsupported aggregation: {agg}")


def safe_numeric_diff(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").diff()


def camel_to_title(name: str) -> str:
    text = name.replace("_", " ")
    return text.title()


def string_match_mask(df: pd.DataFrame, pattern: str) -> pd.Series:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    masks = []
    for col in df.columns:
        if df[col].dtype == object:
            masks.append(df[col].fillna("").astype(str).str.contains(regex))
    if not masks:
        return pd.Series(False, index=df.index)
    out = masks[0].copy()
    for mask in masks[1:]:
        out = out | mask
    return out


def choose_numeric_column(df: pd.DataFrame, preferred_keywords: list[str] | None = None) -> str | None:
    preferred_keywords = preferred_keywords or []
    numeric_candidates: list[str] = []
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() > 0:
            numeric_candidates.append(col)
    if not numeric_candidates:
        return None

    for keyword in preferred_keywords:
        for col in numeric_candidates:
            if keyword.lower() in col.lower():
                return col
    return numeric_candidates[0]


def to_iso_date_index(series: pd.Series) -> list[str]:
    return [pd.Timestamp(idx).date().isoformat() for idx in series.index]


def flatten_long(df: pd.DataFrame, value_name: str = "value") -> pd.DataFrame:
    out = df.copy()
    out.index.name = "date"
    long_df = out.reset_index().melt(id_vars="date", var_name="series", value_name=value_name)
    long_df["date"] = pd.to_datetime(long_df["date"]).dt.date.astype(str)
    return long_df


def round_if_number(value: object, digits: int = 3) -> object:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        return round(float(value), digits)
    except Exception:
        return value
