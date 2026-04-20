from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_monetary_bank_target_stress_review(
    decomposition: pd.DataFrame | None,
    preference_review: pd.DataFrame | None,
) -> pd.DataFrame:
    if decomposition is None or decomposition.empty or preference_review is None or preference_review.empty:
        return pd.DataFrame()

    latest_date = pd.to_datetime(decomposition["date"]).max()
    latest = decomposition[pd.to_datetime(decomposition["date"]) == latest_date].copy()
    if latest.empty:
        return pd.DataFrame()
    row = latest.iloc[0]
    pref = preference_review.iloc[0]

    bank_minus_liquid_share = pd.to_numeric(row.get("bank_minus_liquid_share_of_target_wedge"), errors="coerce")
    abs_bank_minus_liquid_share = pd.to_numeric(
        row.get("abs_bank_minus_liquid_share_of_components"), errors="coerce"
    )
    small_time_share = pd.to_numeric(row.get("small_time_share_of_target_wedge"), errors="coerce")

    if (
        str(pref.get("commercial_bank_target_role")) == "stress_test_only"
        and pd.notna(abs_bank_minus_liquid_share)
        and float(abs_bank_minus_liquid_share) >= 0.66
    ):
        review_status = "bank_target_is_perimeter_stress_test"
        recommended_use = "stress_test_for_bank_perimeter_definition"
        rationale = (
            "The commercial-bank target is already demoted to stress-test status, and the latest target-definition decomposition is dominated by the bank-minus-liquid/perimeter component rather than the small-time subtraction."
        )
    else:
        review_status = "bank_target_stress_review_still_open"
        recommended_use = "keep_under_review"
        rationale = (
            "The bank-target divergence is not yet clearly dominated by the bank-minus-liquid/perimeter component."
        )

    out = pd.DataFrame(
        [
            {
                "latest_quarter": latest_date.date().isoformat(),
                "commercial_bank_target_role": pref.get("commercial_bank_target_role"),
                "review_status": review_status,
                "recommended_use": recommended_use,
                "bank_minus_depository_target_wedge_mil": row.get("bank_minus_depository_target_wedge_mil"),
                "small_time_component_mil": row.get("small_time_component_mil"),
                "bank_minus_liquid_target_wedge_mil": row.get("bank_minus_liquid_target_wedge_mil"),
                "bank_specific_residual_wedge_mil": row.get("bank_specific_residual_wedge_mil"),
                "small_time_share_of_target_wedge": small_time_share,
                "bank_minus_liquid_share_of_target_wedge": bank_minus_liquid_share,
                "abs_small_time_share_of_components": pd.to_numeric(
                    row.get("abs_small_time_share_of_components"), errors="coerce"
                ),
                "abs_bank_minus_liquid_share_of_components": abs_bank_minus_liquid_share,
                "target_definition_component_dominance": row.get("target_definition_component_dominance"),
                "review_rationale": rationale,
            }
        ]
    )
    return out


def render_monetary_bank_target_stress_review_markdown(review: pd.DataFrame) -> str:
    title = "# Monetary Bank Target Stress Review"
    intro = (
        "Repo-level review of the commercial-bank-deposit target after the target-definition decomposition. "
        "This artifact checks whether the bank target should now be interpreted mainly as a perimeter stress test."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No monetary bank-target stress review is available."])

    row = review.iloc[0]
    summary = (
        f"Latest quarter: {row['latest_quarter']}. "
        f"Review: {row['review_status']}. "
        f"Commercial-bank target role: {row['commercial_bank_target_role']}. "
        f"Bank-minus-depository wedge {_format_millions(row.get('bank_minus_depository_target_wedge_mil'))}; "
        f"small-time component {_format_millions(row.get('small_time_component_mil'))}; "
        f"bank-minus-liquid/perimeter component {_format_millions(row.get('bank_minus_liquid_target_wedge_mil'))}; "
        f"dominance {row.get('target_definition_component_dominance')}."
    )

    header = [
        "| Quarter | Review | Recommended use | Commercial-bank role | Bank minus depository wedge | Small-time component | Bank minus liquid component | Small-time share of wedge | Bank minus liquid share of wedge | Abs bank minus liquid share of components | Dominance | Rationale |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    rows = [
        "| "
        + " | ".join(
            [
                str(row["latest_quarter"]),
                str(row["review_status"]),
                str(row["recommended_use"]),
                str(row["commercial_bank_target_role"]),
                _format_millions(row.get("bank_minus_depository_target_wedge_mil")),
                _format_millions(row.get("small_time_component_mil")),
                _format_millions(row.get("bank_minus_liquid_target_wedge_mil")),
                _format_millions(
                    pd.to_numeric(row.get("small_time_share_of_target_wedge"), errors="coerce") * 100
                    if pd.notna(row.get("small_time_share_of_target_wedge"))
                    else pd.NA
                ),
                _format_millions(
                    pd.to_numeric(row.get("bank_minus_liquid_share_of_target_wedge"), errors="coerce") * 100
                    if pd.notna(row.get("bank_minus_liquid_share_of_target_wedge"))
                    else pd.NA
                ),
                _format_millions(
                    pd.to_numeric(row.get("abs_bank_minus_liquid_share_of_components"), errors="coerce") * 100
                    if pd.notna(row.get("abs_bank_minus_liquid_share_of_components"))
                    else pd.NA
                ),
                str(row.get("target_definition_component_dominance")),
                str(row.get("review_rationale")),
            ]
        )
        + " |"
    ]

    return "\n".join([title, "", intro, "", summary, "", *header, *rows, ""])


def write_monetary_bank_target_stress_review(
    *,
    monetary_target_definition_decomposition: pd.DataFrame,
    monetary_target_preference_review: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_monetary_bank_target_stress_review(
        decomposition=monetary_target_definition_decomposition,
        preference_review=monetary_target_preference_review,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_bank_target_stress_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
