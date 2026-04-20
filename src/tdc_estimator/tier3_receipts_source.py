from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import load_treasury_table

RECEIPT_CANDIDATE_LABELS = {
    "fed_earnings_receipts_candidate": "Deposit of Earnings, Federal Reserve System",
    "customs_duties_candidate": "Customs Duties",
    "deposits_by_states_candidate": "Deposits by States",
}


def _load_mts_receipts(path: Path | str) -> pd.DataFrame:
    df = load_treasury_table(path).copy()
    required = {"record_date", "classification_desc"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"MTS receipts file {path} is missing required columns: {missing}")
    value_column = None
    for candidate in ["current_month_net_rcpt_amt", "net_rcpt_amt"]:
        if candidate in df.columns:
            value_column = candidate
            break
    if value_column is None:
        raise ValueError(
            f"MTS receipts file {path} is missing a supported receipt value column. "
            "Expected one of ['current_month_net_rcpt_amt', 'net_rcpt_amt']."
        )
    out = df.loc[:, ["record_date", "classification_desc", value_column]].copy()
    out["record_date"] = pd.to_datetime(out["record_date"])
    out["classification_desc"] = out["classification_desc"].fillna("").astype(str)
    out["current_month_net_rcpt_amt"] = pd.to_numeric(out[value_column], errors="coerce").fillna(0.0)
    if value_column != "current_month_net_rcpt_amt":
        out = out.drop(columns=[value_column])
    return out


def _full_quarter_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    monthly = pd.to_datetime(df["record_date"]).dt.to_period("M")
    coverage = monthly.groupby(monthly.dt.asfreq("Q")).nunique()
    full = coverage[coverage >= 3].index.to_timestamp("Q")
    return pd.DatetimeIndex(full).sort_values()


def _quarterly_receipt_sum(df: pd.DataFrame, label: str) -> pd.Series:
    sub = df.loc[df["classification_desc"].eq(label), ["record_date", "current_month_net_rcpt_amt"]].copy()
    if sub.empty:
        return pd.Series(dtype="float64")
    series = sub.groupby(sub["record_date"].dt.to_period("Q"))["current_month_net_rcpt_amt"].sum()
    series.index = series.index.to_timestamp("Q")
    return series.sort_index() / 1_000_000.0


