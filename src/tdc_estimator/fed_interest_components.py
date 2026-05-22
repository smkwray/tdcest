from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from .fed_coupon import (
    _payment_dates_in_interval,
    estimate_quarterly_fed_coupon_interest_from_soma_csvs,
    prepare_soma_holdings,
    read_soma_holdings_many,
)
from .utils import ensure_dir


FED_INTEREST_COMPONENT_COLUMNS = [
    "date",
    "fed_tsy_coupon_interest_proxy",
    "fed_tsy_bill_discount_interest_proxy",
    "fed_tsy_frn_interest_proxy",
    "fed_tsy_tips_coupon_interest_proxy",
    "fed_tsy_tips_inflation_comp_proxy",
    "method",
    "source_tier",
    "coverage_note",
]


def _clean_cusip(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).replace("'", "").strip()


def _prepare_bill_security_master(auction_security_master: pd.DataFrame | None) -> pd.DataFrame:
    if auction_security_master is None or auction_security_master.empty:
        return pd.DataFrame(columns=["cusip", "issue_date", "maturity_date", "issue_price_per100"])
    df = auction_security_master.copy()
    df = df.rename(columns={column: str(column).strip().lower() for column in df.columns})
    required = {"cusip", "issue_date", "maturity_date"}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=["cusip", "issue_date", "maturity_date", "issue_price_per100"])
    security_type = df.get("security_type", pd.Series("", index=df.index)).astype(str).str.casefold()
    df = df[security_type.str.contains("bill", na=False)].copy()
    price_cols = [col for col in ["price_per100", "avg_med_price", "high_price", "low_price"] if col in df.columns]
    if not price_cols:
        return pd.DataFrame(columns=["cusip", "issue_date", "maturity_date", "issue_price_per100"])
    df["cusip"] = df["cusip"].map(_clean_cusip)
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce").dt.normalize()
    df["maturity_date"] = pd.to_datetime(df["maturity_date"], errors="coerce").dt.normalize()
    df["issue_price_per100"] = pd.NA
    for price_col in price_cols:
        df["issue_price_per100"] = df["issue_price_per100"].fillna(pd.to_numeric(df[price_col], errors="coerce"))
    df = df.dropna(subset=["cusip", "issue_date", "maturity_date", "issue_price_per100"])
    df = df[df["maturity_date"].gt(df["issue_date"]) & df["issue_price_per100"].between(0.0, 100.0)]
    return df.sort_values(["cusip", "issue_date"]).drop_duplicates("cusip", keep="last").reset_index(drop=True)


