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
    optional_numeric_cols = [
        "historical_credit_intermediation_total_income_tax_after_credits_thousands",
        "historical_management_holding_companies_total_income_tax_after_credits_thousands",
        "historical_credit_intermediation_share_after_credits",
        "historical_credit_intermediation_plus_management_share_after_credits",
    ]
    for col in optional_numeric_cols:
        if col not in df.columns:
            df[col] = pd.NA
    for col in ["source_granularity", "mapping_confidence", "naics_revision"]:
        if col not in df.columns:
            df[col] = pd.NA
    numeric_cols.extend(optional_numeric_cols)
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
        share_method = "current_exact_minor_industry"
        if pd.isna(strict_depository_share) and share_row is not None:
            historical_credit_share = pd.to_numeric(
                pd.Series([share_row.get("historical_credit_intermediation_share_after_credits")]),
                errors="coerce",
            ).iloc[0]
            if pd.notna(historical_credit_share):
                strict_depository_share = float(historical_credit_share)
                share_method = "historical_credit_intermediation_major_industry"
        if pd.isna(depository_plus_bhc_share) and share_row is not None:
            historical_credit_plus_management_share = pd.to_numeric(
                pd.Series([share_row.get("historical_credit_intermediation_plus_management_share_after_credits")]),
                errors="coerce",
            ).iloc[0]
            if pd.notna(historical_credit_plus_management_share):
                depository_plus_bhc_share = float(historical_credit_plus_management_share)

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
                "source_granularity": (
                    str(share_row["source_granularity"]) if share_row is not None and pd.notna(share_row["source_granularity"]) else "current_minor_industry"
                ),
                "mapping_confidence": (
                    str(share_row["mapping_confidence"])
                    if share_row is not None and pd.notna(share_row["mapping_confidence"])
                    else "exact_current_minor_industry_labels"
                ),
                "naics_revision": str(share_row["naics_revision"]) if share_row is not None and pd.notna(share_row["naics_revision"]) else "",
                "bank_share_method": share_method if share_row is not None else "n/a",
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
        "Amounts are in millions. Current-period rows use IRS Publication 16 Table 5.1 bank-minor rows for "
        "`Commercial banking`, `Savings institutions / other depository credit intermediation`, and "
        "`Offices of bank holding companies`. Historical rows may use Publication 16 historical Table 6 "
        "major-industry credit-intermediation shares and are flagged by `bank_share_method` / `mapping_confidence`. "
        "The finance share remains only as an upper benchmark / QA check."
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
        "- For historical Table 6 rows, strict depository falls back to major-industry credit intermediation, and depository+BHC falls back to credit intermediation plus broad management / holding companies.",
        f"- Shares older than {DEFAULT_MAX_STALE_SHARE_YEARS} calendar years are not age-eligible for default use under the current policy.",
        "- The finance share is retained only as a reproducibility / upper-benchmark check and should no longer be treated as the main bank-side default candidate.",
    ]

    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, "", *notes, ""])