def _load_revenue_collections(path: Path | str) -> pd.DataFrame:
    df = load_treasury_table(path).copy()
    required = {"record_date", "channel_type_desc", "tax_category_desc", "net_collections_amt"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Revenue Collections file {path} is missing required columns: {missing}")
    out = df.loc[:, ["record_date", "channel_type_desc", "tax_category_desc", "net_collections_amt"]].copy()
    out["record_date"] = pd.to_datetime(out["record_date"])
    out["channel_type_desc"] = out["channel_type_desc"].fillna("").astype(str)
    out["tax_category_desc"] = out["tax_category_desc"].fillna("").astype(str)
    out["net_collections_amt"] = pd.to_numeric(out["net_collections_amt"], errors="coerce").fillna(0.0)
    return out


def _quarterly_rcm_sum(
    df: pd.DataFrame,
    *,
    channel: str,
    tax_category: str | None = None,
) -> pd.Series:
    mask = df["channel_type_desc"].eq(channel)
    if tax_category is not None:
        mask &= df["tax_category_desc"].eq(tax_category)
    sub = df.loc[mask, ["record_date", "net_collections_amt"]].copy()
    if sub.empty:
        return pd.Series(dtype="float64")
    series = sub.groupby(sub["record_date"].dt.to_period("Q"))["net_collections_amt"].sum()
    series.index = series.index.to_timestamp("Q")
    return series.sort_index() / 1_000_000.0


def build_tier3_receipt_source_diagnostics(
    *,
    mts_receipts_path: Path | str,
    revenue_collections_path: Path | str | None = None,
    start: str = "2022-09-30",
) -> pd.DataFrame:
    receipts = _load_mts_receipts(mts_receipts_path)
    full_quarters = _full_quarter_index(receipts)
    diag = pd.DataFrame(index=full_quarters)

    for key, label in RECEIPT_CANDIDATE_LABELS.items():
        diag[key] = _quarterly_receipt_sum(receipts, label).reindex(full_quarters).fillna(0.0)

    # Current Tier 3 defaults intentionally exclude these candidate receipts.
    diag["bank_nonborrow_receipt_included_default"] = 0.0
    diag["row_nonborrow_receipt_included_default"] = 0.0
    diag["fed_earnings_excluded_as_bank_or_row_receipt"] = diag["fed_earnings_receipts_candidate"]
    diag["customs_excluded_as_row_receipt"] = diag["customs_duties_candidate"]
    diag["state_deposits_excluded_as_bank_or_row_receipt"] = diag["deposits_by_states_candidate"]

    if revenue_collections_path is not None and Path(revenue_collections_path).exists():
        rcm = _load_revenue_collections(revenue_collections_path)
        rcm_quarters = pd.DatetimeIndex(sorted(diag.index.union(_full_quarter_index(rcm))))
        diag = diag.reindex(rcm_quarters).sort_index()
        diag["rcm_bank_channel_total_candidate"] = _quarterly_rcm_sum(
            rcm, channel="Bank"
        ).reindex(diag.index).fillna(0.0)
        diag["rcm_bank_channel_non_tax_candidate"] = _quarterly_rcm_sum(
            rcm, channel="Bank", tax_category="Non-Tax"
        ).reindex(diag.index).fillna(0.0)
        diag["rcm_bank_channel_irs_tax_candidate"] = _quarterly_rcm_sum(
            rcm, channel="Bank", tax_category="IRS Tax"
        ).reindex(diag.index).fillna(0.0)
        diag["rcm_bank_channel_irs_nontax_candidate"] = _quarterly_rcm_sum(
            rcm, channel="Bank", tax_category="IRS Non-Tax"
        ).reindex(diag.index).fillna(0.0)
        diag["rcm_bank_channel_excluded_from_default"] = diag["rcm_bank_channel_total_candidate"]

    return diag.loc[diag.index >= pd.Timestamp(start)].copy()


def render_tier3_receipt_source_diagnostics_markdown(diagnostics: pd.DataFrame) -> str:
    title = "# Tier 3 Receipt Source Diagnostics"
    intro = (
        "Quarter-by-quarter diagnostics for the current MTS receipt-side Tier 3 review. "
        "Amounts are in millions. The current default keeps bank and ROW nonborrow receipt corrections at zero "
        "because the visible MTS receipt candidates do not cleanly map to those counterparty buckets."
    )
    if diagnostics.empty:
        return "\n".join([title, "", intro, "", "No full-quarter MTS receipt coverage is available."])

    latest_date = diagnostics.index.max()
    latest = diagnostics.loc[latest_date]
    latest_summary = (
        f"Latest source-covered quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Fed earnings candidate {float(latest['fed_earnings_receipts_candidate']):,.3f}; "
        f"customs candidate {float(latest['customs_duties_candidate']):,.3f}; "
        f"state deposits candidate {float(latest['deposits_by_states_candidate']):,.3f}; "
        f"RCM bank-channel candidate {float(latest.get('rcm_bank_channel_total_candidate', 0.0)):,.3f}; "
        f"default bank receipt included {float(latest['bank_nonborrow_receipt_included_default']):,.3f}; "
        f"default ROW receipt included {float(latest['row_nonborrow_receipt_included_default']):,.3f}."
    )

    header = (
        "| Quarter | Fed earnings cand. | Customs cand. | State deposits cand. | RCM bank cand. | RCM bank non-tax | Default bank receipt | Default ROW receipt |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    rows: list[str] = []
    for date, row in diagnostics.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    f"{float(row.get('fed_earnings_receipts_candidate', 0.0)):,.3f}",
                    f"{float(row.get('customs_duties_candidate', 0.0)):,.3f}",
                    f"{float(row.get('deposits_by_states_candidate', 0.0)):,.3f}",
                    f"{float(row.get('rcm_bank_channel_total_candidate', 0.0)):,.3f}",
                    f"{float(row.get('rcm_bank_channel_non_tax_candidate', 0.0)):,.3f}",
                    f"{float(row.get('bank_nonborrow_receipt_included_default', 0.0)):,.3f}",
                    f"{float(row.get('row_nonborrow_receipt_included_default', 0.0)):,.3f}",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `Deposit of Earnings, Federal Reserve System` is a Fed receipt line, not a bank or ROW receipt.",
        "- `Customs Duties` are excluded from the ROW receipt default because the legal cash payer is typically a domestic importer.",
        "- `Deposits by States` are excluded because they are not receipts from banks or ROW.",
        "- Revenue Collections `Bank` channel values are visible and material, but the channel reflects payment routing through banking networks rather than a clean bank-sector counterparty flow.",
        "- DTS `deposits_withdrawals_operating_cash` is useful for cash-timing diagnostics, but its visible categories are agency/program transaction labels rather than bank or ROW counterparty sectors.",
    ]

    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, "", *notes, ""])


def write_tier3_receipt_source_diagnostics(
    *,
    mts_receipts_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    revenue_collections_path: Path | str | None = None,
    start: str = "2022-09-30",
) -> tuple[Path, Path, pd.DataFrame]:
    diagnostics = build_tier3_receipt_source_diagnostics(
        mts_receipts_path=mts_receipts_path,
        revenue_collections_path=revenue_collections_path,
        start=start,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = diagnostics.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_tier3_receipt_source_diagnostics_markdown(diagnostics), encoding="utf-8")

    return csv_path, markdown_path, diagnostics
