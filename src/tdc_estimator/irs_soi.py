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


def publication16_table11_url(tax_year: int) -> str:
    yy = str(tax_year)[-2:]
    return f"https://www.irs.gov/pub/irs-soi/{yy}co11ccr.xlsx"


def publication16_table51_url(tax_year: int) -> str:
    yy = str(tax_year)[-2:]
    return f"https://www.irs.gov/pub/irs-soi/{yy}co51ccr.xlsx"


def publication16_table53_url(tax_year: int) -> str:
    yy = str(tax_year)[-2:]
    return f"https://www.irs.gov/pub/irs-soi/{yy}co53ccr.xlsx"


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
