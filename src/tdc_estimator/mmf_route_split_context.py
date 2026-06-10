from __future__ import annotations

from pathlib import Path
import zipfile

import pandas as pd

from .mmf_rrp import _latest_nmfp_accessions, _read_nmfp_tsv, _sec_date


MMF_ROUTE_SPLIT_CONTEXT_FIELDS = [
    "date",
    "quarter",
    "route_id",
    "route_label",
    "source_family",
    "source_artifact_count",
    "fund_scope",
    "fund_type_scope",
    "fund_count",
    "total_assets_bil",
    "treasury_total_bil",
    "treasury_bills_bil",
    "treasury_coupons_bil",
    "fed_onrrp_bil",
    "m1_scope",
    "m2_scope",
    "deposit_pass_through_scope",
    "current_demand_eligible",
    "tdc_estimator_treatment",
    "ratewall_treatment",
    "canonical_tdc_math_change",
    "exact_blocker",
    "source_status",
    "notes",
]


def _quarter_from_date(value: object) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return f"{timestamp.year}Q{((timestamp.month - 1) // 3) + 1}"


def _sec_value_bil(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0) / 1_000_000_000.0


def _bool_flag(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=bool)
    return series.fillna("").astype(str).str.upper().eq("Y")


def _read_nmfp_route_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        submission = _read_nmfp_tsv(
            zf,
            "NMFP_SUBMISSION.tsv",
            usecols=[
                "ACCESSION_NUMBER",
                "FILING_DATE",
                "SUBMISSIONTYPE",
                "REPORTDATE",
                "SERIESID",
            ],
        )
        latest = _latest_nmfp_accessions(submission)
        if latest.empty:
            return pd.DataFrame()

        series = _read_nmfp_tsv(zf, "NMFP_SERIESLEVELINFO.tsv")
        for column in [
            "ACCESSION_NUMBER",
            "FEEDERFUNDFLAG",
            "NETASSETOFSERIES",
            "MONEYMARKETFUNDCATEGORY",
            "FUNDRETAILMONEYMARKETFLAG",
            "GOVMONEYMRKTFUNDFLAG",
        ]:
            if column not in series.columns:
                series[column] = pd.NA
        securities = _read_nmfp_tsv(
            zf,
            "NMFP_SCHPORTFOLIOSECURITIES.tsv",
            usecols=[
                "ACCESSION_NUMBER",
                "NAMEOFISSUER",
                "TITLEOFISSUER",
                "INVESTMENTCATEGORY",
                "INCLUDINGVALUEOFANYSPONSORSUPP",
                "EXCLUDINGVALUEOFANYSPONSORSUPP",
            ],
        )

    selected = latest[["ACCESSION_NUMBER", "REPORTDATE", "fund_id"]].copy()
    info = selected.merge(series, on="ACCESSION_NUMBER", how="left")
    if "FEEDERFUNDFLAG" in info.columns:
        info = info.loc[
            ~info["FEEDERFUNDFLAG"].fillna("").astype(str).str.upper().eq("Y")
        ].copy()
    if info.empty:
        return pd.DataFrame()
    info["date"] = _sec_date(info["REPORTDATE"]).dt.to_period("M").dt.to_timestamp("M")
    info = info.loc[info["date"].notna()].copy()
    info["retail_flag"] = _bool_flag(info.get("FUNDRETAILMONEYMARKETFLAG"))
    info["government_flag"] = _bool_flag(info.get("GOVMONEYMRKTFUNDFLAG"))
    info["fund_type"] = info["MONEYMARKETFUNDCATEGORY"].fillna("unknown").astype(str)
    info["total_assets_bil"] = _sec_value_bil(info["NETASSETOFSERIES"])

    selected_accessions = set(info["ACCESSION_NUMBER"].astype(str))
    sec = securities.loc[
        securities["ACCESSION_NUMBER"].astype(str).isin(selected_accessions)
    ].copy()
    raw_value = pd.to_numeric(sec["EXCLUDINGVALUEOFANYSPONSORSUPP"], errors="coerce")
    raw_value = raw_value.fillna(
        pd.to_numeric(sec["INCLUDINGVALUEOFANYSPONSORSUPP"], errors="coerce")
    )
    sec["value_bil"] = raw_value.fillna(0.0) / 1_000_000_000.0
    category = sec["INVESTMENTCATEGORY"].fillna("").astype(str)
    issuer_title = (
        sec["NAMEOFISSUER"].fillna("").astype(str)
        + " "
        + sec["TITLEOFISSUER"].fillna("").astype(str)
    )
    is_treasury = category.str.contains("U.S. Treasury Debt", case=False, regex=False)
    is_bill = is_treasury & issuer_title.str.contains(
        r"Treasury Bill|T-Bill|\bBill\b", case=False, regex=True
    )
    is_repo = category.str.contains("Repurchase Agreement", case=False, regex=False)
    is_fed = issuer_title.str.contains(
        "Federal Reserve|Federal Reserve Bank of New York|FRBNY",
        case=False,
        regex=True,
    )

    grouped = pd.DataFrame(index=pd.Index(sorted(selected_accessions), name="ACCESSION_NUMBER"))
    grouped["treasury_total_bil"] = sec.loc[is_treasury].groupby("ACCESSION_NUMBER")[
        "value_bil"
    ].sum()
    grouped["treasury_bills_bil"] = sec.loc[is_bill].groupby("ACCESSION_NUMBER")[
        "value_bil"
    ].sum()
    grouped["fed_onrrp_bil"] = sec.loc[is_repo & is_fed].groupby("ACCESSION_NUMBER")[
        "value_bil"
    ].sum()
    grouped = grouped.fillna(0.0).reset_index()
    out = info.merge(grouped, on="ACCESSION_NUMBER", how="left")
    for column in ("treasury_total_bil", "treasury_bills_bil", "fed_onrrp_bil"):
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    out["treasury_coupons_bil"] = (
        out["treasury_total_bil"] - out["treasury_bills_bil"]
    ).clip(lower=0.0)
    out["source_zip"] = path.name
    return out


