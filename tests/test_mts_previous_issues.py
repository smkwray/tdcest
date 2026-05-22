from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.mts_previous_issues import (
    build_mts_fas_early_window_qa,
    build_mts_parser_total_reconciliation,
    build_mts_target_overlap_audit,
    build_mts_previous_issue_coverage_report,
    build_mts_previous_issues_manifest,
    build_mts_table4_target_history_from_manifest,
    build_mts_table5_target_history_from_manifest,
    month_ends,
    mts_archive_pdf_url,
    parse_mts_table4_target_lines,
    parse_mts_table4_printed_total_line,
    parse_mts_table3_receipt_source_line,
    parse_mts_table5_target_lines,
    parse_mts_table5_printed_total_line,
    parse_mts_summary_total_lines,
    render_mts_fas_early_window_qa_markdown,
    render_mts_parser_total_reconciliation_markdown,
    render_mts_previous_issue_coverage_markdown,
    render_mts_target_overlap_audit_markdown,
    stitch_previous_targets_with_fiscaldata,
    table4_target_history_to_fiscaldata_receipts,
    table5_target_history_to_fiscaldata_outlays,
    write_stitched_previous_targets_with_fiscaldata,
    write_table4_target_history_as_fiscaldata_receipts,
    write_table5_target_history_as_fiscaldata_outlays,
    write_mts_table4_target_history_from_manifest,
    write_mts_table5_target_history_from_manifest,
    write_mts_previous_issues_manifest,
    write_mts_previous_issue_coverage_report,
    write_mts_target_overlap_audit,
)


def test_month_ends_normalizes_to_month_end() -> None:
    months = month_ends("2003-01-01", "2003-03-15")

    assert months == list(pd.to_datetime(["2003-01-31", "2003-02-28", "2003-03-31"]))


def test_mts_archive_pdf_url_uses_legacy_mmyy_name() -> None:
    assert mts_archive_pdf_url(pd.Timestamp("2005-01-31")).endswith("/mts0105.pdf")


def test_build_mts_previous_issues_manifest_tracks_track_a_window(tmp_path: Path) -> None:
    manifest = build_mts_previous_issues_manifest(cache_dir=tmp_path)

    assert len(manifest) == 146
    assert manifest.iloc[0]["record_date"] == "2003-01-31"
    assert manifest.iloc[-1]["record_date"] == "2015-02-28"
    assert manifest.iloc[0]["pdf_url"].endswith("/mts0103.pdf")
    assert manifest.iloc[-1]["pdf_url"].endswith("/mts0215.pdf")
    assert manifest["fiscaldata_api_available"].eq(False).all()
    assert set(manifest.loc[manifest["issue_month"].str.startswith("2003"), "fas_direct_leaf_status"]) == {
        "manual_qa_required"
    }
    assert set(manifest.loc[manifest["issue_month"].str.startswith("2004"), "fas_direct_leaf_status"]) == {
        "manual_qa_required"
    }
    assert set(manifest.loc[manifest["issue_month"].str.startswith("2005"), "fas_direct_leaf_status"]) == {
        "unchecked"
    }


def test_write_mts_previous_issues_manifest_writes_csv(tmp_path: Path) -> None:
    out_path = tmp_path / "mts_previous_issues_manifest.csv"

    written = write_mts_previous_issues_manifest(
        out_path=out_path,
        start="2005-01-31",
        end="2005-02-28",
        cache_dir=tmp_path / "cache",
    )

    assert written == out_path
    frame = pd.read_csv(out_path)
    assert list(frame["mmyy"]) == [105, 205]
    assert list(frame["table5_parse_status"]) == ["pending", "pending"]


