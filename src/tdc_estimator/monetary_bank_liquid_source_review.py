from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _series_token(candidate_text: object, index: int = 0) -> str:
    if candidate_text is None or pd.isna(candidate_text):
        return "n/a"
    head = str(candidate_text).split(";")
    if not head:
        return "n/a"
    if index >= len(head):
        return head[0].strip()
    return head[index].strip()


def build_monetary_bank_liquid_source_review(
    liability_candidate_audit: pd.DataFrame | None,
    perimeter_gap_review: pd.DataFrame | None,
    perimeter_source_map: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        liability_candidate_audit is None
        or liability_candidate_audit.empty
        or perimeter_gap_review is None
        or perimeter_gap_review.empty
        or perimeter_source_map is None
        or perimeter_source_map.empty
    ):
        return pd.DataFrame()

    latest_date = pd.to_datetime(liability_candidate_audit["date"]).max()
    latest_audit = liability_candidate_audit[pd.to_datetime(liability_candidate_audit["date"]) == latest_date].copy()
    if latest_audit.empty:
        return pd.DataFrame()
    audit_row = latest_audit.iloc[0]
    review_row = perimeter_gap_review.iloc[0]

    liquid_rows = perimeter_source_map[
        perimeter_source_map["source_family_key"] == "bank_only_liquid_deposit_subcomponents"
    ]
    large_time_rows = perimeter_source_map[
        perimeter_source_map["source_family_key"] == "large_time_or_wholesale_deposit_components"
    ]
    liquid_row = liquid_rows.iloc[0] if not liquid_rows.empty else pd.Series(dtype=object)
    large_time_row = large_time_rows.iloc[0] if not large_time_rows.empty else pd.Series(dtype=object)

    missing_families = set(str(review_row.get("missing_source_families") or "").split(";"))
    has_clean_loaded = bool(review_row.get("has_bank_only_liquid_deposit_subcomponents"))
    broad_context_stance = str(liquid_row.get("current_repo_stance") or "")

    if not has_clean_loaded and "bank_only_liquid_deposit_subcomponents" in missing_families:
        if broad_context_stance == "loaded_broad_context_not_subcomponent":
            review_status = "no_clean_bank_only_liquid_subcomponent_loaded"
            recommendation_status = "keep_current_context_boundary"
            rationale = (
                "The repo now has a loaded broad bank-deposit context series and a loaded large-time bucket, but it still lacks a clean bank-only liquid-deposit subcomponent family. "
                "That means the bank-only-liquid problem remains a public-source boundary rather than a missing transformation."
            )
        else:
            review_status = "bank_only_liquid_family_still_missing"
            recommendation_status = "new_source_family_required"
            rationale = (
                "The repo still lacks a clean bank-only liquid-deposit source family, so the commercial-bank target remains a perimeter stress test."
            )
    else:
        review_status = "candidate_bank_only_liquid_family_under_review"
        recommendation_status = "reassess_context_boundary"
        rationale = (
            "A candidate bank-only liquid-deposit family may now be available for review, so the current context-only boundary should be reassessed."
        )

    return pd.DataFrame(
        [
            {
                "latest_quarter": latest_date.date().isoformat(),
                "review_status": review_status,
                "recommendation_status": recommendation_status,
                "recommended_next_step": review_row.get("recommended_next_step"),
                "bank_only_liquid_missing_for_next_step": "bank_only_liquid_deposit_subcomponents" in missing_families,
                "has_clean_bank_only_liquid_subcomponent_loaded": has_clean_loaded,
                "best_loaded_broad_context_series": _series_token(liquid_row.get("candidate_series_or_product"), 0),
                "best_loaded_broad_context_role": "broad_context_only",
                "best_loaded_broad_context_change_mil": audit_row.get("delta_other_deposits_all_commercial_banks_level_mil"),
                "best_loaded_broad_context_share_of_wedge": audit_row.get("other_deposits_share_of_bank_minus_liquid_wedge"),
                "loaded_large_time_series": _series_token(large_time_row.get("candidate_series_or_product"), 0),
                "loaded_large_time_role": str(large_time_row.get("current_repo_stance") or "n/a"),
                "loaded_large_time_change_mil": audit_row.get("delta_large_time_deposits_all_commercial_banks_level_mil"),
                "loaded_large_time_share_of_wedge": audit_row.get("large_time_share_of_bank_minus_liquid_wedge"),
                "loaded_nonbank_bridge_change_mil": audit_row.get("delta_nonbank_depository_bridge_level_mil"),
                "loaded_nonbank_bridge_share_of_wedge": audit_row.get("nonbank_bridge_share_of_bank_minus_liquid_wedge"),
                "loaded_additive_liability_context_mil": audit_row.get("loaded_liability_context_total_mil"),
                "loaded_additive_liability_context_share_of_wedge": audit_row.get(
                    "loaded_liability_context_share_of_bank_minus_liquid_wedge"
                ),
                "residual_after_loaded_additive_liability_context_mil": audit_row.get(
                    "residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil"
                ),
                "rejected_candidate_construction": "ODSACBM027NBOG_plus_WDDNS",
                "rejected_candidate_reason": "likely_double_counts_demand_deposits",
                "source_map_liquid_stance": broad_context_stance,
                "perimeter_review_status": review_row.get("review_status"),
                "perimeter_review_rationale": review_row.get("review_rationale"),
                "review_rationale": rationale,
            }
        ]
    )