def build_mmf_route_split_context(zip_paths: list[Path | str]) -> pd.DataFrame:
    frames = [_read_nmfp_route_zip(Path(path)) for path in sorted(map(Path, zip_paths))]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=MMF_ROUTE_SPLIT_CONTEXT_FIELDS)

    fund_month = pd.concat(frames, ignore_index=True)
    fund_month = fund_month.sort_values(["fund_id", "date", "source_zip"])
    fund_month = fund_month.drop_duplicates(["fund_id", "date"], keep="last")
    fund_month["quarter"] = fund_month["date"].map(_quarter_from_date)
    quarter_dates = fund_month.groupby("quarter")["date"].transform("max")
    fund_month = fund_month.loc[fund_month["date"].eq(quarter_dates)].copy()
    fund_month["scope"] = fund_month["retail_flag"].map(
        {True: "retail_mmf", False: "institutional_or_nonretail_mmf"}
    )

    grouped = (
        fund_month.groupby(["quarter", "scope"], as_index=False)
        .agg(
            date=("date", "max"),
            fund_count=("fund_id", "nunique"),
            total_assets_bil=("total_assets_bil", "sum"),
            treasury_total_bil=("treasury_total_bil", "sum"),
            treasury_bills_bil=("treasury_bills_bil", "sum"),
            treasury_coupons_bil=("treasury_coupons_bil", "sum"),
            fed_onrrp_bil=("fed_onrrp_bil", "sum"),
            source_artifact_count=("source_zip", "nunique"),
        )
        .sort_values(["date", "scope"])
    )

    rows: list[dict[str, str]] = []
    for _, row in grouped.iterrows():
        is_retail = row["scope"] == "retail_mmf"
        prefix = "retail" if is_retail else "institutional_or_nonretail"
        fund_scope = "retail_mmf" if is_retail else "institutional_or_nonretail_mmf"
        m2_scope = "true" if is_retail else "false"
        route_label_prefix = "Retail MMF" if is_retail else "Institutional/nonretail MMF"
        base = {
            "date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
            "quarter": str(row["quarter"]),
            "source_family": "sec_nmfp_fund_type_portfolio_context",
            "source_artifact_count": str(int(row["source_artifact_count"])),
            "fund_scope": fund_scope,
            "fund_type_scope": "all_sec_nmfp_money_market_fund_categories",
            "fund_count": str(int(row["fund_count"])),
            "total_assets_bil": _format_number(row["total_assets_bil"]),
            "treasury_total_bil": _format_number(row["treasury_total_bil"]),
            "treasury_bills_bil": _format_number(row["treasury_bills_bil"]),
            "treasury_coupons_bil": _format_number(row["treasury_coupons_bil"]),
            "fed_onrrp_bil": _format_number(row["fed_onrrp_bil"]),
            "m1_scope": "false",
            "m2_scope": m2_scope,
            "deposit_pass_through_scope": "false",
            "current_demand_eligible": "false",
            "tdc_estimator_treatment": "context_only_not_canonical_tdc_math",
            "canonical_tdc_math_change": "false",
            "source_status": "source_backed_sec_nmfp_context",
        }
        rows.append(
            {
                **base,
                "route_id": f"{prefix}_mmf_treasury_holdings_context",
                "route_label": f"{route_label_prefix} Treasury holdings context.",
                "ratewall_treatment": "context_only_not_deposit_pass_through",
                "exact_blocker": (
                    "fund_type_and_portfolio_holdings_do_not_identify_final_"
                    "investor_current_demand_conversion"
                ),
                "notes": (
                    "SEC N-MFP identifies fund retail status and portfolio "
                    "Treasury holdings, but not final investor spending behavior."
                ),
            }
        )
        rows.append(
            {
                **base,
                "route_id": f"{prefix}_mmf_onrrp_plumbing_context",
                "route_label": f"{route_label_prefix} Fed ON-RRP holdings context.",
                "ratewall_treatment": "fed_onrrp_plumbing_context_only",
                "exact_blocker": (
                    "fed_onrrp_holdings_are_fed_plumbing_not_bank_deposit_or_"
                    "recipient_demand_evidence"
                ),
                "notes": (
                    "SEC N-MFP identifies Fed ON-RRP portfolio holdings by fund "
                    "scope; use as plumbing context only."
                ),
            }
        )

    return pd.DataFrame(rows, columns=MMF_ROUTE_SPLIT_CONTEXT_FIELDS)


def _format_number(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def render_mmf_route_split_context_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "# MMF Route Split Context\n\nNo rows were generated.\n"
    latest_quarter = frame["quarter"].dropna().iloc[-1]
    latest = frame.loc[frame["quarter"].eq(latest_quarter)].copy()
    return "\n".join(
        [
            "# MMF Route Split Context",
            "",
            f"- Latest quarter: `{latest_quarter}`.",
            f"- Latest route rows: `{len(latest)}`.",
            "- Source: SEC Form N-MFP fund retail flag and portfolio holdings.",
            "- Boundary: context-only; this split does not identify final investor current-demand conversion.",
            "- RateWall use: classify retail vs institutional/nonretail MMF Treasury and ON-RRP plumbing without changing canonical TDC math.",
            "",
        ]
    )


def write_mmf_route_split_context(
    *,
    zip_paths: list[Path | str],
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None, pd.DataFrame]:
    frame = build_mmf_route_split_context(zip_paths)
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    md_target: Path | None = None
    if markdown_path is not None:
        md_target = Path(markdown_path)
        md_target.parent.mkdir(parents=True, exist_ok=True)
        md_target.write_text(
            render_mmf_route_split_context_markdown(frame),
            encoding="utf-8",
        )
    return target, md_target, frame