def test_parse_mts_table5_target_lines_extracts_fas_and_mint() -> None:
    text = """
    Financial Management Service:
      Financial agent services . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .                                  31        ......            31        108      ......        108       ......    ......      ......
    United States Mint . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .                        106           136           -30         352        450         -98         293       331            -38
    """

    parsed = parse_mts_table5_target_lines(text, record_date="2005-01-31")

    assert list(parsed["classification_desc"]) == ["Financial Agent Services", "United States Mint"]
    fas = parsed.loc[parsed["classification_desc"].eq("Financial Agent Services")].iloc[0]
    assert fas["current_month_gross_outly_mil"] == 31.0
    assert pd.isna(fas["current_month_app_rcpt_mil"])
    assert fas["current_month_net_outly_mil"] == 31.0
    mint = parsed.loc[parsed["classification_desc"].eq("United States Mint")].iloc[0]
    assert mint["current_month_gross_outly_mil"] == 106.0
    assert mint["current_month_app_rcpt_mil"] == 136.0
    assert mint["current_month_net_outly_mil"] == -30.0


def test_parse_mts_table5_target_lines_extracts_row_outlay_labels() -> None:
    text = """
    International Organizations and Conferences                         10               ......          10
    Foreign Military Financing Program                                  20               ......          20
    Global Health Programs                                              30               ......          30
    """

    parsed = parse_mts_table5_target_lines(text, record_date="2009-09-30")

    assert set(parsed["classification_desc"]) == {
        "International Organizations and Conferences",
        "Foreign Military Financing Program",
        "Global Health Programs",
    }


def test_parse_mts_table4_target_lines_extracts_corporation_tax_detail_row() -> None:
    text = """
    Corporation income taxes . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .                              6,699                                                    47,564                        226,526
    Corporation income taxes . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .                                 8,223         1,524         6,699       182,765      11,728      71,038       65,543       17,979        47,564
    """

    parsed = parse_mts_table4_target_lines(text, record_date="2005-01-31")

    assert list(parsed["classification_desc"]) == ["Corporation Income Taxes"]
    row = parsed.iloc[0]
    assert row["current_month_gross_rcpt_mil"] == 8223.0
    assert row["current_month_refund_mil"] == 1524.0
    assert row["current_month_net_rcpt_mil"] == 6699.0
    assert row["current_fytd_gross_rcpt_mil"] == 182765.0
    assert row["current_fytd_refund_mil"] == 11728.0
    assert row["current_fytd_net_rcpt_mil"] == 71038.0


def test_parse_mts_table4_target_lines_accepts_corporate_label_variant() -> None:
    text = " Corporation Income Taxes                                             9,577            2,383          7,194        106,069       13,976         92,093      118,268       13,767        104,500"

    parsed = parse_mts_table4_target_lines(text, record_date="2016-01-31")

    assert parsed.iloc[0]["classification_desc"] == "Corporation Income Taxes"
    assert parsed.iloc[0]["current_month_net_rcpt_mil"] == 7194.0


def test_parse_mts_table4_target_lines_ignores_later_monthly_summary_sections() -> None:
    text = """
    Table 4. Receipts of the U.S. Government
    Corporation Income Taxes.............................................................................                       36,996            8,203            28,793         225,891     87,662        138,229       354,293     49,947         304,346
    Table 5. Outlays of the U.S. Government
    Table 7. Receipts and Outlays of the U.S. Government by Month
    Corporation Income Taxes.....................................................                      81    1,994 48,293 4,532       -2,056      3,392 14,545      -1,404   32,529    2,577     4,953 28,793         138,229        304,346
    """

    parsed = parse_mts_table4_target_lines(text, record_date="2009-09-30")

    assert parsed.iloc[0]["current_month_gross_rcpt_mil"] == 36996.0
    assert parsed.iloc[0]["current_month_refund_mil"] == 8203.0
    assert parsed.iloc[0]["current_month_net_rcpt_mil"] == 28793.0