def _quarter_segments(start: pd.Timestamp, end_exclusive: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    start = pd.Timestamp(start).normalize()
    end_exclusive = pd.Timestamp(end_exclusive).normalize()
    segments: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    current = start
    while current < end_exclusive:
        quarter_end_exclusive = current.to_period("Q").end_time.normalize() + pd.Timedelta(days=1)
        segment_end = min(quarter_end_exclusive, end_exclusive)
        segments.append((current, segment_end))
        current = segment_end
    return segments


def estimate_quarterly_fed_bill_discount_from_soma_snapshots(
    holdings: pd.DataFrame,
    auction_security_master: pd.DataFrame | None,
) -> pd.Series:
    bills = prepare_soma_holdings(holdings)
    bills = bills[bills["instrument_type"].eq("bill")].copy()
    master = _prepare_bill_security_master(auction_security_master)
    if bills.empty or master.empty:
        return pd.Series(dtype="float64", name="fed_tsy_bill_discount_interest_proxy")

    bills["cusip"] = bills["cusip"].map(_clean_cusip)
    merged = bills.merge(master, on="cusip", suffixes=("", "_master"), how="inner")
    if merged.empty:
        return pd.Series(dtype="float64", name="fed_tsy_bill_discount_interest_proxy")

    values = pd.to_numeric(merged["par_value"], errors="coerce").dropna().abs()
    unit_scale = 1_000_000.0 if not values.empty and float(values.median()) >= 1_000_000.0 else 1.0
    snapshot_dates = sorted(pd.to_datetime(merged["as_of_date"]).dt.normalize().unique())
    totals: dict[pd.Timestamp, float] = {}

    for idx, snapshot_date in enumerate(snapshot_dates):
        interval_start = pd.Timestamp(snapshot_date).normalize()
        if idx == len(snapshot_dates) - 1:
            interval_end_exclusive = interval_start.to_period("Q").end_time.normalize() + pd.Timedelta(days=1)
        else:
            interval_end_exclusive = pd.Timestamp(snapshot_dates[idx + 1]).normalize()
        snapshot = merged[merged["as_of_date"].eq(interval_start)]
        for _, row in snapshot.iterrows():
            issue_date = pd.Timestamp(row["issue_date"]).normalize()
            maturity_date = pd.Timestamp(row["maturity_date_master"]).normalize()
            accrual_start = max(interval_start, issue_date)
            accrual_end = min(interval_end_exclusive, maturity_date)
            if accrual_start >= accrual_end:
                continue
            term_days = max((maturity_date - issue_date).days, 1)
            discount_total = float(row["par_value"]) * max(100.0 - float(row["issue_price_per100"]), 0.0) / 100.0
            daily_accrual = discount_total / term_days / unit_scale
            for segment_start, segment_end in _quarter_segments(accrual_start, accrual_end):
                days = (segment_end - segment_start).days
                quarter_end = segment_start.to_period("Q").end_time.normalize()
                totals[quarter_end] = totals.get(quarter_end, 0.0) + daily_accrual * days

    out = pd.Series(totals, name="fed_tsy_bill_discount_interest_proxy").sort_index()
    return out.astype("float64")


def estimate_quarterly_fed_tips_coupon_from_soma_snapshots(holdings: pd.DataFrame) -> pd.Series:
    tips = prepare_soma_holdings(holdings)
    tips = tips[tips["instrument_type"].eq("tips")].copy()
    if tips.empty:
        return pd.Series(dtype="float64", name="fed_tsy_tips_coupon_interest_proxy")

    values = pd.to_numeric(tips["par_value"], errors="coerce").dropna().abs()
    unit_scale = 1_000_000.0 if not values.empty and float(values.median()) >= 1_000_000.0 else 1.0
    snapshot_dates = sorted(pd.to_datetime(tips["as_of_date"]).dt.normalize().unique())
    totals: dict[pd.Timestamp, float] = {}

    for idx, snapshot_date in enumerate(snapshot_dates):
        interval_start = pd.Timestamp(snapshot_date).normalize()
        is_last = idx == len(snapshot_dates) - 1
        if is_last:
            interval_end = interval_start.to_period("Q").end_time.normalize()
        else:
            interval_end = pd.Timestamp(snapshot_dates[idx + 1]).normalize()
        snapshot = tips[tips["as_of_date"].eq(interval_start)]
        for _, row in snapshot.iterrows():
            par = pd.to_numeric(pd.Series([row.get("par_value")]), errors="coerce").iloc[0]
            inflation = pd.to_numeric(pd.Series([row.get("inflation_compensation")]), errors="coerce").iloc[0]
            coupon_rate = pd.to_numeric(pd.Series([row.get("coupon_rate_pct")]), errors="coerce").iloc[0]
            if pd.isna(par) or pd.isna(coupon_rate) or float(coupon_rate) == 0.0:
                continue
            inflation_value = 0.0 if pd.isna(inflation) else float(inflation)
            adjusted_principal = float(par) + inflation_value
            coupon_payment = adjusted_principal * float(coupon_rate) / 100.0 / 2.0 / unit_scale
            for payment_date in _payment_dates_in_interval(
                maturity_date=pd.Timestamp(row["maturity_date"]),
                instrument_type="tips",
                interval_start=interval_start,
                interval_end=interval_end,
                include_end=is_last,
            ):
                quarter_end = payment_date.to_period("Q").end_time.normalize()
                totals[quarter_end] = totals.get(quarter_end, 0.0) + coupon_payment

    out = pd.Series(totals, name="fed_tsy_tips_coupon_interest_proxy").sort_index()
    return out.astype("float64")


def _prepare_frn_daily_indexes(frn_daily_indexes: pd.DataFrame | None) -> pd.DataFrame:
    if frn_daily_indexes is None or frn_daily_indexes.empty:
        return pd.DataFrame(columns=["cusip", "accrual_date", "daily_accrued_int_per100"])
    df = frn_daily_indexes.copy()
    df = df.rename(columns={column: str(column).strip().lower() for column in df.columns})
    required = {"cusip", "start_of_accrual_period", "daily_accrued_int_per100"}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=["cusip", "accrual_date", "daily_accrued_int_per100"])
    out = pd.DataFrame(
        {
            "cusip": df["cusip"].map(_clean_cusip),
            "accrual_date": pd.to_datetime(df["start_of_accrual_period"], errors="coerce").dt.normalize(),
            "daily_accrued_int_per100": pd.to_numeric(df["daily_accrued_int_per100"], errors="coerce"),
        }
    )
    return out.dropna(subset=["cusip", "accrual_date", "daily_accrued_int_per100"]).reset_index(drop=True)


