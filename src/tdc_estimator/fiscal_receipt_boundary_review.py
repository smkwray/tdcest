from __future__ import annotations

from pathlib import Path

import pandas as pd


REVIEW_COLUMNS = [
    "boundary_key",
    "counterparty_group",
    "receipt_family",
    "current_repo_role",
    "included_in_live_tier3_headline",
    "included_in_historical_overlay",
    "latest_reference_date",
    "latest_value_millions",
    "strongest_supporting_surface",
    "binding_blocker",
    "downstream_use",
    "interpretation",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def _latest_quality_row(
    frame: pd.DataFrame | None,
    *,
    counterparty: str,
    source: str,
    note_contains: str | None = None,
) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype="object")
    subset = frame.loc[
        frame["row_family"].eq("nonborrow_receipts")
        & frame["counterparty_column"].eq(counterparty)
        & frame["source"].eq(source)
    ].copy()
    if note_contains:
        subset = subset.loc[subset["notes"].fillna("").str.contains(note_contains, case=False, regex=False)]
    if subset.empty:
        return pd.Series(dtype="object")
    if "last_date" in subset.columns:
        subset["last_date"] = pd.to_datetime(subset["last_date"], errors="coerce")
        subset = subset.sort_values("last_date")
    return subset.iloc[-1]


