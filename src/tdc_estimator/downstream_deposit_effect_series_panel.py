from __future__ import annotations

from pathlib import Path

import pandas as pd


PANEL_COLUMNS = [
    "date",
    "series_key",
    "series_family",
    "use_case_key",
    "current_role",
    "default_classification",
    "deposit_scope",
    "value_millions",
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


def _series_rows(
    *,
    series: pd.Series,
    series_key: str,
    series_family: str,
    use_case_key: str,
    current_role: str,
    default_classification: str,
    deposit_scope: str,
    bank_receipt_boundary: str,
    row_receipt_boundary: str,
    historical_only: bool,
    nondefault_only: bool,
    summary_note: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    aligned = pd.to_numeric(series, errors="coerce").dropna()
    for date, value in aligned.items():
        rows.append(
            {
                "date": pd.Timestamp(date),
                "series_key": series_key,
                "series_family": series_family,
                "use_case_key": use_case_key,
                "current_role": current_role,
                "default_classification": default_classification,
                "deposit_scope": deposit_scope,
                "value_millions": float(value),
                "bank_receipt_boundary": bank_receipt_boundary,
                "row_receipt_boundary": row_receipt_boundary,
                "historical_only": bool(historical_only),
                "nondefault_only": bool(nondefault_only),
                "summary_note": summary_note,
            }
        )
    return rows


def build_downstream_deposit_effect_series_panel(
    *,
    estimates: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
) -> pd.DataFrame:
    if estimates is None or estimates.empty:
        return pd.DataFrame(columns=PANEL_COLUMNS)

    est = estimates.copy()
    est.index = pd.to_datetime(est.index)

    hist = tier3_historical_bank_receipt_research.copy() if tier3_historical_bank_receipt_research is not None else pd.DataFrame()
    if not hist.empty:
        if "date" in hist.columns:
            hist["date"] = pd.to_datetime(hist["date"])
            hist = hist.set_index("date")
        else:
            hist.index = pd.to_datetime(hist.index)

    mrv = row_state_visa_timing_sensitivity.copy() if row_state_visa_timing_sensitivity is not None else pd.DataFrame()
    if not mrv.empty:
        if "date" in mrv.columns:
            mrv["date"] = pd.to_datetime(mrv["date"])
            mrv = mrv.set_index("date")
        else:
            mrv.index = pd.to_datetime(mrv.index)

    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    bank_current = _get_row(receipt, "branch_key", "bank_table51_current_window")
    bank_hist = _get_row(receipt, "branch_key", "bank_table51_historical_window")
    row_mrv = _get_row(receipt, "branch_key", "row_mrv_cbsp_primary")

    bank_boundary = str(bank_current.get("promotion_boundary", "historical_default_only_current_nondefault"))
    row_boundary = str(row_mrv.get("promotion_boundary", "stop_at_mrv_nondefault_pilot"))

    rows: list[dict[str, object]] = []

    base_specs = [
        (
            "tdc_base_bank_only_ru_flow",
            "estimator_series",
            "current_quarter_bank_only_headline",
            "headline_anchor",
            "headline_default",
            "bank_only",
            False,
            False,
            "Base bank-only anchor for ladder comparisons.",
        ),
        (
            "tdc_tier2_interest_corrected_bank_only_ru_flow",
            "estimator_series",
            "current_quarter_bank_only_headline",
            "interest_cleaned_comparison",
            "default_sensitivity_with_stronger_transfer_cleanup",
            "bank_only",
            False,
            False,
            "Tier 2 comparison surface used to isolate coupon cleanup from receipt-side issues.",
        ),
        (
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            "estimator_series",
            "current_quarter_bank_only_headline",
            "live_bank_only_headline",
            "live_default_with_partial_receipt_cells",
            "bank_only",
            False,
            False,
            "Live fiscal-flow bank-only headline with explicit receipt-side caveats.",
        ),
        (
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
            "estimator_series",
            "deposit_perimeter_comparison",
            "broad_depository_comparison",
            "broad_depository_default",
            "broad_depository",
            False,
            False,
            "Broad-depository comparison series for perimeter-effect work.",
        ),
    ]
    for (
        column,
        family,
        use_case,
        role,
        classification,
        scope,
        historical_only,
        nondefault_only,
        note,
    ) in base_specs:
        if column not in est.columns:
            continue
        rows.extend(
            _series_rows(
                series=est[column],
                series_key=column,
                series_family=family,
                use_case_key=use_case,
                current_role=role,
                default_classification=classification,
                deposit_scope=scope,
                bank_receipt_boundary=bank_boundary,
                row_receipt_boundary=row_boundary,
                historical_only=historical_only,
                nondefault_only=nondefault_only,
                summary_note=note,
            )
        )

    if not hist.empty:
        hist_specs = [
            (
                "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate",
                "historical_overlay",
                "historical_bank_receipt_backtest",
                "historical_candidate_overlay",
                "historical_default_only",
                "bank_only",
                "Historical age-eligible bank receipt overlay candidate.",
            ),
            (
                "tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound",
                "historical_overlay",
                "historical_bank_receipt_backtest",
                "historical_lower_bound_overlay",
                "historical_lower_bound",
                "bank_only",
                "Historical lower-bound bank receipt overlay.",
            ),
        ]
        for column, family, use_case, role, classification, scope, note in hist_specs:
            if column not in hist.columns:
                continue
            rows.extend(
                _series_rows(
                    series=hist[column],
                    series_key=column,
                    series_family=family,
                    use_case_key=use_case,
                    current_role=role,
                    default_classification=classification,
                    deposit_scope=scope,
                    bank_receipt_boundary=str(
                        bank_hist.get("promotion_boundary", "historical_default_only_current_nondefault")
                    ),
                    row_receipt_boundary=row_boundary,
                    historical_only=True,
                    nondefault_only=False,
                    summary_note=note,
                )
            )

    if not mrv.empty and "row_state_visa_allocated_receipt_mil" in mrv.columns:
        rows.extend(
            _series_rows(
                series=mrv["row_state_visa_allocated_receipt_mil"],
                series_key="row_mrv_primary_nondefault_pilot_series",
                series_family="nondefault_pilot_series",
                use_case_key="current_row_receipt_sensitivity",
                current_role="bounded_row_receipt_sensitivity_series",
                default_classification="nondefault_pilot",
                deposit_scope="bank_only",
                bank_receipt_boundary=bank_boundary,
                row_receipt_boundary=row_boundary,
                historical_only=False,
                nondefault_only=True,
                summary_note="MRV-first recurring ROW receipt sensitivity series. Use only as a bounded nondefault pilot.",
            )
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=PANEL_COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["latest_nonzero_date"] = pd.NaT
    frame["latest_nonzero_value_millions"] = pd.NA
    for series_key, group in frame.groupby("series_key", sort=False):
        nonzero = group.loc[group["value_millions"].ne(0)]
        if nonzero.empty:
            continue
        latest_nonzero = nonzero.sort_values("date").iloc[-1]
        mask = frame["series_key"].eq(series_key)
        frame.loc[mask, "latest_nonzero_date"] = latest_nonzero["date"]
        frame.loc[mask, "latest_nonzero_value_millions"] = float(latest_nonzero["value_millions"])
    frame = frame.sort_values(["series_key", "date"]).reset_index(drop=True)
    return frame.reindex(columns=PANEL_COLUMNS)


def render_downstream_deposit_effect_series_panel_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Deposit-Effect Series Panel"
    intro = (
        "Tidy backend panel for downstream deposit-effect work. It packages the main estimator series, "
        "historical bank overlays, and bounded MRV pilot series with the relevant boundary labels attached."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream deposit-effect series rows are available."])

    latest = frame.sort_values("date").groupby("series_key", as_index=False).tail(1)
    lines = [
        title,
        "",
        intro,
        "",
        "| Series | Use case | Role | Classification | Scope | Latest date | Latest value (mil) | Latest nonzero support | Historical only | Nondefault only |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for _, row in latest.iterrows():
        date = pd.Timestamp(row["date"]).date().isoformat() if pd.notna(row["date"]) else "n/a"
        value = row["value_millions"]
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
                    str(row["series_key"]),
                    str(row["use_case_key"]),
                    str(row["current_role"]),
                    str(row["default_classification"]),
                    str(row["deposit_scope"]),
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


def write_downstream_deposit_effect_series_panel(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    estimates: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_deposit_effect_series_panel(
        estimates=estimates,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        receipt_unblock_status=receipt_unblock_status,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_deposit_effect_series_panel_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
