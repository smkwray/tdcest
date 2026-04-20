from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from tdc_estimator.bank_corp_tax_receipts_bridge import (
    build_bank_corp_tax_receipts_bridge,
    render_bank_corp_tax_receipts_bridge_markdown,
)
from tdc_estimator.irs_soi import extract_publication16_table11_row, extract_publication16_table51_row


def test_build_bank_corp_tax_receipts_bridge_applies_annual_shares_to_quarterly_mts_cash(tmp_path: Path):
    mts_path = tmp_path / "mts_receipts.csv"
    shares_path = tmp_path / "irs_shares.csv"

    pd.DataFrame(
        [
            ["2025-10-31", "Corporation Income Taxes", 100_000_000.0, 10_000_000.0, 90_000_000.0],
            ["2025-11-30", "Corporation Income Taxes", 120_000_000.0, 20_000_000.0, 100_000_000.0],
            ["2025-12-31", "Corporation Income Taxes", 140_000_000.0, 30_000_000.0, 110_000_000.0],
            ["2026-01-31", "Corporation Income Taxes", 160_000_000.0, 40_000_000.0, 120_000_000.0],
            ["2026-02-28", "Corporation Income Taxes", 180_000_000.0, 50_000_000.0, 130_000_000.0],
            ["2026-03-31", "Corporation Income Taxes", 200_000_000.0, 60_000_000.0, 140_000_000.0],
        ],
        columns=[
            "record_date",
            "classification_desc",
            "current_month_gross_rcpt_amt",
            "current_month_refund_amt",
            "current_month_net_rcpt_amt",
        ],
    ).to_csv(mts_path, index=False)

    pd.DataFrame(
        [
            [2025, "Publication 16 Table 5.1", 1_000_000.0, 100_000.0, 10_000.0, 5_000.0, 3_000.0, "Savings institutions and other depository credit intermediation", 0.10, 0.015, 0.018],
        ],
        columns=[
            "tax_year",
            "source_table",
            "all_total_income_tax_after_credits_thousands",
            "finance_and_insurance_total_income_tax_after_credits_thousands",
            "commercial_banking_total_income_tax_after_credits_thousands",
            "savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands",
            "bank_holding_companies_total_income_tax_after_credits_thousands",
            "depository_label_observed",
            "finance_share_after_credits",
            "strict_depository_share_after_credits",
            "depository_plus_bhc_share_after_credits",
        ],
    ).to_csv(shares_path, index=False)

    bridge = build_bank_corp_tax_receipts_bridge(
        mts_receipts_path=mts_path,
        irs_soi_bank_tax_shares_path=shares_path,
        start="2025-12-31",
    )

    latest_2025 = bridge.loc[pd.Timestamp("2025-12-31")]
    latest_2026 = bridge.loc[pd.Timestamp("2026-03-31")]

    assert round(latest_2025["mts_corp_income_tax_gross_mil"], 3) == 360.000
    assert round(latest_2025["mts_corp_income_tax_refunds_mil"], 3) == 60.000
    assert round(latest_2025["mts_corp_income_tax_net_mil"], 3) == 300.000
    assert round(latest_2025["bank_corp_tax_receipts_gross_strict_depository_mil"], 3) == 5.400
    assert round(latest_2025["bank_corp_tax_receipts_gross_depository_plus_bhc_mil"], 3) == 6.480
    assert round(latest_2025["bank_corp_tax_receipts_gross_finance_share_mil"], 3) == 36.000
    assert latest_2025["share_status"] == "observed"
    assert int(latest_2025["stale_share_years"]) == 0
    assert bool(latest_2025["share_age_eligible_for_default"])

    assert int(latest_2026["soi_tax_year_used"]) == 2025
    assert latest_2026["share_status"] == "carry_forward_latest"
    assert round(latest_2026["bank_corp_tax_receipts_net_strict_depository_mil"], 3) == 5.850
    assert round(latest_2026["bank_corp_tax_receipts_net_depository_plus_bhc_mil"], 3) == 7.020
    assert int(latest_2026["stale_share_years"]) == 1


