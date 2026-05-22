from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from tdc_estimator.irs_soi import (
    build_publication16_bank_share_source_manifest,
    build_publication16_bank_tax_share_table_from_manifest,
    cache_publication16_bank_share_sources_from_manifest,
    build_publication16_table53_availability_table,
    extract_publication16_historical_table6_row,
    extract_publication16_table53_availability_rows,
    publication16_bank_share_source_url,
    write_publication16_bank_share_source_manifest,
)


def test_publication16_bank_share_source_url_uses_historical_table6_boundary() -> None:
    assert publication16_bank_share_source_url(2003).endswith("/03co06nr.xls")
    assert publication16_bank_share_source_url(2013).endswith("/13co06ccr.xls")
    assert publication16_bank_share_source_url(2014).endswith("/14co51ccr.xlsx")


def test_build_publication16_bank_share_source_manifest_marks_current_equivalent(tmp_path: Path) -> None:
    manifest = build_publication16_bank_share_source_manifest(
        start_year=2003,
        end_year=2014,
        cache_dir=tmp_path / "cache",
    )

    assert list(manifest["tax_year"]) == list(range(2003, 2015))
    assert manifest.loc[manifest["tax_year"].eq(2003), "source_table_printed_nbr"].iloc[0] == "6"
    assert manifest.loc[manifest["tax_year"].eq(2003), "current_table_equivalent"].iloc[0] == "Basic Table 5.1"
    assert manifest.loc[manifest["tax_year"].eq(2014), "source_table_printed_nbr"].iloc[0] == "5.1"
    assert manifest.loc[manifest["tax_year"].eq(2007), "naics_revision"].iloc[0] == "NAICS_2007"
    assert manifest.loc[manifest["tax_year"].eq(2012), "naics_revision"].iloc[0] == "NAICS_2012"
    assert set(manifest.loc[manifest["tax_year"].le(2013), "parser_status"]) == {"needs_xls_parser"}
    assert set(manifest.loc[manifest["tax_year"].ge(2014), "parser_status"]) == {"current_xlsx_parser_available"}


def test_write_publication16_bank_share_source_manifest_writes_csv(tmp_path: Path) -> None:
    out_path = tmp_path / "irs_pub16_manifest.csv"

    written = write_publication16_bank_share_source_manifest(
        out_path=out_path,
        start_year=2021,
        end_year=2022,
        cache_dir=tmp_path / "cache",
    )

    assert written == out_path
    frame = pd.read_csv(out_path)
    assert list(frame["tax_year"]) == [2021, 2022]
    assert list(frame["naics_revision"]) == ["NAICS_2017", "NAICS_2022"]


def test_cache_publication16_bank_share_sources_from_manifest_downloads_missing(monkeypatch, tmp_path: Path) -> None:
    manifest = build_publication16_bank_share_source_manifest(
        start_year=2003,
        end_year=2004,
        cache_dir=tmp_path / "cache",
    )
    calls: list[tuple[int, Path]] = []

    def fake_download_publication16_bank_share_source(*, tax_year: int, out_path: Path) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(f"year={tax_year}".encode("utf-8"))
        calls.append((tax_year, out_path))
        return out_path

    monkeypatch.setattr(
        "tdc_estimator.irs_soi.download_publication16_bank_share_source",
        fake_download_publication16_bank_share_source,
    )

    cached = cache_publication16_bank_share_sources_from_manifest(manifest)

    assert [call[0] for call in calls] == [2003, 2004]
    assert set(cached["cache_status"]) == {"downloaded"}
    assert cached["cache_exists"].all()
    assert cached["cache_size_bytes"].gt(0).all()


