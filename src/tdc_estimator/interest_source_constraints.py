from __future__ import annotations

from pathlib import Path

import pandas as pd


BANK_SECTOR_KEY = "bank_broad_private_depositories_marketable_proxy"
CU_SECTOR_KEY = "credit_unions_marketable_proxy"
MMF_SECTOR_KEY = "money_market_funds"
ROW_SECTOR_KEY = "foreigners_total"


def _safe_read(path: Path | str | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    table_path = Path(path)
    if not table_path.exists():
        return pd.DataFrame()
    return pd.read_csv(table_path)


def _resolve_pointer_path(path: Path | str | None) -> Path | None:
    if path is None:
        return None
    table_path = Path(path)
    if not table_path.exists():
        return table_path
    try:
        text = table_path.read_text(encoding="utf-8", errors="replace").strip()
    except UnicodeDecodeError:
        return table_path
    if "\n" not in text and text.startswith("/") and Path(text).exists():
        return Path(text)
    return table_path


def _read_tic_frame(path: Path | str | None) -> pd.DataFrame:
    table_path = _resolve_pointer_path(path)
    if table_path is None or not table_path.exists():
        return pd.DataFrame()
    try:
        raw = pd.read_csv(table_path, sep="\t", skiprows=8, dtype=str, low_memory=False)
        if {"country_code", "date", "for_treas_pos", "for_lt_treas_pos", "for_st_treas_pos"}.issubset(raw.columns):
            return raw
    except Exception:
        pass
    return pd.read_csv(table_path)


def _date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _ratio(numerator: float, denominator: float) -> float | pd.NA:
    if denominator == 0 or pd.isna(denominator):
        return pd.NA
    return float(numerator) / float(denominator)


def _quarterly_sums(frame: pd.DataFrame, date_col: str, value_cols: list[str]) -> pd.DataFrame:
    if frame.empty or date_col not in frame.columns:
        return pd.DataFrame()
    df = frame.copy()
    df["date"] = _date(df[date_col])
    df = df.loc[df["date"].notna()].copy()
    if df.empty:
        return pd.DataFrame()
    for column in value_cols:
        df[column] = _num(df, column)
    return df.groupby("date", as_index=False)[value_cols].sum(min_count=1).sort_values("date")


def _regulatory_constraint_rows(frame: pd.DataFrame, *, sector_key: str, source_family: str, source_path: Path | str) -> list[dict[str, object]]:
    grouped = _quarterly_sums(
        frame,
        "date",
        [
            "total_treasuries_amortized_cost",
            "total_treasuries_fair_value",
            "total_treasuries_level_proxy",
            "treasury_ladder_total",
            "treasury_bucket_3m_or_less",
            "treasury_bucket_3_12m",
            "treasury_bucket_1_3y",
            "treasury_bucket_3_5y",
            "treasury_bucket_5_15y",
            "treasury_bucket_over_15y",
        ],
    )
    if grouped.empty:
        return [{
            "sector_key": sector_key,
            "source_family": source_family,
            "component_key": "coupon_accrual,bill_amortized_discount",
            "constraint_status": "missing_source",
            "source_path": str(source_path),
        }]
    rows: list[dict[str, object]] = []
    for _, latest in grouped.iterrows():
        level = float(latest.get("total_treasuries_amortized_cost", 0.0))
        if level == 0:
            level = float(latest.get("total_treasuries_level_proxy", 0.0))
        # FFIEC Call Report money fields are in thousands of dollars in this
        # normalized artifact. The NCUA extract stores dollar amounts.
        mil_divisor = 1_000_000.0 if source_family == "NCUA_CALL_REPORT" else 1000.0
        ladder = float(latest.get("treasury_ladder_total", 0.0))
        bill_proxy = float(latest.get("treasury_bucket_3m_or_less", 0.0))
        short_proxy = bill_proxy + float(latest.get("treasury_bucket_3_12m", 0.0))
        bill_share = _ratio(bill_proxy, ladder)
        fallback_split = source_family == "NCUA_CALL_REPORT" and pd.isna(bill_share)
        rows.append(
            {
                "date": latest["date"],
                "sector_key": sector_key,
                "source_family": source_family,
                "component_key": "coupon_accrual,bill_amortized_discount",
                "constraint_status": (
                    "usable_level_constraint_wamest_split_fallback"
                    if fallback_split
                    else "usable_constraint"
                ),
                "level_mil": level / mil_divisor,
                "fair_value_mil": float(latest.get("total_treasuries_fair_value", 0.0)) / mil_divisor,
                "bill_weight_proxy": bill_share,
                "short_weight_proxy_le_1y": _ratio(short_proxy, ladder),
                "coupon_weight_proxy": pd.NA if pd.isna(bill_share) else 1.0 - float(bill_share),
                "fallback_split_accepted": fallback_split,
                "constraint_basis": (
                    "ncua_treasury_level_only_wamest_interest_contract_split_fallback"
                    if fallback_split
                    else "aggregate_call_report_treasury_level_plus_maturity_bucket_proxy"
                ),
                "source_path": str(source_path),
            }
        )
    return rows


def _mmf_constraint_rows(frame: pd.DataFrame, *, source_path: Path | str) -> list[dict[str, object]]:
    grouped = _quarterly_sums(
        frame,
        "date",
        ["treasury_total", "treasury_bills", "fed_rrp", "nav"],
    )
    if grouped.empty:
        return [{
            "sector_key": MMF_SECTOR_KEY,
            "source_family": "SEC_NMFP_OR_OFR_MMF",
            "component_key": "coupon_accrual,bill_amortized_discount",
            "constraint_status": "missing_source",
            "source_path": str(source_path),
        }]
    rows: list[dict[str, object]] = []
    for _, latest in grouped.iterrows():
        treasury_total = float(latest.get("treasury_total", 0.0))
        treasury_bills = float(latest.get("treasury_bills", 0.0))
        bill_share = _ratio(treasury_bills, treasury_total)
        rows.append(
            {
                "date": latest["date"],
                "sector_key": MMF_SECTOR_KEY,
                "source_family": "SEC_NMFP_OR_OFR_MMF",
                "component_key": "coupon_accrual,bill_amortized_discount",
                "constraint_status": "usable_denominator_constraint",
                "level_mil": treasury_total,
                "bill_weight_proxy": bill_share,
                "coupon_weight_proxy": pd.NA if pd.isna(bill_share) else 1.0 - float(bill_share),
                "constraint_basis": "fund_month_treasury_total_and_treasury_bill_holdings",
                "source_path": str(source_path),
            }
        )
    return rows


def _row_tic_constraint_rows(frame: pd.DataFrame, *, source_path: Path | str) -> list[dict[str, object]]:
    if {"country_code", "date", "for_treas_pos", "for_lt_treas_pos", "for_st_treas_pos"}.issubset(frame.columns):
        tic = frame.loc[frame["country_code"].astype(str).str.strip().eq("99996")].copy()
        tic["date"] = pd.to_datetime(tic["date"].astype(str) + "-01", errors="coerce").dt.to_period("M").dt.to_timestamp("M")
        for column in ["for_treas_pos", "for_lt_treas_pos", "for_st_treas_pos"]:
            tic[column] = pd.to_numeric(tic[column].astype(str).str.replace(",", "", regex=False), errors="coerce")
        tic = tic.dropna(subset=["date", "for_treas_pos"]).sort_values("date")
        if not tic.empty:
            rows: list[dict[str, object]] = []
            for _, latest in tic.iterrows():
                total_pos = float(latest["for_treas_pos"])
                long_pos = float(latest.get("for_lt_treas_pos", 0.0))
                short_pos = float(latest.get("for_st_treas_pos", 0.0))
                rows.append(
                    {
                        "date": latest["date"],
                        "sector_key": ROW_SECTOR_KEY,
                        "source_family": "TIC_SLT",
                        "component_key": "coupon_accrual,bill_amortized_discount",
                        "constraint_status": "usable_constraint",
                        "level_mil": total_pos,
                        "long_position_mil": long_pos,
                        "short_position_mil": short_pos,
                        "bill_weight_proxy": _ratio(short_pos, total_pos),
                        "coupon_weight_proxy": _ratio(long_pos, total_pos),
                        "constraint_basis": "tic_slt_table3_foreign_holder_position_long_short_split",
                        "source_path": str(source_path),
                    }
                )
            return rows

    grouped = _quarterly_sums(
        frame,
        "month",
        [
            "tic_foreign_total_treasury_net_flow_usd_millions",
            "tic_foreign_official_long_treasury_net_flow_usd_millions",
            "tic_foreign_official_short_treasury_net_flow_usd_millions",
            "tic_foreign_private_long_treasury_net_flow_usd_millions",
            "tic_foreign_private_short_treasury_net_flow_usd_millions",
        ],
    )
    if grouped.empty:
        return [{
            "sector_key": ROW_SECTOR_KEY,
            "source_family": "TIC",
            "component_key": "coupon_accrual,bill_amortized_discount",
            "constraint_status": "missing_source",
            "source_path": str(source_path),
        }]
    rows: list[dict[str, object]] = []
    for _, latest in grouped.iterrows():
        long_flow = float(latest.get("tic_foreign_official_long_treasury_net_flow_usd_millions", 0.0)) + float(
            latest.get("tic_foreign_private_long_treasury_net_flow_usd_millions", 0.0)
        )
        short_flow = float(latest.get("tic_foreign_official_short_treasury_net_flow_usd_millions", 0.0)) + float(
            latest.get("tic_foreign_private_short_treasury_net_flow_usd_millions", 0.0)
        )
        gross_abs = abs(long_flow) + abs(short_flow)
        rows.append(
            {
                "date": latest["date"],
                "sector_key": ROW_SECTOR_KEY,
                "source_family": "TIC",
                "component_key": "coupon_accrual,bill_amortized_discount",
                "constraint_status": "diagnostic_flow_only_not_default_weight",
                "flow_mil": float(latest.get("tic_foreign_total_treasury_net_flow_usd_millions", 0.0)),
                "long_flow_mil": long_flow,
                "short_flow_mil": short_flow,
                "bill_weight_proxy": _ratio(abs(short_flow), gross_abs),
                "coupon_weight_proxy": _ratio(abs(long_flow), gross_abs),
                "constraint_basis": "monthly_tic_net_flow_long_short_split_not_holder_position",
                "source_path": str(source_path),
            }
        )
    return rows


def build_interest_source_constraints(
    *,
    bank_ffiec_path: Path | str | None,
    credit_union_ncua_path: Path | str | None,
    mmf_path: Path | str | None,
    row_tic_path: Path | str | None,
) -> pd.DataFrame:
    rows = [
        *_regulatory_constraint_rows(
            _safe_read(bank_ffiec_path),
            sector_key=BANK_SECTOR_KEY,
            source_family="FFIEC_CALL_REPORT",
            source_path=bank_ffiec_path or "",
        ),
        *_regulatory_constraint_rows(
            _safe_read(credit_union_ncua_path),
            sector_key=CU_SECTOR_KEY,
            source_family="NCUA_CALL_REPORT",
            source_path=credit_union_ncua_path or "",
        ),
        *_mmf_constraint_rows(_safe_read(mmf_path), source_path=mmf_path or ""),
        *_row_tic_constraint_rows(_read_tic_frame(row_tic_path), source_path=row_tic_path or ""),
    ]
    out = pd.DataFrame(rows)
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date.astype(str).replace("NaT", "")
    return out


def _markdown_summary(frame: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 Interest Source Constraints",
        "",
        "This diagnostic records which public-source constraints are locally available for the component-anchored Tier 2 interest allocation.",
        "",
        "| Sector | Source | Status | Rows | First date | Latest date | Basis |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    if "date" in frame.columns:
        work = frame.copy()
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
    else:
        work = frame.copy()
        work["date"] = pd.NaT
    for column in ["sector_key", "source_family", "constraint_status", "constraint_basis"]:
        if column not in work.columns:
            work[column] = ""
    for (sector, source, status, basis), group in work.groupby(
        ["sector_key", "source_family", "constraint_status", "constraint_basis"],
        dropna=False,
    ):
        dates = group["date"].dropna()
        first_date = "" if dates.empty else dates.min().date().isoformat()
        latest_date = "" if dates.empty else dates.max().date().isoformat()
        lines.append(
            f"| {sector} | {source} | {status} | {len(group):,} | {first_date} | {latest_date} | {basis} |"
        )
    lines.extend(
        [
            "",
            "Latest usable rows:",
            "",
        "| Sector | Source | Status | Latest date | Basis |",
        "|---|---|---:|---:|---|",
        ]
    )
    latest_rows = (
        work.sort_values("date")
        .dropna(subset=["date"])
        .groupby(["sector_key", "source_family"], as_index=False)
        .tail(1)
    )
    if latest_rows.empty:
        latest_rows = work
    for _, row in latest_rows.iterrows():
        lines.append(
            "| {sector} | {source} | {status} | {date} | {basis} |".format(
                sector=row.get("sector_key", ""),
                source=row.get("source_family", ""),
                status=row.get("constraint_status", ""),
                date="" if pd.isna(row.get("date")) else pd.Timestamp(row.get("date")).date().isoformat(),
                basis=row.get("constraint_basis", ""),
            )
        )
    row_status = ""
    if "sector_key" in frame.columns and "constraint_status" in frame.columns:
        row = frame.loc[frame["sector_key"].astype(str).eq(ROW_SECTOR_KEY)]
        if not row.empty:
            row_status = str(row.iloc[0].get("constraint_status", ""))
    if row_status == "usable_constraint":
        note = (
            "Promotion note: FFIEC, MMF, and TIC SLT rows can constrain allocation weights. "
            "The credit-union row constrains the official NCUA Treasury level and uses a documented WAMEST split fallback."
        )
    else:
        note = (
            "Promotion note: FFIEC, NCUA, and MMF rows can constrain allocation weights. "
            "The current TIC row is a flow diagnostic, not a default ROW interest weight; ROW still needs "
            "a TIC holder-position/maturity structure input before promotion."
        )
    lines.extend(["", note])
    return "\n".join(lines) + "\n"


def write_interest_source_constraints(
    *,
    out_path: Path | str,
    markdown_out_path: Path | str,
    bank_ffiec_path: Path | str | None,
    credit_union_ncua_path: Path | str | None,
    mmf_path: Path | str | None,
    row_tic_path: Path | str | None,
) -> tuple[Path, Path, pd.DataFrame]:
    out = build_interest_source_constraints(
        bank_ffiec_path=bank_ffiec_path,
        credit_union_ncua_path=credit_union_ncua_path,
        mmf_path=mmf_path,
        row_tic_path=row_tic_path,
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    markdown_out_path = Path(markdown_out_path)
    markdown_out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_out_path.write_text(_markdown_summary(out), encoding="utf-8")
    return out_path, markdown_out_path, out
