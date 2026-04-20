from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_monetary_target_preference_review(
    residuals: pd.DataFrame | None,
    wedge: pd.DataFrame | None,
) -> pd.DataFrame:
    if residuals is None or residuals.empty or wedge is None or wedge.empty:
        return pd.DataFrame()

    latest_date = pd.Timestamp(residuals["date"].max())
    latest_residuals = residuals[pd.to_datetime(residuals["date"]) == latest_date].copy()
    latest_wedge = wedge[pd.to_datetime(wedge["date"]) == latest_date].copy()
    if latest_residuals.empty or latest_wedge.empty:
        return pd.DataFrame()

    residual_map = latest_residuals.set_index("target_family")
    dep = residual_map.loc["depository_target"]
    bank = residual_map.loc["commercial_bank_deposit_target"]
    wedge_row = latest_wedge.iloc[0]

    dep_regime = str(dep["residual_regime"])
    bank_regime = str(bank["residual_regime"])
    wedge_dom = str(wedge_row["bank_wedge_dominance"])

    if dep_regime in {"partly_explained", "largely_explained"} and (
        bank_regime == "mostly_unresolved" or wedge_dom == "bank_target_wedge_dominant"
    ):
        recommendation = "prefer_depository_target_crosscheck"
        commercial_bank_role = "stress_test_only"
        rationale = (
            "The depository target now behaves materially better under the expanded Stage 1 block, while the commercial-bank-deposit target remains mostly unresolved and is dominated by a bank-target-specific wedge."
        )
    else:
        recommendation = "keep_targets_parallel_under_review"
        commercial_bank_role = "parallel_review_surface"
        rationale = (
            "The target split is not decisive enough to demote the commercial-bank-deposit target yet."
        )

    row = {
        "latest_quarter": latest_date.date().isoformat(),
        "preferred_target": "depository_target",
        "preferred_target_role": "main_monetary_crosscheck",
        "commercial_bank_target_role": commercial_bank_role,
        "recommendation_status": recommendation,
        "depository_residual_regime": dep_regime,
        "commercial_bank_residual_regime": bank_regime,
        "bank_wedge_dominance": wedge_dom,
        "depository_gap_vs_tier3_mil": dep["gap_vs_tier3_mil"],
        "depository_residual_after_expanded_mil": dep["residual_after_expanded_mil"],
        "depository_explained_share_after_expanded": dep["total_explained_share_after_expanded"],
        "commercial_bank_gap_vs_tier3_mil": bank["gap_vs_tier3_mil"],
        "commercial_bank_residual_after_expanded_mil": bank["residual_after_expanded_mil"],
        "commercial_bank_explained_share_after_expanded": bank["total_explained_share_after_expanded"],
        "bank_specific_residual_wedge_mil": wedge_row["bank_specific_residual_wedge_mil"],
        "bank_specific_residual_share_of_bank_residual": wedge_row["bank_specific_residual_share_of_bank_residual"],
        "review_rationale": rationale,
    }
    return pd.DataFrame([row])


def render_monetary_target_preference_review_markdown(review: pd.DataFrame) -> str:
    title = "# Monetary Target Preference Review"
    intro = (
        "Repo-level recommendation on which monetary target should be treated as the primary cross-check surface. "
        "This is a review artifact, not a headline estimator."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No monetary target preference review is available."])

    row = review.iloc[0]
    summary = (
        f"Latest quarter: {row['latest_quarter']}. "
        f"Recommendation: {row['recommendation_status']}. "
        f"Preferred target: {row['preferred_target']} as {row['preferred_target_role']}; "
        f"commercial-bank-deposit target role: {row['commercial_bank_target_role']}. "
        f"Depository regime {row['depository_residual_regime']} versus commercial-bank regime {row['commercial_bank_residual_regime']}; "
        f"bank-specific residual wedge {_format_millions(row.get('bank_specific_residual_wedge_mil'))} "
        f"({_format_millions(pd.to_numeric(row.get('bank_specific_residual_share_of_bank_residual'), errors='coerce') * 100 if pd.notna(row.get('bank_specific_residual_share_of_bank_residual')) else pd.NA)}% of the bank residual)."
    )

    header = [
        "| Quarter | Recommendation | Preferred target | Preferred role | Commercial-bank role | Depository explained share | Commercial-bank explained share | Bank wedge dominance | Rationale |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    rows = [
        "| "
        + " | ".join(
            [
                str(row["latest_quarter"]),
                str(row["recommendation_status"]),
                str(row["preferred_target"]),
                str(row["preferred_target_role"]),
                str(row["commercial_bank_target_role"]),
                _format_millions(
                    pd.to_numeric(row.get("depository_explained_share_after_expanded"), errors="coerce") * 100
                    if pd.notna(row.get("depository_explained_share_after_expanded"))
                    else pd.NA
                ),
                _format_millions(
                    pd.to_numeric(row.get("commercial_bank_explained_share_after_expanded"), errors="coerce") * 100
                    if pd.notna(row.get("commercial_bank_explained_share_after_expanded"))
                    else pd.NA
                ),
                str(row["bank_wedge_dominance"]),
                str(row["review_rationale"]),
            ]
        )
        + " |"
    ]

    return "\n".join([title, "", intro, "", summary, "", *header, *rows, ""])


def write_monetary_target_preference_review(
    *,
    monetary_residual_interpretation: pd.DataFrame,
    monetary_target_wedge: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_monetary_target_preference_review(
        residuals=monetary_residual_interpretation,
        wedge=monetary_target_wedge,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_target_preference_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
