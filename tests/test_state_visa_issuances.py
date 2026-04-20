from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from tdc_estimator.state_visa_issuances import (
    _sum_issuance_column,
    state_iv_issuance_url,
    state_niv_issuance_url,
)


def _write_tiny_xlsx(path: Path, *, title: str, rows: list[tuple[str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    shared_strings = [title, "Category", "Visa Class", "Issuances"]
    for a, b, _ in rows:
        shared_strings.extend([a, b])

    def sst_xml(strings: list[str]) -> str:
        items = "".join(f"<si><t>{value}</t></si>" for value in strings)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'count="{len(strings)}" uniqueCount="{len(strings)}">{items}</sst>'
        )

    cells = [
        ('A1', 's', '0'),
        ('A2', 's', '1'),
        ('B2', 's', '2'),
        ('C2', 's', '3'),
    ]
    idx = 4
    row_no = 3
    for a, b, c in rows:
        cells.extend(
            [
                (f"A{row_no}", "s", str(idx)),
                (f"B{row_no}", "s", str(idx + 1)),
                (f"C{row_no}", None, c),
            ]
        )
        idx += 2
        row_no += 1

    row_map: dict[int, list[tuple[str, str | None, str]]] = {}
    for ref, cell_type, value in cells:
        digits = "".join(ch for ch in ref if ch.isdigit())
        row_map.setdefault(int(digits), []).append((ref, cell_type, value))

    sheet_rows = []
    for row_idx in sorted(row_map):
        inner = []
        for ref, cell_type, value in row_map[row_idx]:
            attr = f' r="{ref}"'
            if cell_type:
                attr += f' t="{cell_type}"'
            inner.append(f"<c{attr}><v>{value}</v></c>")
        sheet_rows.append(f'<row r="{row_idx}">{"".join(inner)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '</Types>'
    )

    with ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", sst_xml(shared_strings))


def test_sum_issuance_column_sums_numeric_column_c(tmp_path: Path) -> None:
    path = tmp_path / "tiny.xlsx"
    _write_tiny_xlsx(
        path,
        title="Sample Visa Issuances",
        rows=[("A", "B1", "10"), ("B", "B2", "20"), ("C", "F1", "3")],
    )

    assert _sum_issuance_column(path) == 33


def test_state_visa_issuance_urls_follow_fiscal_year_pattern() -> None:
    assert "FY2025/JANUARY%202025" in state_niv_issuance_url(fiscal_year=2025, month=1)
    assert "FY2025/OCTOBER%202024" in state_niv_issuance_url(fiscal_year=2025, month=10)
    assert "FY2024/SEPTEMBER%202024" in state_iv_issuance_url(fiscal_year=2024, month=9)
