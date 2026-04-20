from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pandas as pd

from .config import USER_AGENT

XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MONTH_NAMES = {
    1: "JANUARY",
    2: "FEBRUARY",
    3: "MARCH",
    4: "APRIL",
    5: "MAY",
    6: "JUNE",
    7: "JULY",
    8: "AUGUST",
    9: "SEPTEMBER",
    10: "OCTOBER",
    11: "NOVEMBER",
    12: "DECEMBER",
}


def state_niv_issuance_url(*, fiscal_year: int, month: int) -> str:
    calendar_year = fiscal_year - 1 if month >= 10 else fiscal_year
    month_name = MONTH_NAMES[month]
    return (
        "https://travel.state.gov/content/dam/visas/Statistics/Non-Immigrant-Statistics/MonthlyNIVIssuances/"
        f"Excel/FY{fiscal_year}/{month_name}%20{calendar_year}%20-%20NIV%20Issuances%20by%20Nationality%20and%20Visa%20Class.xlsx"
    )


def state_iv_issuance_url(*, fiscal_year: int, month: int) -> str:
    calendar_year = fiscal_year - 1 if month >= 10 else fiscal_year
    month_name = MONTH_NAMES[month]
    return (
        "https://travel.state.gov/content/dam/visas/Statistics/Immigrant-Statistics/MonthlyIVIssuances/"
        f"Excel/FY{fiscal_year}/{month_name}%20{calendar_year}%20-%20IV%20Issuances%20by%20FSC%20or%20Place%20of%20Birth%20and%20Visa%20Class.xlsx"
    )


def _download(url: str, out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def _xlsx_cells(path: Path | str) -> dict[str, str]:
    out: dict[str, str] = {}
    with ZipFile(path) as zf:
        shared_strings: list[str] = []
        shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in shared_root.findall("x:si", XML_NS):
            shared_strings.append(
                "".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
            )

        sheet_root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        for row in sheet_root.find("x:sheetData", XML_NS).findall("x:row", XML_NS):
            for cell in row.findall("x:c", XML_NS):
                value = cell.find("x:v", XML_NS)
                if value is None:
                    continue
                text = value.text or ""
                if cell.attrib.get("t") == "s":
                    text = shared_strings[int(text)]
                out[cell.attrib["r"]] = text
    return out


def _cell_column(ref: str) -> str:
    letters = []
    for ch in ref:
        if ch.isalpha():
            letters.append(ch)
        else:
            break
    return "".join(letters)


def _sum_issuance_column(path: Path | str) -> int:
    total = 0
    for ref, value in _xlsx_cells(path).items():
        if _cell_column(ref) != "C":
            continue
        try:
            total += int(float(value))
        except ValueError:
            continue
    return total


def build_state_visa_monthly_issuances(
    *,
    cache_dir: Path | str,
    fiscal_year_start: int = 2023,
    fiscal_year_end: int = 2025,
) -> pd.DataFrame:
    cache_dir = Path(cache_dir)
    rows: list[dict[str, object]] = []

    for fiscal_year in range(fiscal_year_start, fiscal_year_end + 1):
        for month in [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
            calendar_year = fiscal_year - 1 if month >= 10 else fiscal_year
            date = pd.Timestamp(year=calendar_year, month=month, day=1) + pd.offsets.MonthEnd(0)

            niv_url = state_niv_issuance_url(fiscal_year=fiscal_year, month=month)
            niv_path = cache_dir / Path(niv_url).name
            iv_url = state_iv_issuance_url(fiscal_year=fiscal_year, month=month)
            iv_path = cache_dir / Path(iv_url).name
            try:
                _download(niv_url, niv_path)
                _download(iv_url, iv_path)
            except HTTPError as exc:
                if exc.code == 404:
                    continue
                raise

            rows.append(
                {
                    "date": date,
                    "fiscal_year": fiscal_year,
                    "niv_issuances_total": _sum_issuance_column(niv_path),
                    "iv_issuances_total": _sum_issuance_column(iv_path),
                    "niv_source_url": niv_url,
                    "iv_source_url": iv_url,
                }
            )

    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def write_state_visa_monthly_issuances(
    *,
    out_path: Path | str,
    cache_dir: Path | str,
    fiscal_year_start: int = 2023,
    fiscal_year_end: int = 2025,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame = build_state_visa_monthly_issuances(
        cache_dir=cache_dir,
        fiscal_year_start=fiscal_year_start,
        fiscal_year_end=fiscal_year_end,
    )
    frame.to_csv(out_path, index=False)
    return out_path