def estimate_quarterly_fed_frn_interest_from_soma_snapshots(
    holdings: pd.DataFrame,
    frn_daily_indexes: pd.DataFrame | None,
) -> pd.Series:
    frn = prepare_soma_holdings(holdings)
    frn = frn[frn["instrument_type"].eq("frn")].copy()
    indexes = _prepare_frn_daily_indexes(frn_daily_indexes)
    if frn.empty or indexes.empty:
        return pd.Series(dtype="float64", name="fed_tsy_frn_interest_proxy")

    frn["cusip"] = frn["cusip"].map(_clean_cusip)
    values = pd.to_numeric(frn["par_value"], errors="coerce").dropna().abs()
    unit_scale = 1_000_000.0 if not values.empty and float(values.median()) >= 1_000_000.0 else 1.0
    snapshot_dates = sorted(pd.to_datetime(frn["as_of_date"]).dt.normalize().unique())
    totals: dict[pd.Timestamp, float] = {}

    for idx, snapshot_date in enumerate(snapshot_dates):
        interval_start = pd.Timestamp(snapshot_date).normalize()
        if idx == len(snapshot_dates) - 1:
            interval_end = interval_start.to_period("Q").end_time.normalize() + pd.Timedelta(days=1)
        else:
            interval_end = pd.Timestamp(snapshot_dates[idx + 1]).normalize()
        snapshot = frn[frn["as_of_date"].eq(interval_start)]
        if snapshot.empty:
            continue
        matched = snapshot.loc[:, ["cusip", "par_value"]].merge(indexes, on="cusip", how="inner")
        matched = matched[matched["accrual_date"].ge(interval_start) & matched["accrual_date"].lt(interval_end)]
        if matched.empty:
            continue
        matched["interest_mil"] = (
            pd.to_numeric(matched["par_value"], errors="coerce")
            / 100.0
            * pd.to_numeric(matched["daily_accrued_int_per100"], errors="coerce")
            / unit_scale
        )
        for quarter_end, value in matched.groupby(matched["accrual_date"].dt.to_period("Q").dt.end_time.dt.normalize())[
            "interest_mil"
        ].sum().items():
            quarter = pd.Timestamp(quarter_end).normalize()
            totals[quarter] = totals.get(quarter, 0.0) + float(value)

    out = pd.Series(totals, name="fed_tsy_frn_interest_proxy").sort_index()
    return out.astype("float64")


def estimate_quarterly_fed_tips_inflation_comp_from_soma_snapshots(holdings: pd.DataFrame) -> pd.Series:
    tips = prepare_soma_holdings(holdings)
    tips = tips[tips["instrument_type"].eq("tips")].copy()
    if tips.empty or "inflation_compensation" not in tips.columns:
        return pd.Series(dtype="float64", name="fed_tsy_tips_inflation_comp_proxy")

    values = pd.to_numeric(tips["inflation_compensation"], errors="coerce").dropna().abs()
    unit_scale = 1_000_000.0 if not values.empty and float(values.median()) >= 1_000_000.0 else 1.0
    tips["inflation_compensation"] = pd.to_numeric(tips["inflation_compensation"], errors="coerce") / unit_scale
    totals = tips.groupby("as_of_date")["inflation_compensation"].sum(min_count=1).sort_index()
    changes = totals.diff()
    if changes.empty:
        return pd.Series(dtype="float64", name="fed_tsy_tips_inflation_comp_proxy")
    changes.index = pd.to_datetime(changes.index).to_period("Q").end_time.normalize()
    out = changes.groupby(changes.index).sum(min_count=1).dropna().sort_index()
    out.name = "fed_tsy_tips_inflation_comp_proxy"
    return out.astype("float64")


