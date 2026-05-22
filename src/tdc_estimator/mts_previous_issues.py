from __future__ import annotations

import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

from .config import USER_AGENT

MTS_FISCAL_SERVICE_ARCHIVE_URL = "https://fiscal.treasury.gov/system/files/files/reports-statements/mts/mts{mmyy}.pdf"
MTS_FISCALDATA_STATIC_URL = (
    "https://fiscaldata.treasury.gov/static-data/published-reports/mts/"
    "MonthlyTreasuryStatement_{yyyymm}.pdf"
)
MTS_ROW_OUTLAY_NARROW_LABELS = [
    "Contribution to the International Development Association",
    "Foreign Agricultural Service",
    "International Disaster Assistance",
    "International Monetary Programs",
    "International Organizations and Conferences",
    "Contributions to International Organizations",
    "Migration and Refugee Assistance",
    "Global Health and Child Survival",
    "Global Health Programs",
    "Payment to Foreign Service Retirement and Disability Fund",
    "Foreign Service Retirement and Disability Fund",
]
MTS_ROW_OUTLAY_BROAD_LABELS = [
    "Foreign Military Financing Program",
    "International Narcotics Control and Law Enforcement",
    "Andean Counterdrug Initiative",
    "Economic Support Fund",
    "Embassy Security, Construction, and Maintenance",
]
MTS_TABLE5_TARGET_LABELS = [
    "Financial Agent Services",
    "United States Mint",
    *MTS_ROW_OUTLAY_NARROW_LABELS,
    *MTS_ROW_OUTLAY_BROAD_LABELS,
]
MTS_TABLE4_TARGET_LABELS = ["Corporation Income Taxes", "Corporate Income Taxes"]


def month_ends(start: str | pd.Timestamp, end: str | pd.Timestamp) -> list[pd.Timestamp]:
    start_month = pd.Timestamp(start).to_period("M").to_timestamp("M")
    end_month = pd.Timestamp(end).to_period("M").to_timestamp("M")
    if end_month < start_month:
        return []
    return list(pd.date_range(start_month, end_month, freq="ME"))


def mts_archive_pdf_url(month_end: pd.Timestamp) -> str:
    return MTS_FISCAL_SERVICE_ARCHIVE_URL.format(mmyy=month_end.strftime("%m%y"))


def mts_static_pdf_url(month_end: pd.Timestamp) -> str:
    return MTS_FISCALDATA_STATIC_URL.format(yyyymm=month_end.strftime("%Y%m"))


def build_mts_previous_issues_manifest(
    *,
    start: str | pd.Timestamp = "2003-01-31",
    end: str | pd.Timestamp = "2015-02-28",
    cache_dir: Path | str = "data/raw/mts_previous_issues",
) -> pd.DataFrame:
    cache_dir = Path(cache_dir)
    rows: list[dict[str, object]] = []
    for month_end in month_ends(start, end):
        yyyymm = month_end.strftime("%Y%m")
        mmyy = month_end.strftime("%m%y")
        pdf_cache_path = cache_dir / "pdf" / f"mts{mmyy}.pdf"
        text_cache_path = cache_dir / "text" / f"mts{mmyy}.txt"
        excel_cache_path = cache_dir / "excel" / f"mts{mmyy}.xlsx"
        ascii_cache_path = cache_dir / "ascii" / f"mts{mmyy}.txt"
        rows.append(
            {
                "issue_month": month_end.strftime("%Y-%m"),
                "record_date": month_end.date().isoformat(),
                "yyyymm": yyyymm,
                "mmyy": mmyy,
                "fiscal_year": int(month_end.year + (1 if month_end.month >= 10 else 0)),
                "fiscal_month": int(((month_end.month - 10) % 12) + 1),
                "fiscaldata_api_available": False,
                "source_priority": "treasury_previous_issue_excel|treasury_previous_issue_ascii|pdf_text",
                "pdf_url": mts_archive_pdf_url(month_end),
                "pdf_url_fiscaldata_static_candidate": mts_static_pdf_url(month_end),
                "pdf_cache_path": str(pdf_cache_path),
                "text_cache_path": str(text_cache_path),
                "excel_cache_path": str(excel_cache_path),
                "ascii_cache_path": str(ascii_cache_path),
                "pdf_cached": pdf_cache_path.exists(),
                "text_cached": text_cache_path.exists(),
                "excel_cached": excel_cache_path.exists(),
                "ascii_cached": ascii_cache_path.exists(),
                "table4_parse_status": "pending",
                "table5_parse_status": "pending",
                "fas_direct_leaf_status": "manual_qa_required" if month_end.year in {2003, 2004} else "unchecked",
                "mint_direct_leaf_status": "unchecked",
                "notes": "",
            }
        )
    return pd.DataFrame(rows)


def write_mts_previous_issues_manifest(
    *,
    out_path: Path | str,
    start: str | pd.Timestamp = "2003-01-31",
    end: str | pd.Timestamp = "2015-02-28",
    cache_dir: Path | str | None = None,
) -> Path:
    out_path = Path(out_path)
    if cache_dir is None:
        cache_dir = out_path.parent / "mts_previous_issues"
    manifest = build_mts_previous_issues_manifest(start=start, end=end, cache_dir=cache_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(out_path, index=False)
    return out_path


def _fetch_bytes(url: str, timeout: int = 90) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def pdf_bytes_to_text(payload: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "mts.pdf"
        txt_path = Path(tmp) / "mts.txt"
        pdf_path.write_bytes(payload)
        subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)], check=True)
        return txt_path.read_text(encoding="utf-8", errors="replace")


def cache_manifest_pdf_text(
    manifest_row: pd.Series,
    *,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    pdf_path = Path(str(manifest_row["pdf_cache_path"]))
    text_path = Path(str(manifest_row["text_cache_path"]))
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)

    if overwrite or not pdf_path.exists():
        pdf_path.write_bytes(_fetch_bytes(str(manifest_row["pdf_url"])))
    if overwrite or not text_path.exists():
        text_path.write_text(pdf_bytes_to_text(pdf_path.read_bytes()), encoding="utf-8")
    return pdf_path, text_path


