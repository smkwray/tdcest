from __future__ import annotations

from pathlib import Path

import pandas as pd


RECURRING_PILOT_REVIEW_COLUMNS = [
    "date",
    "branch_name",
    "annual_amount_mil",
    "latest_quarter_amount_mil",
    "timing_basis",
    "payer_identity_status",
    "current_role",
    "promotion_status",
    "default_blocker",
    "review_note",
]


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _latest_nonzero(series: pd.Series | None) -> float | None:
    if series is None:
        return None
    s = pd.to_numeric(series, errors="coerce").dropna()
    s = s.loc[s.ne(0.0)]
    if s.empty:
        return None
    return float(s.iloc[-1])


def build_row_recurring_pilot_review(
    *,
    row_visa_consular_pilot: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
    row_mrv_default_readiness: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        row_visa_consular_pilot is None
        or row_visa_consular_pilot.empty
        or row_state_visa_timing_sensitivity is None
        or row_state_visa_timing_sensitivity.empty
    ):
        return pd.DataFrame(columns=RECURRING_PILOT_REVIEW_COLUMNS)

    pilot = row_visa_consular_pilot.copy()
    pilot["date"] = pd.to_datetime(pilot["date"])
    timing = row_state_visa_timing_sensitivity.copy()
    timing.index = pd.to_datetime(timing.index)

    latest_pilot_date = pd.Timestamp(pilot["date"].max())
    latest_timing_date = timing.loc[
        pd.to_numeric(timing.get("row_state_visa_total_allocated_receipt_mil", pd.Series(dtype="float64")), errors="coerce")
        .fillna(0.0)
        .ne(0.0)
    ].index.max()
    latest_date = latest_timing_date if pd.notna(latest_timing_date) else latest_pilot_date

    latest_pilot = pilot.loc[pilot["date"].eq(latest_pilot_date)].copy()
    latest_timing = timing.loc[latest_date]

    primary_annual = float(
        latest_pilot.loc[latest_pilot["pilot_bucket"].eq("mrv_cbsp_primary_candidate"), "receipt_amt_mil"].sum()
    )
    secondary_annual = float(
        latest_pilot.loc[latest_pilot["pilot_bucket"].eq("state_visa_secondary_sensitivity"), "receipt_amt_mil"].sum()
    )

    readiness_row = pd.Series(dtype="object")
    if row_mrv_default_readiness is not None and not row_mrv_default_readiness.empty:
        readiness = row_mrv_default_readiness.copy()
        readiness_row = readiness.loc[readiness["check_name"].eq("debited_account_or_legal_remitter")].iloc[0]

    rows = [
        {
            "date": latest_date,
            "branch_name": "mrv_cbsp_primary",
            "annual_amount_mil": primary_annual,
            "latest_quarter_amount_mil": float(latest_timing.get("row_state_visa_allocated_receipt_mil", 0.0)),
            "timing_basis": "monthly_niv_issuance_share_proxy",
            "payer_identity_status": "applicant_link_not_debited_account",
            "current_role": "primary_recurring_row_pilot",
            "promotion_status": "future_row_mrv_default_pilot_under_review",
            "default_blocker": str(readiness_row.get("metric_value", "needs_cash_payer_and_debited_account_evidence")),
            "review_note": (
                "Primary recurring ROW pilot. Uses the annual MRV / CBSP line with monthly NIV issuance shares for timing. "
                "This remains the only recurring ROW branch under real default review."
            ),
        },
        {
            "date": latest_date,
            "branch_name": "secondary_state_visa",
            "annual_amount_mil": secondary_annual,
            "latest_quarter_amount_mil": float(latest_timing.get("row_state_visa_secondary_allocated_receipt_mil", 0.0)),
            "timing_basis": "monthly_iv_issuance_share_proxy",
            "payer_identity_status": "secondary_visa_fee_link_not_direct_cash_payer",
            "current_role": "secondary_recurring_row_sensitivity",
            "promotion_status": "keep_secondary_visa_nondefault",
            "default_blocker": "secondary_visa_line_not_primary_recurring_row_candidate",
            "review_note": (
                "Secondary recurring State-visa branch. Kept visible for scale and auditability, "
                "but it does not enter the main recurring ROW delta and is not in line for default promotion."
            ),
        },
    ]

    return pd.DataFrame(rows).reindex(columns=RECURRING_PILOT_REVIEW_COLUMNS)


def render_row_recurring_pilot_review_markdown(review: pd.DataFrame) -> str:
    title = "# ROW Recurring Pilot Review"
    intro = (
        "Direct comparison of the recurring State / visa branches. "
        "This artifact keeps the MRV / CBSP primary bridge separate from the secondary visa branch so the repo does not blur the main recurring ROW pilot with auxiliary sensitivities."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No recurring ROW pilot review rows are available."])

    latest = review.iloc[0]
    primary = review.loc[review["branch_name"].eq("mrv_cbsp_primary")].iloc[0]
    secondary = review.loc[review["branch_name"].eq("secondary_state_visa")].iloc[0]
    summary = (
        f"Latest quarter in view: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Primary MRV branch {_format_millions(primary['latest_quarter_amount_mil'])} million versus secondary visa branch "
        f"{_format_millions(secondary['latest_quarter_amount_mil'])} million."
    )

    header = [
        "| Branch | Annual amount (mil) | Latest quarter (mil) | Current role | Promotion status |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    rows = []
    for _, row in review.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["branch_name"]),
                    _format_millions(row["annual_amount_mil"]),
                    _format_millions(row["latest_quarter_amount_mil"]),
                    str(row["current_role"]),
                    str(row["promotion_status"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `mrv_cbsp_primary` is the only recurring ROW branch under default review.",
        "- `secondary_state_visa` remains a separate recurring sensitivity, not part of the main downstream ROW delta.",
        "- Both branches still use activity-based timing proxies rather than observed Treasury cash timing.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_row_recurring_pilot_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    row_visa_consular_pilot: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
    row_mrv_default_readiness: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_row_recurring_pilot_review(
        row_visa_consular_pilot=row_visa_consular_pilot,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        row_mrv_default_readiness=row_mrv_default_readiness,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_recurring_pilot_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