def test_parse_mts_printed_total_lines_extracts_summary_and_detailed_totals() -> None:
    text = """
    Table 3. Summary of Receipts and Outlays of the U.S. Government
    Corporation income taxes ............................................................... 11,585 44,566 78,334 143,186
    Total Receipts ........................................................................ 120,371 825,156 878,943 1,836,218
    Total outlays ......................................................................... 179,082 1,077,805 1,010,864 2,140,377
    Table 4. Receipts of the U.S. Government
    Total Receipts ........................................................................ 120,371 825,156 878,943 1,836,218
    Table 5. Outlays of the U.S. Government
    Total outlays ......................................................................... 196,330 17,248 179,082 1,184,173 106,368 1,077,805 1,120,576 109,713 1,010,864
    Table 6. Means of Financing
    """

    summary = parse_mts_summary_total_lines(text, record_date="2003-03-31")
    corp = parse_mts_table3_receipt_source_line(text, record_date="2003-03-31")
    table4 = parse_mts_table4_printed_total_line(text, record_date="2003-03-31")
    table5 = parse_mts_table5_printed_total_line(text, record_date="2003-03-31")

    assert set(summary["total_name"]) == {"total_receipts", "total_outlays"}
    assert corp.iloc[0]["current_month_net_mil"] == 11585.0
    assert table4.iloc[0]["current_month_net_mil"] == 120371.0
    assert table5.iloc[0]["current_month_gross_mil"] == 196330.0
    assert table5.iloc[0]["current_month_app_receipts_mil"] == 17248.0
    assert table5.iloc[0]["current_month_net_mil"] == 179082.0


def test_build_mts_parser_total_reconciliation_passes_matching_printed_totals(tmp_path: Path) -> None:
    text_path = tmp_path / "mts0303.txt"
    text_path.write_text(
        """
        Table 3. Summary of Receipts and Outlays of the U.S. Government
        Corporation income taxes ............................................................... 11,585 44,566 78,334 143,186
        Total Receipts ........................................................................ 120,371 825,156 878,943 1,836,218
        Total outlays ......................................................................... 179,082 1,077,805 1,010,864 2,140,377
        Table 4. Receipts of the U.S. Government
        Total Receipts ........................................................................ 120,371 825,156 878,943 1,836,218
        Table 5. Outlays of the U.S. Government
        Total outlays ......................................................................... 196,330 17,248 179,082 1,184,173 106,368 1,077,805 1,120,576 109,713 1,010,864
        Table 6. Means of Financing
        """,
        encoding="utf-8",
    )
    manifest = pd.DataFrame([{"record_date": "2003-03-31", "text_cache_path": str(text_path)}])
    table4_history = pd.DataFrame(
        [
            {
                "record_date": "2003-03-31",
                "current_month_gross_rcpt_mil": 21861.0,
                "current_month_refund_mil": 10276.0,
                "current_month_net_rcpt_mil": 11585.0,
                "current_fytd_net_rcpt_mil": 44566.0,
            }
        ]
    )

    reconciliation = build_mts_parser_total_reconciliation(manifest, table4_history=table4_history)

    assert len(reconciliation) == 2
    assert set(reconciliation["status"]) == {"pass"}
    markdown = render_mts_parser_total_reconciliation_markdown(reconciliation)
    assert "All parsed printed total checks pass" in markdown


def test_parse_mts_table5_target_lines_handles_unicode_minus_and_bfs_parent() -> None:
    text = """
    Bureau of the Fiscal Service:
      Financial Agent Services                                          50               ......          50             207              ......         207            197             ......         197
    United States Mint                                                 248              359           −110       1,014           1,153           −138       1,086           1,265           −179
    """

    parsed = parse_mts_table5_target_lines(text, record_date="2016-01-31")

    assert list(parsed["classification_desc"]) == ["Financial Agent Services", "United States Mint"]
    assert parsed.loc[1, "current_month_net_outly_mil"] == -110.0
    assert parsed.loc[1, "current_fytd_gross_outly_mil"] == 1014.0