def _fmt_value(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return float(parsed)


def build_fiscal_receipt_boundary_review(
    *,
    fiscal_source_quality: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    tier3_research_comparison: pd.DataFrame | None,
    downstream_estimator_gap_review: pd.DataFrame | None,
    row_mrv_nondefault_evidence_summary: pd.DataFrame | None,
) -> pd.DataFrame:
    quality = fiscal_source_quality.copy() if fiscal_source_quality is not None else pd.DataFrame()
    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    research = tier3_research_comparison.copy() if tier3_research_comparison is not None else pd.DataFrame()
    gap = downstream_estimator_gap_review.copy() if downstream_estimator_gap_review is not None else pd.DataFrame()
    mrv_summary = (
        row_mrv_nondefault_evidence_summary.copy() if row_mrv_nondefault_evidence_summary is not None else pd.DataFrame()
    )

    bank_hist = _get_row(receipt, "branch_key", "bank_table51_historical_window")
    bank_current = _get_row(receipt, "branch_key", "bank_table51_current_window")
    row_mrv = _get_row(receipt, "branch_key", "row_mrv_cbsp_primary")
    latest_hist = _get_row(research, "comparison_key", "latest_historical_bank_window")
    latest_live = _get_row(research, "comparison_key", "latest_live_defaults")
    hist_gap = _get_row(gap, "gap_key", "latest_historical_bank_receipt_overlay")
    mrv_state = mrv_summary.iloc[0] if not mrv_summary.empty else pd.Series(dtype="object")
    historical_default = pd.to_numeric(latest_hist.get("tier3_bank_only_mil"), errors="coerce")
    historical_candidate = pd.to_numeric(latest_hist.get("historical_bank_receipt_variant_mil"), errors="coerce")
    historical_lower = pd.to_numeric(latest_hist.get("historical_bank_lower_bound_variant_mil"), errors="coerce")
    historical_candidate_effect = None
    historical_lower_effect = None
    if not pd.isna(historical_candidate) and not pd.isna(historical_default):
        historical_candidate_effect = float(historical_candidate - historical_default)
    if not pd.isna(historical_lower) and not pd.isna(historical_default):
        historical_lower_effect = float(historical_lower - historical_default)

    bank_default = _latest_quality_row(
        quality,
        counterparty="banks_default",
        source="tier3_support_file",
        note_contains="Current default bank nonborrow-receipt correction",
    )
    row_default = _latest_quality_row(
        quality,
        counterparty="row_total",
        source="tier3_support_file",
        note_contains="Current default ROW nonborrow-receipt correction",
    )
    bank_candidate = _latest_quality_row(
        quality,
        counterparty="banks_default",
        source="mts_plus_irs_soi_bridge",
        note_contains="default-candidate",
    )
    bank_strict = _latest_quality_row(
        quality,
        counterparty="banks_default",
        source="mts_plus_irs_soi_bridge",
        note_contains="strict-depository",
    )
    bank_finance = _latest_quality_row(
        quality,
        counterparty="banks_default",
        source="mts_plus_irs_soi_bridge",
        note_contains="Upper benchmark",
    )
    row_bea = _latest_quality_row(
        quality,
        counterparty="row_total",
        source="bea_nipa_table_3_2",
    )

    rows = [
        {
            "boundary_key": "bank_live_default_receipt_cell",
            "counterparty_group": "bank",
            "receipt_family": "missing_live_receipt_cell",
            "current_repo_role": "missing_not_measured_cell",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": False,
            "latest_reference_date": bank_default.get("last_date"),
            "latest_value_millions": _fmt_value(bank_default.get("latest_value_millions")),
            "strongest_supporting_surface": "tdc_fiscal_source_quality.csv",
            "binding_blocker": str(bank_current.get("binding_blocker", "stale_share_rule")),
            "downstream_use": "Treat as missing/not measured in current-quarter fiscal-flow work; any numeric zero is an arithmetic placeholder only.",
            "interpretation": "The live Tier 3 bank receipt cell is missing/not measured, not evidence that bank receipts are negligible; current-quarter promotion remains blocked by stale public shares.",
        },
        {
            "boundary_key": "row_live_default_receipt_cell",
            "counterparty_group": "row",
            "receipt_family": "missing_live_receipt_cell",
            "current_repo_role": "missing_not_measured_cell",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": False,
            "latest_reference_date": row_default.get("last_date"),
            "latest_value_millions": _fmt_value(row_default.get("latest_value_millions")),
            "strongest_supporting_surface": "tdc_fiscal_source_quality.csv",
            "binding_blocker": str(row_mrv.get("binding_blocker", "evidence_boundary")),
            "downstream_use": "Treat as missing/not measured in current-quarter fiscal-flow work; MRV remains a bounded nondefault pilot.",
            "interpretation": "The live Tier 3 ROW receipt cell is missing/not measured because the MRV branch remains a bounded nondefault pilot rather than a promotable additive correction.",
        },
        {
            "boundary_key": "bank_receipt_bridge_depository_plus_bhc",
            "counterparty_group": "bank",
            "receipt_family": "benchmark_bridge",
            "current_repo_role": "strongest_historical_bridge",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": False,
            "latest_reference_date": bank_candidate.get("last_date"),
            "latest_value_millions": _fmt_value(bank_candidate.get("latest_value_millions")),
            "strongest_supporting_surface": "tdc_fiscal_source_quality.csv",
            "binding_blocker": str(bank_current.get("binding_blocker", "stale_share_rule")),
            "downstream_use": "Use as the latest loaded bank bridge input and as the main benchmark behind the historical overlay, not as the historical overlay itself.",
            "interpretation": "This is the best official public bank receipt bridge in the repo, but the latest loaded bridge date can extend beyond the admissible historical overlay window.",
        },
        {
            "boundary_key": "bank_receipt_bridge_strict_depository_lower_bound",
            "counterparty_group": "bank",
            "receipt_family": "benchmark_bridge",
            "current_repo_role": "historical_lower_bound",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": False,
            "latest_reference_date": bank_strict.get("last_date"),
            "latest_value_millions": _fmt_value(bank_strict.get("latest_value_millions")),
            "strongest_supporting_surface": "tdc_fiscal_source_quality.csv",
            "binding_blocker": str(bank_current.get("binding_blocker", "stale_share_rule")),
            "downstream_use": "Use as the latest loaded conservative bridge input behind the historical lower-bound overlay, not as the historical overlay itself.",
            "interpretation": "This stricter depository-only bridge is useful for uncertainty bounds, but its latest loaded bridge date can also sit beyond the admissible historical overlay window.",
        },
        {
            "boundary_key": "bank_receipt_bridge_broad_finance_upper_benchmark",
            "counterparty_group": "bank",
            "receipt_family": "benchmark_bridge",
            "current_repo_role": "upper_benchmark_only",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": False,
            "latest_reference_date": bank_finance.get("last_date"),
            "latest_value_millions": _fmt_value(bank_finance.get("latest_value_millions")),
            "strongest_supporting_surface": "tdc_fiscal_source_quality.csv",
            "binding_blocker": "perimeter_too_broad",
            "downstream_use": "Use only as a scale benchmark to show how much broader finance attribution overstates a bank-only correction.",
            "interpretation": "This upper benchmark remains useful for scale checking, but it is not admissible as a bank default receipt correction.",
        },
        {
            "boundary_key": "bank_receipt_historical_overlay_candidate",
            "counterparty_group": "bank",
            "receipt_family": "historical_overlay",
            "current_repo_role": "historical_default_view",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": True,
            "latest_reference_date": latest_hist.get("reference_date"),
            "latest_value_millions": (
                historical_candidate_effect
                if historical_candidate_effect is not None
                else _fmt_value(hist_gap.get("net_delta_millions"))
            ),
            "strongest_supporting_surface": "tdc_tier3_historical_bank_receipt_research.csv",
            "binding_blocker": "none_within_current_policy_window",
            "downstream_use": "Use to study how much a nonzero bank receipt correction changes historical Tier 3 inside the age-eligible window.",
            "interpretation": "This overlay is the repo’s main historical receipt-side improvement path for bank analysis.",
        },
        {
            "boundary_key": "bank_receipt_historical_overlay_lower_bound",
            "counterparty_group": "bank",
            "receipt_family": "historical_overlay",
            "current_repo_role": "historical_lower_bound",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": True,
            "latest_reference_date": latest_hist.get("reference_date"),
            "latest_value_millions": historical_lower_effect,
            "strongest_supporting_surface": "tdc_tier3_historical_bank_receipt_research.csv",
            "binding_blocker": "none_within_current_policy_window",
            "downstream_use": "Use as the conservative historical lower-bound effect versus the Tier 3 partial shell, not as the candidate-minus-lower-bound spread.",
            "interpretation": "This lower bound keeps the historical bank overlay from being treated as a single-point truth by showing the conservative additive effect versus the partial shell.",
        },
        {
            "boundary_key": "row_mrv_primary_nondefault_pilot",
            "counterparty_group": "row",
            "receipt_family": "nondefault_pilot",
            "current_repo_role": "leading_recurring_row_pilot",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": False,
            "latest_reference_date": row_mrv.get("latest_relevant_date"),
            "latest_value_millions": _fmt_value(row_mrv.get("latest_value_millions")),
            "strongest_supporting_surface": "tdc_row_mrv_nondefault_evidence_summary.csv",
            "binding_blocker": str(row_mrv.get("binding_blocker", "evidence_boundary")),
            "downstream_use": "Use as the bounded recurring ROW receipt sensitivity and as the main statement of what still blocks current-quarter ROW receipt promotion.",
            "interpretation": str(
                mrv_state.get(
                    "strongest_nondefault_claim",
                    "MRV remains the leading recurring ROW pilot, but still lacks the evidence needed for default use.",
                )
            ),
        },
        {
            "boundary_key": "row_bea_receipt_benchmark",
            "counterparty_group": "row",
            "receipt_family": "benchmark_bridge",
            "current_repo_role": "macro_benchmark_only",
            "included_in_live_tier3_headline": False,
            "included_in_historical_overlay": False,
            "latest_reference_date": row_bea.get("last_date"),
            "latest_value_millions": _fmt_value(row_bea.get("latest_value_millions")),
            "strongest_supporting_surface": "tdc_fiscal_source_quality.csv",
            "binding_blocker": "not_treasury_cash_payer_identity",
            "downstream_use": "Use as a macro benchmark for scale and direction, not as a Treasury cash-payer receipt correction.",
            "interpretation": "BEA ROW receipts help contextualize scale, but they do not solve the Treasury cash-payer identity problem.",
        },
    ]

    frame = pd.DataFrame(rows)
    if "latest_reference_date" in frame.columns:
        frame["latest_reference_date"] = pd.to_datetime(frame["latest_reference_date"], errors="coerce")
    return frame.reindex(columns=REVIEW_COLUMNS)


def render_fiscal_receipt_boundary_review_markdown(frame: pd.DataFrame) -> str:
    title = "# Fiscal Receipt Boundary Review"
    intro = (
        "Receipt-side boundary map for the fiscal shell. It shows which receipt cells are missing/not measured in the live partial shell, "
        "which are historical-only overlays, which are bounded nondefault pilots, and which remain benchmark-only."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No fiscal receipt boundary rows are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Boundary | Group | Family | Role | Live Tier 3 | Historical overlay | Latest date | Latest value (mil) | Blocker |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for _, row in frame.iterrows():
        latest_date = (
            pd.Timestamp(row["latest_reference_date"]).date().isoformat()
            if pd.notna(row["latest_reference_date"])
            else "n/a"
        )
        value = row["latest_value_millions"]
        value_text = "n/a" if value is None or pd.isna(value) else f"{float(value):,.3f}"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["boundary_key"]),
                    str(row["counterparty_group"]),
                    str(row["receipt_family"]),
                    str(row["current_repo_role"]),
                    "yes" if bool(row["included_in_live_tier3_headline"]) else "no",
                    "yes" if bool(row["included_in_historical_overlay"]) else "no",
                    latest_date,
                    value_text,
                    str(row["binding_blocker"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Notes", ""])
    for _, row in frame.iterrows():
        lines.append(f"- `{row['boundary_key']}`: {row['interpretation']}")

    return "\n".join(lines + [""])


def write_fiscal_receipt_boundary_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    fiscal_source_quality: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    tier3_research_comparison: pd.DataFrame | None,
    downstream_estimator_gap_review: pd.DataFrame | None,
    row_mrv_nondefault_evidence_summary: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_fiscal_receipt_boundary_review(
        fiscal_source_quality=fiscal_source_quality,
        receipt_unblock_status=receipt_unblock_status,
        tier3_research_comparison=tier3_research_comparison,
        downstream_estimator_gap_review=downstream_estimator_gap_review,
        row_mrv_nondefault_evidence_summary=row_mrv_nondefault_evidence_summary,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_fiscal_receipt_boundary_review_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
