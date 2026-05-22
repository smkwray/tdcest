from __future__ import annotations

from pathlib import Path

import pandas as pd


def _fmt(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _fmt_date(value: object) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return "n/a"
    return pd.Timestamp(ts).date().isoformat()


def build_tier3_research_comparison(
    *,
    estimates: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
) -> pd.DataFrame:
    if estimates is None or estimates.empty:
        return pd.DataFrame()

    est = estimates.copy()
    est.index = pd.to_datetime(est.index)
    latest_date = est.index.max()
    latest = est.loc[latest_date]

    hist = tier3_historical_bank_receipt_research.copy() if tier3_historical_bank_receipt_research is not None else pd.DataFrame()
    latest_hist = pd.Series(dtype="object")
    if not hist.empty:
        if "date" in hist.columns:
            hist["date"] = pd.to_datetime(hist["date"])
            hist = hist.set_index("date")
        else:
            hist.index = pd.to_datetime(hist.index)
        latest_hist = hist.sort_index().iloc[-1]

    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    bank_hist = pd.Series(dtype="object")
    bank_current = pd.Series(dtype="object")
    row_mrv = pd.Series(dtype="object")
    if not receipt.empty:
        bank_hist = receipt.loc[receipt["branch_key"].eq("bank_table51_historical_window")].iloc[0] if receipt["branch_key"].eq("bank_table51_historical_window").any() else pd.Series(dtype="object")
        bank_current = receipt.loc[receipt["branch_key"].eq("bank_table51_current_window")].iloc[0] if receipt["branch_key"].eq("bank_table51_current_window").any() else pd.Series(dtype="object")
        row_mrv = receipt.loc[receipt["branch_key"].eq("row_mrv_cbsp_primary")].iloc[0] if receipt["branch_key"].eq("row_mrv_cbsp_primary").any() else pd.Series(dtype="object")

    rows = [
        {
            "comparison_key": "latest_live_tier2_vs_partial_shell",
            "reference_date": pd.Timestamp(latest_date).date().isoformat(),
            "tier2_bank_only_mil": float(latest.get("tdc_tier2_interest_corrected_bank_only_ru_flow", pd.NA)),
            "tier3_bank_only_mil": float(latest.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow", pd.NA)),
            "historical_bank_receipt_variant_mil": pd.NA,
            "historical_bank_lower_bound_variant_mil": pd.NA,
            "bank_receipt_boundary": str(bank_current.get("promotion_boundary", "n/a")),
            "row_receipt_boundary": str(row_mrv.get("promotion_boundary", "n/a")),
            "current_row_mrv_pilot_latest_date": pd.to_datetime(row_mrv.get("latest_relevant_date"), errors="coerce"),
            "current_row_mrv_pilot_mil": pd.to_numeric(row_mrv.get("latest_value_millions"), errors="coerce"),
            "interpretation": "Latest live comparison between Tier 2 and the Tier 3 partial shell; current receipt cells remain missing/not measured.",
        }
    ]

    if not latest_hist.empty:
        rows.append(
            {
                "comparison_key": "latest_historical_bank_window",
                "reference_date": pd.Timestamp(latest_hist.name).date().isoformat(),
                "tier2_bank_only_mil": float(est.loc[pd.Timestamp(latest_hist.name), "tdc_tier2_interest_corrected_bank_only_ru_flow"]),
                "tier3_bank_only_mil": float(latest_hist.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow", pd.NA)),
                "historical_bank_receipt_variant_mil": float(
                    latest_hist.get("tdc_tier3_bank_only_plus_historical_bank_receipt_candidate", pd.NA)
                ),
                "historical_bank_lower_bound_variant_mil": float(
                    latest_hist.get("tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound", pd.NA)
                ),
                "bank_receipt_boundary": str(bank_hist.get("promotion_boundary", "historical_default_only_current_nondefault")),
                "row_receipt_boundary": str(row_mrv.get("promotion_boundary", "n/a")),
                "current_row_mrv_pilot_latest_date": pd.to_datetime(row_mrv.get("latest_relevant_date"), errors="coerce"),
                "current_row_mrv_pilot_mil": pd.to_numeric(row_mrv.get("latest_value_millions"), errors="coerce"),
                "interpretation": "Latest historical age-eligible bank window showing how the nonzero historical bank receipt view changes Tier 3.",
            }
        )

    return pd.DataFrame(rows)


def render_tier3_research_comparison_markdown(frame: pd.DataFrame) -> str:
    title = "# Tier 3 Research Comparison"
    intro = (
        "Compact research comparison surface tying together the live Tier 2 headline / Tier 3 partial shell, "
        "the historical bank-receipt window, and the current receipt-side promotion boundaries."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No Tier 3 research comparison rows are available."])

    header = [
        "| Comparison | Reference date | Tier 2 bank-only | Tier 3 partial shell | Historical bank variant | Historical lower bound | Bank boundary | ROW boundary | MRV pilot date | MRV pilot (mil) | Interpretation |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | --- |",
    ]
    rows: list[str] = []
    for _, row in frame.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["comparison_key"]),
                    str(row["reference_date"]),
                    _fmt(row.get("tier2_bank_only_mil")),
                    _fmt(row.get("tier3_bank_only_mil")),
                    _fmt(row.get("historical_bank_receipt_variant_mil")),
                    _fmt(row.get("historical_bank_lower_bound_variant_mil")),
                    str(row.get("bank_receipt_boundary", "n/a")),
                    str(row.get("row_receipt_boundary", "n/a")),
                    _fmt_date(row.get("current_row_mrv_pilot_latest_date")),
                    _fmt(row.get("current_row_mrv_pilot_mil")),
                    str(row.get("interpretation", "")),
                ]
            )
            + " |"
        )

    return "\n".join([title, "", intro, "", *header, *rows, ""])


def write_tier3_research_comparison(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    estimates: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_tier3_research_comparison(
        estimates=estimates,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
        receipt_unblock_status=receipt_unblock_status,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_tier3_research_comparison_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
