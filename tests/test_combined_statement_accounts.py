from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

import pandas as pd

from tdc_estimator.combined_statement_accounts import (
    CombinedStatementSheetSpec,
    CombinedStatementWatchItem,
    build_combined_statement_receipt_accounts_support,
    discover_current_combined_statement_excel_links,
)


def _write_minimal_xlsx(path: Path, *, title: str, aid_cd: str, main_cd: str, sub_cd: str, amount: str) -> None:
    shared_strings = [
        "Appropriations, Outlays, and Balances",
        "",
        title,
        "No Year",
        aid_cd,
        main_cd,
        sub_cd,
        amount,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>""",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="8" uniqueCount="8">
"""
            + "".join(f"<si><t>{text}</t></si>" for text in shared_strings)
            + "</sst>",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c></row>
<row r="2"><c r="A2" t="s"><v>2</v></c></row>
<row r="3"><c r="A3" t="s"><v>1</v></c></row>
<row r="4">
  <c r="A4" t="s"><v>1</v></c>
  <c r="B4" t="s"><v>3</v></c>
  <c r="D4" t="s"><v>4</v></c>
  <c r="E4" t="s"><v>5</v></c>
  <c r="F4" t="s"><v>6</v></c>
  <c r="H4" t="s"><v>7</v></c>
</row>
</sheetData></worksheet>""",
        )


def test_build_combined_statement_receipt_accounts_support_extracts_watch_rows(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    xlsx_path = cache_dir / "combined_statement__2025_treasury.xlsx"
    _write_minimal_xlsx(
        xlsx_path,
        title="Financial Research Fund, Departmental Offices, Treasury",
        aid_cd="020",
        main_cd="5590",
        sub_cd="000",
        amount="108,251,226.24",
    )

    table = build_combined_statement_receipt_accounts_support(
        cache_dir=cache_dir,
        sheet_specs=[
            CombinedStatementSheetSpec(
                fiscal_year=2025,
                source_department="treasury",
                url="https://example.invalid/unused.xlsx",
            )
        ],
        watchlist=[
            CombinedStatementWatchItem(
                fiscal_year=2025,
                source_department="treasury",
                aid_cd="20",
                main_cd="5590",
                title_contains="Financial Research Fund",
                combined_statement_match_scope="main_account_rollup",
                combined_statement_metric_basis="appropriations_and_transfers_mil",
            )
        ],
    )

    assert len(table) == 1
    row = table.iloc[0]
    assert row["aid_cd"] == "20"
    assert row["main_cd"] == "5590"
    assert row["sub_cd"] == "0"
    assert row["combined_statement_metric_basis"] == "appropriations_and_transfers_mil"
    assert row["combined_statement_match_scope"] == "main_account_rollup"
    assert pd.Series([row["combined_statement_amt_mil"]]).round(3).iloc[0] == 108.251


def test_discover_current_combined_statement_excel_links_parses_department_labels(monkeypatch) -> None:
    html = b"""
    <html><body>
    <p>Department of Homeland Security</p>
    <ul class="no-marker">
      <li><a href="/system/files/files/reports-statements/combined-statement/cs2025/c18.pdf">PDF</a> |
          <a href="/system/files/files/reports-statements/combined-statement/cs2025/c18.xlsx">EXCEL</a></li>
    </ul>
    <p>Independent Agencies</p>
    <ul class="no-marker">
      <li><a href="/system/files/files/reports-statements/combined-statement/cs2025/c55.pdf">PDF</a> |
          <a href="/system/files/files/reports-statements/combined-statement/cs2025/c55.xlsx">EXCEL</a></li>
    </ul>
    </body></html>
    """

    class _FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

    monkeypatch.setattr(
        "tdc_estimator.combined_statement_accounts.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(html),
    )

    links = discover_current_combined_statement_excel_links("https://example.invalid/current")

    assert links["Department of Homeland Security"].endswith("/c18.xlsx")
    assert links["Independent Agencies"].endswith("/c55.xlsx")