def test_build_mts_table5_target_history_from_manifest_reads_cached_text(tmp_path: Path) -> None:
    text_path = tmp_path / "text" / "mts0105.txt"
    text_path.parent.mkdir()
    text_path.write_text(
        "Financial agent services 31 ...... 31 108 ...... 108 ...... ...... ......\n"
        "United States Mint 106 136 -30 352 450 -98 293 331 -38\n",
        encoding="utf-8",
    )
    manifest = pd.DataFrame(
        [
            {
                "record_date": "2005-01-31",
                "pdf_url": "https://example.test/mts0105.pdf",
                "text_cache_path": str(text_path),
            }
        ]
    )

    history = build_mts_table5_target_history_from_manifest(manifest)

    assert list(history["classification_desc"]) == ["Financial Agent Services", "United States Mint"]
    assert list(history["source_url"]) == ["https://example.test/mts0105.pdf"] * 2


def test_build_mts_fas_early_window_qa_keeps_early_missing_fas_nonpreferred() -> None:
    manifest = pd.DataFrame(
        [
            {"record_date": "2003-01-31"},
            {"record_date": "2004-12-31"},
            {"record_date": "2005-01-31"},
        ]
    )
    table5 = pd.DataFrame(
        [
            {"record_date": "2005-01-31", "classification_desc": "Financial Agent Services", "current_month_net_outly_mil": 31.0},
        ]
    )

    qa = build_mts_fas_early_window_qa(manifest=manifest, table5_history=table5)

    assert len(qa) == 2
    assert set(qa["qa_status"]) == {"manual_qa_no_direct_leaf"}
    assert not qa["preferred_research_eligible"].any()
    assert set(qa["fallback_treatment"]) == {"no_silent_backfill_keep_direct_component_zero"}
    markdown = render_mts_fas_early_window_qa_markdown(qa)
    assert "pre-stable Financial Agent Services window" in markdown


def test_build_mts_table4_target_history_from_manifest_reads_cached_text(tmp_path: Path) -> None:
    text_path = tmp_path / "text" / "mts0105.txt"
    text_path.parent.mkdir()
    text_path.write_text(
        "Corporation Income Taxes 8,223 1,524 6,699 182,765 11,728 71,038 65,543 17,979 47,564\n",
        encoding="utf-8",
    )
    manifest = pd.DataFrame(
        [
            {
                "record_date": "2005-01-31",
                "pdf_url": "https://example.test/mts0105.pdf",
                "text_cache_path": str(text_path),
            }
        ]
    )

    history = build_mts_table4_target_history_from_manifest(manifest)

    assert list(history["classification_desc"]) == ["Corporation Income Taxes"]
    assert history.iloc[0]["current_month_gross_rcpt_mil"] == 8223.0
    assert history.iloc[0]["source_url"] == "https://example.test/mts0105.pdf"