def test_render_bank_corp_tax_receipts_bridge_markdown_mentions_table51_bridge():
    bridge = pd.DataFrame(
        {
            "mts_corp_income_tax_gross_mil": [360.0],
            "mts_corp_income_tax_refunds_mil": [60.0],
            "mts_corp_income_tax_net_mil": [300.0],
            "soi_tax_year_used": [2025],
            "share_status": ["observed"],
            "stale_share_years": [0],
            "share_age_eligible_for_default": [True],
            "share_age_policy": ["max_2_calendar_years"],
            "bank_tax_share_strict_depository": [0.015],
            "bank_tax_share_depository_plus_bhc": [0.018],
            "finance_share_reproduction_qa": [0.1],
            "bank_corp_tax_receipts_gross_strict_depository_mil": [5.4],
            "bank_corp_tax_receipts_net_strict_depository_mil": [4.5],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [6.48],
            "bank_corp_tax_receipts_net_depository_plus_bhc_mil": [5.4],
            "bank_corp_tax_receipts_gross_finance_share_mil": [36.0],
            "bank_corp_tax_receipts_net_finance_share_mil": [30.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    markdown = render_bank_corp_tax_receipts_bridge_markdown(bridge)

    assert "Bank Corporate-Tax Receipts Bridge" in markdown
    assert "Table 5.1" in markdown
    assert "Age-eligible for default" in markdown
    assert "2025-12-31" in markdown


def test_extract_publication16_table11_row_reads_minimal_xlsx_payload(tmp_path: Path):
    xlsx_path = tmp_path / "22co11ccr.xlsx"
    shared_strings = [
        "all sectors",
        "finance and insurance",
        "management of companies holding companies",
        "income tax",
        "total income tax after credits [4]",
    ]
    shared_xml = "".join(f"<si><t>{text}</t></si>" for text in shared_strings)
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheets><sheet name="Table 11" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets>'
        "</workbook>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="4"><c r="B4" t="s"><v>0</v></c></row>'
        '<row r="5"><c r="L5" t="s"><v>1</v></c><c r="O5" t="s"><v>2</v></c></row>'
        '<row r="37"><c r="A37" t="s"><v>3</v></c><c r="B37"><v>1000</v></c><c r="L37"><v>120</v></c><c r="O37"><v>80</v></c></row>'
        '<row r="48"><c r="A48" t="s"><v>4</v></c><c r="B48"><v>900</v></c><c r="L48"><v>135</v></c><c r="O48"><v>45</v></c></row>'
        "</sheetData></worksheet>"
    )
    with ZipFile(xlsx_path, "w") as zf:
        zf.writestr(
            "xl/sharedStrings.xml",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{shared_xml}</sst>',
        )
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    row = extract_publication16_table11_row(xlsx_path, tax_year=2022)

    assert row.tax_year == 2022
    assert row.all_total_income_tax_after_credits_thousands == 900.0
    assert round(row.finance_share_after_credits, 6) == round(135.0 / 900.0, 6)
    assert round(row.finance_plus_holding_share_after_credits, 6) == round((135.0 + 45.0) / 900.0, 6)


def test_extract_publication16_table51_row_reads_minimal_xlsx_payload(tmp_path: Path):
    xlsx_path = tmp_path / "22co51ccr.xlsx"
    shared_strings = [
        "All Industries",
        "Finance and insurance",
        "Management of companies (holding companies)",
        "Commercial banking",
        "Savings institutions and other depository credit intermediation",
        "Offices of bank holding companies",
        "Total income tax after credits",
    ]
    shared_xml = "".join(f"<si><t>{text}</t></si>" for text in shared_strings)
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheets><sheet name="Table 5.1" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets>'
        "</workbook>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        '<row r="5"><c r="B5" t="s"><v>0</v></c><c r="EQ5" t="s"><v>1</v></c><c r="FZ5" t="s"><v>2</v></c></row>'
        '<row r="6"><c r="ER6" t="s"><v>3</v></c><c r="ES6" t="s"><v>4</v></c><c r="GA6" t="s"><v>5</v></c></row>'
        '<row r="81"><c r="A81" t="s"><v>6</v></c><c r="B81"><v>1000</v></c><c r="EQ81"><v>140</v></c><c r="ER81"><v>9</v></c><c r="ES81"><v>6</v></c><c r="GA81"><v>30</v></c></row>'
        "</sheetData></worksheet>"
    )
    with ZipFile(xlsx_path, "w") as zf:
        zf.writestr(
            "xl/sharedStrings.xml",
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{shared_xml}</sst>',
        )
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    row = extract_publication16_table51_row(xlsx_path, tax_year=2022)

    assert row.tax_year == 2022
    assert row.all_total_income_tax_after_credits_thousands == 1000.0
    assert round(row.strict_depository_share_after_credits, 6) == round((9.0 + 6.0) / 1000.0, 6)
    assert round(row.depository_plus_bhc_share_after_credits, 6) == round((9.0 + 6.0 + 30.0) / 1000.0, 6)