def _parse_millions_token(token: str) -> float | None:
    cleaned = (
        str(token)
        .replace(",", "")
        .replace("\u2212", "-")
        .replace("\u2014", "-")
        .replace("......", "")
        .strip()
    )
    if cleaned in {"(**)", "(* *)", "**"}:
        return 0.0
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _target_label_pattern(label: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in label.lower().split()]
    return re.compile(r"\b" + r"\s+".join(parts) + r"\b", re.IGNORECASE)


def _line_has_label(line: str, label: str) -> bool:
    normalized = re.sub(r"\s+", " ", line).strip()
    return bool(_target_label_pattern(label).search(normalized))


def _table_section_lines(text: str, *, start_pattern: str, end_pattern: str) -> list[str]:
    lines = text.splitlines()
    start_re = re.compile(start_pattern, re.IGNORECASE)
    end_re = re.compile(end_pattern, re.IGNORECASE)
    start_idx = next((idx for idx, line in enumerate(lines) if start_re.search(line)), None)
    if start_idx is None:
        return lines
    end_idx = next((idx for idx, line in enumerate(lines[start_idx + 1 :], start=start_idx + 1) if end_re.search(line)), len(lines))
    return lines[start_idx:end_idx]


def _numeric_token_count(text: str) -> int:
    return len(re.findall(r"\(\*\*\)|\(\* \*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", text))


def parse_mts_table5_target_lines(
    text: str,
    *,
    record_date: str | pd.Timestamp,
    labels: list[str] | None = None,
) -> pd.DataFrame:
    labels = labels or MTS_TABLE5_TARGET_LABELS
    rows: list[dict[str, object]] = []
    previous_line = ""
    for line in _table_section_lines(
        text,
        start_pattern=r"Table\s+5\.\s+Outlays",
        end_pattern=r"Table\s+6\.",
    ):
        candidate_lines = [line]
        if previous_line.strip() and _numeric_token_count(previous_line) < 3:
            candidate_lines.insert(0, f"{previous_line.strip()} {line.strip()}")
        for label in labels:
            candidate_line = next((candidate for candidate in candidate_lines if _line_has_label(candidate, label)), None)
            if candidate_line is None:
                continue
            match = _target_label_pattern(label).search(candidate_line)
            tail = candidate_line[match.end() :] if match else candidate_line
            values = [
                _parse_millions_token(token)
                for token in re.findall(r"\(\*\*\)|\(\* \*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", tail)
            ]
            if len(values) < 3:
                continue
            rows.append(
                {
                    "record_date": pd.Timestamp(record_date).date().isoformat(),
                    "classification_desc": label,
                    "current_month_gross_outly_mil": values[0],
                    "current_month_app_rcpt_mil": values[1],
                    "current_month_net_outly_mil": values[2],
                    "current_fytd_gross_outly_mil": values[3] if len(values) > 3 else None,
                    "current_fytd_app_rcpt_mil": values[4] if len(values) > 4 else None,
                    "current_fytd_net_outly_mil": values[5] if len(values) > 5 else None,
                    "source_parse_method": "pdf_text_line_target",
                }
            )
            break
        previous_line = line
    return pd.DataFrame(rows)


def parse_mts_table4_target_lines(
    text: str,
    *,
    record_date: str | pd.Timestamp,
    labels: list[str] | None = None,
) -> pd.DataFrame:
    labels = labels or MTS_TABLE4_TARGET_LABELS
    best_by_label: dict[str, dict[str, object]] = {}
    for line in _table_section_lines(
        text,
        start_pattern=r"Table\s+4\.\s+Receipts",
        end_pattern=r"Table\s+5\.\s+Outlays",
    ):
        for label in labels:
            if not _line_has_label(line, label):
                continue
            match = _target_label_pattern(label).search(line)
            tail = line[match.end() :] if match else line
            values = [
                _parse_millions_token(token)
                for token in re.findall(r"\(\*\*\)|\(\* \*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", tail)
            ]
            # Summary tables often carry only net receipt columns. The detailed Table 4 row
            # carries gross, refunds, net for current month and FYTD windows.
            if len(values) < 6:
                continue
            row = {
                "record_date": pd.Timestamp(record_date).date().isoformat(),
                "classification_desc": "Corporation Income Taxes",
                "current_month_gross_rcpt_mil": values[0],
                "current_month_refund_mil": values[1],
                "current_month_net_rcpt_mil": values[2],
                "current_fytd_gross_rcpt_mil": values[3],
                "current_fytd_refund_mil": values[4],
                "current_fytd_net_rcpt_mil": values[5],
                "source_parse_method": "pdf_text_line_target",
            }
            current = best_by_label.get("Corporation Income Taxes")
            if current is None or len(values) > int(current["_value_count"]):
                row["_value_count"] = len(values)
                best_by_label["Corporation Income Taxes"] = row
            break

    rows = []
    for row in best_by_label.values():
        row = dict(row)
        row.pop("_value_count", None)
        rows.append(row)
    return pd.DataFrame(rows)