def test_write_mts_table5_target_history_from_manifest_writes_empty_shape_for_uncached_text(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    out_path = tmp_path / "history.csv"
    pd.DataFrame(
        [
            {
                "record_date": "2005-01-31",
                "pdf_url": "https://example.test/mts0105.pdf",
                "text_cache_path": str(tmp_path / "missing.txt"),
            }
        ]
    ).to_csv(manifest_path, index=False)

    written = write_mts_table5_target_history_from_manifest(manifest_path=manifest_path, out_path=out_path)

    assert written == out_path
    assert "current_month_net_outly_mil" in pd.read_csv(out_path).columns


def test_write_mts_table4_target_history_from_manifest_writes_empty_shape_for_uncached_text(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    out_path = tmp_path / "history.csv"
    pd.DataFrame(
        [
            {
                "record_date": "2005-01-31",
                "pdf_url": "https://example.test/mts0105.pdf",
                "text_cache_path": str(tmp_path / "missing.txt"),
            }
        ]
    ).to_csv(manifest_path, index=False)

    written = write_mts_table4_target_history_from_manifest(manifest_path=manifest_path, out_path=out_path)

    assert written == out_path
    assert "current_month_net_rcpt_mil" in pd.read_csv(out_path).columns


def test_table4_target_history_to_fiscaldata_receipts_converts_millions_to_dollars() -> None:
    history = pd.DataFrame(
        [
            {
                "record_date": "2005-01-31",
                "classification_desc": "Corporation Income Taxes",
                "current_month_gross_rcpt_mil": 8223.0,
                "current_month_refund_mil": 1524.0,
                "current_month_net_rcpt_mil": 6699.0,
                "source_parse_method": "pdf_text_line_target",
            }
        ]
    )

    receipts = table4_target_history_to_fiscaldata_receipts(history)

    assert receipts.iloc[0]["current_month_gross_rcpt_amt"] == 8_223_000_000.0
    assert receipts.iloc[0]["current_month_refund_amt"] == 1_524_000_000.0
    assert receipts.iloc[0]["current_month_net_rcpt_amt"] == 6_699_000_000.0


def test_table5_target_history_to_fiscaldata_outlays_converts_millions_to_dollars() -> None:
    history = pd.DataFrame(
        [
            {
                "record_date": "2005-01-31",
                "classification_desc": "United States Mint",
                "current_month_gross_outly_mil": 106.0,
                "current_month_app_rcpt_mil": 136.0,
                "current_month_net_outly_mil": -30.0,
                "source_parse_method": "pdf_text_line_target",
            }
        ]
    )

    outlays = table5_target_history_to_fiscaldata_outlays(history)

    assert outlays.iloc[0]["current_month_gross_outly_amt"] == 106_000_000.0
    assert outlays.iloc[0]["current_month_app_rcpt_amt"] == 136_000_000.0
    assert outlays.iloc[0]["current_month_net_outly_amt"] == -30_000_000.0


def test_write_target_history_as_fiscaldata_files(tmp_path: Path) -> None:
    table4_history = tmp_path / "table4_history.csv"
    table5_history = tmp_path / "table5_history.csv"
    receipts_out = tmp_path / "receipts.csv"
    outlays_out = tmp_path / "outlays.csv"
    pd.DataFrame(
        [
            {
                "record_date": "2005-01-31",
                "classification_desc": "Corporation Income Taxes",
                "current_month_gross_rcpt_mil": 1.0,
                "current_month_refund_mil": 0.25,
                "current_month_net_rcpt_mil": 0.75,
            }
        ]
    ).to_csv(table4_history, index=False)
    pd.DataFrame(
        [
            {
                "record_date": "2005-01-31",
                "classification_desc": "Financial Agent Services",
                "current_month_gross_outly_mil": 2.0,
                "current_month_app_rcpt_mil": 0.0,
                "current_month_net_outly_mil": 2.0,
            }
        ]
    ).to_csv(table5_history, index=False)

    write_table4_target_history_as_fiscaldata_receipts(history_path=table4_history, out_path=receipts_out)
    write_table5_target_history_as_fiscaldata_outlays(history_path=table5_history, out_path=outlays_out)

    assert pd.read_csv(receipts_out).iloc[0]["current_month_net_rcpt_amt"] == 750_000.0
    assert pd.read_csv(outlays_out).iloc[0]["current_month_net_outly_amt"] == 2_000_000.0


def test_stitch_previous_targets_with_fiscaldata_prefers_api_overlap() -> None:
    previous = pd.DataFrame(
        [
            ["2015-02-28", "Corporation Income Taxes", 1.0],
            ["2015-03-31", "Corporation Income Taxes", 2.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    )
    fiscaldata = pd.DataFrame(
        [
            ["2015-03-31", "Corporation Income Taxes", 3.0],
            ["2015-04-30", "Corporation Income Taxes", 4.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    )

    stitched = stitch_previous_targets_with_fiscaldata(previous_targets=previous, fiscaldata=fiscaldata)

    assert list(stitched["record_date"]) == ["2015-02-28", "2015-03-31", "2015-04-30"]
    assert list(stitched["current_month_net_rcpt_amt"]) == [1.0, 3.0, 4.0]
    assert list(stitched["source_tier"]) == ["D_pdf_text_parsed", "A_fiscaldata_api", "A_fiscaldata_api"]


def test_write_stitched_previous_targets_with_fiscaldata_writes_combined_csv(tmp_path: Path) -> None:
    previous_path = tmp_path / "previous.csv"
    fiscaldata_path = tmp_path / "api.csv"
    out_path = tmp_path / "stitched.csv"
    pd.DataFrame(
        [["2015-02-28", "United States Mint", 1.0]],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(previous_path, index=False)
    pd.DataFrame(
        [["2015-03-31", "United States Mint", 2.0]],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(fiscaldata_path, index=False)

    written = write_stitched_previous_targets_with_fiscaldata(
        previous_targets_path=previous_path,
        fiscaldata_path=fiscaldata_path,
        out_path=out_path,
    )

    assert written == out_path
    stitched = pd.read_csv(out_path)
    assert list(stitched["current_month_net_outly_amt"]) == [1.0, 2.0]


def test_build_mts_previous_issue_coverage_report_flags_expected_targets() -> None:
    manifest = pd.DataFrame(
        [
            {"record_date": "2004-01-31", "issue_month": "2004-01", "pdf_cached": True, "text_cached": True},
            {"record_date": "2005-01-31", "issue_month": "2005-01", "pdf_cached": True, "text_cached": True},
        ]
    )
    table4 = pd.DataFrame(
        [{"record_date": "2005-01-31", "classification_desc": "Corporation Income Taxes"}]
    )
    table5 = pd.DataFrame(
        [
            {"record_date": "2004-01-31", "classification_desc": "United States Mint"},
            {"record_date": "2005-01-31", "classification_desc": "Financial Agent Services"},
            {"record_date": "2005-01-31", "classification_desc": "United States Mint"},
            {"record_date": "2005-01-31", "classification_desc": "International Organizations and Conferences"},
        ]
    )

    report = build_mts_previous_issue_coverage_report(manifest=manifest, table4_history=table4, table5_history=table5)

    jan2004 = report.loc[report["record_date"].eq("2004-01-31")].iloc[0]
    jan2005 = report.loc[report["record_date"].eq("2005-01-31")].iloc[0]
    assert jan2004["fas_status"] == "pre_direct_leaf_manual_qa"
    assert jan2005["coverage_status"] == "ok"
    assert int(jan2005["row_narrow_label_count"]) == 1


def test_render_and_write_mts_previous_issue_coverage_report(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    table4_path = tmp_path / "table4.csv"
    table5_path = tmp_path / "table5.csv"
    csv_path = tmp_path / "coverage.csv"
    md_path = tmp_path / "coverage.md"
    pd.DataFrame([{"record_date": "2005-01-31", "issue_month": "2005-01", "pdf_cached": True, "text_cached": True}]).to_csv(
        manifest_path, index=False
    )
    pd.DataFrame([{"record_date": "2005-01-31", "classification_desc": "Corporation Income Taxes"}]).to_csv(
        table4_path, index=False
    )
    pd.DataFrame([{"record_date": "2005-01-31", "classification_desc": "United States Mint"}]).to_csv(
        table5_path, index=False
    )

    written_csv, written_md = write_mts_previous_issue_coverage_report(
        manifest_path=manifest_path,
        table4_history_path=table4_path,
        table5_history_path=table5_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert written_csv == csv_path
    assert written_md == md_path
    assert "MTS Previous-Issue Coverage Report" in md_path.read_text()
    assert "Needs review" in render_mts_previous_issue_coverage_markdown(pd.read_csv(csv_path))


def test_build_mts_target_overlap_audit_compares_parsed_to_api_with_rounding_tolerance() -> None:
    table4_history = pd.DataFrame(
        [
            {
                "record_date": "2015-03-31",
                "classification_desc": "Corporation Income Taxes",
                "current_month_gross_rcpt_mil": 10.0,
                "current_month_refund_mil": 2.0,
                "current_month_net_rcpt_mil": 8.0,
            }
        ]
    )
    table4_api = pd.DataFrame(
        [
            {
                "record_date": "2015-03-31",
                "classification_desc": "Corporation Income Taxes",
                "current_month_gross_rcpt_amt": 10_200_000.0,
                "current_month_refund_amt": 2_100_000.0,
                "current_month_net_rcpt_amt": 8_100_000.0,
            }
        ]
    )
    table5_history = pd.DataFrame(
        [
            {
                "record_date": "2015-03-31",
                "classification_desc": "United States Mint",
                "current_month_gross_outly_mil": 5.0,
                "current_month_app_rcpt_mil": 7.0,
                "current_month_net_outly_mil": -2.0,
            }
        ]
    )
    table5_api = pd.DataFrame(
        [
            {
                "record_date": "2015-03-31",
                "classification_desc": "United States Mint",
                "current_month_gross_outly_amt": 5_100_000.0,
                "current_month_app_rcpt_amt": 6_900_000.0,
                "current_month_net_outly_amt": -1_800_000.0,
            }
        ]
    )

    audit = build_mts_target_overlap_audit(
        table4_history=table4_history,
        table4_fiscaldata=table4_api,
        table5_history=table5_history,
        table5_fiscaldata=table5_api,
    )

    assert audit["audit_status"].eq("pass").all()
    assert set(audit["table_nbr"]) == {"4", "5"}


def test_build_mts_target_overlap_audit_flags_missing_api_match() -> None:
    table5_history = pd.DataFrame(
        [
            {
                "record_date": "2015-03-31",
                "classification_desc": "Missing Label",
                "current_month_gross_outly_mil": 1.0,
                "current_month_app_rcpt_mil": 0.0,
                "current_month_net_outly_mil": 1.0,
            }
        ]
    )

    audit = build_mts_target_overlap_audit(
        table5_history=table5_history,
        table5_fiscaldata=pd.DataFrame(columns=["record_date", "classification_desc"]),
    )

    assert set(audit["audit_status"]) == {"missing_api_match"}
    assert "blocking" in render_mts_target_overlap_audit_markdown(audit)


def test_write_mts_target_overlap_audit_outputs_csv_and_markdown(tmp_path: Path) -> None:
    table4_history_path = tmp_path / "table4_history.csv"
    table4_api_path = tmp_path / "table4_api.csv"
    table5_history_path = tmp_path / "table5_history.csv"
    table5_api_path = tmp_path / "table5_api.csv"
    csv_path = tmp_path / "audit.csv"
    md_path = tmp_path / "audit.md"
    pd.DataFrame(
        [
            {
                "record_date": "2015-03-31",
                "classification_desc": "Corporation Income Taxes",
                "current_month_gross_rcpt_mil": 1.0,
                "current_month_refund_mil": 0.0,
                "current_month_net_rcpt_mil": 1.0,
            }
        ]
    ).to_csv(table4_history_path, index=False)
    pd.DataFrame(
        [
            {
                "record_date": "2015-03-31",
                "classification_desc": "Corporation Income Taxes",
                "current_month_gross_rcpt_amt": 1_000_000.0,
                "current_month_refund_amt": 0.0,
                "current_month_net_rcpt_amt": 1_000_000.0,
            }
        ]
    ).to_csv(table4_api_path, index=False)
    pd.DataFrame(columns=["record_date", "classification_desc"]).to_csv(table5_history_path, index=False)
    pd.DataFrame(columns=["record_date", "classification_desc"]).to_csv(table5_api_path, index=False)

    written_csv, written_md = write_mts_target_overlap_audit(
        table4_history_path=table4_history_path,
        table4_fiscaldata_path=table4_api_path,
        table5_history_path=table5_history_path,
        table5_fiscaldata_path=table5_api_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert written_csv == csv_path
    assert written_md == md_path
    assert "MTS Target Overlap Audit" in md_path.read_text()
