from __future__ import annotations

import gzip
import json
from pathlib import Path
import re
import urllib.request
import zipfile

import pandas as pd

from .config import USER_AGENT

OFR_MMF_DATASET_URL = "https://data.financialresearch.gov/v1/series/dataset?dataset=mmf"
OFR_MMF_TOTAL_MNEMONIC = "MMF-MMF_TOT-M"
OFR_MMF_TREASURY_MNEMONIC = "MMF-MMF_T_TOT-M"
OFR_MMF_FED_REPO_MNEMONIC = "MMF-MMF_RP_wFR-M"
OFR_MMF_OTHER_ASSETS_MNEMONIC = "MMF-MMF_OA_TOT-M"
OFR_MMF_AGENCY_MNEMONIC = "MMF-MMF_AG_TOT-M"
ON_RRP_OPERATION_START = pd.Timestamp("2013-09-23")
SEC_NMFP_DATASETS_PAGE_URL = "https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets"
SEC_BASE_URL = "https://www.sec.gov"
SEC_USER_AGENT = f"{USER_AGENT} research contact@example.com"

DATE_COLUMNS = ("date", "month", "report_date", "as_of_date")
FUND_COLUMNS = ("fund_id", "series_id", "cik", "lei", "fund_name", "portfolio_id")
FED_RRP_COLUMNS = (
    "fed_rrp",
    "fed_rrp_level",
    "federal_reserve_rrp",
    "federal_reserve_repo",
    "repo_with_fed",
    "repos_with_federal_reserve",
)
TREASURY_TOTAL_COLUMNS = (
    "treasury_total",
    "treasury_securities",
    "total_treasury_securities",
    "us_treasury_securities",
)
TREASURY_BILL_COLUMNS = (
    "treasury_bills",
    "us_treasury_bills",
    "t_bills",
    "tbills",
    "bills",
)
TREASURY_OTHER_COLUMNS = (
    "treasury_other",
    "treasury_notes_bonds_frns",
    "treasury_notes_bonds",
    "other_treasury_securities",
    "treasury_securities_ex_bills",
)
OTHER_USE_COLUMNS = (
    "non_treasury_non_fed_rrp_assets",
    "other_assets_ex_treasury_fed_rrp",
    "non_treasury_assets_ex_fed_rrp",
)
TOTAL_ASSET_COLUMNS = ("total_assets", "assets", "gross_assets")
NAV_COLUMNS = ("nav", "total_net_assets", "net_assets", "total_net_asset_value")
SEC_NMFP_REQUIRED_FILES = (
    "NMFP_SUBMISSION.tsv",
    "NMFP_SERIESLEVELINFO.tsv",
    "NMFP_SCHPORTFOLIOSECURITIES.tsv",
)