def _bridge_with_date_column(bridge: pd.DataFrame) -> pd.DataFrame:
    out = bridge.copy()
    if "date" not in out.columns:
        out = out.reset_index(names="date")
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def build_bank_corp_tax_receipts_bridge_guardrail_audit(
    bridge: pd.DataFrame,
    *,
    tolerance_mil: float = 1e-6,
) -> pd.DataFrame:
    if bridge.empty:
        return pd.DataFrame(
            columns=[
                "check_key",
                "period",
                "variant",
                "audit_status",
                "lhs_value_mil",
                "rhs_value_mil",
                "detail",
            ]
        )

    frame = _bridge_with_date_column(bridge)
    rows: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        strict = pd.to_numeric(pd.Series([row.get("bank_corp_tax_receipts_gross_strict_depository_mil")]), errors="coerce").iloc[0]
        central = pd.to_numeric(pd.Series([row.get("bank_corp_tax_receipts_gross_depository_plus_bhc_mil")]), errors="coerce").iloc[0]
        finance = pd.to_numeric(pd.Series([row.get("bank_corp_tax_receipts_gross_finance_share_mil")]), errors="coerce").iloc[0]
        method = str(row.get("bank_share_method", ""))
        mapping = str(row.get("mapping_confidence", ""))
        if pd.isna(strict) or pd.isna(central) or pd.isna(finance):
            status = "missing_value"
            detail = "One or more bridge variants is missing."
        elif strict <= central + tolerance_mil and central <= finance + tolerance_mil:
            status = "pass"
            detail = "Strict, central, and finance variants are ordered."
        elif strict <= central + tolerance_mil and "historical_credit_intermediation" in method:
            status = "warn_historical_broad_exceeds_finance"
            detail = (
                "Historical dep+BHC proxy uses credit intermediation plus broad management / holding companies; "
                "it is a sensitivity, not a finance-bounded exact minor-industry central variant."
            )
        else:
            status = "fail"
            detail = "Bridge variants violate expected ordering."
        rows.append(
            {
                "check_key": "quarterly_variant_order",
                "period": pd.Timestamp(row["date"]).date().isoformat(),
                "variant": "strict_depository<=depository_plus_bhc<=finance",
                "audit_status": status,
                "lhs_value_mil": strict,
                "rhs_value_mil": finance,
                "detail": detail,
                "mapping_confidence": mapping,
            }
        )

    frame["calendar_year"] = frame["date"].dt.year
    variant_cols = {
        "strict_depository": "bank_corp_tax_receipts_gross_strict_depository_mil",
        "depository_plus_bhc": "bank_corp_tax_receipts_gross_depository_plus_bhc_mil",
        "finance_upper": "bank_corp_tax_receipts_gross_finance_share_mil",
    }
    annual = frame.groupby("calendar_year", as_index=False).agg(
        mts_corp_income_tax_gross_mil=("mts_corp_income_tax_gross_mil", "sum"),
        **{variant: (col, "sum") for variant, col in variant_cols.items()},
    )
    for _, row in annual.iterrows():
        gross = float(row["mts_corp_income_tax_gross_mil"])
        for variant in variant_cols:
            estimate = pd.to_numeric(pd.Series([row.get(variant)]), errors="coerce").iloc[0]
            if pd.isna(estimate):
                status = "missing_value"
                detail = "Annual estimate is missing."
            elif estimate <= gross + tolerance_mil:
                status = "pass"
                detail = "Annual bank-attributed estimate does not exceed gross corporate-income-tax cash."
            else:
                status = "fail"
                detail = "Annual bank-attributed estimate exceeds gross corporate-income-tax cash."
            rows.append(
                {
                    "check_key": "annual_estimate_not_above_gross_corp_tax_cash",
                    "period": str(int(row["calendar_year"])),
                    "variant": variant,
                    "audit_status": status,
                    "lhs_value_mil": estimate,
                    "rhs_value_mil": gross,
                    "detail": detail,
                    "mapping_confidence": "",
                }
            )
    return pd.DataFrame(rows)


def render_bank_corp_tax_receipts_bridge_guardrail_audit_markdown(audit: pd.DataFrame) -> str:
    title = "# Bank Corporate-Tax Receipts Bridge Guardrail Audit"
    if audit.empty:
        return "\n".join([title, "", "No guardrail audit rows are available.", ""])
    counts = audit["audit_status"].value_counts(dropna=False)
    fail_count = int(audit["audit_status"].eq("fail").sum())
    warn_count = int(audit["audit_status"].astype(str).str.startswith("warn").sum())
    lines = [
        title,
        "",
        f"Rows: {len(audit)}. Failures: {fail_count}. Warnings: {warn_count}.",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    for status, count in counts.items():
        lines.append(f"| {status} | {int(count)} |")
    flagged = audit.loc[audit["audit_status"].ne("pass")].head(30)
    if not flagged.empty:
        lines.extend(
            [
                "",
                "First flagged rows:",
                "",
                "| Check | Period | Variant | Status | LHS | RHS | Detail |",
                "| --- | --- | --- | --- | ---: | ---: | --- |",
            ]
        )
        for _, row in flagged.iterrows():
            lhs = row.get("lhs_value_mil")
            rhs = row.get("rhs_value_mil")
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["check_key"]),
                        str(row["period"]),
                        str(row["variant"]),
                        str(row["audit_status"]),
                        "" if pd.isna(lhs) else f"{float(lhs):,.3f}",
                        "" if pd.isna(rhs) else f"{float(rhs):,.3f}",
                        str(row["detail"]),
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def write_bank_corp_tax_receipts_bridge_guardrail_audit(
    *,
    bridge_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None, pd.DataFrame]:
    bridge = pd.read_csv(bridge_path)
    audit = build_bank_corp_tax_receipts_bridge_guardrail_audit(bridge)
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(csv_path, index=False)
    written_md = None
    if markdown_path is not None:
        written_md = Path(markdown_path)
        written_md.parent.mkdir(parents=True, exist_ok=True)
        written_md.write_text(render_bank_corp_tax_receipts_bridge_guardrail_audit_markdown(audit), encoding="utf-8")
    return csv_path, written_md, audit


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
