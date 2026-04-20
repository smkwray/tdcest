from __future__ import annotations

from pathlib import Path

import pandas as pd

HISTORICAL_PROMOTION_COLUMNS = [
    "quarter_end",
    "soi_tax_year_used",
    "share_status",
    "stale_share_years",
    "share_age_eligible_for_default",
    "recommended_historical_variant",
    "strict_depository_bridge_mil",
    "depository_plus_bhc_bridge_mil",
    "finance_upper_benchmark_mil",
    "age_eligible_default_candidate_mil",
    "age_eligible_lower_bound_candidate_mil",
    "historical_window_status",
    "promotion_readiness_label",
    "review_note",
]


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_bank_receipt_historical_promotion(
    *,
    bank_corp_tax_receipts_bridge: pd.DataFrame | None,
) -> pd.DataFrame:
    if bank_corp_tax_receipts_bridge is None or bank_corp_tax_receipts_bridge.empty:
        return pd.DataFrame(columns=HISTORICAL_PROMOTION_COLUMNS)

    bridge = bank_corp_tax_receipts_bridge.copy().sort_index()
    rows: list[dict[str, object]] = []

    for date, row in bridge.iterrows():
        eligible = bool(row.get("share_age_eligible_for_default", False))
        strict_val = pd.to_numeric(pd.Series([row.get("bank_corp_tax_receipts_gross_strict_depository_mil")]), errors="coerce").iloc[0]
        dep_bhc_val = pd.to_numeric(pd.Series([row.get("bank_corp_tax_receipts_gross_depository_plus_bhc_mil")]), errors="coerce").iloc[0]
        finance_val = pd.to_numeric(pd.Series([row.get("bank_corp_tax_receipts_gross_finance_share_mil")]), errors="coerce").iloc[0]
        share_status = str(row.get("share_status", "n/a"))

        if eligible:
            window_status = "historical_age_eligible_window"
            readiness = "historical_default_candidate_under_current_policy"
            note = (
                "Quarter remains inside the current stale-share rule. The depository-plus-BHC bridge is the main historical "
                "default candidate, while strict depository remains the lower-bound sensitivity."
            )
        elif share_status == "pre_source_gap":
            window_status = "pre_source_gap_window"
            readiness = "no_public_share_available"
            note = "Quarter predates the public share history currently loaded for the bank bridge."
        else:
            window_status = "stale_share_nondefault_window"
            readiness = "bridge_only_share_too_stale"
            note = (
                "Quarter remains a bridge/sensitivity only: the Table 5.1 perimeter is acceptable, but the carried-forward "
                "share is outside the current age-eligibility rule."
            )

        rows.append(
            {
                "quarter_end": pd.Timestamp(date),
                "soi_tax_year_used": row.get("soi_tax_year_used"),
                "share_status": share_status,
                "stale_share_years": row.get("stale_share_years"),
                "share_age_eligible_for_default": eligible,
                "recommended_historical_variant": "depository_plus_bhc",
                "strict_depository_bridge_mil": strict_val,
                "depository_plus_bhc_bridge_mil": dep_bhc_val,
                "finance_upper_benchmark_mil": finance_val,
                "age_eligible_default_candidate_mil": dep_bhc_val if eligible and pd.notna(dep_bhc_val) else 0.0,
                "age_eligible_lower_bound_candidate_mil": strict_val if eligible and pd.notna(strict_val) else 0.0,
                "historical_window_status": window_status,
                "promotion_readiness_label": readiness,
                "review_note": note,
            }
        )

    out = pd.DataFrame(rows)
    out["quarter_end"] = pd.to_datetime(out["quarter_end"])
    return out.reindex(columns=HISTORICAL_PROMOTION_COLUMNS)


def render_bank_receipt_historical_promotion_markdown(review: pd.DataFrame) -> str:
    title = "# Bank Receipt Historical Promotion Review"
    intro = (
        "Quarter-by-quarter review surface for the Table 5.1 bank-minor bridge under the current stale-share rule. "
        "This artifact separates historical age-eligible quarters from current stale-share quarters so the repo can "
        "distinguish a historical default candidate from a current nondefault bridge."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No bank receipt historical-promotion rows are available."])

    latest = review.sort_values("quarter_end").iloc[-1]
    eligible = review.loc[review["share_age_eligible_for_default"].fillna(False)].copy()
    latest_eligible = eligible.sort_values("quarter_end").iloc[-1] if not eligible.empty else None

    summary = [
        (
            f"Latest quarter in view: {pd.Timestamp(latest['quarter_end']).date().isoformat()}. "
            f"Current bank bridge status: {latest['promotion_readiness_label']} with depository-plus-BHC bridge "
            f"{_format_millions(latest['depository_plus_bhc_bridge_mil'])}."
        )
    ]
    if latest_eligible is not None:
        summary.append(
            "Latest age-eligible historical quarter: "
            f"{pd.Timestamp(latest_eligible['quarter_end']).date().isoformat()} with depository-plus-BHC candidate "
            f"{_format_millions(latest_eligible['age_eligible_default_candidate_mil'])} and strict-depository lower bound "
            f"{_format_millions(latest_eligible['age_eligible_lower_bound_candidate_mil'])}."
        )
    summary.append(
        f"Eligible historical-quarter count under the current rule: {int(eligible.shape[0])}."
    )

    header = [
        "| Quarter | Share year | Share status | Stale-share years | Age-eligible | Strict bridge | Dep+BHC bridge | Eligible default candidate | Window status |",
        "| --- | ---: | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    rows: list[str] = []
    for _, row in review.sort_values("quarter_end").iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["quarter_end"]).date().isoformat(),
                    str(int(row["soi_tax_year_used"])) if pd.notna(row["soi_tax_year_used"]) else "n/a",
                    str(row["share_status"]),
                    str(int(row["stale_share_years"])) if pd.notna(row["stale_share_years"]) else "n/a",
                    "yes" if bool(row["share_age_eligible_for_default"]) else "no",
                    _format_millions(row["strict_depository_bridge_mil"]),
                    _format_millions(row["depository_plus_bhc_bridge_mil"]),
                    _format_millions(row["age_eligible_default_candidate_mil"]),
                    str(row["historical_window_status"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `historical_age_eligible_window` means the quarter is inside the current two-calendar-year stale-share rule and can be discussed as a historical default candidate under current policy.",
        "- `stale_share_nondefault_window` means the Table 5.1 bank-minor perimeter remains acceptable, but the share is too stale for current default use.",
        "- `finance_upper_benchmark_mil` remains available in the CSV as a scale check only; it is not the preferred bank-side candidate.",
    ]
    return "\n".join([title, "", intro, "", *summary, "", *header, *rows, "", *notes, ""])


def write_bank_receipt_historical_promotion(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    bank_corp_tax_receipts_bridge: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_bank_receipt_historical_promotion(
        bank_corp_tax_receipts_bridge=bank_corp_tax_receipts_bridge,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bank_receipt_historical_promotion_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
