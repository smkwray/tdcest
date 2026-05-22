from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pandas as pd

from .config import USER_AGENT

XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
TABLE11_LABELS = {
    "all_sectors": "all sectors",
    "finance_and_insurance": "finance and insurance",
    "management_holding_companies": "management of companies holding companies",
    "income_tax": "income tax",
    "total_income_tax_after_credits": "total income tax after credits",
}
TABLE51_LABELS = {
    "all_industries": "all industries",
    "finance_and_insurance": "finance and insurance",
    "management_holding_companies": "management of companies holding companies",
    "commercial_banking": "commercial banking",
    "depository_credit_intermediation": "savings institutions and other depository credit intermediation",
    "depository_credit_intermediation_legacy": "savings institutions credit unions and other depository credit intermediation",
    "bank_holding_companies": "offices of bank holding companies",
    "total_income_tax_after_credits": "total income tax after credits",
}
TABLE53_LABELS = {
    "finance_and_insurance": "finance and insurance",
    "management_holding_companies": "management of companies holding companies",
    "commercial_banking": "commercial banking",
    "depository_credit_intermediation": "savings institutions and other depository credit intermediation",
    "bank_holding_companies": "offices of bank holding companies",
    "income_subject_to_tax": "income subject to tax",
    "total_income_tax_after_credits": "total income tax after credits",
}

IRS_CORPORATION_COMPLETE_CURRENT_PAGE_URL = (
    "https://www.irs.gov/statistics/soi-tax-stats-corporation-income-tax-returns-complete-report-publication-16"
)
IRS_CORPORATION_COMPLETE_HISTORICAL_PAGE_URL = (
    "https://www.irs.gov/statistics/soi-tax-stats-corporation-complete-report-1994-to-2013"
)
IRS_CORPORATION_COMPLETE_HISTORICAL_TABLE6_PAGE_URL = (
    "https://www.irs.gov/statistics/soi-tax-stats-returns-of-active-corporations-table-6"
)


@dataclass(frozen=True)
class Publication16Table11Row:
    tax_year: int
    source_url: str
    source_table: str
    all_income_tax_thousands: float
    finance_and_insurance_income_tax_thousands: float
    management_holding_companies_income_tax_thousands: float
    all_total_income_tax_after_credits_thousands: float
    finance_and_insurance_total_income_tax_after_credits_thousands: float
    management_holding_companies_total_income_tax_after_credits_thousands: float

    @property
    def finance_share_after_credits(self) -> float:
        return self.finance_and_insurance_total_income_tax_after_credits_thousands / self.all_total_income_tax_after_credits_thousands

    @property
    def finance_plus_holding_share_after_credits(self) -> float:
        numerator = (
            self.finance_and_insurance_total_income_tax_after_credits_thousands
            + self.management_holding_companies_total_income_tax_after_credits_thousands
        )
        return numerator / self.all_total_income_tax_after_credits_thousands


@dataclass(frozen=True)
class Publication16Table51Row:
    tax_year: int
    source_url: str
    source_table: str
    all_total_income_tax_after_credits_thousands: float
    finance_and_insurance_total_income_tax_after_credits_thousands: float
    commercial_banking_total_income_tax_after_credits_thousands: float
    savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands: float
    bank_holding_companies_total_income_tax_after_credits_thousands: float | None
    depository_label_observed: str

    @property
    def finance_share_after_credits(self) -> float:
        return self.finance_and_insurance_total_income_tax_after_credits_thousands / self.all_total_income_tax_after_credits_thousands

    @property
    def strict_depository_share_after_credits(self) -> float:
        numerator = (
            self.commercial_banking_total_income_tax_after_credits_thousands
            + self.savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands
        )
        return numerator / self.all_total_income_tax_after_credits_thousands

    @property
    def depository_plus_bhc_share_after_credits(self) -> float:
        if self.bank_holding_companies_total_income_tax_after_credits_thousands is None:
            return float("nan")
        numerator = (
            self.commercial_banking_total_income_tax_after_credits_thousands
            + self.savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands
            + self.bank_holding_companies_total_income_tax_after_credits_thousands
        )
        return numerator / self.all_total_income_tax_after_credits_thousands