def test_extract_publication16_historical_table6_row_reads_major_industry_columns(monkeypatch, tmp_path: Path) -> None:
    source_path = tmp_path / "2003_bank_share_source.xls"
    source_path.write_bytes(b"placeholder")
    frame = pd.DataFrame([[""] * 8 for _ in range(6)], dtype=object)
    frame.iat[0, 1] = "All"
    frame.iat[1, 1] = "industries"
    frame.iat[0, 2] = "Finance and insurance"
    frame.iat[0, 3] = "Credit"
    frame.iat[1, 3] = "intermediation"
    frame.iat[0, 4] = "Management"
    frame.iat[1, 4] = "of"
    frame.iat[2, 4] = "companies"
    frame.iat[3, 4] = "(holding"
    frame.iat[4, 4] = "companies)"
    frame.iat[5, 0] = "Total income tax after credits [2].."
    frame.iat[5, 1] = 1000
    frame.iat[5, 2] = 300
    frame.iat[5, 3] = 80
    frame.iat[5, 4] = 20
    monkeypatch.setattr("pandas.read_excel", lambda *args, **kwargs: frame)

    row = extract_publication16_historical_table6_row(source_path, tax_year=2003)

    assert row.all_total_income_tax_after_credits_thousands == 1000.0
    assert row.finance_share_after_credits == 0.3
    assert row.historical_credit_intermediation_share_after_credits == 0.08
    assert row.historical_credit_intermediation_plus_management_share_after_credits == 0.1


