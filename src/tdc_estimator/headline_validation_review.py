from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


REVIEW_COLUMNS = [
    "tier1_bank_only_mil",
    "tier3_bank_only_mil",
    "tier3_minus_tier1_mil",
    "bank_coupon_correction_mil",
    "row_coupon_correction_mil",
    "bank_row_coupon_correction_mil",
    "total_fiscal_shell_correction_mil",
    "receipt_correction_total_mil",
    "coupon_share_of_abs_gap_pct",
    "row_coupon_share_of_abs_gap_pct",
    "coupon_gate_failed",
    "headline_recommendation",
    "headline_reason",
]


def _maybe(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce")
    return pd.Series(index=df.index, dtype="float64")


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _coupon_gate_failed(input_audit: pd.DataFrame | None) -> bool:
    audit = input_audit.copy() if input_audit is not None else pd.DataFrame()
    if audit.empty or "series_key" not in audit.columns or "audit_status" not in audit.columns:
        return False
    flagged_statuses = {"possible_x1000_mismatch", "benchmark_gap", "coupled_scale_risk"}
    flagged = audit.loc[
        audit["series_key"].isin(["bank_tsy_coupon_interest_proxy", "row_tsy_coupon_interest_proxy"])
        & audit["audit_status"].isin(flagged_statuses)
    ]
    return not flagged.empty


def _headline_decision(review: pd.DataFrame, *, coupon_gate_failed: bool) -> tuple[str, str]:
    if review.empty:
        return ("insufficient_overlap", "Tier 1 and Tier 3 do not overlap on any quarter.")
    if coupon_gate_failed:
        return (
            "prefer_tier1_headline",
            "Coupon-proxy scale audit is still flagged, so corrected layers are not promotable as the headline.",
        )

    mean_abs_gap = float(review["tier3_minus_tier1_mil"].abs().mean())
    mean_coupon_share = float(review["coupon_share_of_abs_gap_pct"].dropna().mean())
    receipt_max_abs = float(review["receipt_correction_total_mil"].fillna(0.0).abs().max())
    latest = review.iloc[-1]

    if mean_abs_gap > 0 and receipt_max_abs <= 0.05 * mean_abs_gap and mean_coupon_share >= 75.0:
        return (
            "prefer_tier1_headline",
            "Tier 1 to Tier 3 differences are still overwhelmingly coupon-proxy driven while receipt corrections remain tiny relative to the gap.",
        )
    if mean_coupon_share >= 50.0:
        return (
            "tier3_needs_more_validation",
            "Tier 3 is still mainly moving through coupon proxies, so the corrected layer needs more validation before promotion.",
        )
    return (
        "tier3_candidate_for_headline",
        "Tier 3 is no longer mainly moving through a single coupon-proxy block and can be evaluated as a headline candidate.",
    )


def build_headline_validation_review(
    estimates: pd.DataFrame,
    corrections: pd.DataFrame,
    *,
    input_audit: pd.DataFrame | None = None,
) -> pd.DataFrame:
    frame = pd.DataFrame(index=estimates.index)
    frame["tier1_bank_only_mil"] = _maybe(estimates, "tdc_tier1_fed_corrected_bank_only_ru_flow")
    frame["tier3_bank_only_mil"] = _maybe(estimates, "tdc_tier3_fiscal_corrected_bank_only_ru_flow")
    frame["tier3_minus_tier1_mil"] = frame["tier3_bank_only_mil"] - frame["tier1_bank_only_mil"]
    frame["bank_coupon_correction_mil"] = _maybe(corrections, "tier2_bank_coupon_correction")
    frame["row_coupon_correction_mil"] = _maybe(corrections, "tier2_row_coupon_correction")
    frame["bank_row_coupon_correction_mil"] = (
        frame["bank_coupon_correction_mil"] + frame["row_coupon_correction_mil"]
    )
    frame["total_fiscal_shell_correction_mil"] = (
        _maybe(corrections, "tier3_bank_noninterest_outlay_correction")
        + _maybe(corrections, "tier3_row_noninterest_outlay_correction")
        + _maybe(corrections, "tier3_bank_nonborrow_receipt_correction")
        + _maybe(corrections, "tier3_row_nonborrow_receipt_correction")
        + _maybe(corrections, "tier3_mint_cb_cash_factor_correction")
    )
    frame["receipt_correction_total_mil"] = _maybe(corrections, "tier3_bank_nonborrow_receipt_correction") + _maybe(
        corrections, "tier3_row_nonborrow_receipt_correction"
    )

    abs_gap = frame["tier3_minus_tier1_mil"].abs()
    frame["coupon_share_of_abs_gap_pct"] = pd.NA
    frame["row_coupon_share_of_abs_gap_pct"] = pd.NA
    valid = abs_gap > 0
    if valid.any():
        frame.loc[valid, "coupon_share_of_abs_gap_pct"] = (
            frame.loc[valid, "bank_row_coupon_correction_mil"].abs() / abs_gap.loc[valid]
        ) * 100.0
        frame.loc[valid, "row_coupon_share_of_abs_gap_pct"] = (
            frame.loc[valid, "row_coupon_correction_mil"].abs() / abs_gap.loc[valid]
        ) * 100.0

    frame = frame.dropna(subset=["tier1_bank_only_mil", "tier3_bank_only_mil"]).copy()
    gate_failed = _coupon_gate_failed(input_audit)
    recommendation, reason = _headline_decision(frame, coupon_gate_failed=gate_failed)
    frame["coupon_gate_failed"] = gate_failed
    frame["headline_recommendation"] = recommendation
    frame["headline_reason"] = reason
    return frame.reindex(columns=REVIEW_COLUMNS)


def render_headline_validation_review_markdown(review: pd.DataFrame) -> str:
    title = "# Headline Estimate Validation Review"
    intro = (
        "Quarter-by-quarter check of whether the Tier 1 to Tier 3 move looks like a validated headline improvement "
        "or a large still-provisional correction layer."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No overlapping Tier 1 and Tier 3 quarters are available."])

    latest_date = pd.Timestamp(review.index.max())
    latest = review.loc[latest_date]
    overlap_quarters = len(review)
    mean_abs_gap = float(review["tier3_minus_tier1_mil"].abs().mean())
    mean_coupon_share = float(pd.to_numeric(review["coupon_share_of_abs_gap_pct"], errors="coerce").dropna().mean())
    latest_summary = (
        f"Latest quarter: {latest_date.date().isoformat()}. "
        f"Tier 1 {_format_millions(latest['tier1_bank_only_mil'])}; "
        f"Tier 3 {_format_millions(latest['tier3_bank_only_mil'])}; "
        f"gap {_format_millions(latest['tier3_minus_tier1_mil'])}; "
        f"bank+ROW coupon {_format_millions(latest['bank_row_coupon_correction_mil'])}; "
        f"fiscal shell {_format_millions(latest['total_fiscal_shell_correction_mil'])}; "
        f"receipt correction {_format_millions(latest['receipt_correction_total_mil'])}; "
        f"recommendation: {latest['headline_recommendation']}."
    )
    summary = (
        f"Overlap quarters: {overlap_quarters}. "
        f"Mean absolute Tier 1 to Tier 3 gap: {_format_millions(mean_abs_gap)}. "
        f"Mean coupon share of the gap: {_format_millions(mean_coupon_share)}%."
    )
    rationale = str(latest["headline_reason"])
    header = (
        "| Quarter | Tier 1 | Tier 3 | Gap | Bank+ROW coupon | Fiscal shell | Receipt corr | Coupon share % | ROW share % |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    rows: list[str] = []
    for date, row in review.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    _format_millions(row["tier1_bank_only_mil"]),
                    _format_millions(row["tier3_bank_only_mil"]),
                    _format_millions(row["tier3_minus_tier1_mil"]),
                    _format_millions(row["bank_row_coupon_correction_mil"]),
                    _format_millions(row["total_fiscal_shell_correction_mil"]),
                    _format_millions(row["receipt_correction_total_mil"]),
                    _format_millions(row["coupon_share_of_abs_gap_pct"]),
                    _format_millions(row["row_coupon_share_of_abs_gap_pct"]),
                ]
            )
            + " |"
        )
    return "\n".join([title, "", intro, "", latest_summary, "", summary, "", rationale, "", header, *rows, ""])


def write_headline_validation_review(
    estimates: pd.DataFrame,
    corrections: pd.DataFrame,
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    input_audit: pd.DataFrame | None = None,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_headline_validation_review(estimates, corrections, input_audit=input_audit)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = review.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_headline_validation_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