def render_monetary_bank_liquid_source_review_markdown(review: pd.DataFrame) -> str:
    title = "# Monetary Bank Liquid Source Review"
    intro = (
        "Focused review of the remaining bank-only liquid-deposit problem. "
        "This artifact collapses the current boundary into one decision surface: what is loaded, what is admissible as additive context, what remains context-only, and what is explicitly rejected."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No monetary bank liquid source review is available."])

    row = review.iloc[0]
    summary = (
        f"Latest quarter: {row['latest_quarter']}. "
        f"Review: {row['review_status']}. "
        f"Best loaded broad context series: {row['best_loaded_broad_context_series']} "
        f"with q/q change {_format_millions(row.get('best_loaded_broad_context_change_mil'))}; "
        f"loaded additive liability context {_format_millions(row.get('loaded_additive_liability_context_mil'))} "
        f"({_format_millions(pd.to_numeric(row.get('loaded_additive_liability_context_share_of_wedge'), errors='coerce') * 100 if pd.notna(row.get('loaded_additive_liability_context_share_of_wedge')) else pd.NA)}% of the wedge); "
        f"residual after loaded additive context {_format_millions(row.get('residual_after_loaded_additive_liability_context_mil'))}. "
        f"Rejected construction: {row['rejected_candidate_construction']}."
    )

    header = [
        "| Quarter | Review | Recommendation | Best loaded broad context | Broad-context role | Broad-context change | Broad-context share of wedge | Loaded large-time series | Large-time role | Large-time change | Loaded nonbank bridge | Loaded additive context | Additive-context share | Residual after additive context | Rejected construction | Reason | Rationale |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    rows = [
        "| "
        + " | ".join(
            [
                str(row["latest_quarter"]),
                str(row["review_status"]),
                str(row["recommendation_status"]),
                str(row["best_loaded_broad_context_series"]),
                str(row["best_loaded_broad_context_role"]),
                _format_millions(row.get("best_loaded_broad_context_change_mil")),
                _format_millions(
                    pd.to_numeric(row.get("best_loaded_broad_context_share_of_wedge"), errors="coerce") * 100
                    if pd.notna(row.get("best_loaded_broad_context_share_of_wedge"))
                    else pd.NA
                ),
                str(row["loaded_large_time_series"]),
                str(row["loaded_large_time_role"]),
                _format_millions(row.get("loaded_large_time_change_mil")),
                _format_millions(row.get("loaded_nonbank_bridge_change_mil")),
                _format_millions(row.get("loaded_additive_liability_context_mil")),
                _format_millions(
                    pd.to_numeric(row.get("loaded_additive_liability_context_share_of_wedge"), errors="coerce") * 100
                    if pd.notna(row.get("loaded_additive_liability_context_share_of_wedge"))
                    else pd.NA
                ),
                _format_millions(row.get("residual_after_loaded_additive_liability_context_mil")),
                str(row["rejected_candidate_construction"]),
                str(row["rejected_candidate_reason"]),
                str(row["review_rationale"]),
            ]
        )
        + " |"
    ]

    notes = [
        "Notes:",
        "- `Best loaded broad context` currently refers to `ODSACBM027SBOG`, which remains context-only rather than an admissible bank-only liquid subcomponent.",
        "- `Loaded additive context` currently means `nonbank bridge + large time`, not `other deposits`.",
        "- This artifact is a publication-ready source-boundary review, not a new estimator correction.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_bank_liquid_source_review(
    *,
    monetary_bank_liability_candidate_audit: pd.DataFrame,
    monetary_bank_perimeter_gap_review: pd.DataFrame,
    monetary_bank_perimeter_source_map: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_monetary_bank_liquid_source_review(
        liability_candidate_audit=monetary_bank_liability_candidate_audit,
        perimeter_gap_review=monetary_bank_perimeter_gap_review,
        perimeter_source_map=monetary_bank_perimeter_source_map,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_bank_liquid_source_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