@dataclass(frozen=True)
class Publication16Table53AvailabilityRow:
    tax_year: int
    source_url: str
    source_table: str
    industry_key: str
    industry_label: str
    perimeter_type: str
    source_column: str
    income_subject_to_tax_raw: str | None
    income_subject_to_tax_status: str
    income_subject_to_tax_thousands: float | None
    total_income_tax_after_credits_raw: str | None
    total_income_tax_after_credits_status: str
    total_income_tax_after_credits_thousands: float | None

    @property
    def usable_for_bank_only_share(self) -> bool:
        return (
            self.perimeter_type in {"bank_minor_industry", "bank_holding_minor_industry"}
            and self.income_subject_to_tax_status == "observed"
            and self.total_income_tax_after_credits_status == "observed"
        )


@dataclass(frozen=True)
class Publication16HistoricalTable6Row:
    tax_year: int
    source_url: str
    source_table: str
    all_total_income_tax_after_credits_thousands: float
    finance_and_insurance_total_income_tax_after_credits_thousands: float
    credit_intermediation_total_income_tax_after_credits_thousands: float
    management_holding_companies_total_income_tax_after_credits_thousands: float

    @property
    def finance_share_after_credits(self) -> float:
        return self.finance_and_insurance_total_income_tax_after_credits_thousands / self.all_total_income_tax_after_credits_thousands

    @property
    def historical_credit_intermediation_share_after_credits(self) -> float:
        return self.credit_intermediation_total_income_tax_after_credits_thousands / self.all_total_income_tax_after_credits_thousands

    @property
    def historical_credit_intermediation_plus_management_share_after_credits(self) -> float:
        numerator = (
            self.credit_intermediation_total_income_tax_after_credits_thousands
            + self.management_holding_companies_total_income_tax_after_credits_thousands
        )
        return numerator / self.all_total_income_tax_after_credits_thousands


def publication16_table11_url(tax_year: int) -> str:
    yy = str(tax_year)[-2:]
    return f"https://www.irs.gov/pub/irs-soi/{yy}co11ccr.xlsx"


def publication16_table51_url(tax_year: int) -> str:
    yy = str(tax_year)[-2:]
    return f"https://www.irs.gov/pub/irs-soi/{yy}co51ccr.xlsx"


def publication16_table53_url(tax_year: int) -> str:
    yy = str(tax_year)[-2:]
    return f"https://www.irs.gov/pub/irs-soi/{yy}co53ccr.xlsx"


def publication16_historical_table6_url(tax_year: int) -> str:
    yy = str(tax_year)[-2:]
    suffix = "nr" if tax_year == 2003 else "ccr"
    return f"https://www.irs.gov/pub/irs-soi/{yy}co06{suffix}.xls"


def publication16_bank_share_source_url(tax_year: int) -> str:
    if tax_year <= 2013:
        return publication16_historical_table6_url(tax_year)
    return publication16_table51_url(tax_year)


def _naics_revision_for_tax_year(tax_year: int) -> str:
    if tax_year >= 2022:
        return "NAICS_2022"
    if tax_year >= 2017:
        return "NAICS_2017"
    if tax_year >= 2012:
        return "NAICS_2012"
    if tax_year >= 2007:
        return "NAICS_2007"
    return "NAICS_2002"


def build_publication16_bank_share_source_manifest(
    *,
    start_year: int = 2003,
    end_year: int = 2022,
    cache_dir: Path | str = "data/raw/irs_soi_pub16",
) -> pd.DataFrame:
    cache_dir = Path(cache_dir)
    rows: list[dict[str, object]] = []
    for tax_year in range(start_year, end_year + 1):
        historical = tax_year <= 2013
        source_url = publication16_bank_share_source_url(tax_year)
        extension = ".xls" if historical else ".xlsx"
        cache_path = cache_dir / f"{tax_year}_bank_share_source{extension}"
        rows.append(
            {
                "tax_year": tax_year,
                "source_family": "irs_soi_publication_16",
                "source_table": "Publication 16 historical Table 6" if historical else "Publication 16 Basic Table 5.1",
                "source_table_printed_nbr": "6" if historical else "5.1",
                "current_table_equivalent": "Basic Table 5.1",
                "table_concept": "returns_of_active_corporations_tax_items_by_industry",
                "classified_by": "Major Industry" if historical else "Minor Industry",
                "source_url": source_url,
                "source_page_url": (
                    IRS_CORPORATION_COMPLETE_HISTORICAL_TABLE6_PAGE_URL
                    if historical
                    else IRS_CORPORATION_COMPLETE_CURRENT_PAGE_URL
                ),
                "archive_page_url": IRS_CORPORATION_COMPLETE_HISTORICAL_PAGE_URL if historical else "",
                "cache_path": str(cache_path),
                "file_format": "xls" if historical else "xlsx",
                "cache_exists": cache_path.exists(),
                "naics_revision": _naics_revision_for_tax_year(tax_year),
                "target_naics_codes": "522110|522120|551111",
                "target_share_variants": "strict_depository|depository_plus_bhc|finance_upper",
                "parser_status": "needs_xls_parser" if historical else "current_xlsx_parser_available",
                "notes": (
                    "Historical Table 6 is the current Table 5.1 concept per project crosswalk; parse by concept and labels, not table number."
                    if historical
                    else "Current Publication 16 Table 5.1 parser exists."
                ),
            }
        )
    return pd.DataFrame(rows)


