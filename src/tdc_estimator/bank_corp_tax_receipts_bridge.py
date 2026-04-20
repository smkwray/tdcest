from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import load_treasury_table

MTS_CORP_TAX_LABEL = "Corporation Income Taxes"
DEFAULT_MAX_STALE_SHARE_YEARS = 2


def _full_quarter_index(df: pd.DataFrame, *, date_col: str) -> pd.DatetimeIndex:
    monthly = pd.to_datetime(df[date_col]).dt.to_period("M")
    coverage = monthly.groupby(monthly.dt.asfreq("Q")).nunique()
    full = coverage[coverage >= 3].index.to_timestamp("Q")
    return pd.DatetimeIndex(full).sort_values()


def _load_mts_corporate_tax_receipts(path: Path | str) -> pd.DataFrame:
    df = load_treasury_table(path).copy()
    required = {
        "record_date",
        "classification_desc",
        "current_month_gross_rcpt_amt",
        "current_month_refund_amt",
        "current_month_net_rcpt_amt",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"MTS receipts file {path} is missing required columns: {missing}")

    out = df.loc[
        df["classification_desc"].eq(MTS_CORP_TAX_LABEL),
        [
            "record_date",
            "classification_desc",
            "current_month_gross_rcpt_amt",
            "current_month_refund_amt",
            "current_month_net_rcpt_amt",
        ],
    ].copy()
    out["record_date"] = pd.to_datetime(out["record_date"])
    for col in [
        "current_month_gross_rcpt_amt",
        "current_month_refund_amt",
        "current_month_net_rcpt_amt",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def _quarterly_sum(df: pd.DataFrame, *, value_col: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="float64")
    series = df.groupby(df["record_date"].dt.to_period("Q"))[value_col].sum()
    series.index = series.index.to_timestamp("Q")
    return series.sort_index() / 1_000_000.0


def _load_irs_soi_bank_tax_shares(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path).copy()
    required = {
        "tax_year",
        "source_table",
        "all_total_income_tax_after_credits_thousands",
        "finance_and_insurance_total_income_tax_after_credits_thousands",
        "commercial_banking_total_income_tax_after_credits_thousands",
        "savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands",
        "bank_holding_companies_total_income_tax_after_credits_thousands",
        "finance_share_after_credits",
        "strict_depository_share_after_credits",
        "depository_plus_bhc_share_after_credits",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"IRS SOI bank-tax share file {path} is missing required columns: {missing}")
    df["tax_year"] = pd.to_numeric(df["tax_year"], errors="raise").astype(int)
    numeric_cols = [
        "all_total_income_tax_after_credits_thousands",
        "finance_and_insurance_total_income_tax_after_credits_thousands",
        "commercial_banking_total_income_tax_after_credits_thousands",
        "savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands",
        "bank_holding_companies_total_income_tax_after_credits_thousands",
        "finance_share_after_credits",
        "strict_depository_share_after_credits",
        "depository_plus_bhc_share_after_credits",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "depository_label_observed" not in df.columns:
        df["depository_label_observed"] = pd.NA
    return df.sort_values("tax_year").reset_index(drop=True)


def build_bank_corp_tax_receipts_bridge(
    *,
    mts_receipts_path: Path | str,
    irs_soi_bank_tax_shares_path: Path | str,
    start: str = "2022-09-30",
    max_stale_share_years: int = DEFAULT_MAX_STALE_SHARE_YEARS,
) -> pd.DataFrame:
    mts = _load_mts_corporate_tax_receipts(mts_receipts_path)
    shares = _load_irs_soi_bank_tax_shares(irs_soi_bank_tax_shares_path)
    if shares.empty:
        return pd.DataFrame()

    full_quarters = _full_quarter_index(mts, date_col="record_date")
    bridge = pd.DataFrame(index=full_quarters)
    bridge["mts_corp_income_tax_gross_mil"] = _quarterly_sum(mts, value_col="current_month_gross_rcpt_amt").reindex(full_quarters).fillna(0.0)
    bridge["mts_corp_income_tax_refunds_mil"] = _quarterly_sum(mts, value_col="current_month_refund_amt").reindex(full_quarters).fillna(0.0)
    bridge["mts_corp_income_tax_net_mil"] = _quarterly_sum(mts, value_col="current_month_net_rcpt_amt").reindex(full_quarters).fillna(0.0)

    min_year = int(shares["tax_year"].min())
    max_year = int(shares["tax_year"].max())

    rows: list[dict[str, object]] = []
    for date, row in bridge.iterrows():
        year = pd.Timestamp(date).year
        status = "observed"
        share_year = year
        if year < min_year:
            status = "pre_source_gap"
            share_year = None
        elif year > max_year:
            status = "carry_forward_latest"
            share_year = max_year

        share_row = shares.loc[shares["tax_year"].eq(share_year)].iloc[0] if share_year is not None else None
        finance_share = float(share_row["finance_share_after_credits"]) if share_row is not None else float("nan")
        strict_depository_share = float(share_row["strict_depository_share_after_credits"]) if share_row is not None else float("nan")
        depository_plus_bhc_share = float(share_row["depository_plus_bhc_share_after_credits"]) if share_row is not None else float("nan")

        gross = float(row["mts_corp_income_tax_gross_mil"])
        net = float(row["mts_corp_income_tax_net_mil"])
        stale_share_years = year - share_year if share_year is not None else float("nan")
        age_eligible = share_year is not None and stale_share_years <= max_stale_share_years

        rows.append(
            {
                "date": pd.Timestamp(date),
                "mts_corp_income_tax_gross_mil": gross,
                "mts_corp_income_tax_refunds_mil": float(row["mts_corp_income_tax_refunds_mil"]),
                "mts_corp_income_tax_net_mil": net,
                "soi_tax_year_used": share_year,
                "soi_source_table": str(share_row["source_table"]) if share_row is not None else "n/a",
                "share_status": status,
                "stale_share_years": stale_share_years,
                "share_age_eligible_for_default": age_eligible,
                "share_age_policy": f"max_{max_stale_share_years}_calendar_years",
                "soi_all_tax_after_credits_thousands": (
                    float(share_row["all_total_income_tax_after_credits_thousands"]) if share_row is not None else float("nan")
                ),
                "soi_finance_and_insurance_tax_after_credits_thousands": (
                    float(share_row["finance_and_insurance_total_income_tax_after_credits_thousands"])
                    if share_row is not None
                    else float("nan")
                ),
                "soi_commercial_banking_tax_after_credits_thousands": (
                    float(share_row["commercial_banking_total_income_tax_after_credits_thousands"])
                    if share_row is not None
                    else float("nan")
                ),
                "soi_savings_depository_tax_after_credits_thousands": (
                    float(share_row["savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands"])
                    if share_row is not None
                    else float("nan")
                ),
                "soi_bank_holding_tax_after_credits_thousands": (
                    float(share_row["bank_holding_companies_total_income_tax_after_credits_thousands"])
                    if share_row is not None
                    else float("nan")
                ),
                "depository_label_observed": (
                    str(share_row["depository_label_observed"]) if share_row is not None and pd.notna(share_row["depository_label_observed"]) else ""
                ),
                "finance_share_reproduction_qa": finance_share,
                "bank_tax_share_strict_depository": strict_depository_share,
                "bank_tax_share_depository_plus_bhc": depository_plus_bhc_share,
                "suppression_flag_commercial_banking": False,
                "suppression_flag_savings_depository": False,
                "suppression_flag_bank_holding": False,
                "perimeter_grade": "bank_minor_industry_public_bridge",
                "default_eligible": age_eligible,
                "recommended_role": (
                    "default_candidate_age_eligible" if age_eligible else "bridge_only_share_too_stale"
                ),
                "bank_corp_tax_receipts_gross_strict_depository_mil": gross * strict_depository_share
                if pd.notna(strict_depository_share)
                else float("nan"),
                "bank_corp_tax_receipts_net_strict_depository_mil": net * strict_depository_share
                if pd.notna(strict_depository_share)
                else float("nan"),
                "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": gross * depository_plus_bhc_share
                if pd.notna(depository_plus_bhc_share)
                else float("nan"),
                "bank_corp_tax_receipts_net_depository_plus_bhc_mil": net * depository_plus_bhc_share
                if pd.notna(depository_plus_bhc_share)
                else float("nan"),
                "bank_corp_tax_receipts_gross_finance_share_mil": gross * finance_share if pd.notna(finance_share) else float("nan"),
                "bank_corp_tax_receipts_net_finance_share_mil": net * finance_share if pd.notna(finance_share) else float("nan"),
            }
        )

    out = pd.DataFrame(rows).set_index("date").sort_index()
    return out.loc[out.index >= pd.Timestamp(start)].copy()


def render_bank_corp_tax_receipts_bridge_markdown(bridge: pd.DataFrame) -> str:
    title = "# Bank Corporate-Tax Receipts Bridge"
    intro = (
        "Quarter-by-quarter bridge from MTS corporate-income-tax cash receipts to bank-attributed receipt candidates. "
        "Amounts are in millions. The primary public bridge now uses IRS Publication 16 Table 5.1 bank-minor rows "
        "for `Commercial banking`, `Savings institutions / other depository credit intermediation`, and "
        "`Offices of bank holding companies`, while the finance share remains only as an upper benchmark / QA check."
    )
    if bridge.empty:
        return "\n".join([title, "", intro, "", "No overlapping MTS corporate-tax receipts and IRS annual share inputs are available."])

    latest_date = bridge.index.max()
    latest = bridge.loc[latest_date]
    latest_summary = (
        f"Latest bridge quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"MTS gross corporate tax {float(latest['mts_corp_income_tax_gross_mil']):,.3f}; "
        f"MTS net corporate tax {float(latest['mts_corp_income_tax_net_mil']):,.3f}; "
        f"share year used {latest['soi_tax_year_used'] if pd.notna(latest['soi_tax_year_used']) else 'n/a'} "
        f"({latest['share_status']}); "
        f"stale-share age {int(latest['stale_share_years']) if pd.notna(latest['stale_share_years']) else 'n/a'} "
        f"under `{latest['share_age_policy']}`; "
        f"strict-depository gross bridge {float(latest['bank_corp_tax_receipts_gross_strict_depository_mil']):,.3f}; "
        f"depository-plus-BHC gross bridge {float(latest['bank_corp_tax_receipts_gross_depository_plus_bhc_mil']):,.3f}; "
        f"finance-share QA bridge {float(latest['bank_corp_tax_receipts_gross_finance_share_mil']):,.3f}."
    )

    header = (
        "| Quarter | MTS gross corp tax | MTS refunds | MTS net corp tax | Share year | Share status | Stale-share years | Age-eligible for default | Strict depository share | Depository+BHC share | Finance QA share | Gross bridge (strict) | Gross bridge (dep+BHC) |\n"
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"
    )
    rows: list[str] = []
    for date, row in bridge.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    f"{float(row['mts_corp_income_tax_gross_mil']):,.3f}",
                    f"{float(row['mts_corp_income_tax_refunds_mil']):,.3f}",
                    f"{float(row['mts_corp_income_tax_net_mil']):,.3f}",
                    "n/a" if pd.isna(row["soi_tax_year_used"]) else str(int(row["soi_tax_year_used"])),
                    str(row["share_status"]),
                    "n/a" if pd.isna(row["stale_share_years"]) else str(int(row["stale_share_years"])),
                    "yes" if bool(row["share_age_eligible_for_default"]) else "no",
                    "n/a" if pd.isna(row["bank_tax_share_strict_depository"]) else f"{float(row['bank_tax_share_strict_depository']):.4f}",
                    "n/a" if pd.isna(row["bank_tax_share_depository_plus_bhc"]) else f"{float(row['bank_tax_share_depository_plus_bhc']):.4f}",
                    "n/a" if pd.isna(row["finance_share_reproduction_qa"]) else f"{float(row['finance_share_reproduction_qa']):.4f}",
                    "n/a"
                    if pd.isna(row["bank_corp_tax_receipts_gross_strict_depository_mil"])
                    else f"{float(row['bank_corp_tax_receipts_gross_strict_depository_mil']):,.3f}",
                    "n/a"
                    if pd.isna(row["bank_corp_tax_receipts_gross_depository_plus_bhc_mil"])
                    else f"{float(row['bank_corp_tax_receipts_gross_depository_plus_bhc_mil']):,.3f}",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- Gross MTS corporate-income-tax receipts are closer to the strict `paid Treasury` receipt identity than net receipts, so gross is the primary bridge output.",
        "- `Strict depository` = commercial banking + savings / depository credit intermediation.",
        "- `Depository+BHC` = strict depository + offices of bank holding companies; this is the current primary default-candidate variant for bank corporate groups.",
        f"- Shares older than {DEFAULT_MAX_STALE_SHARE_YEARS} calendar years are not age-eligible for default use under the current policy.",
        "- The finance share is retained only as a reproducibility / upper-benchmark check and should no longer be treated as the main bank-side default candidate.",
    ]

    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, "", *notes, ""])


def write_bank_corp_tax_receipts_bridge(
    *,
    mts_receipts_path: Path | str,
    irs_soi_bank_tax_shares_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2022-09-30",
    max_stale_share_years: int = DEFAULT_MAX_STALE_SHARE_YEARS,
) -> tuple[Path, Path, pd.DataFrame]:
    bridge = build_bank_corp_tax_receipts_bridge(
        mts_receipts_path=mts_receipts_path,
        irs_soi_bank_tax_shares_path=irs_soi_bank_tax_shares_path,
        start=start,
        max_stale_share_years=max_stale_share_years,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = bridge.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bank_corp_tax_receipts_bridge_markdown(bridge), encoding="utf-8")

    return csv_path, markdown_path, bridge