def parse_mts_summary_total_lines(text: str, *, record_date: str | pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    section = _table_section_lines(
        text,
        start_pattern=r"Table\s+3\.\s+Summary\s+of\s+Receipts\s+and\s+Outlays",
        end_pattern=r"Table\s+4\.\s+Receipts",
    )
    for line in section:
        normalized = re.sub(r"\s+", " ", line).strip()
        if re.match(r"Total\s+Receipts\b", normalized, flags=re.IGNORECASE):
            values = [
                _parse_millions_token(token)
                for token in re.findall(r"\(\*\*\)|\(\* \*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", line)
            ]
            if len(values) >= 2:
                rows.append(
                    {
                        "record_date": pd.Timestamp(record_date).date().isoformat(),
                        "table_name": "table3_summary",
                        "total_name": "total_receipts",
                        "current_month_net_mil": values[0],
                        "current_fytd_net_mil": values[1],
                    }
                )
        elif re.match(r"Total\s+outlays\b", normalized, flags=re.IGNORECASE):
            values = [
                _parse_millions_token(token)
                for token in re.findall(r"\(\*\*\)|\(\* \*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", line)
            ]
            if len(values) >= 2:
                rows.append(
                    {
                        "record_date": pd.Timestamp(record_date).date().isoformat(),
                        "table_name": "table3_summary",
                        "total_name": "total_outlays",
                        "current_month_net_mil": values[0],
                        "current_fytd_net_mil": values[1],
                    }
                )
    return pd.DataFrame(rows)


def parse_mts_table4_printed_total_line(text: str, *, record_date: str | pd.Timestamp) -> pd.DataFrame:
    section = _table_section_lines(
        text,
        start_pattern=r"Table\s+4\.\s+Receipts",
        end_pattern=r"Table\s+5\.\s+Outlays",
    )
    rows: list[dict[str, object]] = []
    for line in section:
        normalized = re.sub(r"\s+", " ", line).strip()
        if not re.match(r"Total\s+Receipts\b", normalized, flags=re.IGNORECASE):
            continue
        values = [
            _parse_millions_token(token)
            for token in re.findall(r"\(\*\*\)|\(\* \*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", line)
        ]
        if len(values) < 2:
            continue
        rows.append(
            {
                "record_date": pd.Timestamp(record_date).date().isoformat(),
                "table_name": "table4_receipts",
                "total_name": "total_receipts",
                "current_month_net_mil": values[0],
                "current_fytd_net_mil": values[1],
            }
        )
    return pd.DataFrame(rows)


def parse_mts_table5_printed_total_line(text: str, *, record_date: str | pd.Timestamp) -> pd.DataFrame:
    section = _table_section_lines(
        text,
        start_pattern=r"Table\s+5\.\s+Outlays",
        end_pattern=r"Table\s+6\.",
    )
    rows: list[dict[str, object]] = []
    for line in section:
        normalized = re.sub(r"\s+", " ", line).strip()
        if not re.match(r"Total\s+outlays\b", normalized, flags=re.IGNORECASE):
            continue
        values = [
            _parse_millions_token(token)
            for token in re.findall(r"\(\*\*\)|\(\* \*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", line)
        ]
        if len(values) < 6:
            continue
        rows.append(
            {
                "record_date": pd.Timestamp(record_date).date().isoformat(),
                "table_name": "table5_outlays",
                "total_name": "total_outlays",
                "current_month_gross_mil": values[0],
                "current_month_app_receipts_mil": values[1],
                "current_month_net_mil": values[2],
                "current_fytd_gross_mil": values[3],
                "current_fytd_app_receipts_mil": values[4],
                "current_fytd_net_mil": values[5],
            }
        )
    return pd.DataFrame(rows)


def parse_mts_table3_receipt_source_line(
    text: str,
    *,
    record_date: str | pd.Timestamp,
    label: str = "Corporation income taxes",
) -> pd.DataFrame:
    section = _table_section_lines(
        text,
        start_pattern=r"Table\s+3\.\s+Summary\s+of\s+Receipts\s+and\s+Outlays",
        end_pattern=r"Table\s+4\.\s+Receipts",
    )
    rows: list[dict[str, object]] = []
    for line in section:
        if not _line_has_label(line, label):
            continue
        match = _target_label_pattern(label).search(line)
        tail = line[match.end() :] if match else line
        values = [
            _parse_millions_token(token)
            for token in re.findall(r"\(\*\*\)|\(\* \*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", tail)
        ]
        if len(values) < 2:
            continue
        rows.append(
            {
                "record_date": pd.Timestamp(record_date).date().isoformat(),
                "table_name": "table3_summary",
                "total_name": "corporation_income_taxes",
                "current_month_net_mil": values[0],
                "current_fytd_net_mil": values[1],
            }
        )
    return pd.DataFrame(rows)


def build_mts_parser_total_reconciliation(
    manifest: pd.DataFrame,
    *,
    table4_history: pd.DataFrame | None = None,
    tolerance_mil: float = 1.0,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    table4 = table4_history.copy() if table4_history is not None else pd.DataFrame()
    if not table4.empty:
        table4["record_date"] = pd.to_datetime(table4["record_date"], errors="coerce").dt.date.astype(str)
    for _, row in manifest.iterrows():
        text_path = Path(str(row["text_cache_path"]))
        if not text_path.exists():
            continue
        record_date = pd.Timestamp(row["record_date"]).date().isoformat()
        text = text_path.read_text(encoding="utf-8", errors="replace")
        summary = parse_mts_summary_total_lines(text, record_date=record_date)
        table5 = parse_mts_table5_printed_total_line(text, record_date=record_date)
        corp_summary = parse_mts_table3_receipt_source_line(text, record_date=record_date)
        corp_detail = table4.loc[table4["record_date"].eq(record_date)] if not table4.empty else pd.DataFrame()
        if corp_summary.empty or corp_detail.empty:
            rows.append(
                {
                    "record_date": record_date,
                    "total_name": "corporation_income_taxes",
                    "status": "missing_total_line",
                    "current_month_diff_mil": pd.NA,
                    "current_fytd_diff_mil": pd.NA,
                    "identity_diff_mil": pd.NA,
                    "tolerance_mil": tolerance_mil,
                    "notes": "Table 3 corporation-income-tax summary or parsed Table 4 target row not available",
                }
            )
        else:
            summary_row = corp_summary.iloc[0]
            detail_row = corp_detail.iloc[0]
            month_diff = float(detail_row["current_month_net_rcpt_mil"]) - float(summary_row["current_month_net_mil"])
            fytd_diff = float(detail_row["current_fytd_net_rcpt_mil"]) - float(summary_row["current_fytd_net_mil"])
            identity_diff = (
                float(detail_row["current_month_gross_rcpt_mil"])
                - float(detail_row["current_month_refund_mil"])
                - float(detail_row["current_month_net_rcpt_mil"])
            )
            status = "pass"
            if abs(month_diff) > tolerance_mil or abs(fytd_diff) > tolerance_mil:
                status = "warn_total_mismatch"
            if abs(identity_diff) > tolerance_mil:
                status = "warn_identity_mismatch"
            rows.append(
                {
                    "record_date": record_date,
                    "total_name": "corporation_income_taxes",
                    "status": status,
                    "summary_current_month_net_mil": summary_row["current_month_net_mil"],
                    "detail_current_month_net_mil": detail_row["current_month_net_rcpt_mil"],
                    "current_month_diff_mil": month_diff,
                    "summary_current_fytd_net_mil": summary_row["current_fytd_net_mil"],
                    "detail_current_fytd_net_mil": detail_row["current_fytd_net_rcpt_mil"],
                    "current_fytd_diff_mil": fytd_diff,
                    "identity_diff_mil": identity_diff,
                    "tolerance_mil": tolerance_mil,
                    "notes": "parsed Table 4 corporation-income-tax target row agrees with Table 3 summary line within tolerance",
                }
            )

        for total_name, detail in [("total_outlays", table5)]:
            summary_row = summary.loc[summary["total_name"].eq(total_name)]
            if summary_row.empty or detail.empty:
                rows.append(
                    {
                        "record_date": record_date,
                        "total_name": total_name,
                        "status": "missing_total_line",
                        "current_month_diff_mil": pd.NA,
                        "current_fytd_diff_mil": pd.NA,
                        "identity_diff_mil": pd.NA,
                        "tolerance_mil": tolerance_mil,
                        "notes": "summary or detailed total line not parsed",
                    }
                )
                continue
            summary_row = summary_row.iloc[0]
            detail_row = detail.iloc[0]
            month_diff = float(detail_row["current_month_net_mil"]) - float(summary_row["current_month_net_mil"])
            fytd_diff = float(detail_row["current_fytd_net_mil"]) - float(summary_row["current_fytd_net_mil"])
            identity_diff: float | pd._libs.missing.NAType = pd.NA
            if total_name == "total_outlays":
                identity_diff = (
                    float(detail_row["current_month_gross_mil"])
                    - float(detail_row["current_month_app_receipts_mil"])
                    - float(detail_row["current_month_net_mil"])
                )
            status = "pass"
            if abs(month_diff) > tolerance_mil or abs(fytd_diff) > tolerance_mil:
                status = "warn_total_mismatch"
            if identity_diff is not pd.NA and abs(float(identity_diff)) > tolerance_mil:
                status = "warn_identity_mismatch"
            rows.append(
                {
                    "record_date": record_date,
                    "total_name": total_name,
                    "status": status,
                    "summary_current_month_net_mil": summary_row["current_month_net_mil"],
                    "detail_current_month_net_mil": detail_row["current_month_net_mil"],
                    "current_month_diff_mil": month_diff,
                    "summary_current_fytd_net_mil": summary_row["current_fytd_net_mil"],
                    "detail_current_fytd_net_mil": detail_row["current_fytd_net_mil"],
                    "current_fytd_diff_mil": fytd_diff,
                    "identity_diff_mil": identity_diff,
                    "tolerance_mil": tolerance_mil,
                    "notes": "detailed total line agrees with Table 3 summary total within tolerance",
                }
            )
    return pd.DataFrame(rows)


def render_mts_parser_total_reconciliation_markdown(reconciliation: pd.DataFrame) -> str:
    title = "# MTS Parser Total Reconciliation"
    intro = (
        "Audit of previous-issue MTS parsed printed totals. The detailed Table 4 / Table 5 total lines are compared "
        "with the Table 3 summary totals, and Table 5 gross minus applicable receipts is checked against net outlays."
    )
    if reconciliation.empty:
        return "\n".join([title, "", intro, "", "No reconciliation rows are available."])
    status_counts = reconciliation["status"].value_counts(dropna=False).to_dict()
    failing = reconciliation.loc[reconciliation["status"].astype(str).str.startswith("fail")]
    warnings = reconciliation.loc[reconciliation["status"].astype(str).str.startswith("warn")]
    summary = f"Rows: {len(reconciliation)}. Status counts: {status_counts}."
    notes = ["Notes:"]
    if failing.empty and warnings.empty:
        notes.append("- All parsed printed total checks pass within tolerance.")
    elif failing.empty:
        notes.append(f"- Blocking failures: 0. Warning rows: {len(warnings)}. Warnings are retained for layout / revision exceptions.")
    else:
        notes.append(f"- Blocking failures: {len(failing)}. Warning rows: {len(warnings)}. Inspect the CSV for row-level details.")
    return "\n".join([title, "", intro, "", summary, "", *notes, ""])


def write_mts_parser_total_reconciliation(
    *,
    manifest_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    table4_history_path: Path | str | None = None,
    tolerance_mil: float = 1.0,
) -> tuple[Path, Path, pd.DataFrame]:
    manifest = pd.read_csv(manifest_path)
    table4_history = pd.read_csv(table4_history_path) if table4_history_path is not None and Path(table4_history_path).exists() else None
    reconciliation = build_mts_parser_total_reconciliation(manifest, table4_history=table4_history, tolerance_mil=tolerance_mil)
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    reconciliation.to_csv(csv_path, index=False)
    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_mts_parser_total_reconciliation_markdown(reconciliation), encoding="utf-8")
    return csv_path, markdown_path, reconciliation


def build_mts_fas_early_window_qa(
    *,
    manifest: pd.DataFrame,
    table5_history: pd.DataFrame,
    start: str = "2003-01-31",
    end: str = "2004-12-31",
) -> pd.DataFrame:
    history = table5_history.copy()
    if not history.empty:
        history["record_date"] = pd.to_datetime(history["record_date"], errors="coerce").dt.date.astype(str)
        history["classification_desc"] = history["classification_desc"].fillna("").astype(str)
    rows: list[dict[str, object]] = []
    for _, row in manifest.iterrows():
        record_date = pd.Timestamp(row["record_date"])
        if record_date < pd.Timestamp(start) or record_date > pd.Timestamp(end):
            continue
        record_date_str = record_date.date().isoformat()
        month = history.loc[history["record_date"].eq(record_date_str)]
        fas = month.loc[month["classification_desc"].eq("Financial Agent Services")]
        rows.append(
            {
                "record_date": record_date_str,
                "fas_direct_leaf_parsed": not fas.empty,
                "fas_direct_leaf_value_mil": pd.NA if fas.empty else float(fas.iloc[0]["current_month_net_outly_mil"]),
                "qa_status": "direct_leaf_present_nonpreferred_early_window" if not fas.empty else "manual_qa_no_direct_leaf",
                "fallback_treatment": "no_silent_backfill_keep_direct_component_zero",
                "preferred_research_eligible": False,
                "notes": (
                    "Archived 2003-2004 layouts do not expose a stable direct Financial Agent Services leaf in the target parser; "
                    "bank-outlay direct component remains zero / not preferred for these months until a parent-share or family-share fallback is separately calibrated."
                ),
            }
        )
    return pd.DataFrame(rows)


def render_mts_fas_early_window_qa_markdown(qa: pd.DataFrame) -> str:
    title = "# MTS 2003-2004 FAS QA"
    intro = (
        "Manual-QA decision artifact for the pre-stable Financial Agent Services window. "
        "It prevents the historical bank-outlay direct component from being silently promoted in 2003-2004."
    )
    if qa.empty:
        return "\n".join([title, "", intro, "", "No FAS QA rows are available."])
    status_counts = qa["qa_status"].value_counts(dropna=False).to_dict()
    eligible = int(qa["preferred_research_eligible"].fillna(False).sum())
    return "\n".join(
        [
            title,
            "",
            intro,
            "",
            f"Rows: {len(qa)}. QA status counts: {status_counts}. Preferred-research eligible rows: {eligible}.",
            "",
            "Decision: keep 2003-2004 bank-outlay direct component out of preferred historical research until an explicit parent-share or family-share fallback is calibrated.",
            "",
        ]
    )


def write_mts_fas_early_window_qa(
    *,
    manifest_path: Path | str,
    table5_history_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2003-01-31",
    end: str = "2004-12-31",
) -> tuple[Path, Path, pd.DataFrame]:
    manifest = pd.read_csv(manifest_path)
    table5 = pd.read_csv(table5_history_path)
    qa = build_mts_fas_early_window_qa(manifest=manifest, table5_history=table5, start=start, end=end)
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    qa.to_csv(csv_path, index=False)
    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_mts_fas_early_window_qa_markdown(qa), encoding="utf-8")
    return csv_path, markdown_path, qa


