from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .fed_coupon import normalize_col


DEFAULT_BANK_SECTOR_KEYS = [
    "bank_us_chartered",
    "bank_foreign_banking_offices_us",
    "bank_us_affiliated_areas",
]
DEFAULT_ROW_SECTOR_KEYS = ["foreigners_total"]
DEFAULT_WAMEST_SECTOR_MATURITY_CANDIDATES = [
    Path("outputs/full_coverage_release/canonical_sector_maturity.csv"),
    Path("data/processed/sector_effective_maturity_full.csv"),
    Path("outputs/public_preview/sector_effective_maturity.csv"),
    Path("tests/fixtures/report_sector_effective_maturity.csv"),
]
DEFAULT_WAMEST_SECTOR_PANEL_CANDIDATES = [
    Path("data/external/normalized/z1_series_fred.csv"),
    Path("outputs/full_coverage_release/z1_series_auto_full.csv"),
    Path("data/interim/z1_sector_panel_full.csv"),
    Path("data/examples/toy_sector_panel_ready.csv"),
]
DEFAULT_WAMEST_CURVE_CANDIDATES = [
    Path("data/external/normalized/h15_curves_auto_nominal_treasury_constant_maturity.csv"),
    Path("data/external/normalized/h15_curves_fed.csv"),
    Path("data/external/normalized/h15_curves_fred.csv"),
    Path("data/examples/toy_h15_curves.csv"),
]


