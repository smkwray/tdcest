from __future__ import annotations

from pathlib import Path

import pandas as pd


PANEL_COLUMNS = [
    "date",
    "comparison_key",
    "comparison_family",
    "lhs_series_key",
    "rhs_series_key",
    "lhs_value_millions",
    "rhs_value_millions",
    "net_delta_millions",
    "bank_receipt_boundary",
    "row_receipt_boundary",
    "historical_only",
    "nondefault_only",
    "latest_nonzero_date",
    "latest_nonzero_value_millions",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def _num_series(df: pd.DataFrame | None, column: str) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(dtype="float64")
    series = pd.to_numeric(df[column], errors="coerce")
    series.index = pd.to_datetime(series.index)
    return series


def _rows_for_comparison(
    *,
    lhs: pd.Series,
    rhs: pd.Series | None,
    comparison_key: str,
    comparison_family: str,
    lhs_series_key: str,
    rhs_series_key: str,
    bank_receipt_boundary: str,
    row_receipt_boundary: str,
    historical_only: bool,
    nondefault_only: bool,
    summary_note: str,
) -> list[dict[str, object]]:
    rhs = rhs if rhs is not None else pd.Series(0.0, index=lhs.index, dtype="float64")
    index = lhs.index.union(rhs.index).sort_values()
    lhs_aligned = pd.to_numeric(lhs, errors="coerce").reindex(index)
    rhs_aligned = pd.to_numeric(rhs, errors="coerce").reindex(index)
    out: list[dict[str, object]] = []
    for date in index:
        lhs_value = lhs_aligned.loc[date]
        rhs_value = rhs_aligned.loc[date]
        if pd.isna(lhs_value) or pd.isna(rhs_value):
            continue
        out.append(
            {
                "date": pd.Timestamp(date),
                "comparison_key": comparison_key,
                "comparison_family": comparison_family,
                "lhs_series_key": lhs_series_key,
                "rhs_series_key": rhs_series_key,
                "lhs_value_millions": float(lhs_value),
                "rhs_value_millions": float(rhs_value),
                "net_delta_millions": float(lhs_value - rhs_value),
                "bank_receipt_boundary": bank_receipt_boundary,
                "row_receipt_boundary": row_receipt_boundary,
                "historical_only": bool(historical_only),
                "nondefault_only": bool(nondefault_only),
                "summary_note": summary_note,
            }
        )
    return out


def build_downstream_deposit_effect_comparison_panel(
    *,
    estimates: pd.DataFrame | None,
    corrections: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
) -> pd.DataFrame:
    if estimates is None or estimates.empty:
        return pd.DataFrame(columns=PANEL_COLUMNS)

    est = estimates.copy()
    est.index = pd.to_datetime(est.index)
    corr = corrections.copy() if corrections is not None else pd.DataFrame()
    if not corr.empty:
        corr.index = pd.to_datetime(corr.index)

    hist = tier3_historical_bank_receipt_research.copy() if tier3_historical_bank_receipt_research is not None else pd.DataFrame()
    if not hist.empty:
        if "date" in hist.columns:
            hist["date"] = pd.to_datetime(hist["date"])
            hist = hist.set_index("date")
        else:
            hist.index = pd.to_datetime(hist.index)

    row_mrv = row_state_visa_timing_sensitivity.copy() if row_state_visa_timing_sensitivity is not None else pd.DataFrame()
    if not row_mrv.empty:
        if "date" in row_mrv.columns:
            row_mrv["date"] = pd.to_datetime(row_mrv["date"])
            row_mrv = row_mrv.set_index("date")
        else:
            row_mrv.index = pd.to_datetime(row_mrv.index)

    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    bank_current = _get_row(receipt, "branch_key", "bank_table51_current_window")
    bank_hist = _get_row(receipt, "branch_key", "bank_table51_historical_window")
    row_branch = _get_row(receipt, "branch_key", "row_mrv_cbsp_primary")

    bank_boundary = str(bank_current.get("promotion_boundary", "historical_default_only_current_nondefault"))
    bank_hist_boundary = str(bank_hist.get("promotion_boundary", bank_boundary))
    row_boundary = str(row_branch.get("promotion_boundary", "stop_at_mrv_nondefault_pilot"))

    rows: list[dict[str, object]] = []

    base = _num_series(est, "tdc_base_bank_only_ru_flow")
    tier2 = _num_series(est, "tdc_tier2_interest_corrected_bank_only_ru_flow")
    tier3 = _num_series(est, "tdc_tier3_fiscal_corrected_bank_only_ru_flow")
    broad = _num_series(est, "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow")

    rows.extend(
        _rows_for_comparison(
            lhs=tier2,
            rhs=base,
            comparison_key="bank_only_tier2_minus_base",
            comparison_family="interest_cleanup",
            lhs_series_key="tdc_tier2_interest_corrected_bank_only_ru_flow",
            rhs_series_key="tdc_base_bank_only_ru_flow",
            bank_receipt_boundary=bank_boundary,
            row_receipt_boundary=row_boundary,
            historical_only=False,
            nondefault_only=False,
            summary_note="Interest-cleanup comparison between the base bank-only headline and Tier 2.",
        )
    )
    rows.extend(
        _rows_for_comparison(
            lhs=tier3,
            rhs=tier2,
            comparison_key="bank_only_tier3_partial_shell_minus_tier2",
            comparison_family="partial_fiscal_shell",
            lhs_series_key="tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            rhs_series_key="tdc_tier2_interest_corrected_bank_only_ru_flow",
            bank_receipt_boundary=bank_boundary,
            row_receipt_boundary=row_boundary,
            historical_only=False,
            nondefault_only=False,
            summary_note="Partial fiscal-shell comparison between Tier 2 and the outlay-backed Tier 3 diagnostic.",
        )
    )
    rows.extend(
        _rows_for_comparison(
            lhs=broad,
            rhs=tier3,
            comparison_key="broad_depository_tier3_minus_bank_only_tier3",
            comparison_family="deposit_perimeter",
            lhs_series_key="tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
            rhs_series_key="tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            bank_receipt_boundary=bank_boundary,
            row_receipt_boundary=row_boundary,
            historical_only=False,
            nondefault_only=False,
            summary_note="Perimeter comparison between broad-depository and bank-only Tier 3 partial-shell diagnostics.",
        )
    )

    if not hist.empty:
        hist_candidate = _num_series(hist, "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate")
        hist_lower = _num_series(hist, "tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound")
        hist_default = _num_series(hist, "tdc_tier3_fiscal_corrected_bank_only_ru_flow")

        rows.extend(
            _rows_for_comparison(
                lhs=hist_candidate,
                rhs=hist_default,
                comparison_key="historical_bank_receipt_candidate_minus_partial_shell",
                comparison_family="historical_receipt_overlay",
                lhs_series_key="tdc_tier3_bank_only_plus_historical_bank_receipt_candidate",
                rhs_series_key="tdc_tier3_fiscal_corrected_bank_only_ru_flow",
                bank_receipt_boundary=bank_hist_boundary,
                row_receipt_boundary=row_boundary,
                historical_only=True,
                nondefault_only=False,
                summary_note="Historical bank receipt overlay relative to the historical Tier 3 partial-shell series.",
            )
        )
        rows.extend(
            _rows_for_comparison(
                lhs=hist_candidate,
                rhs=hist_lower,
                comparison_key="historical_bank_receipt_candidate_minus_lower_bound",
                comparison_family="historical_receipt_uncertainty",
                lhs_series_key="tdc_tier3_bank_only_plus_historical_bank_receipt_candidate",
                rhs_series_key="tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound",
                bank_receipt_boundary=bank_hist_boundary,
                row_receipt_boundary=row_boundary,
                historical_only=True,
                nondefault_only=False,
                summary_note="Historical bank receipt candidate versus lower-bound overlay.",
            )
        )

    if not row_mrv.empty and "row_state_visa_allocated_receipt_mil" in row_mrv.columns:
        rows.extend(
            _rows_for_comparison(
                lhs=_num_series(row_mrv, "row_state_visa_allocated_receipt_mil"),
                rhs=None,
                comparison_key="row_mrv_nondefault_pilot_minus_live_zero",
                comparison_family="nondefault_row_receipt_pilot",
                lhs_series_key="row_mrv_primary_nondefault_pilot_series",
                rhs_series_key="row_live_receipt_missing_placeholder",
                bank_receipt_boundary=bank_boundary,
                row_receipt_boundary=row_boundary,
                historical_only=False,
                nondefault_only=True,
                summary_note="Bounded MRV receipt pilot compared against the missing/not-measured live ROW receipt placeholder.",
            )
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=PANEL_COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["latest_nonzero_date"] = pd.NaT
    frame["latest_nonzero_value_millions"] = pd.NA
    for comparison_key, group in frame.groupby("comparison_key", sort=False):
        nonzero = group.loc[group["net_delta_millions"].ne(0)]
        if nonzero.empty:
            continue
        latest_nonzero = nonzero.sort_values("date").iloc[-1]
        mask = frame["comparison_key"].eq(comparison_key)
        frame.loc[mask, "latest_nonzero_date"] = latest_nonzero["date"]
        frame.loc[mask, "latest_nonzero_value_millions"] = float(latest_nonzero["net_delta_millions"])
    frame = frame.sort_values(["comparison_key", "date"]).reset_index(drop=True)
    return frame.reindex(columns=PANEL_COLUMNS)


def render_downstream_deposit_effect_comparison_panel_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Deposit-Effect Comparison Panel"
    intro = (
        "Quarter-by-quarter comparison panel for downstream deposit-effect work. "
        "It tracks the main estimator deltas, historical bank overlays, and bounded MRV pilot deltas over time."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream comparison-panel rows are available."])

    latest = frame.sort_values("date").groupby("comparison_key", as_index=False).tail(1)
    lines = [
        title,
        "",
        intro,
        "",
        "| Comparison | Family | Latest date | Net delta (mil) | Latest nonzero support | Historical only | Nondefault only |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for _, row in latest.iterrows():
        date = pd.Timestamp(row["date"]).date().isoformat() if pd.notna(row["date"]) else "n/a"
        value = row["net_delta_millions"]
        value_text = "n/a" if value is None or pd.isna(value) else f"{float(value):,.3f}"
        latest_nonzero_date = (
            pd.Timestamp(row["latest_nonzero_date"]).date().isoformat()
            if pd.notna(row.get("latest_nonzero_date"))
            else "n/a"
        )
        latest_nonzero_value = row.get("latest_nonzero_value_millions")
        latest_nonzero_text = (
            f"{latest_nonzero_date} / {float(latest_nonzero_value):,.3f}"
            if latest_nonzero_value is not None and not pd.isna(latest_nonzero_value)
            else "n/a"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["comparison_key"]),
                    str(row["comparison_family"]),
                    date,
                    value_text,
                    latest_nonzero_text,
                    "yes" if bool(row["historical_only"]) else "no",
                    "yes" if bool(row["nondefault_only"]) else "no",
                ]
            )
            + " |"
        )

    return "\n".join(lines + [""])


def write_downstream_deposit_effect_comparison_panel(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    estimates: pd.DataFrame | None,
    corrections: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_deposit_effect_comparison_panel(
        estimates=estimates,
        corrections=corrections,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        receipt_unblock_status=receipt_unblock_status,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_deposit_effect_comparison_panel_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