def write_publication16_bank_share_source_manifest(
    *,
    out_path: Path | str,
    start_year: int = 2003,
    end_year: int = 2022,
    cache_dir: Path | str | None = None,
) -> Path:
    out_path = Path(out_path)
    if cache_dir is None:
        cache_dir = out_path.parent / "irs_soi_pub16"
    manifest = build_publication16_bank_share_source_manifest(
        start_year=start_year,
        end_year=end_year,
        cache_dir=cache_dir,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(out_path, index=False)
    return out_path


def download_publication16_table11_xlsx(tax_year: int, out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(publication16_table11_url(tax_year), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def download_publication16_table51_xlsx(tax_year: int, out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(publication16_table51_url(tax_year), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def download_publication16_table53_xlsx(tax_year: int, out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(publication16_table53_url(tax_year), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def download_publication16_bank_share_source(
    *,
    tax_year: int,
    out_path: Path | str,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(publication16_bank_share_source_url(tax_year), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=90) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def cache_publication16_bank_share_sources_from_manifest(
    manifest: pd.DataFrame,
    *,
    overwrite: bool = False,
    continue_on_error: bool = True,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, source_row in manifest.iterrows():
        tax_year = int(source_row["tax_year"])
        cache_path = Path(str(source_row["cache_path"]))
        status = "cached_existing" if cache_path.exists() and not overwrite else "pending"
        error = ""
        if status == "pending":
            try:
                download_publication16_bank_share_source(tax_year=tax_year, out_path=cache_path)
                status = "downloaded"
            except Exception as exc:
                status = "download_failed"
                error = str(exc)
                if not continue_on_error:
                    raise
        rows.append(
            {
                **source_row.to_dict(),
                "cache_exists": cache_path.exists(),
                "cache_size_bytes": cache_path.stat().st_size if cache_path.exists() else 0,
                "cache_status": status,
                "cache_error": error,
            }
        )
    return pd.DataFrame(rows)


def write_cached_publication16_bank_share_sources_from_manifest(
    *,
    manifest_path: Path | str,
    out_path: Path | str | None = None,
    overwrite: bool = False,
    continue_on_error: bool = True,
) -> Path:
    manifest = pd.read_csv(manifest_path)
    cached = cache_publication16_bank_share_sources_from_manifest(
        manifest,
        overwrite=overwrite,
        continue_on_error=continue_on_error,
    )
    out = Path(out_path) if out_path is not None else Path(manifest_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cached.to_csv(out, index=False)
    return out


def _cell_column(ref: str) -> str:
    letters = []
    for ch in ref:
        if ch.isalpha():
            letters.append(ch)
        else:
            break
    return "".join(letters)


def _cell_row(ref: str) -> int:
    digits = []
    for ch in ref:
        if ch.isdigit():
            digits.append(ch)
    return int("".join(digits))


def _normalize_label(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


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


def _find_cell(cells: dict[str, str], *, normalized_label: str) -> str:
    target = _normalize_label(normalized_label)
    for ref, value in cells.items():
        if _normalize_label(value) == target:
            return ref
    raise ValueError(f"Could not find cell for label {normalized_label!r}")


def _find_row_label_cell(cells: dict[str, str], *, label: str, exact: bool = False) -> str:
    target = _normalize_label(label)
    for ref, value in cells.items():
        if _cell_column(ref) != "A":
            continue
        normalized_value = _normalize_label(value)
        if exact and normalized_value == target:
            return ref
        if not exact and target in normalized_value:
            return ref
    raise ValueError(f"Could not find row label for {label!r}")


def _float_or_raise(value: str, *, ref: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Expected numeric value in {ref}, found {value!r}") from exc


def _find_cell_in_row(cells: dict[str, str], *, row: int, normalized_label: str) -> str:
    target = _normalize_label(normalized_label)
    for ref, value in cells.items():
        if _cell_row(ref) != row:
            continue
        if _normalize_label(value) == target:
            return ref
    raise ValueError(f"Could not find row {row} cell for label {normalized_label!r}")


def _classify_observation(raw_value: str | None) -> tuple[str, float | None]:
    if raw_value is None or raw_value == "":
        return "missing", None
    normalized = raw_value.strip().lower()
    if normalized == "d":
        return "suppressed", None
    if normalized == "*":
        return "flagged_estimate", None
    try:
        return "observed", float(raw_value.replace(",", ""))
    except ValueError:
        return "non_numeric", None


def _normalize_frame_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _find_frame_row_containing(frame: pd.DataFrame, label: str) -> int:
    target = _normalize_label(label)
    for row_idx in range(len(frame)):
        row_text = " ".join(_normalize_frame_text(value) for value in frame.iloc[row_idx].tolist())
        if target in _normalize_label(row_text):
            return row_idx
    raise ValueError(f"Could not find row containing {label!r}")


def _find_frame_column_containing(frame: pd.DataFrame, label: str, *, header_rows: int = 13) -> int:
    target = _normalize_label(label)
    search_rows = min(header_rows, len(frame))
    for col_idx in range(frame.shape[1]):
        col_text = " ".join(_normalize_frame_text(frame.iat[row_idx, col_idx]) for row_idx in range(search_rows))
        if target in _normalize_label(col_text):
            return col_idx
    raise ValueError(f"Could not find column containing {label!r}")


def _find_frame_parent_total_column(frame: pd.DataFrame, label: str, *, total_row: int, header_rows: int = 13) -> int:
    label_col = _find_frame_column_containing(frame, label, header_rows=header_rows)
    label_header = " ".join(_normalize_frame_text(frame.iat[row_idx, label_col]) for row_idx in range(min(header_rows, len(frame))))
    label_header_norm = _normalize_label(label_header)
    if "total" in label_header_norm:
        return label_col

    for col_idx in range(max(0, label_col - 4), label_col):
        header = " ".join(_normalize_frame_text(frame.iat[row_idx, col_idx]) for row_idx in range(min(header_rows, len(frame))))
        status, _ = _classify_observation(_normalize_frame_text(frame.iat[total_row, col_idx]))
        if "total" in _normalize_label(header) and status == "observed":
            return col_idx
    for col_idx in range(label_col + 1, min(frame.shape[1], label_col + 5)):
        header = " ".join(_normalize_frame_text(frame.iat[row_idx, col_idx]) for row_idx in range(min(header_rows, len(frame))))
        status, _ = _classify_observation(_normalize_frame_text(frame.iat[total_row, col_idx]))
        if "total" in _normalize_label(header) and status == "observed":
            return col_idx
    return label_col


def _frame_float_or_raise(frame: pd.DataFrame, row: int, col: int) -> float:
    raw_value = frame.iat[row, col]
    status, value = _classify_observation(None if pd.isna(raw_value) else str(raw_value))
    if status == "observed" and value is not None:
        return value
    raise ValueError(f"Expected observed numeric value at row {row}, column {col}; found {raw_value!r}")


def extract_publication16_table11_row(path: Path | str, *, tax_year: int | None = None) -> Publication16Table11Row:
    source_path = Path(path)
    cells = _xlsx_cells(source_path)

    all_col = _cell_column(_find_cell(cells, normalized_label=TABLE11_LABELS["all_sectors"]))
    finance_col = _cell_column(_find_cell(cells, normalized_label=TABLE11_LABELS["finance_and_insurance"]))
    management_col = _cell_column(_find_cell(cells, normalized_label=TABLE11_LABELS["management_holding_companies"]))

    income_tax_row = _cell_row(_find_row_label_cell(cells, label=TABLE11_LABELS["income_tax"], exact=True))
    total_after_credits_row = _cell_row(
        _find_row_label_cell(cells, label=TABLE11_LABELS["total_income_tax_after_credits"])
    )

    inferred_year = tax_year
    if inferred_year is None:
        stem = source_path.stem
        if len(stem) >= 4 and stem[:4].isdigit():
            inferred_year = int(stem[:4])
        elif len(stem) >= 2 and stem[:2].isdigit():
            inferred_year = 2000 + int(stem[:2])
    if inferred_year is None:
        raise ValueError(f"Could not infer tax year from {source_path}")

    source_url = publication16_table11_url(inferred_year)

    return Publication16Table11Row(
        tax_year=inferred_year,
        source_url=source_url,
        source_table="Publication 16 Table 11",
        all_income_tax_thousands=_float_or_raise(cells[f"{all_col}{income_tax_row}"], ref=f"{all_col}{income_tax_row}"),
        finance_and_insurance_income_tax_thousands=_float_or_raise(
            cells[f"{finance_col}{income_tax_row}"], ref=f"{finance_col}{income_tax_row}"
        ),
        management_holding_companies_income_tax_thousands=_float_or_raise(
            cells[f"{management_col}{income_tax_row}"], ref=f"{management_col}{income_tax_row}"
        ),
        all_total_income_tax_after_credits_thousands=_float_or_raise(
            cells[f"{all_col}{total_after_credits_row}"], ref=f"{all_col}{total_after_credits_row}"
        ),
        finance_and_insurance_total_income_tax_after_credits_thousands=_float_or_raise(
            cells[f"{finance_col}{total_after_credits_row}"], ref=f"{finance_col}{total_after_credits_row}"
        ),
        management_holding_companies_total_income_tax_after_credits_thousands=_float_or_raise(
            cells[f"{management_col}{total_after_credits_row}"], ref=f"{management_col}{total_after_credits_row}"
        ),
    )


def _extract_publication16_historical_table6_row_from_frame(
    frame: pd.DataFrame,
    *,
    tax_year: int,
    source_url: str,
) -> Publication16HistoricalTable6Row:
    total_after_credits_row = _find_frame_row_containing(frame, "Total income tax after credits")
    all_col = _find_frame_column_containing(frame, "All industries")
    finance_col = _find_frame_parent_total_column(
        frame,
        "Finance and insurance",
        total_row=total_after_credits_row,
    )
    credit_col = _find_frame_column_containing(frame, "Credit intermediation")
    management_col = _find_frame_column_containing(frame, "Management of companies holding companies")
    return Publication16HistoricalTable6Row(
        tax_year=tax_year,
        source_url=source_url,
        source_table="Publication 16 historical Table 6",
        all_total_income_tax_after_credits_thousands=_frame_float_or_raise(frame, total_after_credits_row, all_col),
        finance_and_insurance_total_income_tax_after_credits_thousands=_frame_float_or_raise(
            frame,
            total_after_credits_row,
            finance_col,
        ),
        credit_intermediation_total_income_tax_after_credits_thousands=_frame_float_or_raise(
            frame,
            total_after_credits_row,
            credit_col,
        ),
        management_holding_companies_total_income_tax_after_credits_thousands=_frame_float_or_raise(
            frame,
            total_after_credits_row,
            management_col,
        ),
    )


def extract_publication16_historical_table6_row(
    path: Path | str,
    *,
    tax_year: int | None = None,
) -> Publication16HistoricalTable6Row:
    source_path = Path(path)
    inferred_year = tax_year
    if inferred_year is None:
        stem = source_path.stem
        if len(stem) >= 4 and stem[:4].isdigit():
            inferred_year = int(stem[:4])
        elif len(stem) >= 2 and stem[:2].isdigit():
            inferred_year = 2000 + int(stem[:2])
    if inferred_year is None:
        raise ValueError(f"Could not infer tax year from {source_path}")
    frame = pd.read_excel(source_path, sheet_name=0, header=None, dtype=object)
    return _extract_publication16_historical_table6_row_from_frame(
        frame,
        tax_year=inferred_year,
        source_url=publication16_historical_table6_url(inferred_year),
    )


def extract_publication16_table51_row(path: Path | str, *, tax_year: int | None = None) -> Publication16Table51Row:
    source_path = Path(path)
    cells = _xlsx_cells(source_path)

    all_col = _cell_column(_find_cell(cells, normalized_label=TABLE51_LABELS["all_industries"]))
    finance_col = _cell_column(_find_cell(cells, normalized_label=TABLE51_LABELS["finance_and_insurance"]))
    management_col = _cell_column(_find_cell(cells, normalized_label=TABLE51_LABELS["management_holding_companies"]))
    commercial_banking_col = _cell_column(_find_cell(cells, normalized_label=TABLE51_LABELS["commercial_banking"]))
    try:
        depository_ref = _find_cell(cells, normalized_label=TABLE51_LABELS["depository_credit_intermediation"])
    except ValueError:
        depository_ref = _find_cell(
            cells,
            normalized_label=TABLE51_LABELS["depository_credit_intermediation_legacy"],
        )
    depository_col = _cell_column(depository_ref)
    bank_holding_col = _cell_column(_find_cell(cells, normalized_label=TABLE51_LABELS["bank_holding_companies"]))

    total_after_credits_row = _cell_row(
        _find_row_label_cell(cells, label=TABLE51_LABELS["total_income_tax_after_credits"], exact=True)
    )

    inferred_year = tax_year
    if inferred_year is None:
        stem = source_path.stem
        if len(stem) >= 4 and stem[:4].isdigit():
            inferred_year = int(stem[:4])
        elif len(stem) >= 2 and stem[:2].isdigit():
            inferred_year = 2000 + int(stem[:2])
    if inferred_year is None:
        raise ValueError(f"Could not infer tax year from {source_path}")

    source_url = publication16_table51_url(inferred_year)
    bank_holding_status, bank_holding_value = _classify_observation(cells.get(f"{bank_holding_col}{total_after_credits_row}"))

    return Publication16Table51Row(
        tax_year=inferred_year,
        source_url=source_url,
        source_table="Publication 16 Table 5.1",
        all_total_income_tax_after_credits_thousands=_float_or_raise(
            cells[f"{all_col}{total_after_credits_row}"], ref=f"{all_col}{total_after_credits_row}"
        ),
        finance_and_insurance_total_income_tax_after_credits_thousands=_float_or_raise(
            cells[f"{finance_col}{total_after_credits_row}"], ref=f"{finance_col}{total_after_credits_row}"
        ),
        commercial_banking_total_income_tax_after_credits_thousands=_float_or_raise(
            cells[f"{commercial_banking_col}{total_after_credits_row}"], ref=f"{commercial_banking_col}{total_after_credits_row}"
        ),
        savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands=_float_or_raise(
            cells[f"{depository_col}{total_after_credits_row}"], ref=f"{depository_col}{total_after_credits_row}"
        ),
        bank_holding_companies_total_income_tax_after_credits_thousands=bank_holding_value if bank_holding_status == "observed" else None,
        depository_label_observed=str(cells[depository_ref]),
    )


def extract_publication16_table53_availability_rows(
    path: Path | str,
    *,
    tax_year: int | None = None,
) -> list[Publication16Table53AvailabilityRow]:
    source_path = Path(path)
    cells = _xlsx_cells(source_path)

    finance_total_col = _cell_column(_find_cell_in_row(cells, row=5, normalized_label=TABLE53_LABELS["finance_and_insurance"]))
    management_total_col = _cell_column(
        _find_cell_in_row(cells, row=5, normalized_label=TABLE53_LABELS["management_holding_companies"])
    )
    commercial_banking_col = _cell_column(
        _find_cell_in_row(cells, row=6, normalized_label=TABLE53_LABELS["commercial_banking"])
    )
    depository_credit_col = _cell_column(
        _find_cell_in_row(cells, row=6, normalized_label=TABLE53_LABELS["depository_credit_intermediation"])
    )
    bank_holding_col = _cell_column(
        _find_cell_in_row(cells, row=6, normalized_label=TABLE53_LABELS["bank_holding_companies"])
    )

    income_subject_row = _cell_row(_find_row_label_cell(cells, label=TABLE53_LABELS["income_subject_to_tax"], exact=True))
    total_after_credits_row = _cell_row(
        _find_row_label_cell(cells, label=TABLE53_LABELS["total_income_tax_after_credits"], exact=True)
    )

    inferred_year = tax_year
    if inferred_year is None:
        stem = source_path.stem
        if len(stem) >= 4 and stem[:4].isdigit():
            inferred_year = int(stem[:4])
        elif len(stem) >= 2 and stem[:2].isdigit():
            inferred_year = 2000 + int(stem[:2])
    if inferred_year is None:
        raise ValueError(f"Could not infer tax year from {source_path}")

    source_url = publication16_table53_url(inferred_year)
    rows: list[Publication16Table53AvailabilityRow] = []
    for industry_key, industry_label, perimeter_type, column in [
        ("finance_total_table53", "Finance and insurance total (Table 5.3)", "broad_sector_total", finance_total_col),
        ("commercial_banking", "Commercial banking", "bank_minor_industry", commercial_banking_col),
        (
            "savings_and_other_depository_credit_intermediation",
            "Savings institutions and other depository credit intermediation",
            "bank_minor_industry",
            depository_credit_col,
        ),
        (
            "management_holding_companies_total_table53",
            "Management of companies (holding companies) total (Table 5.3)",
            "broad_sector_total",
            management_total_col,
        ),
        ("offices_of_bank_holding_companies", "Offices of bank holding companies", "bank_holding_minor_industry", bank_holding_col),
    ]:
        income_ref = f"{column}{income_subject_row}"
        total_ref = f"{column}{total_after_credits_row}"
        income_raw = cells.get(income_ref)
        total_raw = cells.get(total_ref)
        income_status, income_value = _classify_observation(income_raw)
        total_status, total_value = _classify_observation(total_raw)
        rows.append(
            Publication16Table53AvailabilityRow(
                tax_year=inferred_year,
                source_url=source_url,
                source_table="Publication 16 Table 5.3",
                industry_key=industry_key,
                industry_label=industry_label,
                perimeter_type=perimeter_type,
                source_column=column,
                income_subject_to_tax_raw=income_raw,
                income_subject_to_tax_status=income_status,
                income_subject_to_tax_thousands=income_value,
                total_income_tax_after_credits_raw=total_raw,
                total_income_tax_after_credits_status=total_status,
                total_income_tax_after_credits_thousands=total_value,
            )
        )
    return rows


def build_publication16_table11_share_table(paths: list[Path | str]) -> pd.DataFrame:
    rows = []
    for path in paths:
        row = extract_publication16_table11_row(path)
        rows.append(
            {
                "tax_year": row.tax_year,
                "source_table": row.source_table,
                "source_url": row.source_url,
                "all_income_tax_thousands": row.all_income_tax_thousands,
                "finance_and_insurance_income_tax_thousands": row.finance_and_insurance_income_tax_thousands,
                "management_holding_companies_income_tax_thousands": row.management_holding_companies_income_tax_thousands,
                "all_total_income_tax_after_credits_thousands": row.all_total_income_tax_after_credits_thousands,
                "finance_and_insurance_total_income_tax_after_credits_thousands": row.finance_and_insurance_total_income_tax_after_credits_thousands,
                "management_holding_companies_total_income_tax_after_credits_thousands": row.management_holding_companies_total_income_tax_after_credits_thousands,
                "finance_share_after_credits": row.finance_share_after_credits,
                "finance_plus_holding_share_after_credits": row.finance_plus_holding_share_after_credits,
            }
        )
    frame = pd.DataFrame(rows).sort_values("tax_year").reset_index(drop=True)
    return frame


def build_publication16_table51_share_table(paths: list[Path | str]) -> pd.DataFrame:
    rows = []
    for path in paths:
        row = extract_publication16_table51_row(path)
        rows.append(
            {
                "tax_year": row.tax_year,
                "source_table": row.source_table,
                "source_url": row.source_url,
                "all_total_income_tax_after_credits_thousands": row.all_total_income_tax_after_credits_thousands,
                "finance_and_insurance_total_income_tax_after_credits_thousands": row.finance_and_insurance_total_income_tax_after_credits_thousands,
                "commercial_banking_total_income_tax_after_credits_thousands": row.commercial_banking_total_income_tax_after_credits_thousands,
                "savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands": row.savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands,
                "bank_holding_companies_total_income_tax_after_credits_thousands": row.bank_holding_companies_total_income_tax_after_credits_thousands,
                "depository_label_observed": row.depository_label_observed,
                "finance_share_after_credits": row.finance_share_after_credits,
                "strict_depository_share_after_credits": row.strict_depository_share_after_credits,
                "depository_plus_bhc_share_after_credits": row.depository_plus_bhc_share_after_credits,
            }
        )
    frame = pd.DataFrame(rows).sort_values("tax_year").reset_index(drop=True)
    return frame


def build_publication16_historical_table6_share_table(paths: list[Path | str]) -> pd.DataFrame:
    rows = []
    for path in paths:
        row = extract_publication16_historical_table6_row(path)
        rows.append(
            {
                "tax_year": row.tax_year,
                "source_table": row.source_table,
                "source_url": row.source_url,
                "source_granularity": "historical_major_industry",
                "mapping_confidence": "major_industry_credit_intermediation_not_minor_bank",
                "all_total_income_tax_after_credits_thousands": row.all_total_income_tax_after_credits_thousands,
                "finance_and_insurance_total_income_tax_after_credits_thousands": row.finance_and_insurance_total_income_tax_after_credits_thousands,
                "commercial_banking_total_income_tax_after_credits_thousands": None,
                "savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands": None,
                "bank_holding_companies_total_income_tax_after_credits_thousands": None,
                "historical_credit_intermediation_total_income_tax_after_credits_thousands": row.credit_intermediation_total_income_tax_after_credits_thousands,
                "historical_management_holding_companies_total_income_tax_after_credits_thousands": row.management_holding_companies_total_income_tax_after_credits_thousands,
                "finance_share_after_credits": row.finance_share_after_credits,
                "strict_depository_share_after_credits": None,
                "depository_plus_bhc_share_after_credits": None,
                "historical_credit_intermediation_share_after_credits": row.historical_credit_intermediation_share_after_credits,
                "historical_credit_intermediation_plus_management_share_after_credits": row.historical_credit_intermediation_plus_management_share_after_credits,
            }
        )
    return pd.DataFrame(rows).sort_values("tax_year").reset_index(drop=True)


def build_publication16_bank_tax_share_table_from_manifest(manifest: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    table_nbr = manifest["source_table_printed_nbr"].astype(str).str.replace(r"\.0$", "", regex=True)
    historical_paths = [
        Path(str(row["cache_path"]))
        for _, row in manifest.loc[table_nbr.eq("6")].iterrows()
        if Path(str(row["cache_path"])).exists()
    ]
    if historical_paths:
        frames.append(build_publication16_historical_table6_share_table(historical_paths))

    current_paths = [
        Path(str(row["cache_path"]))
        for _, row in manifest.loc[table_nbr.eq("5.1")].iterrows()
        if Path(str(row["cache_path"])).exists()
    ]
    if current_paths:
        current = build_publication16_table51_share_table(current_paths)
        current["source_granularity"] = "current_minor_industry"
        current["mapping_confidence"] = "exact_current_minor_industry_labels"
        current["historical_credit_intermediation_total_income_tax_after_credits_thousands"] = None
        current["historical_management_holding_companies_total_income_tax_after_credits_thousands"] = None
        current["historical_credit_intermediation_share_after_credits"] = None
        current["historical_credit_intermediation_plus_management_share_after_credits"] = None
        frames.append(current)

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    if "tax_year" in manifest.columns:
        metadata = manifest[
            [
                "tax_year",
                "source_table_printed_nbr",
                "current_table_equivalent",
                "table_concept",
                "classified_by",
                "cache_path",
                "naics_revision",
                "parser_status",
            ]
        ].copy()
        out = out.merge(metadata, on="tax_year", how="left")
    return out.sort_values("tax_year").reset_index(drop=True)


def build_publication16_table53_availability_table(paths: list[Path | str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in paths:
        for row in extract_publication16_table53_availability_rows(path):
            rows.append(
                {
                    "tax_year": row.tax_year,
                    "source_table": row.source_table,
                    "source_url": row.source_url,
                    "industry_key": row.industry_key,
                    "industry_label": row.industry_label,
                    "perimeter_type": row.perimeter_type,
                    "source_column": row.source_column,
                    "income_subject_to_tax_raw": row.income_subject_to_tax_raw,
                    "income_subject_to_tax_status": row.income_subject_to_tax_status,
                    "income_subject_to_tax_thousands": row.income_subject_to_tax_thousands,
                    "total_income_tax_after_credits_raw": row.total_income_tax_after_credits_raw,
                    "total_income_tax_after_credits_status": row.total_income_tax_after_credits_status,
                    "total_income_tax_after_credits_thousands": row.total_income_tax_after_credits_thousands,
                    "usable_for_bank_only_share": row.usable_for_bank_only_share,
                }
            )
    frame = pd.DataFrame(rows).sort_values(["tax_year", "industry_key"]).reset_index(drop=True)
    return frame


def write_publication16_table11_share_table(
    paths: list[Path | str],
    *,
    out_path: Path | str,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame = build_publication16_table11_share_table(paths)
    frame.to_csv(out_path, index=False)
    return out_path


def write_publication16_table51_share_table(
    paths: list[Path | str],
    *,
    out_path: Path | str,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame = build_publication16_table51_share_table(paths)
    frame.to_csv(out_path, index=False)
    return out_path


def write_publication16_table53_availability_table(
    paths: list[Path | str],
    *,
    out_path: Path | str,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame = build_publication16_table53_availability_table(paths)
    frame.to_csv(out_path, index=False)
    return out_path


def write_publication16_bank_tax_share_table_from_manifest(
    *,
    manifest_path: Path | str,
    out_path: Path | str,
) -> Path:
    manifest = pd.read_csv(manifest_path)
    frame = build_publication16_bank_tax_share_table_from_manifest(manifest)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_path, index=False)
    return out_path
