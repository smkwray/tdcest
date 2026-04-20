from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd


XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CURRENT_COMBINED_STATEMENT_PAGE = "https://fiscal.treasury.gov/accounting/combined-statement-of-receipts/current"
TREASURY_BASE_URL = "https://fiscal.treasury.gov"


@dataclass(frozen=True)
class CombinedStatementSheetSpec:
    fiscal_year: int
    source_department: str
    page_label: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class CombinedStatementWatchItem:
    fiscal_year: int
    source_department: str
    aid_cd: str
    main_cd: str
    title_contains: str
    combined_statement_match_scope: str
    combined_statement_metric_basis: str


DEFAULT_SHEET_SPECS = [
    CombinedStatementSheetSpec(
        fiscal_year=2025,
        source_department="state",
        page_label="Department of State",
        url="https://fiscal.treasury.gov/system/files/files/reports-statements/combined-statement/cs2025/c34.xlsx",
    ),
    CombinedStatementSheetSpec(
        fiscal_year=2025,
        source_department="treasury",
        page_label="Department of the Treasury",
        url="https://fiscal.treasury.gov/system/files/files/reports-statements/combined-statement/cs2025/c40.xlsx",
    ),
    CombinedStatementSheetSpec(
        fiscal_year=2025,
        source_department="homeland_security",
        page_label="Department of Homeland Security",
        url="https://fiscal.treasury.gov/system/files/files/reports-statements/combined-statement/cs2025/c18.xlsx",
    ),
    CombinedStatementSheetSpec(
        fiscal_year=2025,
        source_department="international_assistance",
        page_label="International Assistance Programs",
        url="https://fiscal.treasury.gov/system/files/files/reports-statements/combined-statement/cs2025/c04.xlsx",
    ),
    CombinedStatementSheetSpec(
        fiscal_year=2025,
        source_department="independent_agencies",
        page_label="Independent Agencies",
        url="https://fiscal.treasury.gov/system/files/files/reports-statements/combined-statement/cs2025/c55.xlsx",
    ),
]


DEFAULT_WATCHLIST = [
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="state",
        aid_cd="19",
        main_cd="5713",
        title_contains="Consular and Border Security Programs",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="treasury",
        aid_cd="20",
        main_cd="5590",
        title_contains="Financial Research Fund",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="treasury",
        aid_cd="20",
        main_cd="8413",
        title_contains="Assessment Funds, Office of the Comptroller of the Currency",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="treasury",
        aid_cd="20",
        main_cd="5697",
        title_contains="Treasury Forfeiture Fund",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="homeland_security",
        aid_cd="70",
        main_cd="5088",
        title_contains="Immigration Examination Fees",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="homeland_security",
        aid_cd="70",
        main_cd="5087",
        title_contains="Immigration User Fee",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="homeland_security",
        aid_cd="70",
        main_cd="5543",
        title_contains="International Registered Traveler Program Fund",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="homeland_security",
        aid_cd="70",
        main_cd="5702",
        title_contains="9-11 Response and Biometric Exit Account",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="international_assistance",
        aid_cd="11",
        main_cd="8242",
        title_contains="Advances, Foreign Military Sales",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="international_assistance",
        aid_cd="72",
        main_cd="8502",
        title_contains="United States Dollars Advanced from Foreign Governments",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="international_assistance",
        aid_cd="11",
        main_cd="8246",
        title_contains="Advances from Foreign Governments",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
    CombinedStatementWatchItem(
        fiscal_year=2025,
        source_department="independent_agencies",
        aid_cd="51",
        main_cd="4596",
        title_contains="Deposit Insurance Fund",
        combined_statement_match_scope="main_account_rollup",
        combined_statement_metric_basis="appropriations_and_transfers_mil",
    ),
]