def build_fed_interest_components_from_soma_csvs(
    soma_paths: Sequence[Path | str],
    auction_security_master: pd.DataFrame | None = None,
    frn_daily_indexes: pd.DataFrame | None = None,
) -> pd.DataFrame:
    coupon = estimate_quarterly_fed_coupon_interest_from_soma_csvs(soma_paths)
    holdings = read_soma_holdings_many(soma_paths)
    bill_discount = estimate_quarterly_fed_bill_discount_from_soma_snapshots(holdings, auction_security_master)
    tips_coupon = estimate_quarterly_fed_tips_coupon_from_soma_snapshots(holdings)
    frn_interest = estimate_quarterly_fed_frn_interest_from_soma_snapshots(holdings, frn_daily_indexes)
    tips_inflation = estimate_quarterly_fed_tips_inflation_comp_from_soma_snapshots(holdings)

    if coupon.empty:
        return pd.DataFrame(columns=FED_INTEREST_COMPONENT_COLUMNS)

    out = coupon.rename("fed_tsy_coupon_interest_proxy").reset_index()
    out = out.rename(columns={"index": "date"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["fed_tsy_bill_discount_interest_proxy"] = pd.to_numeric(
        bill_discount.reindex(pd.to_datetime(out["date"]).dt.normalize()).to_numpy(),
        errors="coerce",
    )
    out["fed_tsy_frn_interest_proxy"] = pd.to_numeric(
        frn_interest.reindex(pd.to_datetime(out["date"]).dt.normalize()).to_numpy(),
        errors="coerce",
    )
    out["fed_tsy_tips_coupon_interest_proxy"] = pd.to_numeric(
        tips_coupon.reindex(pd.to_datetime(out["date"]).dt.normalize()).to_numpy(),
        errors="coerce",
    )
    out["fed_tsy_tips_inflation_comp_proxy"] = pd.to_numeric(
        tips_inflation.reindex(pd.to_datetime(out["date"]).dt.normalize()).to_numpy(),
        errors="coerce",
    )
    out["method"] = "soma_coupon_bill_tips_frn_component_pass"
    out["source_tier"] = "coupon_bill_tips_frn_present_tips_comp_stock_change_proxy"
    out["coverage_note"] = (
        "Coupon component reuses the existing SOMA coupon schedule logic; bill discount uses matched "
        "auction issue price, issue date, maturity date, and snapshot-held par. TIPS coupon uses "
        "SOMA par plus inflation compensation where available. FRN interest uses FiscalData FRN daily "
        "accrued interest per $100 when supplied. TIPS inflation-compensation is a stock-change proxy "
        "and remains nondefault."
    )
    out["soma_source_rows"] = len(holdings)

    return out.loc[:, [*FED_INTEREST_COMPONENT_COLUMNS, "soma_source_rows"]].sort_values("date").reset_index(drop=True)


def summarize_fed_interest_components(components: pd.DataFrame) -> str:
    lines = ["# Fed Treasury Interest Components", ""]
    if components.empty:
        return "\n".join(lines + ["No Fed component rows were available."]) + "\n"

    df = components.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    first = df["date"].min().date().isoformat()
    latest = df["date"].max().date().isoformat()
    latest_row = df.sort_values("date").iloc[-1]
    coupon = latest_row.get("fed_tsy_coupon_interest_proxy")
    bills = latest_row.get("fed_tsy_bill_discount_interest_proxy")
    tips_coupon = latest_row.get("fed_tsy_tips_coupon_interest_proxy")
    frn = latest_row.get("fed_tsy_frn_interest_proxy")
    tips_inflation = latest_row.get("fed_tsy_tips_inflation_comp_proxy")
    coupon_text = "NA" if pd.isna(coupon) else f"${float(coupon):,.0f} million"
    bill_text = "NA" if pd.isna(bills) else f"${float(bills):,.0f} million"
    tips_coupon_text = "NA" if pd.isna(tips_coupon) else f"${float(tips_coupon):,.0f} million"
    frn_text = "NA" if pd.isna(frn) else f"${float(frn):,.0f} million"
    tips_inflation_text = "NA" if pd.isna(tips_inflation) else f"${float(tips_inflation):,.0f} million"
    lines.extend(
        [
            f"Coverage runs from {first} through {latest}.",
            "",
            f"Latest quarter ({latest}) SOMA coupon component is {coupon_text}.",
            f"Latest quarter ({latest}) SOMA bill-discount component is {bill_text}.",
            f"Latest quarter ({latest}) SOMA TIPS coupon component is {tips_coupon_text}.",
            f"Latest quarter ({latest}) SOMA FRN interest component is {frn_text}.",
            f"Latest quarter ({latest}) SOMA TIPS inflation-compensation proxy is {tips_inflation_text}.",
            "",
            "TIPS inflation-compensation is a nondefault stock-change proxy, not coupon cash.",
            "It is intentionally not filled by the WAMEST/H.15 maturity proxy path.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_fed_interest_components_from_soma_csvs(
    *,
    soma_paths: Sequence[Path | str],
    out_csv_path: Path | str,
    out_markdown_path: Path | str | None = None,
    auction_security_master_path: Path | str | None = None,
    frn_daily_indexes_path: Path | str | None = None,
) -> tuple[Path, Path | None]:
    auction_security_master = (
        pd.read_csv(auction_security_master_path, low_memory=False)
        if auction_security_master_path is not None and Path(auction_security_master_path).exists()
        else None
    )
    frn_daily_indexes = (
        pd.read_csv(frn_daily_indexes_path, low_memory=False)
        if frn_daily_indexes_path is not None and Path(frn_daily_indexes_path).exists()
        else None
    )
    components = build_fed_interest_components_from_soma_csvs(
        soma_paths,
        auction_security_master,
        frn_daily_indexes,
    )
    csv_path = Path(out_csv_path)
    ensure_dir(csv_path.parent)
    components.to_csv(csv_path, index=False)

    markdown_path = Path(out_markdown_path) if out_markdown_path is not None else None
    if markdown_path is not None:
        ensure_dir(markdown_path.parent)
        markdown_path.write_text(summarize_fed_interest_components(components), encoding="utf-8")
    return csv_path, markdown_path