def read_table(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df.rename(columns={column: normalize_col(column) for column in df.columns})


def read_sector_maturity_table(path: Path | str) -> pd.DataFrame:
    df = read_table(path)
    if "publication_status" not in df.columns:
        return df

    publishable = df["publication_status"].isin(["published_estimate", "history_preserving_backfill"])
    filtered = df.loc[publishable].copy()
    return filtered if not filtered.empty else df


def read_sector_panel_table(path: Path | str) -> pd.DataFrame:
    table_path = Path(path)
    df = read_table(table_path)
    if "sector_key" in df.columns:
        return df

    series_code_col = _first_existing(df, ["series_code", "series_key"])
    level_col = _first_existing(df, ["value", "level"])
    if series_code_col is None or level_col is None:
        return df

    inventory_path = _resolve_inventory_path(table_path)
    if inventory_path is None:
        return df

    inventory = read_table(inventory_path)
    code_candidates = ["level_source_code", "level_series_key", "level_fred_id"]
    inventory_code_col = next(
        (
            column
            for column in code_candidates
            if column in inventory.columns and inventory[column].notna().any()
        ),
        None,
    )
    if inventory_code_col is None or "sector_key" not in inventory.columns:
        return df

    code_map = (
        inventory.loc[:, ["sector_key", inventory_code_col]]
        .dropna()
        .drop_duplicates(subset=["sector_key"])
        .rename(columns={inventory_code_col: series_code_col})
    )
    if code_map.empty:
        return df

    merged = df.merge(code_map, on=series_code_col, how="inner")
    if merged.empty or "date" not in merged.columns:
        return df

    out = merged.loc[:, ["date", "sector_key", level_col]].copy()
    out = out.rename(columns={level_col: "level"})
    # Normalized FRED/Z.1 levels already use the repo's millions convention.
    out["level_units"] = "millions"
    out["method_priority"] = "full_coverage_release_level_map"
    return out


def _resolve_inventory_path(table_path: Path) -> Path | None:
    candidates = [table_path.parent / "required_sector_inventory.csv"]
    candidates.extend(parent / "outputs" / "full_coverage_release" / "required_sector_inventory.csv" for parent in table_path.parents)
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists():
            return candidate
    return None


def resolve_first_existing(base_dir: Path | str, candidates: Sequence[Path | str]) -> Path:
    base = Path(base_dir)
    for candidate in candidates:
        path = base / candidate
        if path.exists():
            return path
    joined = ", ".join(str(Path(candidate)) for candidate in candidates)
    raise FileNotFoundError(f"No matching artifact found under {base}. Tried: {joined}")


def resolve_wamest_artifact_paths(
    wamest_root: Path | str,
    sector_maturity_file: Path | str | None = None,
    sector_panel_file: Path | str | None = None,
    curve_file: Path | str | None = None,
) -> tuple[Path, Path, Path]:
    root = Path(wamest_root)

    if sector_maturity_file is None and sector_panel_file is None:
        full_release_maturity = root / DEFAULT_WAMEST_SECTOR_MATURITY_CANDIDATES[0]
        full_release_panel = root / DEFAULT_WAMEST_SECTOR_PANEL_CANDIDATES[0]
        full_release_inventory = root / "outputs" / "full_coverage_release" / "required_sector_inventory.csv"
        if full_release_maturity.exists() and full_release_panel.exists() and full_release_inventory.exists():
            sector_maturity_file = full_release_maturity
            sector_panel_file = full_release_panel

    sector_maturity_path = (
        Path(sector_maturity_file)
        if sector_maturity_file is not None
        else resolve_first_existing(root, DEFAULT_WAMEST_SECTOR_MATURITY_CANDIDATES)
    )
    sector_panel_path = (
        Path(sector_panel_file)
        if sector_panel_file is not None
        else resolve_first_existing(root, DEFAULT_WAMEST_SECTOR_PANEL_CANDIDATES)
    )
    curve_path = (
        Path(curve_file)
        if curve_file is not None
        else resolve_first_existing(root, DEFAULT_WAMEST_CURVE_CANDIDATES)
    )
    return sector_maturity_path, sector_panel_path, curve_path


def _first_existing(df: pd.DataFrame, candidates: Sequence[str]) -> str | None:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _curve_label_to_years(label: str) -> float | None:
    text = normalize_col(label)
    match = re.search(r"(?<!\d)(\d+)(m|mo|mos|month|months|y|yr|yrs|year|years)(?![a-z])", text)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit.startswith("m"):
        return value / 12.0
    return value


def prepare_curve_file(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={column: normalize_col(column) for column in df.columns})
    date_col = _first_existing(df, ["date", "record_date", "as_of_date", "report_date"])
    if date_col is None:
        raise ValueError("Curve file needs a date column.")

    curve_map: dict[str, float] = {}
    for column in df.columns:
        if column == date_col:
            continue
        years = _curve_label_to_years(column)
        if years is not None:
            curve_map[column] = years
    if not curve_map:
        raise ValueError("Curve file needs at least one maturity column such as 1y, 2y, 5y, or 10y.")

    out = pd.DataFrame(index=df.index)
    out["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    for column in curve_map:
        out[column] = pd.to_numeric(df[column], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    numeric_cols = list(curve_map)
    values = out[numeric_cols].stack().dropna()
    if not values.empty and float(values.abs().median()) > 1.0:
        out[numeric_cols] = out[numeric_cols] / 100.0
    return out


def _curve_points(curves: pd.DataFrame) -> list[tuple[str, float]]:
    points: list[tuple[str, float]] = []
    for column in curves.columns:
        if column == "date":
            continue
        years = _curve_label_to_years(column)
        if years is not None:
            points.append((column, years))
    return sorted(points, key=lambda item: item[1])


def _latest_curve_row_on_or_before(curves: pd.DataFrame, target_date: pd.Timestamp) -> pd.Series | None:
    eligible = curves[curves["date"] <= pd.Timestamp(target_date).normalize()]
    if eligible.empty:
        return None
    curve_columns = [column for column in curves.columns if column != "date"]
    if curve_columns:
        eligible = eligible.dropna(subset=curve_columns, how="all")
        if eligible.empty:
            return None
    return eligible.iloc[-1]


def _interpolate_curve_yield(curve_row: pd.Series, years: float, curve_points: Sequence[tuple[str, float]]) -> float | None:
    if not curve_points or not pd.notna(years):
        return None

    populated: list[tuple[float, float]] = []
    for column, maturity_years in curve_points:
        value = pd.to_numeric(curve_row.get(column), errors="coerce")
        if pd.notna(value):
            populated.append((maturity_years, float(value)))
    if not populated:
        return None

    if years <= populated[0][0]:
        return populated[0][1]
    if years >= populated[-1][0]:
        return populated[-1][1]

    for (left_years, left_value), (right_years, right_value) in zip(populated, populated[1:]):
        if left_years <= years <= right_years:
            span = right_years - left_years
            if span <= 0:
                return left_value
            weight = (years - left_years) / span
            return left_value + weight * (right_value - left_value)
    return None


def prepare_sector_maturity(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={column: normalize_col(column) for column in df.columns})
    if "publication_status" in df.columns:
        publishable = df["publication_status"].isin(["published_estimate", "history_preserving_backfill"])
        filtered = df.loc[publishable].copy()
        if not filtered.empty:
            df = filtered
    date_col = _first_existing(df, ["date", "record_date", "quarter_date"])
    if date_col is None or "sector_key" not in df.columns:
        raise ValueError("Sector maturity file needs date and sector_key columns.")

    out = pd.DataFrame(index=df.index)
    out["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    out["sector_key"] = df["sector_key"].astype(str).str.strip()

    if "coupon_share" in df.columns:
        out["coupon_share"] = pd.to_numeric(df["coupon_share"], errors="coerce")
    elif "bill_share" in df.columns:
        out["coupon_share"] = 1.0 - pd.to_numeric(df["bill_share"], errors="coerce")
    else:
        raise ValueError("Sector maturity file needs coupon_share or bill_share.")

    maturity_col = _first_existing(
        df,
        ["coupon_only_maturity_years", "effective_duration_years", "zero_coupon_equivalent_years"],
    )
    if maturity_col is None:
        raise ValueError(
            "Sector maturity file needs coupon_only_maturity_years, effective_duration_years, or zero_coupon_equivalent_years."
        )
    out["coupon_only_maturity_years"] = pd.to_numeric(df[maturity_col], errors="coerce")
    return out.dropna(subset=["date", "sector_key"]).reset_index(drop=True)


def prepare_sector_panel(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={column: normalize_col(column) for column in df.columns})
    date_col = _first_existing(df, ["date", "record_date", "quarter_date"])
    level_col = _first_existing(df, ["level", "constraint_level"])
    if date_col is None or "sector_key" not in df.columns or level_col is None:
        raise ValueError("Sector panel file needs date, sector_key, and level-style columns.")

    out = pd.DataFrame(index=df.index)
    out["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    out["sector_key"] = df["sector_key"].astype(str).str.strip()
    out["level"] = pd.to_numeric(df[level_col], errors="coerce")
    out["level"] = out["level"] * _panel_level_scale_to_millions(df, level_col)
    return out.dropna(subset=["date", "sector_key"]).reset_index(drop=True)


def _panel_level_scale_to_millions(df: pd.DataFrame, level_col: str) -> float:
    values = pd.to_numeric(df[level_col], errors="coerce").dropna().abs()
    if values.empty:
        return 1.0

    unit_col = _first_existing(df, ["level_units", "level_unit", "units"])
    if unit_col is not None:
        unit_text = " ".join(df[unit_col].dropna().astype(str).str.lower().unique())
        if "million" in unit_text:
            return 1.0
        if "billion" in unit_text:
            return 1_000.0

    has_wamest_full_panel_markers = any(
        column in df.columns
        for column in [
            "method_priority",
            "level_source_provider_used",
            "included_in_public_preview_default",
            "sector_family",
            "transactions",
        ]
    )
    all_holders_total_level = None
    if "sector_key" in df.columns:
        mask = df["sector_key"].astype(str).eq("all_holders_total")
        if mask.any():
            total_values = pd.to_numeric(df.loc[mask, level_col], errors="coerce").dropna().abs()
            if not total_values.empty:
                all_holders_total_level = float(total_values.median())

    if has_wamest_full_panel_markers and (
        (all_holders_total_level is not None and all_holders_total_level < 100_000.0)
        or float(values.median()) < 100_000.0
    ):
        return 1_000.0
    return 1.0


def estimate_quarterly_sector_coupon_interest_proxy(
    sector_maturity: pd.DataFrame,
    sector_panel: pd.DataFrame,
    curves: pd.DataFrame,
    sector_keys: Iterable[str],
    series_name: str,
) -> pd.Series:
    maturity = prepare_sector_maturity(sector_maturity)
    panel = prepare_sector_panel(sector_panel)
    curve_frame = prepare_curve_file(curves)
    curve_points = _curve_points(curve_frame)

    selected = set(str(key).strip() for key in sector_keys)
    merged = maturity.merge(panel, on=["date", "sector_key"], how="inner")
    merged = merged[merged["sector_key"].isin(selected)].copy()
    if merged.empty:
        return pd.Series(dtype="float64", name=series_name)

    rows: list[dict[str, object]] = []
    for date, frame in merged.groupby("date", sort=True):
        curve_row = _latest_curve_row_on_or_before(curve_frame, pd.Timestamp(date))
        if curve_row is None:
            continue
        total = 0.0
        for _, row in frame.iterrows():
            coupon_share = pd.to_numeric(row.get("coupon_share"), errors="coerce")
            maturity_years = pd.to_numeric(row.get("coupon_only_maturity_years"), errors="coerce")
            level = pd.to_numeric(row.get("level"), errors="coerce")
            if pd.isna(coupon_share) or pd.isna(maturity_years) or pd.isna(level):
                continue
            annual_rate = _interpolate_curve_yield(curve_row, float(maturity_years), curve_points)
            if annual_rate is None:
                continue
            total += float(level) * max(float(coupon_share), 0.0) * max(float(annual_rate), 0.0) / 4.0
        rows.append({"date": pd.Timestamp(date).normalize(), "value": total})

    out = pd.DataFrame(rows).sort_values("date")
    return pd.Series(
        pd.to_numeric(out["value"], errors="coerce").values,
        index=pd.to_datetime(out["date"]),
        name=series_name,
        dtype="float64",
    )


def estimate_quarterly_bank_coupon_interest_proxy(
    sector_maturity: pd.DataFrame,
    sector_panel: pd.DataFrame,
    curves: pd.DataFrame,
    sector_keys: Iterable[str] = DEFAULT_BANK_SECTOR_KEYS,
) -> pd.Series:
    return estimate_quarterly_sector_coupon_interest_proxy(
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=curves,
        sector_keys=sector_keys,
        series_name="bank_tsy_coupon_interest_proxy",
    )


def estimate_quarterly_row_coupon_interest_proxy(
    sector_maturity: pd.DataFrame,
    sector_panel: pd.DataFrame,
    curves: pd.DataFrame,
    sector_keys: Iterable[str] = DEFAULT_ROW_SECTOR_KEYS,
) -> pd.Series:
    return estimate_quarterly_sector_coupon_interest_proxy(
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=curves,
        sector_keys=sector_keys,
        series_name="row_tsy_coupon_interest_proxy",
    )


def write_sector_coupon_interest_proxy(
    series: pd.Series,
    out_path: Path | str,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({"date": series.index, "value": series.values})
    frame.to_csv(out_path, index=False)
    return out_path


def write_quarterly_bank_coupon_interest_proxy(
    sector_maturity_path: Path | str,
    sector_panel_path: Path | str,
    curve_path: Path | str,
    out_path: Path | str,
    sector_keys: Iterable[str] = DEFAULT_BANK_SECTOR_KEYS,
) -> Path:
    series = estimate_quarterly_bank_coupon_interest_proxy(
        sector_maturity=read_sector_maturity_table(sector_maturity_path),
        sector_panel=read_sector_panel_table(sector_panel_path),
        curves=read_table(curve_path),
        sector_keys=sector_keys,
    )
    return write_sector_coupon_interest_proxy(series, out_path)


def write_quarterly_row_coupon_interest_proxy(
    sector_maturity_path: Path | str,
    sector_panel_path: Path | str,
    curve_path: Path | str,
    out_path: Path | str,
    sector_keys: Iterable[str] = DEFAULT_ROW_SECTOR_KEYS,
) -> Path:
    series = estimate_quarterly_row_coupon_interest_proxy(
        sector_maturity=read_sector_maturity_table(sector_maturity_path),
        sector_panel=read_sector_panel_table(sector_panel_path),
        curves=read_table(curve_path),
        sector_keys=sector_keys,
    )
    return write_sector_coupon_interest_proxy(series, out_path)


def write_quarterly_tier2_coupon_interest_proxies(
    sector_maturity_path: Path | str,
    sector_panel_path: Path | str,
    curve_path: Path | str,
    bank_out_path: Path | str,
    row_out_path: Path | str,
    bank_sector_keys: Iterable[str] = DEFAULT_BANK_SECTOR_KEYS,
    row_sector_keys: Iterable[str] = DEFAULT_ROW_SECTOR_KEYS,
) -> tuple[Path, Path]:
    bank_written = write_quarterly_bank_coupon_interest_proxy(
        sector_maturity_path=sector_maturity_path,
        sector_panel_path=sector_panel_path,
        curve_path=curve_path,
        out_path=bank_out_path,
        sector_keys=bank_sector_keys,
    )
    row_written = write_quarterly_row_coupon_interest_proxy(
        sector_maturity_path=sector_maturity_path,
        sector_panel_path=sector_panel_path,
        curve_path=curve_path,
        out_path=row_out_path,
        sector_keys=row_sector_keys,
    )
    return bank_written, row_written