def _normalize_code(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "null":
        return ""
    if text.isdigit():
        return str(int(text))
    return text


def _col_letters(ref: str) -> str:
    return "".join(ch for ch in ref if ch.isalpha())


def _download_if_needed(url: str, cache_path: Path) -> Path:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not cache_path.exists():
        urllib.request.urlretrieve(url, cache_path)
    return cache_path


def _absolute_combined_statement_url(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"{TREASURY_BASE_URL}{href}"
    return f"{TREASURY_BASE_URL}/{href}"


def discover_current_combined_statement_excel_links(
    current_page_url: str = CURRENT_COMBINED_STATEMENT_PAGE,
) -> dict[str, str]:
    with urllib.request.urlopen(current_page_url) as response:
        html = response.read().decode("utf-8", "ignore")

    pattern = re.compile(
        r"<p>(?P<label>[^<]+)</p>\s*<ul[^>]*>.*?<a href=\"(?P<href>[^\"]+\.xlsx)\"",
        flags=re.IGNORECASE | re.DOTALL,
    )
    links: dict[str, str] = {}
    for match in pattern.finditer(html):
        label = " ".join(match.group("label").split())
        href = _absolute_combined_statement_url(match.group("href"))
        links[label] = href
    return links


def _resolve_sheet_url(
    spec: CombinedStatementSheetSpec,
    discovered_links: dict[str, str] | None,
) -> str:
    if spec.page_label and discovered_links and spec.page_label in discovered_links:
        return discovered_links[spec.page_label]
    if spec.url:
        return spec.url
    raise ValueError(
        f"Unable to resolve Combined Statement sheet URL for {spec.source_department} "
        f"(page_label={spec.page_label!r}, fiscal_year={spec.fiscal_year})."
    )


def _load_xlsx_rows(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as zf:
        shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        shared_strings = [
            "".join(t.text or "" for t in si.iterfind(".//x:t", XML_NS))
            for si in shared_root.findall("x:si", XML_NS)
        ]
        sheet_root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

    rows: list[dict[str, str]] = []
    for row in sheet_root.find("x:sheetData", XML_NS):
        values: dict[str, str] = {}
        for cell in row.findall("x:c", XML_NS):
            col = _col_letters(cell.attrib["r"])
            kind = cell.attrib.get("t")
            raw = cell.find("x:v", XML_NS)
            if raw is None:
                value = ""
            elif kind == "s":
                value = shared_strings[int(raw.text)]
            else:
                value = raw.text or ""
            values[col] = value
        rows.append(values)
    return rows


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).replace(",", "").strip()
    if not text or text == "----------":
        return None
    try:
        return float(text) / 1_000_000.0
    except ValueError:
        return None


def _is_heading(title: str, aid_cd: str, main_cd: str, sub_cd: str) -> bool:
    if not title:
        return False
    if any([aid_cd, main_cd, sub_cd]):
        return False
    title_l = title.lower()
    return title_l not in {"fund resources:", "undisbursed funds", "intragovernmental funds", "subtotal"}


def _extract_sheet_accounts(spec: CombinedStatementSheetSpec, cache_path: Path) -> pd.DataFrame:
    rows = _load_xlsx_rows(cache_path)
    current_title = ""
    extracted: list[dict[str, object]] = []
    for row in rows:
        title = (row.get("A") or "").strip()
        aid_cd = _normalize_code(row.get("D"))
        main_cd = _normalize_code(row.get("E"))
        sub_cd = _normalize_code(row.get("F"))
        if _is_heading(title, aid_cd, main_cd, sub_cd):
            current_title = title
        if not aid_cd or not main_cd:
            continue
        extracted.append(
            {
                "fiscal_year": spec.fiscal_year,
                "source_department": spec.source_department,
                "combined_statement_title": current_title,
                "period_of_availability": (row.get("B") or "").strip(),
                "ata": _normalize_code(row.get("C")),
                "aid_cd": aid_cd,
                "a_cd": "",
                "main_cd": main_cd,
                "sub_cd": sub_cd,
                "beginning_balance_mil": _safe_float(row.get("G")),
                "appropriations_and_transfers_mil": _safe_float(row.get("H")),
                "other_transactions_mil": _safe_float(row.get("I")),
                "outlays_mil": _safe_float(row.get("J")),
                "balances_withdrawn_mil": _safe_float(row.get("K")),
                "ending_balance_mil": _safe_float(row.get("L")),
            }
        )
    return pd.DataFrame(extracted)


def build_combined_statement_receipt_accounts_support(
    *,
    cache_dir: Path | str,
    sheet_specs: list[CombinedStatementSheetSpec] | None = None,
    watchlist: list[CombinedStatementWatchItem] | None = None,
) -> pd.DataFrame:
    cache_dir = Path(cache_dir)
    specs = DEFAULT_SHEET_SPECS if sheet_specs is None else sheet_specs
    items = DEFAULT_WATCHLIST if watchlist is None else watchlist
    discovered_links: dict[str, str] | None = None
    if any(spec.page_label for spec in specs):
        try:
            discovered_links = discover_current_combined_statement_excel_links()
        except Exception:
            discovered_links = None

    parsed: list[pd.DataFrame] = []
    for spec in specs:
        sheet_url = _resolve_sheet_url(spec, discovered_links)
        cache_path = cache_dir / f"combined_statement__{spec.fiscal_year}_{spec.source_department}.xlsx"
        _download_if_needed(sheet_url, cache_path)
        parsed.append(_extract_sheet_accounts(spec, cache_path))

    if not parsed:
        return pd.DataFrame()

    full = pd.concat(parsed, ignore_index=True)
    rows: list[dict[str, object]] = []
    for item in items:
        matches = full.loc[
            full["fiscal_year"].eq(item.fiscal_year)
            & full["source_department"].eq(item.source_department)
            & full["aid_cd"].eq(item.aid_cd)
            & full["main_cd"].eq(item.main_cd)
            & full["combined_statement_title"].str.contains(item.title_contains, case=False, regex=False, na=False)
        ].copy()
        if matches.empty:
            continue
        chosen = matches.sort_values(["sub_cd", "appropriations_and_transfers_mil"], ascending=[True, False]).iloc[0]
        rows.append(
            {
                "fiscal_year": int(chosen["fiscal_year"]),
                "aid_cd": chosen["aid_cd"],
                "a_cd": chosen["a_cd"],
                "main_cd": chosen["main_cd"],
                "sub_cd": chosen["sub_cd"],
                "combined_statement_title": chosen["combined_statement_title"],
                "combined_statement_amt_mil": chosen["appropriations_and_transfers_mil"],
                "combined_statement_metric_basis": item.combined_statement_metric_basis,
                "combined_statement_match_scope": item.combined_statement_match_scope,
                "source_department": chosen["source_department"],
                "period_of_availability": chosen["period_of_availability"],
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["fiscal_year", "aid_cd", "main_cd", "sub_cd"], ascending=[False, True, True, True]
    )


def write_combined_statement_receipt_accounts_support(
    *,
    out_path: Path | str,
    cache_dir: Path | str,
    sheet_specs: list[CombinedStatementSheetSpec] | None = None,
    watchlist: list[CombinedStatementWatchItem] | None = None,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = build_combined_statement_receipt_accounts_support(
        cache_dir=cache_dir,
        sheet_specs=sheet_specs,
        watchlist=watchlist,
    )
    table.to_csv(out_path, index=False)
    return out_path
