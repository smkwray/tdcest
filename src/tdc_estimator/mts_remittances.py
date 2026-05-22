from __future__ import annotations

import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

from .config import USER_AGENT

MTS_FED_REMITTANCE_LABEL = "Deposits of earnings by Federal Reserve Banks"
MTS_STATIC_PDF_URL = (
    "https://fiscaldata.treasury.gov/static-data/published-reports/mts/"
    "MonthlyTreasuryStatement_{yyyymm}.pdf"
)


def _month_range(start: str | pd.Timestamp, end: str | pd.Timestamp) -> list[pd.Timestamp]:
    start_month = pd.Timestamp(start).to_period("M").to_timestamp("M")
    end_month = pd.Timestamp(end).to_period("M").to_timestamp("M")
    return list(pd.date_range(start_month, end_month, freq="ME"))


def _fetch_bytes(url: str, timeout: int = 90) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def mts_pdf_url(month_end: pd.Timestamp) -> str:
    return MTS_STATIC_PDF_URL.format(yyyymm=month_end.strftime("%Y%m"))


def pdf_bytes_to_text(payload: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "mts.pdf"
        txt_path = Path(tmp) / "mts.txt"
        pdf_path.write_bytes(payload)
        subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)], check=True)
        return txt_path.read_text(encoding="utf-8", errors="replace")


def _parse_millions_token(token: str) -> float | None:
    cleaned = (
        str(token)
        .replace(",", "")
        .replace("−", "-")
        .replace("—", "-")
        .replace("......", "")
        .strip()
    )
    if cleaned in {"(**)", "(* *)", "**"}:
        return 0.0
    if not cleaned or cleaned in {"(*", "*)"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_fed_remittance_receipt_from_mts_text(text: str) -> float:
    for line in text.splitlines():
        normalized_line = re.sub(r"\s+", " ", line).lower()
        if not (
            "deposit" in normalized_line
            and "earnings" in normalized_line
            and "federal reserve" in normalized_line
        ):
            continue
        tail = re.split(r"Federal Reserve(?: Banks| System)?", line, flags=re.IGNORECASE, maxsplit=1)[-1]
        values = [
            _parse_millions_token(token)
            for token in re.findall(r"\(\*\*\)|(?<!\.)\.{6}(?!\.)|(?:-|\u2212)?[\d,]+(?:\.\d+)?", tail)
        ]
        if len(values) < 3:
            raise ValueError(f"Could not parse current-month net receipts from MTS line: {line!r}")
        current_month_net = values[2]
        if current_month_net is None:
            return 0.0
        return float(current_month_net)
    raise ValueError(f"Could not find MTS line: {MTS_FED_REMITTANCE_LABEL}")


def build_monthly_fed_remittance_mts(
    *,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    cache_dir: Path | str | None = None,
) -> pd.DataFrame:
    cache = Path(cache_dir) if cache_dir is not None else None
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for month_end in _month_range(start, end):
        url = mts_pdf_url(month_end)
        payload: bytes
        cache_path = cache / f"MonthlyTreasuryStatement_{month_end:%Y%m}.pdf" if cache is not None else None
        if cache_path is not None and cache_path.exists():
            payload = cache_path.read_bytes()
        else:
            payload = _fetch_bytes(url)
            if cache_path is not None:
                cache_path.write_bytes(payload)
        text = pdf_bytes_to_text(payload)
        rows.append(
            {
                "date": month_end,
                "value": parse_fed_remittance_receipt_from_mts_text(text),
                "source_url": url,
                "source_line": MTS_FED_REMITTANCE_LABEL,
            }
        )
    return pd.DataFrame(rows)


def monthly_fed_remittance_from_mts_receipts_csv(path: Path | str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"record_date", "classification_desc", "current_month_net_rcpt_amt"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"MTS receipts file {path} is missing required columns: {missing}")
    mask = (
        frame["classification_desc"].astype(str).str.lower().str.contains("deposit")
        & frame["classification_desc"].astype(str).str.lower().str.contains("earnings")
        & frame["classification_desc"].astype(str).str.lower().str.contains("federal reserve")
    )
    out = frame.loc[mask, ["record_date", "current_month_net_rcpt_amt"]].copy()
    out["date"] = pd.to_datetime(out["record_date"], errors="coerce")
    out["value"] = pd.to_numeric(out["current_month_net_rcpt_amt"], errors="coerce").fillna(0.0) / 1_000_000.0
    out = out.dropna(subset=["date"]).sort_values("date")
    return out.loc[:, ["date", "value"]]


def write_fed_remittance_mts_support(
    *,
    out_path: Path | str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    cache_dir: Path | str | None = None,
    mts_receipts_path: Path | str | None = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    api_monthly = (
        monthly_fed_remittance_from_mts_receipts_csv(mts_receipts_path)
        if mts_receipts_path is not None and Path(mts_receipts_path).exists()
        else pd.DataFrame(columns=["date", "value"])
    )
    api_monthly = api_monthly.loc[
        pd.to_datetime(api_monthly["date"]).between(pd.Timestamp(start), pd.Timestamp(end))
    ].copy()
    pdf_end = pd.Timestamp(end)
    if not api_monthly.empty:
        first_api_month = pd.to_datetime(api_monthly["date"]).min()
        pdf_end = min(pdf_end, (first_api_month - pd.offsets.MonthEnd()).normalize())
    if pd.Timestamp(start) <= pdf_end:
        pdf_monthly = build_monthly_fed_remittance_mts(start=start, end=pdf_end, cache_dir=cache_dir)
    else:
        pdf_monthly = pd.DataFrame(columns=["date", "value", "source_url", "source_line"])

    monthly = pd.concat([pdf_monthly, api_monthly], ignore_index=True, sort=False)
    monthly["date"] = pd.to_datetime(monthly["date"], errors="coerce")
    monthly = monthly.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date")
    monthly.loc[:, ["date", "value"]].to_csv(out_path, index=False)
    monthly.to_csv(out_path.with_name(out_path.stem + "_monthly_audit.csv"), index=False)
    return out_path