def _first_existing(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    lowered = {str(col).lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _numeric(df: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def _positive(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(lower=0.0)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(denominator, errors="coerce")
    out = pd.to_numeric(numerator, errors="coerce") / denominator.where(denominator.ne(0))
    return out.fillna(0.0)


def normalize_mmf_fund_month(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize a Form N-MFP/OFR-style fund-month panel into estimator inputs."""

    if frame.empty:
        return pd.DataFrame()

    df = frame.copy()
    date_col = _first_existing(df, DATE_COLUMNS)
    if date_col is None:
        raise ValueError("MMF/RRP input must contain a date-like column.")
    fund_col = _first_existing(df, FUND_COLUMNS)

    df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.loc[df["date"].notna()].copy()
    if fund_col is None:
        df["fund_id"] = "aggregate"
    else:
        df["fund_id"] = df[fund_col].fillna("unknown").astype(str)

    fed_rrp = _numeric(df, _first_existing(df, FED_RRP_COLUMNS)).fillna(0.0)
    treasury_total_col = _first_existing(df, TREASURY_TOTAL_COLUMNS)
    treasury_bills = _numeric(df, _first_existing(df, TREASURY_BILL_COLUMNS))
    treasury_other = _numeric(df, _first_existing(df, TREASURY_OTHER_COLUMNS))
    if treasury_total_col is None:
        treasury_total = treasury_bills.add(treasury_other, fill_value=0.0)
    else:
        treasury_total = _numeric(df, treasury_total_col)

    other_use_col = _first_existing(df, OTHER_USE_COLUMNS)
    if other_use_col is None:
        total_assets = _numeric(df, _first_existing(df, TOTAL_ASSET_COLUMNS))
        if total_assets.notna().any() and total_assets.abs().sum(skipna=True) > 0:
            other_assets = total_assets - fed_rrp.fillna(0.0) - treasury_total.fillna(0.0)
        else:
            other_assets = pd.Series(0.0, index=df.index, dtype="float64")
    else:
        other_assets = _numeric(df, other_use_col)
    nav = _numeric(df, _first_existing(df, NAV_COLUMNS))

    out = pd.DataFrame(
        {
            "date": df["date"],
            "fund_id": df["fund_id"],
            "fed_rrp": fed_rrp,
            "treasury_total": treasury_total,
            "treasury_bills": treasury_bills,
            "non_treasury_non_fed_rrp_assets": other_assets,
            "nav": nav,
        }
    )
    out = out.sort_values(["fund_id", "date"]).reset_index(drop=True)
    return out


def _read_nmfp_tsv(zf: zipfile.ZipFile, name: str, usecols: list[str] | None = None) -> pd.DataFrame:
    members = {Path(member).name.upper(): member for member in zf.namelist()}
    member = members.get(name.upper())
    if member is None:
        raise FileNotFoundError(f"SEC N-MFP ZIP is missing {name}")
    return pd.read_csv(zf.open(member), sep="\t", dtype=str, usecols=usecols, low_memory=False)


def _sec_numeric_millions(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") / 1_000_000.0


def _sec_date(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="%d-%b-%Y", errors="coerce")
    if parsed.notna().sum() < pd.Series(series).notna().sum():
        fallback = pd.to_datetime(series, errors="coerce")
        parsed = parsed.fillna(fallback)
    return parsed


def _latest_nmfp_accessions(submission: pd.DataFrame) -> pd.DataFrame:
    required = {"ACCESSION_NUMBER", "FILING_DATE", "REPORTDATE", "SERIESID", "SUBMISSIONTYPE"}
    missing = required - set(submission.columns)
    if missing:
        raise ValueError(f"SEC N-MFP submission table is missing columns: {sorted(missing)}")

    sub = submission.copy()
    sub["SUBMISSIONTYPE"] = sub["SUBMISSIONTYPE"].fillna("").astype(str)
    sub = sub.loc[sub["SUBMISSIONTYPE"].str.startswith("N-MFP", na=False)].copy()
    sub["REPORTDATE"] = _sec_date(sub["REPORTDATE"])
    sub["FILING_DATE"] = _sec_date(sub["FILING_DATE"])
    sub = sub.loc[sub["REPORTDATE"].notna()].copy()
    sub["fund_id"] = sub["SERIESID"].fillna("").replace("", pd.NA)
    sub["fund_id"] = sub["fund_id"].fillna(sub["ACCESSION_NUMBER"]).astype(str)
    sub = sub.sort_values(["fund_id", "REPORTDATE", "FILING_DATE", "ACCESSION_NUMBER"])
    return sub.drop_duplicates(["fund_id", "REPORTDATE"], keep="last")


def normalize_sec_nmfp_zip(path: Path | str) -> pd.DataFrame:
    """Normalize one SEC Form N-MFP ZIP into fund-month MMF/RRP support rows.

    Values are reported in millions of dollars. For duplicate fund-month filings,
    the latest filing/amendment in the ZIP is retained.
    """

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
                "SERIES_NAME",
            ],
        )
        latest = _latest_nmfp_accessions(submission)
        if latest.empty:
            return pd.DataFrame(columns=["date", "fund_id", "fed_rrp", "treasury_total", "treasury_bills", "non_treasury_non_fed_rrp_assets", "nav"])

        series = _read_nmfp_tsv(
            zf,
            "NMFP_SERIESLEVELINFO.tsv",
            usecols=[
                "ACCESSION_NUMBER",
                "FEEDERFUNDFLAG",
                "MASTERFUNDFLAG",
                "CASH",
                "TOTALVALUEPORTFOLIOSECURITIES",
                "TOTALVALUEOTHERASSETS",
                "NETASSETOFSERIES",
            ],
        )
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

    selected = latest[
        ["ACCESSION_NUMBER", "REPORTDATE", "fund_id", "SERIESID", "SERIES_NAME", "FILING_DATE"]
    ].copy()
    selected_accessions = set(selected["ACCESSION_NUMBER"].astype(str))

    info = selected.merge(series, on="ACCESSION_NUMBER", how="left")
    if "FEEDERFUNDFLAG" in info.columns:
        # OFR's aggregate monitor avoids feeder/master double counting. Keeping
        # master portfolios while excluding feeder funds matches the aggregate
        # scale closely in current N-MFP files.
        info = info.loc[~info["FEEDERFUNDFLAG"].fillna("").astype(str).str.upper().eq("Y")].copy()
    info["date"] = pd.to_datetime(info["REPORTDATE"], errors="coerce").dt.to_period("M").dt.to_timestamp("M")
    info["nav"] = _sec_numeric_millions(info["NETASSETOFSERIES"])
    asset_total = (
        pd.to_numeric(info["CASH"], errors="coerce").fillna(0.0)
        + pd.to_numeric(info["TOTALVALUEPORTFOLIOSECURITIES"], errors="coerce").fillna(0.0)
        + pd.to_numeric(info["TOTALVALUEOTHERASSETS"], errors="coerce").fillna(0.0)
    ) / 1_000_000.0
    info["asset_total"] = asset_total.where(asset_total.ne(0.0), info["nav"])

    sec = securities.loc[securities["ACCESSION_NUMBER"].astype(str).isin(selected_accessions)].copy()
    value = pd.to_numeric(sec["EXCLUDINGVALUEOFANYSPONSORSUPP"], errors="coerce")
    value = value.fillna(pd.to_numeric(sec["INCLUDINGVALUEOFANYSPONSORSUPP"], errors="coerce")) / 1_000_000.0
    sec["value_mil"] = value.fillna(0.0)
    category = sec["INVESTMENTCATEGORY"].fillna("").astype(str)
    issuer_title = (
        sec["NAMEOFISSUER"].fillna("").astype(str) + " " + sec["TITLEOFISSUER"].fillna("").astype(str)
    )
    is_treasury = category.str.contains("U.S. Treasury Debt", case=False, regex=False)
    is_bill = is_treasury & issuer_title.str.contains("Treasury Bill|T-Bill|\\bBill\\b", case=False, regex=True)
    is_repo = category.str.contains("Repurchase Agreement", case=False, regex=False)
    is_fed = issuer_title.str.contains("Federal Reserve|Federal Reserve Bank of New York|FRBNY", case=False, regex=True)

    grouped = pd.DataFrame(index=pd.Index(sorted(selected_accessions), name="ACCESSION_NUMBER"))
    grouped["treasury_total"] = sec.loc[is_treasury].groupby("ACCESSION_NUMBER")["value_mil"].sum()
    grouped["treasury_bills"] = sec.loc[is_bill].groupby("ACCESSION_NUMBER")["value_mil"].sum()
    grouped["fed_rrp"] = sec.loc[is_repo & is_fed].groupby("ACCESSION_NUMBER")["value_mil"].sum()
    grouped = grouped.fillna(0.0).reset_index()

    out = info.merge(grouped, on="ACCESSION_NUMBER", how="left")
    for col in ("treasury_total", "treasury_bills", "fed_rrp"):
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    out["non_treasury_non_fed_rrp_assets"] = (
        pd.to_numeric(out["asset_total"], errors="coerce").fillna(0.0)
        - out["treasury_total"]
        - out["fed_rrp"]
    )
    return out[
        [
            "date",
            "fund_id",
            "fed_rrp",
            "treasury_total",
            "treasury_bills",
            "non_treasury_non_fed_rrp_assets",
            "nav",
        ]
    ].sort_values(["fund_id", "date"]).reset_index(drop=True)


def build_sec_nmfp_fund_month_support(paths: list[Path | str]) -> pd.DataFrame:
    frames = [normalize_sec_nmfp_zip(path) for path in paths]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["date", "fund_id", "fed_rrp", "treasury_total", "treasury_bills", "non_treasury_non_fed_rrp_assets", "nav"])
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.loc[out["date"].notna()].copy()
    out = out.sort_values(["fund_id", "date"]).drop_duplicates(["fund_id", "date"], keep="last")
    return out.reset_index(drop=True)


def discover_sec_nmfp_dataset_links(html: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    pattern = re.compile(
        r'<a\s+href="(?P<href>/files/dera/data/form-n-mfp-data-sets/[^"]+_nmfp\.zip)"[^>]*>(?P<label>[^<]+)</a>',
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        label = re.sub(r"\s+", " ", match.group("label")).strip()
        href = match.group("href")
        date = _date_from_nmfp_label(label)
        rows.append(
            {
                "label": label,
                "date": date,
                "url": href if href.startswith("http") else f"{SEC_BASE_URL}{href}",
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out.sort_values(["date", "label"]).reset_index(drop=True)


def _date_from_nmfp_label(label: str) -> pd.Timestamp | pd.NaT:
    monthly = re.search(r"(?P<year>\d{4})\s+(?P<month>[A-Za-z]+)\s+NMFP", label)
    if monthly:
        return pd.Timestamp(f"{monthly.group('year')} {monthly.group('month')} 1") + pd.offsets.MonthEnd(0)
    quarterly = re.search(r"(?P<year>\d{4})\s+Q(?P<quarter>[1-4])\s+NMFP", label, flags=re.IGNORECASE)
    if quarterly:
        year = int(quarterly.group("year"))
        quarter = int(quarterly.group("quarter"))
        return pd.Timestamp(year=year, month=quarter * 3, day=1) + pd.offsets.MonthEnd(0)
    return pd.NaT


def load_sec_nmfp_dataset_links(url: str = SEC_NMFP_DATASETS_PAGE_URL, *, timeout: int = 60) -> pd.DataFrame:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate", "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        if str(resp.headers.get("Content-Encoding", "")).lower() == "gzip" or body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
    return discover_sec_nmfp_dataset_links(body.decode("utf-8", errors="replace"))


def download_sec_nmfp_zips(
    *,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    cache_dir: Path | str,
    links: pd.DataFrame | None = None,
    timeout: int = 120,
) -> list[Path]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    link_frame = load_sec_nmfp_dataset_links(timeout=timeout) if links is None else links.copy()
    if link_frame.empty:
        return []
    link_frame["date"] = pd.to_datetime(link_frame["date"], errors="coerce")
    link_frame = link_frame.loc[link_frame["date"].between(start_ts, end_ts, inclusive="both")].copy()
    target_dir = Path(cache_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for _, row in link_frame.iterrows():
        url = str(row["url"])
        target = target_dir / Path(url).name
        if not target.exists():
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": SEC_USER_AGENT,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "application/zip,application/octet-stream,*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                target.write_bytes(resp.read())
        out.append(target)
    return out


def write_sec_nmfp_fund_month_support(
    *,
    zip_paths: list[Path | str],
    out_path: Path | str,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> Path:
    support = build_sec_nmfp_fund_month_support(zip_paths)
    if not support.empty and (start is not None or end is not None):
        dates = pd.to_datetime(support["date"], errors="coerce")
        if start is not None:
            support = support.loc[dates.ge(pd.Timestamp(start))].copy()
            dates = pd.to_datetime(support["date"], errors="coerce")
        if end is not None:
            support = support.loc[dates.le(pd.Timestamp(end))].copy()
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    support.to_csv(target, index=False)
    return target


def compute_mmf_rrp_monthly_adjustments(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_mmf_fund_month(frame)
    if normalized.empty:
        return normalized

    df = normalized.copy()
    df.loc[pd.to_datetime(df["date"], errors="coerce").lt(ON_RRP_OPERATION_START), "fed_rrp"] = 0.0
    group = df.groupby("fund_id", sort=False)
    # Missing Fed RRP observations represent no observed Fed RRP funding source,
    # not a free pass-through of MMF Treasury increases into the RRP adjustment.
    df["rrp_runoff"] = _positive(-group["fed_rrp"].diff()).fillna(0.0)
    df["treasury_increase"] = _positive(group["treasury_total"].diff())
    df["treasury_bills_increase"] = _positive(group["treasury_bills"].diff())
    df["other_asset_increase"] = _positive(group["non_treasury_non_fed_rrp_assets"].diff())
    df["nav_decline"] = _positive(-group["nav"].diff())
    df["other_uses"] = df["other_asset_increase"].add(df["nav_decline"], fill_value=0.0)

    denominator = df["treasury_increase"].add(df["other_uses"], fill_value=0.0)
    bill_denominator = df["treasury_bills_increase"].add(df["other_uses"], fill_value=0.0)

    df["mmf_rrp_adjustment_ub"] = pd.concat(
        [df["treasury_increase"], df["rrp_runoff"]], axis=1
    ).min(axis=1)
    raw_prop = df["rrp_runoff"] * _safe_ratio(df["treasury_increase"], denominator)
    df["mmf_rrp_adjustment_lb"] = pd.concat(
        [df["treasury_increase"], _positive(df["rrp_runoff"] - df["other_uses"])],
        axis=1,
    ).min(axis=1)
    df["mmf_rrp_adjustment_prop"] = pd.concat(
        [raw_prop, df["mmf_rrp_adjustment_ub"]],
        axis=1,
    ).min(axis=1)
    df["mmf_rrp_bills_adjustment_ub"] = pd.concat(
        [df["treasury_bills_increase"], df["rrp_runoff"]], axis=1
    ).min(axis=1)
    raw_bills_prop = df["rrp_runoff"] * _safe_ratio(df["treasury_bills_increase"], bill_denominator)
    df["mmf_rrp_bills_adjustment_lb"] = pd.concat(
        [df["treasury_bills_increase"], _positive(df["rrp_runoff"] - df["other_uses"])],
        axis=1,
    ).min(axis=1)
    df["mmf_rrp_bills_adjustment_prop"] = pd.concat(
        [raw_bills_prop, df["mmf_rrp_bills_adjustment_ub"]],
        axis=1,
    ).min(axis=1)
    return df


def aggregate_mmf_rrp_to_quarter(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame()

    value_cols = [
        "rrp_runoff",
        "treasury_increase",
        "treasury_bills_increase",
        "other_uses",
        "mmf_rrp_adjustment_lb",
        "mmf_rrp_adjustment_prop",
        "mmf_rrp_adjustment_ub",
        "mmf_rrp_bills_adjustment_lb",
        "mmf_rrp_bills_adjustment_prop",
        "mmf_rrp_bills_adjustment_ub",
    ]
    working = monthly.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.loc[working["date"].notna()].copy()
    out = (
        working.set_index("date")[value_cols]
        .resample("QE-DEC")
        .sum(min_count=1)
        .sort_index()
    )
    out.index.name = "date"
    return out


def build_mmf_rrp_adjustment_from_csv(path: Path | str) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(path)
    monthly = compute_mmf_rrp_monthly_adjustments(raw)
    quarterly = aggregate_mmf_rrp_to_quarter(monthly)
    return monthly, quarterly


def build_mmf_rrp_source_comparison(
    *,
    preferred_raw_path: Path | str,
    fallback_raw_path: Path | str,
    materiality_threshold_mil: float = 10_000.0,
) -> pd.DataFrame:
    """Compare preferred fund-level MMF/RRP adjustments with an aggregate fallback."""

    _, preferred = build_mmf_rrp_adjustment_from_csv(preferred_raw_path)
    _, fallback = build_mmf_rrp_adjustment_from_csv(fallback_raw_path)
    value_cols = [
        "rrp_runoff",
        "treasury_increase",
        "other_uses",
        "mmf_rrp_adjustment_lb",
        "mmf_rrp_adjustment_prop",
        "mmf_rrp_adjustment_ub",
        "mmf_rrp_bills_adjustment_prop",
    ]
    rows = pd.concat(
        [
            preferred[value_cols].add_prefix("preferred_"),
            fallback[value_cols].add_prefix("fallback_"),
        ],
        axis=1,
        join="outer",
    ).sort_index()
    rows.index.name = "date"
    rows["preferred_minus_fallback_prop"] = (
        rows["preferred_mmf_rrp_adjustment_prop"] - rows["fallback_mmf_rrp_adjustment_prop"]
    )
    rows["abs_preferred_minus_fallback_prop"] = rows["preferred_minus_fallback_prop"].abs()
    rows["preferred_to_fallback_prop_ratio"] = _safe_ratio(
        rows["preferred_mmf_rrp_adjustment_prop"],
        rows["fallback_mmf_rrp_adjustment_prop"],
    )
    rows["material_difference"] = rows["abs_preferred_minus_fallback_prop"].ge(materiality_threshold_mil)
    return rows.reset_index()


def write_mmf_rrp_source_comparison(
    *,
    preferred_raw_path: Path | str,
    fallback_raw_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
    materiality_threshold_mil: float = 10_000.0,
) -> pd.DataFrame:
    comparison = build_mmf_rrp_source_comparison(
        preferred_raw_path=preferred_raw_path,
        fallback_raw_path=fallback_raw_path,
        materiality_threshold_mil=materiality_threshold_mil,
    )
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(target, index=False)

    if markdown_path is not None:
        md_target = Path(markdown_path)
        md_target.parent.mkdir(parents=True, exist_ok=True)
        common = comparison.dropna(
            subset=["preferred_mmf_rrp_adjustment_prop", "fallback_mmf_rrp_adjustment_prop"],
            how="any",
        ).copy()
        material = common.loc[common["material_difference"]]
        latest = common.tail(1)
        top = common.sort_values("abs_preferred_minus_fallback_prop", ascending=False).head(5)
        lines = [
            "# MMF/RRP source comparison",
            "",
            "Preferred source: SEC Form N-MFP fund-month allocation.",
            "",
            "Fallback source: OFR aggregate monthly MMF bridge.",
            "",
            f"Common quarters: {len(common)}",
            f"Material quarters at ${materiality_threshold_mil:,.0f} million threshold: {len(material)}",
        ]
        if not latest.empty:
            row = latest.iloc[0]
            lines.extend(
                [
                    "",
                    "Latest common quarter:",
                    "",
                    (
                        f"- {pd.Timestamp(row['date']).date().isoformat()}: "
                        f"preferred prop {row['preferred_mmf_rrp_adjustment_prop']:.3f}; "
                        f"fallback prop {row['fallback_mmf_rrp_adjustment_prop']:.3f}; "
                        f"difference {row['preferred_minus_fallback_prop']:.3f}."
                    ),
                ]
            )
        if not top.empty:
            lines.extend(["", "Largest absolute differences:", "", "| Quarter | Preferred prop | Fallback prop | Difference |", "|---|---:|---:|---:|"])
            for _, row in top.iterrows():
                lines.append(
                    "| "
                    f"{pd.Timestamp(row['date']).date().isoformat()} | "
                    f"{row['preferred_mmf_rrp_adjustment_prop']:.3f} | "
                    f"{row['fallback_mmf_rrp_adjustment_prop']:.3f} | "
                    f"{row['preferred_minus_fallback_prop']:.3f} |"
                )
        md_target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return comparison


def build_mmf_rrp_scale_audit(
    *,
    raw: pd.DataFrame,
    monthly: pd.DataFrame,
    quarterly: pd.DataFrame,
    z1_mmf_treasury_level: pd.Series | None = None,
    z1_mmf_treasury_bills_level: pd.Series | None = None,
) -> pd.DataFrame:
    normalized = normalize_mmf_fund_month(raw)
    rows: list[dict[str, object]] = []

    if normalized.empty:
        return pd.DataFrame(
            [
                {
                    "check": "input_presence",
                    "status": "fail",
                    "value": 0.0,
                    "detail": "No normalized MMF support rows were available.",
                }
            ]
        )

    fund_count = int(normalized["fund_id"].nunique())
    source_granularity = "aggregate_monthly" if fund_count == 1 else "fund_month"
    first_month = pd.to_datetime(normalized["date"]).min()
    latest_month = pd.to_datetime(normalized["date"]).max()
    latest = normalized.loc[pd.to_datetime(normalized["date"]).eq(latest_month)].copy()

    rows.extend(
        [
            {
                "check": "source_granularity",
                "status": "warn" if source_granularity == "aggregate_monthly" else "pass",
                "value": source_granularity,
                "detail": "Aggregate OFR bridge is usable for candidate comparison but is not the final fund-level N-MFP allocation.",
            },
            {
                "check": "fund_count",
                "status": "warn" if fund_count == 1 else "pass",
                "value": fund_count,
                "detail": "Number of distinct fund identifiers in the normalized support file.",
            },
            {
                "check": "monthly_range",
                "status": "pass",
                "value": f"{first_month.date().isoformat()}:{latest_month.date().isoformat()}",
                "detail": "Inclusive monthly support range.",
            },
            {
                "check": "latest_fed_rrp_millions",
                "status": "pass",
                "value": float(pd.to_numeric(latest["fed_rrp"], errors="coerce").sum()),
                "detail": "Latest-month Fed repo/RRP position in millions.",
            },
            {
                "check": "latest_treasury_total_millions",
                "status": "pass",
                "value": float(pd.to_numeric(latest["treasury_total"], errors="coerce").sum()),
                "detail": "Latest-month MMF Treasury securities in millions.",
            },
            {
                "check": "latest_nav_millions",
                "status": "pass",
                "value": float(pd.to_numeric(latest["nav"], errors="coerce").sum()),
                "detail": "Latest-month MMF NAV or total net assets in millions.",
            },
        ]
    )

    if monthly.empty or quarterly.empty:
        rows.append(
            {
                "check": "adjustment_presence",
                "status": "fail",
                "value": 0.0,
                "detail": "MMF/RRP adjustment rows were not produced.",
            }
        )
        return pd.DataFrame(rows)

    bound_checks = [
        ("mmf_rrp_adjustment", "mmf_rrp_adjustment_lb", "mmf_rrp_adjustment_prop", "mmf_rrp_adjustment_ub"),
        (
            "mmf_rrp_bills_adjustment",
            "mmf_rrp_bills_adjustment_lb",
            "mmf_rrp_bills_adjustment_prop",
            "mmf_rrp_bills_adjustment_ub",
        ),
    ]
    for label, lb_col, prop_col, ub_col in bound_checks:
        if {lb_col, prop_col, ub_col}.issubset(monthly.columns):
            if label == "mmf_rrp_bills_adjustment":
                bills_increase = pd.to_numeric(monthly.get("treasury_bills_increase"), errors="coerce")
                if bills_increase.notna().sum() == 0:
                    rows.append(
                        {
                            "check": f"{label}_monthly_bounds",
                            "status": "skip",
                            "value": pd.NA,
                            "detail": "Treasury-bills support is unavailable in this MMF input; bills-only robustness checks are skipped.",
                        }
                    )
                    continue
            lb = pd.to_numeric(monthly[lb_col], errors="coerce")
            prop = pd.to_numeric(monthly[prop_col], errors="coerce")
            ub = pd.to_numeric(monthly[ub_col], errors="coerce")
            violations = int(((prop + 1e-9 < lb) | (prop - 1e-9 > ub)).sum())
            rows.append(
                {
                    "check": f"{label}_monthly_bounds",
                    "status": "pass" if violations == 0 else "fail",
                    "value": violations,
                    "detail": "Monthly lower/proportional/upper ordering violations.",
                }
            )

    latest_quarter = quarterly.dropna(how="all").tail(1)
    if not latest_quarter.empty:
        row = latest_quarter.iloc[0]
        prop = float(row.get("mmf_rrp_adjustment_prop", 0.0) or 0.0)
        ub = float(row.get("mmf_rrp_adjustment_ub", 0.0) or 0.0)
        rows.extend(
            [
                {
                    "check": "latest_quarter",
                    "status": "pass",
                    "value": latest_quarter.index[0].date().isoformat(),
                    "detail": "Latest quarterly adjustment row.",
                },
                {
                    "check": "latest_prop_share_of_upper_bound",
                    "status": "pass" if ub >= 0.0 and prop <= ub + 1e-9 else "fail",
                    "value": prop / ub if ub else 0.0,
                    "detail": "Preferred proportional adjustment divided by upper bound in the latest quarter.",
                },
            ]
        )

    _append_z1_scale_check(
        rows,
        normalized=normalized,
        z1_series=z1_mmf_treasury_level,
        support_col="treasury_total",
        check_name="z1_mmf_treasury_total_level_match",
        detail="Quarter-end OFR/support MMF Treasury total compared with Z.1 MMF Treasury securities level.",
    )
    _append_z1_scale_check(
        rows,
        normalized=normalized,
        z1_series=z1_mmf_treasury_bills_level,
        support_col="treasury_bills",
        check_name="z1_mmf_treasury_bills_level_match",
        detail="Quarter-end OFR/support MMF Treasury bills compared with Z.1 MMF Treasury bills level.",
    )

    return pd.DataFrame(rows)


def _append_z1_scale_check(
    rows: list[dict[str, object]],
    *,
    normalized: pd.DataFrame,
    z1_series: pd.Series | None,
    support_col: str,
    check_name: str,
    detail: str,
) -> None:
    if z1_series is None or z1_series.empty:
        rows.append(
            {
                "check": check_name,
                "status": "skip",
                "value": pd.NA,
                "detail": "Z.1 comparison series is unavailable in the current raw bundle.",
            }
        )
        return
    if support_col not in normalized.columns:
        rows.append(
            {
                "check": check_name,
                "status": "skip",
                "value": pd.NA,
                "detail": f"MMF support column {support_col!r} is unavailable.",
            }
        )
        return
    support_values = pd.to_numeric(normalized[support_col], errors="coerce")
    if support_values.notna().sum() == 0:
        rows.append(
            {
                "check": check_name,
                "status": "skip",
                "value": pd.NA,
                "detail": f"MMF support column {support_col!r} has no numeric observations.",
            }
        )
        return

    support = normalized.copy()
    support["date"] = pd.to_datetime(support["date"], errors="coerce")
    support[support_col] = support_values
    support = support.loc[support["date"].notna()].copy()
    support["quarter"] = support["date"].dt.to_period("Q").dt.to_timestamp("Q")
    latest_month = support.groupby("quarter")["date"].transform("max")
    support_q = (
        support.loc[support["date"].eq(latest_month)]
        .groupby("quarter")[support_col]
        .sum(min_count=1)
        .sort_index()
    )
    z1 = pd.to_numeric(z1_series, errors="coerce").copy()
    z1.index = pd.to_datetime(z1.index, errors="coerce").to_period("Q").to_timestamp("Q")
    common = pd.concat([support_q.rename("support"), z1.rename("z1")], axis=1, join="inner").dropna()
    if common.empty:
        rows.append(
            {
                "check": check_name,
                "status": "skip",
                "value": pd.NA,
                "detail": "No common quarters between MMF support and Z.1 comparison series.",
            }
        )
        return

    latest = common.iloc[-1]
    denom = abs(float(latest["z1"]))
    rel_diff = abs(float(latest["support"]) - float(latest["z1"])) / denom if denom else 0.0
    rows.append(
        {
            "check": check_name,
            "status": "pass" if rel_diff <= 0.05 else "warn",
            "value": rel_diff,
            "detail": f"{detail} Latest common quarter: {common.index[-1].date().isoformat()}.",
        }
    )


def write_mmf_rrp_adjustment_outputs(
    *,
    raw_path: Path | str,
    monthly_csv_path: Path | str,
    quarterly_csv_path: Path | str,
    markdown_path: Path | str,
    audit_csv_path: Path | str | None = None,
    audit_markdown_path: Path | str | None = None,
    z1_mmf_treasury_level: pd.Series | None = None,
    z1_mmf_treasury_bills_level: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(raw_path)
    monthly = compute_mmf_rrp_monthly_adjustments(raw)
    quarterly = aggregate_mmf_rrp_to_quarter(monthly)

    monthly_target = Path(monthly_csv_path)
    quarterly_target = Path(quarterly_csv_path)
    markdown_target = Path(markdown_path)
    monthly_target.parent.mkdir(parents=True, exist_ok=True)
    quarterly_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)

    monthly.to_csv(monthly_target, index=False)
    quarterly.to_csv(quarterly_target)
    audit = build_mmf_rrp_scale_audit(
        raw=raw,
        monthly=monthly,
        quarterly=quarterly,
        z1_mmf_treasury_level=z1_mmf_treasury_level,
        z1_mmf_treasury_bills_level=z1_mmf_treasury_bills_level,
    )
    if audit_csv_path is not None:
        audit_target = Path(audit_csv_path)
        audit_target.parent.mkdir(parents=True, exist_ok=True)
        audit.to_csv(audit_target, index=False)
    if audit_markdown_path is not None:
        audit_markdown_target = Path(audit_markdown_path)
        audit_markdown_target.parent.mkdir(parents=True, exist_ok=True)
        failed = audit.loc[audit["status"].eq("fail")]
        warned = audit.loc[audit["status"].eq("warn")]
        status = "fail" if not failed.empty else ("warn" if not warned.empty else "pass")
        audit_markdown_target.write_text(
            "\n".join(
                [
                    "# MMF/RRP scale audit",
                    "",
                    f"Status: {status}",
                    "",
                    f"Failed checks: {len(failed)}",
                    f"Warning checks: {len(warned)}",
                    "",
                    "Warnings are expected when the OFR aggregate bridge is used instead of a fund-level N-MFP panel.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    latest = quarterly.dropna(how="all").tail(1)
    if latest.empty:
        latest_note = "No quarterly MMF/RRP adjustment rows were produced."
    else:
        row = latest.iloc[0]
        latest_note = (
            f"Latest quarter {latest.index[0].date().isoformat()}: "
            f"prop={row.get('mmf_rrp_adjustment_prop'):.3f}, "
            f"lb={row.get('mmf_rrp_adjustment_lb'):.3f}, "
            f"ub={row.get('mmf_rrp_adjustment_ub'):.3f}."
        )
    markdown_target.write_text(
        "\n".join(
            [
                "# MMF/RRP adjustment",
                "",
                "This artifact computes the fund-month source-of-funds adjustment from a normalized Form N-MFP/OFR-style support file.",
                "",
                latest_note,
                "",
                "The proportional row is a candidate Tier 2 adjustment. Lower and upper rows are bounds.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return monthly, quarterly


def _ofr_timeseries(payload: dict, mnemonic: str) -> pd.Series:
    try:
        rows = payload["timeseries"][mnemonic]["timeseries"]["aggregation"]
    except KeyError as exc:
        raise KeyError(f"Missing OFR MMF mnemonic: {mnemonic}") from exc
    if not rows:
        return pd.Series(dtype="float64", name=mnemonic)
    return pd.Series(
        [float(value) / 1_000_000.0 if value is not None else pd.NA for _, value in rows],
        index=pd.to_datetime([date for date, _ in rows], errors="coerce"),
        name=mnemonic,
        dtype="float64",
    ).sort_index()


def load_ofr_mmf_dataset(url: str = OFR_MMF_DATASET_URL, *, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        if str(resp.headers.get("Content-Encoding", "")).lower() == "gzip" or body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        return json.loads(body.decode("utf-8"))


def build_ofr_mmf_aggregate_support(payload: dict) -> pd.DataFrame:
    total = _ofr_timeseries(payload, OFR_MMF_TOTAL_MNEMONIC)
    treasury = _ofr_timeseries(payload, OFR_MMF_TREASURY_MNEMONIC)
    fed_repo = _ofr_timeseries(payload, OFR_MMF_FED_REPO_MNEMONIC)
    other_assets = _ofr_timeseries(payload, OFR_MMF_OTHER_ASSETS_MNEMONIC)

    frame = pd.concat(
        [
            total.rename("nav"),
            treasury.rename("treasury_total"),
            fed_repo.rename("fed_rrp"),
            other_assets.rename("non_treasury_non_fed_rrp_assets"),
        ],
        axis=1,
    ).sort_index()
    frame["date"] = frame.index
    frame["fund_id"] = "ofr_aggregate_mmf"
    frame["treasury_bills"] = pd.NA
    return frame[
        [
            "date",
            "fund_id",
            "fed_rrp",
            "treasury_total",
            "treasury_bills",
            "non_treasury_non_fed_rrp_assets",
            "nav",
        ]
    ].reset_index(drop=True)


def write_ofr_mmf_aggregate_support(
    *,
    out_path: Path | str,
    raw_json_path: Path | str | None = None,
    timeout: int = 60,
) -> Path:
    payload = load_ofr_mmf_dataset(timeout=timeout)
    if raw_json_path is not None:
        raw_target = Path(raw_json_path)
        raw_target.parent.mkdir(parents=True, exist_ok=True)
        raw_target.write_text(json.dumps(payload), encoding="utf-8")
    support = build_ofr_mmf_aggregate_support(payload)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    support.to_csv(target, index=False)
    return target