def test_build_publication16_bank_tax_share_table_from_manifest_combines_historical_and_current(monkeypatch, tmp_path: Path) -> None:
    historical_path = tmp_path / "2003.xls"
    current_path = tmp_path / "2014.xlsx"
    historical_path.write_bytes(b"historical")
    current_path.write_bytes(b"current")
    manifest = pd.DataFrame(
        [
            {
                "tax_year": 2003,
                "source_table_printed_nbr": 6,
                "current_table_equivalent": "Basic Table 5.1",
                "table_concept": "returns_of_active_corporations_tax_items_by_industry",
                "classified_by": "Major Industry",
                "cache_path": str(historical_path),
                "naics_revision": "NAICS_2002",
                "parser_status": "needs_xls_parser",
            },
            {
                "tax_year": 2014,
                "source_table_printed_nbr": "5.1",
                "current_table_equivalent": "Basic Table 5.1",
                "table_concept": "returns_of_active_corporations_tax_items_by_industry",
                "classified_by": "Minor Industry",
                "cache_path": str(current_path),
                "naics_revision": "NAICS_2012",
                "parser_status": "current_xlsx_parser_available",
            },
        ]
    )

    monkeypatch.setattr(
        "tdc_estimator.irs_soi.build_publication16_historical_table6_share_table",
        lambda paths: pd.DataFrame(
            [
                {
                    "tax_year": 2003,
                    "source_table": "Publication 16 historical Table 6",
                    "source_url": "https://example.test/2003.xls",
                    "source_granularity": "historical_major_industry",
                    "mapping_confidence": "major_industry_credit_intermediation_not_minor_bank",
                    "all_total_income_tax_after_credits_thousands": 1000.0,
                    "finance_share_after_credits": 0.3,
                    "historical_credit_intermediation_share_after_credits": 0.08,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "tdc_estimator.irs_soi.build_publication16_table51_share_table",
        lambda paths: pd.DataFrame(
            [
                {
                    "tax_year": 2014,
                    "source_table": "Publication 16 Table 5.1",
                    "source_url": "https://example.test/2014.xlsx",
                    "all_total_income_tax_after_credits_thousands": 2000.0,
                    "finance_share_after_credits": 0.25,
                    "strict_depository_share_after_credits": 0.03,
                    "depository_plus_bhc_share_after_credits": 0.04,
                }
            ]
        ),
    )

    shares = build_publication16_bank_tax_share_table_from_manifest(manifest)

    assert list(shares["tax_year"]) == [2003, 2014]
    assert shares.loc[0, "source_granularity"] == "historical_major_industry"
    assert shares.loc[1, "source_granularity"] == "current_minor_industry"
    assert shares.loc[0, "naics_revision"] == "NAICS_2002"
    assert shares.loc[1, "strict_depository_share_after_credits"] == 0.03


def test_extract_publication16_table53_availability_rows_reads_bank_minor_industry_statuses(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "22co53ccr.xlsx"
    shared_strings = [
        "Finance and insurance",
        "Management of companies (holding companies)",
        "Total",
        "Commercial banking",
        "Savings institutions and other depository credit intermediation",
        "Offices of bank holding companies",
        "Income subject to tax",
        "Total income tax after credits",
    ]
    shared_xml = "".join(f"<si><t>{text}</t></si>" for text in shared_strings)
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheets><sheet name="Table 5.3" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets>'
        "</workbook>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="5"><c r="EQ5" t="s"><v>0</v></c><c r="FY5" t="s"><v>1</v></c></row>'
        '<row r="6">'
        '<c r="EQ6" t="s"><v>2</v></c>'
        '<c r="ER6" t="s"><v>3</v></c>'
        '<c r="ES6" t="s"><v>4</v></c>'
        '<c r="FY6" t="s"><v>2</v></c>'
        '<c r="FZ6" t="s"><v>5</v></c>'
        "</row>"
        '<row r="79">'
        '<c r="A79" t="s"><v>6</v></c>'
        '<c r="EQ79"><v>d</v></c>'
        '<c r="ER79"><v>d</v></c>'
        '<c r="ES79"><v>d</v></c>'
        '<c r="FY79"><v>1000</v></c>'
        '<c r="FZ79"><v>d</v></c>'
        "</row>"
        '<row r="80">'
        '<c r="A80" t="s"><v>7</v></c>'
        '<c r="EQ80"><v>d</v></c>'
        '<c r="ER80"><v>d</v></c>'
        '<c r="ES80"><v>d</v></c>'
        '<c r="FY80"><v>900</v></c>'
        '<c r="FZ80"><v>d</v></c>'
        "</row>"
        "</sheetData></worksheet>"
    )
    with ZipFile(xlsx_path, "w") as zf:
        zf.writestr(
            "xl/sharedStrings.xml",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{shared_xml}</sst>',
        )
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    rows = extract_publication16_table53_availability_rows(xlsx_path, tax_year=2022)
    by_key = {row.industry_key: row for row in rows}

    assert by_key["commercial_banking"].income_subject_to_tax_status == "suppressed"
    assert by_key["commercial_banking"].total_income_tax_after_credits_status == "suppressed"
    assert not by_key["commercial_banking"].usable_for_bank_only_share
    assert by_key["management_holding_companies_total_table53"].total_income_tax_after_credits_status == "observed"
    assert by_key["management_holding_companies_total_table53"].total_income_tax_after_credits_thousands == 900.0


def test_build_publication16_table53_availability_table_marks_bank_rows_unusable(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "22co53ccr.xlsx"
    with ZipFile(xlsx_path, "w") as zf:
        zf.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<si><t>Finance and insurance</t></si>"
            "<si><t>Management of companies (holding companies)</t></si>"
            "<si><t>Total</t></si>"
            "<si><t>Commercial banking</t></si>"
            "<si><t>Savings institutions and other depository credit intermediation</t></si>"
            "<si><t>Offices of bank holding companies</t></si>"
            "<si><t>Income subject to tax</t></si>"
            "<si><t>Total income tax after credits</t></si>"
            "</sst>",
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="Table 5.3" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>',
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            '<row r="5"><c r="EQ5" t="s"><v>0</v></c><c r="FY5" t="s"><v>1</v></c></row>'
            '<row r="6"><c r="EQ6" t="s"><v>2</v></c><c r="ER6" t="s"><v>3</v></c><c r="ES6" t="s"><v>4</v></c><c r="FY6" t="s"><v>2</v></c><c r="FZ6" t="s"><v>5</v></c></row>'
            '<row r="79"><c r="A79" t="s"><v>6</v></c><c r="EQ79"><v>d</v></c><c r="ER79"><v>d</v></c><c r="ES79"><v>d</v></c><c r="FY79"><v>1000</v></c><c r="FZ79"><v>d</v></c></row>'
            '<row r="80"><c r="A80" t="s"><v>7</v></c><c r="EQ80"><v>d</v></c><c r="ER80"><v>d</v></c><c r="ES80"><v>d</v></c><c r="FY80"><v>900</v></c><c r="FZ80"><v>d</v></c></row>'
            "</sheetData></worksheet>",
        )

    frame = build_publication16_table53_availability_table([xlsx_path])
    bank_like = frame.loc[frame["perimeter_type"].isin(["bank_minor_industry", "bank_holding_minor_industry"])].copy()

    assert len(bank_like) == 3
    assert not bank_like["usable_for_bank_only_share"].any()
