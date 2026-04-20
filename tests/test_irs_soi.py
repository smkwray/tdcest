from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from tdc_estimator.irs_soi import (
    build_publication16_table53_availability_table,
    extract_publication16_table53_availability_rows,
)


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