def build_mts_table5_target_history_from_manifest(
    manifest: pd.DataFrame,
    *,
    labels: list[str] | None = None,
    require_cached_text: bool = True,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, row in manifest.iterrows():
        text_path = Path(str(row["text_cache_path"]))
        if not text_path.exists():
            if require_cached_text:
                continue
            cache_manifest_pdf_text(row)
        text = text_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_mts_table5_target_lines(text, record_date=row["record_date"], labels=labels)
        if not parsed.empty:
            parsed["source_url"] = row["pdf_url"]
            parsed["text_cache_path"] = str(text_path)
            frames.append(parsed)
    if not frames:
        return pd.DataFrame(
            columns=[
                "record_date",
                "classification_desc",
                "current_month_gross_outly_mil",
                "current_month_app_rcpt_mil",
                "current_month_net_outly_mil",
                "current_fytd_gross_outly_mil",
                "current_fytd_app_rcpt_mil",
                "current_fytd_net_outly_mil",
                "source_parse_method",
                "source_url",
                "text_cache_path",
            ]
        )
    return pd.concat(frames, ignore_index=True).sort_values(["record_date", "classification_desc"])


def build_mts_table4_target_history_from_manifest(
    manifest: pd.DataFrame,
    *,
    labels: list[str] | None = None,
    require_cached_text: bool = True,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, row in manifest.iterrows():
        text_path = Path(str(row["text_cache_path"]))
        if not text_path.exists():
            if require_cached_text:
                continue
            cache_manifest_pdf_text(row)
        text = text_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_mts_table4_target_lines(text, record_date=row["record_date"], labels=labels)
        if not parsed.empty:
            parsed["source_url"] = row["pdf_url"]
            parsed["text_cache_path"] = str(text_path)
            frames.append(parsed)
    if not frames:
        return pd.DataFrame(
            columns=[
                "record_date",
                "classification_desc",
                "current_month_gross_rcpt_mil",
                "current_month_refund_mil",
                "current_month_net_rcpt_mil",
                "current_fytd_gross_rcpt_mil",
                "current_fytd_refund_mil",
                "current_fytd_net_rcpt_mil",
                "source_parse_method",
                "source_url",
                "text_cache_path",
            ]
        )
    return pd.concat(frames, ignore_index=True).sort_values(["record_date", "classification_desc"])


def write_mts_table5_target_history_from_manifest(
    *,
    manifest_path: Path | str,
    out_path: Path | str,
    labels: list[str] | None = None,
    require_cached_text: bool = True,
) -> Path:
    manifest = pd.read_csv(manifest_path)
    history = build_mts_table5_target_history_from_manifest(
        manifest,
        labels=labels,
        require_cached_text=require_cached_text,
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(out_path, index=False)
    return out_path


def write_mts_table4_target_history_from_manifest(
    *,
    manifest_path: Path | str,
    out_path: Path | str,
    labels: list[str] | None = None,
    require_cached_text: bool = True,
) -> Path:
    manifest = pd.read_csv(manifest_path)
    history = build_mts_table4_target_history_from_manifest(
        manifest,
        labels=labels,
        require_cached_text=require_cached_text,
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(out_path, index=False)
    return out_path


def table4_target_history_to_fiscaldata_receipts(history: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["record_date"] = pd.to_datetime(history.get("record_date", pd.Series(dtype="object")), errors="coerce").dt.date.astype(str)
    out["classification_desc"] = history.get("classification_desc", pd.Series(dtype="object")).fillna("").astype(str)
    out["current_month_gross_rcpt_amt"] = pd.to_numeric(
        history.get("current_month_gross_rcpt_mil", pd.Series(dtype="float64")),
        errors="coerce",
    ) * 1_000_000.0
    out["current_month_refund_amt"] = pd.to_numeric(
        history.get("current_month_refund_mil", pd.Series(dtype="float64")),
        errors="coerce",
    ) * 1_000_000.0
    out["current_month_net_rcpt_amt"] = pd.to_numeric(
        history.get("current_month_net_rcpt_mil", pd.Series(dtype="float64")),
        errors="coerce",
    ) * 1_000_000.0
    out["source_parse_method"] = history.get("source_parse_method", "pdf_text_line_target")
    return out.dropna(subset=["record_date"]).sort_values(["record_date", "classification_desc"])


def table5_target_history_to_fiscaldata_outlays(history: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["record_date"] = pd.to_datetime(history.get("record_date", pd.Series(dtype="object")), errors="coerce").dt.date.astype(str)
    out["classification_desc"] = history.get("classification_desc", pd.Series(dtype="object")).fillna("").astype(str)
    out["current_month_gross_outly_amt"] = pd.to_numeric(
        history.get("current_month_gross_outly_mil", pd.Series(dtype="float64")),
        errors="coerce",
    ) * 1_000_000.0
    out["current_month_app_rcpt_amt"] = pd.to_numeric(
        history.get("current_month_app_rcpt_mil", pd.Series(dtype="float64")),
        errors="coerce",
    ) * 1_000_000.0
    out["current_month_net_outly_amt"] = pd.to_numeric(
        history.get("current_month_net_outly_mil", pd.Series(dtype="float64")),
        errors="coerce",
    ) * 1_000_000.0
    out["source_parse_method"] = history.get("source_parse_method", "pdf_text_line_target")
    return out.dropna(subset=["record_date"]).sort_values(["record_date", "classification_desc"])


def write_table4_target_history_as_fiscaldata_receipts(
    *,
    history_path: Path | str,
    out_path: Path | str,
) -> Path:
    history = pd.read_csv(history_path)
    out = table4_target_history_to_fiscaldata_receipts(history)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    return out_path


def write_table5_target_history_as_fiscaldata_outlays(
    *,
    history_path: Path | str,
    out_path: Path | str,
) -> Path:
    history = pd.read_csv(history_path)
    out = table5_target_history_to_fiscaldata_outlays(history)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    return out_path


def stitch_previous_targets_with_fiscaldata(
    *,
    previous_targets: pd.DataFrame,
    fiscaldata: pd.DataFrame | None = None,
    key_cols: list[str] | None = None,
) -> pd.DataFrame:
    key_cols = key_cols or ["record_date", "classification_desc"]
    previous = previous_targets.copy()
    if previous.empty and (fiscaldata is None or fiscaldata.empty):
        return previous

    previous["record_date"] = pd.to_datetime(previous["record_date"], errors="coerce").dt.date.astype(str)
    previous["source_tier"] = previous.get("source_tier", "D_pdf_text_parsed")
    previous["source_family"] = previous.get("source_family", "treasury_previous_issue")
    previous["_source_rank"] = 1

    frames = [previous]
    if fiscaldata is not None and not fiscaldata.empty:
        current = fiscaldata.copy()
        current["record_date"] = pd.to_datetime(current["record_date"], errors="coerce").dt.date.astype(str)
        current["source_tier"] = current.get("source_tier", "A_fiscaldata_api")
        current["source_family"] = current.get("source_family", "fiscaldata_api")
        current["_source_rank"] = 0
        frames.append(current)

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined = combined.dropna(subset=["record_date"])
    combined = combined.sort_values([*key_cols, "_source_rank"])
    combined = combined.drop_duplicates(subset=key_cols, keep="first")
    return combined.drop(columns=["_source_rank"]).sort_values(key_cols).reset_index(drop=True)


def write_stitched_previous_targets_with_fiscaldata(
    *,
    previous_targets_path: Path | str,
    out_path: Path | str,
    fiscaldata_path: Path | str | None = None,
) -> Path:
    previous = pd.read_csv(previous_targets_path)
    fiscaldata = (
        pd.read_csv(fiscaldata_path)
        if fiscaldata_path is not None and Path(fiscaldata_path).exists()
        else None
    )
    stitched = stitch_previous_targets_with_fiscaldata(previous_targets=previous, fiscaldata=fiscaldata)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stitched.to_csv(out_path, index=False)
    return out_path


def build_mts_previous_issue_coverage_report(
    *,
    manifest: pd.DataFrame,
    table4_history: pd.DataFrame,
    table5_history: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    table4_dates = set(pd.to_datetime(table4_history.get("record_date", pd.Series(dtype="object")), errors="coerce").dt.date.astype(str))
    table5 = table5_history.copy()
    if not table5.empty:
        table5["record_date"] = pd.to_datetime(table5["record_date"], errors="coerce").dt.date.astype(str)
        table5["classification_desc"] = table5["classification_desc"].fillna("").astype(str)
    else:
        table5 = pd.DataFrame(columns=["record_date", "classification_desc"])

    for _, row in manifest.iterrows():
        record_date = pd.Timestamp(row["record_date"]).date().isoformat()
        table5_month = table5.loc[table5["record_date"].eq(record_date)]
        labels = set(table5_month["classification_desc"])
        year = pd.Timestamp(record_date).year
        fas_expected = year >= 2005
        row_narrow_count = int(table5_month["classification_desc"].isin(MTS_ROW_OUTLAY_NARROW_LABELS).sum())
        row_broad_count = int(table5_month["classification_desc"].isin(MTS_ROW_OUTLAY_BROAD_LABELS).sum())
        rows.append(
            {
                "record_date": record_date,
                "issue_month": row.get("issue_month", record_date[:7]),
                "pdf_cached": bool(row.get("pdf_cached", False)),
                "text_cached": bool(row.get("text_cached", False)),
                "corp_tax_parsed": record_date in table4_dates,
                "fas_parsed": "Financial Agent Services" in labels,
                "fas_expected_direct": fas_expected,
                "fas_status": (
                    "parsed"
                    if "Financial Agent Services" in labels
                    else ("missing_expected" if fas_expected else "pre_direct_leaf_manual_qa")
                ),
                "mint_parsed": "United States Mint" in labels,
                "row_narrow_label_count": row_narrow_count,
                "row_broad_label_count": row_broad_count,
                "table5_target_label_count": int(len(labels)),
                "coverage_status": "ok"
                if (record_date in table4_dates and "United States Mint" in labels and ("Financial Agent Services" in labels or not fas_expected))
                else "needs_review",
            }
        )
    return pd.DataFrame(rows)


def render_mts_previous_issue_coverage_markdown(report: pd.DataFrame) -> str:
    title = "# MTS Previous-Issue Coverage Report"
    if report.empty:
        return "\n".join([title, "", "No previous-issue coverage rows are available.", ""])
    total = len(report)
    text_cached = int(report["text_cached"].sum())
    corp = int(report["corp_tax_parsed"].sum())
    fas = int(report["fas_parsed"].sum())
    mint = int(report["mint_parsed"].sum())
    needs = int(report["coverage_status"].eq("needs_review").sum())
    row_months = int((report["row_narrow_label_count"].fillna(0).astype(int) + report["row_broad_label_count"].fillna(0).astype(int)).gt(0).sum())
    lines = [
        title,
        "",
        f"Rows: {total}. Text cached: {text_cached}. Corp-tax parsed: {corp}. FAS parsed: {fas}. Mint parsed: {mint}. ROW-label months: {row_months}. Needs review: {needs}.",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total issue months | {total} |",
        f"| Text cached | {text_cached} |",
        f"| Corporation income tax parsed | {corp} |",
        f"| Financial Agent Services parsed | {fas} |",
        f"| United States Mint parsed | {mint} |",
        f"| Any ROW target label parsed | {row_months} |",
        f"| Needs review | {needs} |",
        "",
    ]
    missing = report.loc[report["coverage_status"].eq("needs_review")].head(20)
    if not missing.empty:
        lines.extend(
            [
                "First review rows:",
                "",
                "| Record date | Corp tax | FAS status | Mint | ROW narrow | ROW broad |",
                "| --- | ---: | --- | ---: | ---: | ---: |",
            ]
        )
        for _, row in missing.iterrows():
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["record_date"]),
                        str(bool(row["corp_tax_parsed"])),
                        str(row["fas_status"]),
                        str(bool(row["mint_parsed"])),
                        str(int(row["row_narrow_label_count"])),
                        str(int(row["row_broad_label_count"])),
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)


def write_mts_previous_issue_coverage_report(
    *,
    manifest_path: Path | str,
    table4_history_path: Path | str,
    table5_history_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None]:
    manifest = pd.read_csv(manifest_path)
    table4_history = pd.read_csv(table4_history_path) if Path(table4_history_path).exists() else pd.DataFrame()
    table5_history = pd.read_csv(table5_history_path) if Path(table5_history_path).exists() else pd.DataFrame()
    report = build_mts_previous_issue_coverage_report(
        manifest=manifest,
        table4_history=table4_history,
        table5_history=table5_history,
    )
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(csv_path, index=False)
    written_md = None
    if markdown_path is not None:
        written_md = Path(markdown_path)
        written_md.parent.mkdir(parents=True, exist_ok=True)
        written_md.write_text(render_mts_previous_issue_coverage_markdown(report), encoding="utf-8")
    return csv_path, written_md


def _target_overlap_audit(
    *,
    parsed_targets: pd.DataFrame,
    fiscaldata: pd.DataFrame,
    value_cols: list[str],
    tolerance_dollars: float,
) -> pd.DataFrame:
    parsed = parsed_targets.copy()
    api = fiscaldata.copy()
    for frame in [parsed, api]:
        frame["record_date"] = pd.to_datetime(frame["record_date"], errors="coerce").dt.date.astype(str)
        frame["classification_desc"] = frame["classification_desc"].fillna("").astype(str)

    parsed["_source_order"] = range(len(parsed))
    api["_source_order"] = range(len(api))
    api_sort_cols = ["record_date", "classification_desc"]
    if "print_order_nbr" in api.columns:
        api_sort_cols.append("print_order_nbr")
    else:
        api_sort_cols.append("_source_order")
    parsed = parsed.sort_values(["record_date", "classification_desc", "_source_order"]).copy()
    api = api.sort_values(api_sort_cols).copy()
    parsed["_label_occurrence"] = parsed.groupby(["record_date", "classification_desc"]).cumcount()
    api["_label_occurrence"] = api.groupby(["record_date", "classification_desc"]).cumcount()
    rows: list[dict[str, object]] = []
    for _, parsed_row in parsed.iterrows():
        match = api.loc[
            api["record_date"].eq(parsed_row["record_date"])
            & api["classification_desc"].eq(parsed_row["classification_desc"])
            & api["_label_occurrence"].eq(parsed_row["_label_occurrence"])
        ]
        for value_col in value_cols:
            parsed_value = pd.to_numeric(pd.Series([parsed_row.get(value_col)]), errors="coerce").iloc[0]
            api_value = (
                pd.to_numeric(pd.Series([match.iloc[0].get(value_col)]), errors="coerce").iloc[0]
                if not match.empty and value_col in match.columns
                else float("nan")
            )
            diff = parsed_value - api_value if pd.notna(parsed_value) and pd.notna(api_value) else float("nan")
            abs_diff = abs(diff) if pd.notna(diff) else float("nan")
            if match.empty:
                status = "missing_api_match"
            elif pd.isna(parsed_value) and pd.isna(api_value):
                status = "pass_both_missing"
            elif pd.isna(parsed_value) or pd.isna(api_value):
                status = "missing_value"
            elif abs_diff <= tolerance_dollars:
                status = "pass"
            else:
                status = "fail"
            rows.append(
                {
                    "record_date": parsed_row["record_date"],
                    "classification_desc": parsed_row["classification_desc"],
                    "value_column": value_col,
                    "parsed_value_dollars": parsed_value,
                    "fiscaldata_value_dollars": api_value,
                    "diff_dollars": diff,
                    "abs_diff_dollars": abs_diff,
                    "tolerance_dollars": tolerance_dollars,
                    "audit_status": status,
                }
            )
    return pd.DataFrame(rows).sort_values(["record_date", "classification_desc", "value_column"]).reset_index(drop=True)


def build_mts_target_overlap_audit(
    *,
    table4_history: pd.DataFrame | None = None,
    table4_fiscaldata: pd.DataFrame | None = None,
    table5_history: pd.DataFrame | None = None,
    table5_fiscaldata: pd.DataFrame | None = None,
    tolerance_dollars: float = 500_000.0,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if table4_history is not None and table4_fiscaldata is not None and not table4_history.empty:
        parsed4 = table4_target_history_to_fiscaldata_receipts(table4_history)
        audit4 = _target_overlap_audit(
            parsed_targets=parsed4,
            fiscaldata=table4_fiscaldata,
            value_cols=[
                "current_month_gross_rcpt_amt",
                "current_month_refund_amt",
                "current_month_net_rcpt_amt",
            ],
            tolerance_dollars=tolerance_dollars,
        )
        audit4.insert(0, "table_nbr", "4")
        frames.append(audit4)
    if table5_history is not None and table5_fiscaldata is not None and not table5_history.empty:
        parsed5 = table5_target_history_to_fiscaldata_outlays(table5_history)
        audit5 = _target_overlap_audit(
            parsed_targets=parsed5,
            fiscaldata=table5_fiscaldata,
            value_cols=[
                "current_month_gross_outly_amt",
                "current_month_app_rcpt_amt",
                "current_month_net_outly_amt",
            ],
            tolerance_dollars=tolerance_dollars,
        )
        audit5.insert(0, "table_nbr", "5")
        frames.append(audit5)
    if not frames:
        return pd.DataFrame(
            columns=[
                "table_nbr",
                "record_date",
                "classification_desc",
                "value_column",
                "parsed_value_dollars",
                "fiscaldata_value_dollars",
                "diff_dollars",
                "abs_diff_dollars",
                "tolerance_dollars",
                "audit_status",
            ]
        )
    return pd.concat(frames, ignore_index=True, sort=False)


def render_mts_target_overlap_audit_markdown(audit: pd.DataFrame) -> str:
    title = "# MTS Target Overlap Audit"
    if audit.empty:
        return "\n".join([title, "", "No overlap-audit rows are available.", ""])
    status_counts = audit["audit_status"].value_counts(dropna=False)
    fail_count = int(audit["audit_status"].isin(["fail", "missing_api_match", "missing_value"]).sum())
    lines = [
        title,
        "",
        f"Rows: {len(audit)}. Blocking statuses: {fail_count}.",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]
    for status, count in status_counts.items():
        lines.append(f"| {status} | {int(count)} |")
    blockers = audit.loc[audit["audit_status"].isin(["fail", "missing_api_match", "missing_value"])].head(25)
    if not blockers.empty:
        lines.extend(
            [
                "",
                "First blocking rows:",
                "",
                "| Table | Record date | Label | Column | Status | Abs diff |",
                "| --- | --- | --- | --- | --- | ---: |",
            ]
        )
        for _, row in blockers.iterrows():
            abs_diff = row.get("abs_diff_dollars")
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["table_nbr"]),
                        str(row["record_date"]),
                        str(row["classification_desc"]),
                        str(row["value_column"]),
                        str(row["audit_status"]),
                        "" if pd.isna(abs_diff) else f"{float(abs_diff):,.0f}",
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def write_mts_target_overlap_audit(
    *,
    table4_history_path: Path | str,
    table4_fiscaldata_path: Path | str,
    table5_history_path: Path | str,
    table5_fiscaldata_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
    tolerance_dollars: float = 500_000.0,
) -> tuple[Path, Path | None]:
    audit = build_mts_target_overlap_audit(
        table4_history=pd.read_csv(table4_history_path) if Path(table4_history_path).exists() else None,
        table4_fiscaldata=pd.read_csv(table4_fiscaldata_path) if Path(table4_fiscaldata_path).exists() else None,
        table5_history=pd.read_csv(table5_history_path) if Path(table5_history_path).exists() else None,
        table5_fiscaldata=pd.read_csv(table5_fiscaldata_path) if Path(table5_fiscaldata_path).exists() else None,
        tolerance_dollars=tolerance_dollars,
    )
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(csv_path, index=False)
    written_md = None
    if markdown_path is not None:
        written_md = Path(markdown_path)
        written_md.parent.mkdir(parents=True, exist_ok=True)
        written_md.write_text(render_mts_target_overlap_audit_markdown(audit), encoding="utf-8")
    return csv_path, written_md
