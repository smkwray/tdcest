from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

DEFAULT_WAMEST_SOMA_CANDIDATES = [
    Path("data/external/normalized/soma_holdings_fed.csv"),
    Path("tests/fixtures/nyfed_soma_tsy_2026-03-18.csv"),
    Path("data/examples/toy_soma_holdings.csv"),
]


def normalize_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def read_soma_holdings(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df.rename(columns={column: normalize_col(column) for column in df.columns})


def read_soma_holdings_many(paths: Sequence[Path | str]) -> pd.DataFrame:
    frames = [read_soma_holdings(path) for path in paths]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def resolve_wamest_soma_path(
    wamest_root: Path | str,
    soma_file: Path | str | None = None,
) -> Path:
    if soma_file is not None:
        return Path(soma_file)
    root = Path(wamest_root)
    for candidate in DEFAULT_WAMEST_SOMA_CANDIDATES:
        path = root / candidate
        if path.exists():
            return path
    joined = ", ".join(str(candidate) for candidate in DEFAULT_WAMEST_SOMA_CANDIDATES)
    raise FileNotFoundError(f"No SOMA holdings artifact found under {root}. Tried: {joined}")


def _first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _classify_instrument(row: pd.Series) -> str:
    text = str(row.get("security_text", "")).lower()
    if "agency" in text or "mbs" in text or "mortgage" in text:
        return "other"
    if "inflation" in text or "tips" in text:
        return "tips"
    if "floating" in text or "frn" in text:
        return "frn"
    if "bill" in text:
        return "bill"
    if any(token in text for token in ["note", "bond", "treasury"]):
        return "coupon"
    coupon_rate = row.get("coupon_rate_pct")
    if pd.notna(coupon_rate) and float(coupon_rate) > 0:
        return "coupon"
    return "other"


def prepare_soma_holdings(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={column: normalize_col(column) for column in df.columns})
    date_col = _first_existing(df, ["as_of_date", "date", "record_date", "report_date"])
    maturity_col = _first_existing(df, ["maturity_date", "maturity", "maturitydate"])
    par_col = _first_existing(
        df,
        ["par_value", "current_par_amount", "paramount", "par", "current_face_amount", "current_face_value"],
    )
    coupon_col = _first_existing(df, ["coupon", "coupon_pct", "coupon_rate", "coupon_percent"])
    type_col = _first_existing(df, ["security_type", "security_type_description", "security", "asset_type"])
    desc_col = _first_existing(df, ["description", "security_description", "security_desc"])

    if date_col is None or maturity_col is None or par_col is None:
        raise ValueError("SOMA holdings file needs as-of date, maturity date, and par-value style columns.")

    df["as_of_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    df["maturity_date"] = pd.to_datetime(df[maturity_col], errors="coerce").dt.normalize()
    df["par_value"] = pd.to_numeric(df[par_col], errors="coerce")
    if coupon_col is not None:
        df["coupon_rate_pct"] = pd.to_numeric(df[coupon_col], errors="coerce").fillna(0.0)
    else:
        df["coupon_rate_pct"] = 0.0
    inflation_col = _first_existing(df, ["inflation_compensation", "inflation_comp", "inflation_accretion"])
    if inflation_col is not None:
        df["inflation_compensation"] = pd.to_numeric(df[inflation_col], errors="coerce")
    else:
        df["inflation_compensation"] = pd.NA

    df["security_text"] = ""
    if type_col is not None:
        df["security_text"] = df[type_col].fillna("").astype(str)
    if desc_col is not None:
        df["security_text"] = (
            df["security_text"].fillna("").astype(str) + " " + df[desc_col].fillna("").astype(str)
        ).str.strip()

    if "cusip" in df.columns:
        df["cusip"] = df["cusip"].astype(str).str.replace("'", "", regex=False).str.strip()
    else:
        df["cusip"] = ""

    df = df.dropna(subset=["as_of_date", "maturity_date", "par_value"]).copy()
    df["instrument_type"] = df.apply(_classify_instrument, axis=1)
    df = df[df["instrument_type"].isin(["bill", "coupon", "tips", "frn"])].copy()
    return df[
        [
            "as_of_date",
            "maturity_date",
            "par_value",
            "coupon_rate_pct",
            "instrument_type",
            "cusip",
            "security_text",
            "inflation_compensation",
        ]
    ].reset_index(drop=True)


def _schedule_step_months(instrument_type: str) -> int | None:
    if instrument_type == "bill":
        return None
    if instrument_type == "frn":
        return 3
    return 6


def _payment_dates_in_window(
    maturity_date: pd.Timestamp,
    instrument_type: str,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> list[pd.Timestamp]:
    step_months = _schedule_step_months(instrument_type)
    if step_months is None:
        return []

    current = pd.Timestamp(maturity_date).normalize()
    dates: list[pd.Timestamp] = []
    while current >= window_start:
        if current <= window_end:
            dates.append(current)
        current = (current - pd.DateOffset(months=step_months)).normalize()
    return dates


def _payment_amount(row: pd.Series) -> float:
    step_months = _schedule_step_months(str(row["instrument_type"]))
    if step_months is None:
        return 0.0
    periods_per_year = 12 / step_months
    return float(row["par_value"]) * float(row["coupon_rate_pct"]) / 100.0 / periods_per_year


def _par_value_scale_to_millions(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().abs()
    if values.empty:
        return 1.0
    return 1_000_000.0 if float(values.median()) >= 1_000_000.0 else 1.0


def _latest_snapshot_on_or_before(snapshot_dates: Iterable[pd.Timestamp], target: pd.Timestamp) -> pd.Timestamp | None:
    eligible = [date for date in snapshot_dates if date <= target]
    if not eligible:
        return None
    return max(eligible)


def _payment_dates_in_interval(
    maturity_date: pd.Timestamp,
    instrument_type: str,
    interval_start: pd.Timestamp,
    interval_end: pd.Timestamp,
    include_end: bool,
) -> list[pd.Timestamp]:
    step_months = _schedule_step_months(instrument_type)
    if step_months is None:
        return []

    current = pd.Timestamp(maturity_date).normalize()
    dates: list[pd.Timestamp] = []
    while current >= interval_start:
        in_upper_bound = current <= interval_end if include_end else current < interval_end
        if in_upper_bound:
            dates.append(current)
        current = (current - pd.DateOffset(months=step_months)).normalize()
    return dates


def estimate_quarterly_fed_coupon_interest_from_soma_snapshots(holdings: pd.DataFrame) -> pd.Series:
    holdings = prepare_soma_holdings(holdings)
    if holdings.empty:
        return pd.Series(dtype="float64", name="fed_tsy_coupon_interest_proxy")

    unit_scale = _par_value_scale_to_millions(holdings["par_value"])
    snapshot_dates = sorted(pd.to_datetime(holdings["as_of_date"]).dt.normalize().unique())
    quarter_totals: dict[pd.Timestamp, float] = {}

    for idx, snapshot_date in enumerate(snapshot_dates):
        interval_start = pd.Timestamp(snapshot_date).normalize()
        is_last = idx == len(snapshot_dates) - 1
        if is_last:
            interval_end = interval_start.to_period("Q").end_time.normalize()
        else:
            interval_end = pd.Timestamp(snapshot_dates[idx + 1]).normalize()

        snapshot = holdings[holdings["as_of_date"] == interval_start]
        if snapshot.empty:
            continue

        for _, row in snapshot.iterrows():
            amount = _payment_amount(row) / unit_scale
            if amount == 0.0:
                continue
            for payment_date in _payment_dates_in_interval(
                maturity_date=pd.Timestamp(row["maturity_date"]),
                instrument_type=str(row["instrument_type"]),
                interval_start=interval_start,
                interval_end=interval_end,
                include_end=is_last,
            ):
                quarter_end = payment_date.to_period("Q").end_time.normalize()
                quarter_totals[quarter_end] = quarter_totals.get(quarter_end, 0.0) + amount

    if not quarter_totals:
        return pd.Series(dtype="float64", name="fed_tsy_coupon_interest_proxy")

    out = pd.DataFrame(
        [
            {"date": quarter_end, "fed_tsy_coupon_interest_proxy": total}
            for quarter_end, total in sorted(quarter_totals.items())
        ]
    ).sort_values("date").reset_index(drop=True)
    return pd.Series(
        pd.to_numeric(out["fed_tsy_coupon_interest_proxy"], errors="coerce").values,
        index=pd.to_datetime(out["date"]),
        name="fed_tsy_coupon_interest_proxy",
        dtype="float64",
    )


def estimate_quarterly_fed_coupon_interest_from_soma_csv(path: Path | str) -> pd.Series:
    return estimate_quarterly_fed_coupon_interest_from_soma_snapshots(read_soma_holdings(path))


def estimate_quarterly_fed_coupon_interest_from_soma_csvs(paths: Sequence[Path | str]) -> pd.Series:
    return estimate_quarterly_fed_coupon_interest_from_soma_snapshots(read_soma_holdings_many(paths))


def _first_full_soma_coupon_quarter(holdings: pd.DataFrame) -> pd.Timestamp | None:
    prepared = prepare_soma_holdings(holdings)
    if prepared.empty:
        return None
    first_snapshot = pd.to_datetime(prepared["as_of_date"], errors="coerce").dropna().min().normalize()
    quarter = first_snapshot.to_period("Q")
    quarter_start = quarter.start_time.normalize()
    quarter_end = quarter.end_time.normalize()
    if first_snapshot <= quarter_start:
        return quarter_end
    return (quarter_end + pd.offsets.QuarterEnd()).normalize()


def estimate_quarterly_fed_coupon_interest_backcast_from_wamest(
    *,
    sector_maturity: pd.DataFrame,
    sector_panel: pd.DataFrame,
    curves: pd.DataFrame,
    before_date: pd.Timestamp,
    start_date: pd.Timestamp | str | None = None,
) -> pd.Series:
    """Infer pre-SOMA Fed Treasury coupon interest from WAMEST/H.15 coupon intensity."""

    from .sector_coupon import (  # Local import avoids a module-level cycle.
        _curve_points,
        _interpolate_curve_yield,
        _latest_curve_row_on_or_before,
        prepare_curve_file,
        prepare_sector_maturity,
        prepare_sector_panel,
    )

    maturity = prepare_sector_maturity(sector_maturity)
    panel = prepare_sector_panel(sector_panel)
    curve_frame = prepare_curve_file(curves)
    curve_points = _curve_points(curve_frame)

    fed_maturity = (
        maturity.loc[maturity["sector_key"].eq("fed"), ["date", "coupon_share", "coupon_only_maturity_years"]]
        .sort_values("date")
        .copy()
    )
    fed_panel = panel.loc[panel["sector_key"].eq("fed"), ["date", "level"]].sort_values("date").copy()
    if fed_maturity.empty or fed_panel.empty:
        return pd.Series(dtype="float64", name="fed_tsy_coupon_interest_proxy")

    merged = fed_panel.merge(fed_maturity, on="date", how="left").sort_values("date")
    merged[["coupon_share", "coupon_only_maturity_years"]] = merged[
        ["coupon_share", "coupon_only_maturity_years"]
    ].ffill()
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.loc[merged["date"].notna() & merged["date"].lt(pd.Timestamp(before_date))]
    if start_date is not None:
        merged = merged.loc[merged["date"].ge(pd.Timestamp(start_date))]

    rows: list[dict[str, object]] = []
    for _, row in merged.iterrows():
        date = pd.Timestamp(row["date"]).normalize()
        level = pd.to_numeric(row.get("level"), errors="coerce")
        coupon_share = pd.to_numeric(row.get("coupon_share"), errors="coerce")
        maturity_years = pd.to_numeric(row.get("coupon_only_maturity_years"), errors="coerce")
        if pd.isna(level) or pd.isna(coupon_share) or pd.isna(maturity_years):
            continue
        curve_row = _latest_curve_row_on_or_before(curve_frame, date)
        if curve_row is None:
            continue
        annual_rate = _interpolate_curve_yield(curve_row, float(maturity_years), curve_points)
        if annual_rate is None:
            continue
        rows.append(
            {
                "date": date,
                "value": float(level) * max(float(coupon_share), 0.0) * max(float(annual_rate), 0.0) / 4.0,
            }
        )

    if not rows:
        return pd.Series(dtype="float64", name="fed_tsy_coupon_interest_proxy")
    out = pd.DataFrame(rows).drop_duplicates(subset=["date"], keep="last").sort_values("date")
    return pd.Series(
        pd.to_numeric(out["value"], errors="coerce").values,
        index=pd.to_datetime(out["date"]),
        name="fed_tsy_coupon_interest_proxy",
        dtype="float64",
    )


def estimate_quarterly_fed_coupon_interest_with_wamest_backcast(
    *,
    soma_holdings: pd.DataFrame,
    sector_maturity: pd.DataFrame,
    sector_panel: pd.DataFrame,
    curves: pd.DataFrame,
    start_date: pd.Timestamp | str | None = "2002-03-31",
) -> pd.Series:
    exact = estimate_quarterly_fed_coupon_interest_from_soma_snapshots(soma_holdings)
    first_full_quarter = _first_full_soma_coupon_quarter(soma_holdings)
    if first_full_quarter is None:
        return exact

    backcast = estimate_quarterly_fed_coupon_interest_backcast_from_wamest(
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=curves,
        before_date=first_full_quarter,
        start_date=start_date,
    )
    exact_full = (
        exact.loc[pd.to_datetime(exact.index) >= first_full_quarter]
        if not exact.empty
        else pd.Series(dtype="float64", name="fed_tsy_coupon_interest_proxy")
    )
    return exact_full.combine_first(backcast).sort_index().rename("fed_tsy_coupon_interest_proxy")


def write_quarterly_fed_coupon_interest_proxy_with_wamest_backcast(
    *,
    soma_paths: Sequence[Path | str],
    sector_maturity_path: Path | str,
    sector_panel_path: Path | str,
    curve_path: Path | str,
    out_path: Path | str,
    start_date: pd.Timestamp | str | None = "2002-03-31",
) -> Path:
    from .sector_coupon import read_sector_maturity_table, read_sector_panel_table, read_table

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    series = estimate_quarterly_fed_coupon_interest_with_wamest_backcast(
        soma_holdings=read_soma_holdings_many(soma_paths),
        sector_maturity=read_sector_maturity_table(sector_maturity_path),
        sector_panel=read_sector_panel_table(sector_panel_path),
        curves=read_table(curve_path),
        start_date=start_date,
    )
    frame = pd.DataFrame({"date": series.index, "value": series.values})
    frame.to_csv(out_path, index=False)
    return out_path


def write_quarterly_fed_coupon_interest_proxy_from_soma_csv(
    soma_path: Path | str,
    out_path: Path | str,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    series = estimate_quarterly_fed_coupon_interest_from_soma_csv(soma_path)
    frame = pd.DataFrame({"date": series.index, "value": series.values})
    frame.to_csv(out_path, index=False)
    return out_path


def write_quarterly_fed_coupon_interest_proxy_from_soma_csvs(
    soma_paths: Sequence[Path | str],
    out_path: Path | str,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    series = estimate_quarterly_fed_coupon_interest_from_soma_csvs(soma_paths)
    frame = pd.DataFrame({"date": series.index, "value": series.values})
    frame.to_csv(out_path, index=False)
    return out_path
