from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _series_present(columns: set[str], candidates: list[str]) -> bool:
    return any(candidate in columns for candidate in candidates)


def build_monetary_bank_perimeter_gap_review(
    quarterly: pd.DataFrame | None,
    gap_attribution: pd.DataFrame | None,
    nonbank_bridge_attribution: pd.DataFrame | None = None,
    liability_candidate_audit: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if quarterly is None or quarterly.empty or gap_attribution is None or gap_attribution.empty:
        return pd.DataFrame()

    latest_date = pd.to_datetime(gap_attribution["date"]).max()
    latest = gap_attribution[pd.to_datetime(gap_attribution["date"]) == latest_date].copy()
    if latest.empty:
        return pd.DataFrame()
    row = latest.iloc[0]
    columns = set(quarterly.columns)
    nonbank_latest = None
    if nonbank_bridge_attribution is not None and not nonbank_bridge_attribution.empty:
        nonbank = nonbank_bridge_attribution.copy()
        nonbank["date"] = pd.to_datetime(nonbank["date"])
        nonbank_latest = nonbank[nonbank["date"] == latest_date]
        if not nonbank_latest.empty:
            nonbank_latest = nonbank_latest.iloc[0]
    liability_latest = None
    if liability_candidate_audit is not None and not liability_candidate_audit.empty:
        liability = liability_candidate_audit.copy()
        liability["date"] = pd.to_datetime(liability["date"])
        liability_latest = liability[liability["date"] == latest_date]
        if not liability_latest.empty:
            liability_latest = liability_latest.iloc[0]

    has_bank_only_liquid_deposit_subcomponents = _series_present(
        columns,
        ["bank_demand_deposits", "bank_other_checkable_deposits", "bank_savings_deposits"],
    )
    has_large_time_or_wholesale_deposit_components = _series_present(
        columns,
        [
            "large_time_deposits_all_commercial_banks",
            "large_time_deposits",
            "wholesale_deposits",
            "large_denomination_time_deposits",
        ],
    )
    has_credit_union_bridge_side = _series_present(
        columns,
        ["credit_union_deposits", "federally_insured_credit_union_deposits"],
    )
    has_thrift_savings_bridge_side = _series_present(
        columns,
        ["thrift_deposits", "fdic_savings_institution_deposits"],
    )
    has_bank_vs_broad_depository_bridge = (
        has_credit_union_bridge_side and has_thrift_savings_bridge_side
    ) or _series_present(columns, ["bank_vs_broad_depository_bridge"])

    missing_families: list[str] = []
    if not has_bank_only_liquid_deposit_subcomponents:
        missing_families.append("bank_only_liquid_deposit_subcomponents")
    if not has_large_time_or_wholesale_deposit_components:
        missing_families.append("large_time_or_wholesale_deposit_components")
    if not has_bank_vs_broad_depository_bridge:
        missing_families.append("bank_vs_broad_depository_bridge")

    if missing_families:
        review_status = "new_source_families_required"
        if missing_families == ["bank_only_liquid_deposit_subcomponents"]:
            recommended_next_step = "target_bank_only_liquid_subcomponents"
            rationale = (
                "The nonbank depository bridge is now loaded on both the credit-union and thrift sides, so the remaining blocker is the bank-only liquid-deposit decomposition. Current inputs can identify the perimeter-style wedge, but not decompose the residual further inside the commercial-bank liability structure."
            )
        else:
            recommended_next_step = "keep_as_perimeter_stress_test"
            rationale = (
                "Current loaded monetary inputs are sufficient to identify the perimeter-style wedge, but not to decompose it further into bank-only liability subcomponents or a cleaner bank-versus-broad-depository bridge."
            )
    else:
        review_status = "existing_source_families_may_support_further_decomposition"
        recommended_next_step = "consider_further_perimeter_decomposition"
        rationale = (
            "The current loaded monetary inputs include candidate bank-liability or perimeter-bridge components that may support further decomposition of the bank-minus-liquid wedge."
        )

    return pd.DataFrame(
        [
            {
                "latest_quarter": latest_date.date().isoformat(),
                "review_status": review_status,
                "recommended_next_step": recommended_next_step,
                "bank_gap_vs_tier3_mil": row.get("bank_gap_vs_tier3_mil"),
                "bank_minus_liquid_target_wedge_mil": row.get("bank_minus_liquid_target_wedge_mil"),
                "bank_minus_liquid_share_of_bank_residual": row.get("bank_minus_liquid_share_of_bank_residual"),
                "has_bank_only_liquid_deposit_subcomponents": has_bank_only_liquid_deposit_subcomponents,
                "has_large_time_or_wholesale_deposit_components": has_large_time_or_wholesale_deposit_components,
                "has_credit_union_bridge_side": has_credit_union_bridge_side,
                "has_thrift_savings_bridge_side": has_thrift_savings_bridge_side,
                "has_bank_vs_broad_depository_bridge": has_bank_vs_broad_depository_bridge,
                "loaded_nonbank_depository_bridge_change_mil": (
                    nonbank_latest.get("delta_nonbank_depository_bridge_level_mil") if nonbank_latest is not None else pd.NA
                ),
                "loaded_nonbank_depository_bridge_share_of_bank_minus_liquid_wedge": (
                    nonbank_latest.get("nonbank_depository_bridge_share_of_bank_minus_liquid_wedge")
                    if nonbank_latest is not None
                    else pd.NA
                ),
                "residual_bank_minus_liquid_wedge_after_loaded_bridge_mil": (
                    nonbank_latest.get("residual_bank_minus_liquid_wedge_after_nonbank_bridge_mil")
                    if nonbank_latest is not None
                    else pd.NA
                ),
                "nonbank_bridge_materiality": (
                    nonbank_latest.get("nonbank_bridge_materiality") if nonbank_latest is not None else pd.NA
                ),
                "loaded_liability_context_total_mil": (
                    liability_latest.get("loaded_liability_context_total_mil") if liability_latest is not None else pd.NA
                ),
                "loaded_liability_context_share_of_bank_minus_liquid_wedge": (
                    liability_latest.get("loaded_liability_context_share_of_bank_minus_liquid_wedge")
                    if liability_latest is not None
                    else pd.NA
                ),
                "residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil": (
                    liability_latest.get("residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil")
                    if liability_latest is not None
                    else pd.NA
                ),
                "loaded_liability_context_materiality": (
                    liability_latest.get("loaded_liability_context_materiality") if liability_latest is not None else pd.NA
                ),
                "missing_source_families": ";".join(missing_families),
                "review_rationale": rationale,
            }
        ]
    )


def render_monetary_bank_perimeter_gap_review_markdown(review: pd.DataFrame) -> str:
    title = "# Monetary Bank Perimeter Gap Review"
    intro = (
        "Source-coverage review for the remaining bank-minus-liquid or perimeter wedge. "
        "This artifact checks whether the current loaded monetary inputs are enough to decompose that wedge further, or whether genuinely new source families are required."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No monetary bank perimeter-gap review is available."])

    row = review.iloc[0]
    summary = (
        f"Latest quarter: {row['latest_quarter']}. "
        f"Review: {row['review_status']}. "
        f"Bank-minus-liquid/perimeter wedge {_format_millions(row.get('bank_minus_liquid_target_wedge_mil'))}; "
        f"loaded nonbank-depository bridge {_format_millions(row.get('loaded_nonbank_depository_bridge_change_mil'))}; "
        f"loaded liability context total {_format_millions(row.get('loaded_liability_context_total_mil'))}; "
        f"residual after loaded bridge {_format_millions(row.get('residual_bank_minus_liquid_wedge_after_loaded_bridge_mil'))}; "
        f"bank-minus-liquid share of bank residual {_format_millions(pd.to_numeric(row.get('bank_minus_liquid_share_of_bank_residual'), errors='coerce') * 100 if pd.notna(row.get('bank_minus_liquid_share_of_bank_residual')) else pd.NA)}%. "
        f"Missing source families: {row.get('missing_source_families') or 'none'}."
    )

    header = [
        "| Quarter | Review | Recommended next step | Bank minus liquid wedge | Loaded nonbank bridge | Loaded liability context total | Residual after loaded bridge | Residual after loaded liability context | Loaded nonbank bridge share | Loaded liability context share | Nonbank bridge materiality | Loaded liability context materiality | Bank minus liquid share of bank residual | Bank-only liquid subcomponents loaded? | Large-time/wholesale components loaded? | Credit-union bridge side loaded? | Thrift bridge side loaded? | Bank-vs-broad-depository bridge loaded? | Missing source families | Rationale |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows = [
        "| "
        + " | ".join(
            [
                str(row["latest_quarter"]),
                str(row["review_status"]),
                str(row["recommended_next_step"]),
                _format_millions(row.get("bank_minus_liquid_target_wedge_mil")),
                _format_millions(row.get("loaded_nonbank_depository_bridge_change_mil")),
                _format_millions(row.get("loaded_liability_context_total_mil")),
                _format_millions(row.get("residual_bank_minus_liquid_wedge_after_loaded_bridge_mil")),
                _format_millions(row.get("residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil")),
                _format_millions(
                    pd.to_numeric(row.get("loaded_nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                    if pd.notna(row.get("loaded_nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"))
                    else pd.NA
                ),
                _format_millions(
                    pd.to_numeric(row.get("loaded_liability_context_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                    if pd.notna(row.get("loaded_liability_context_share_of_bank_minus_liquid_wedge"))
                    else pd.NA
                ),
                str(row.get("nonbank_bridge_materiality")),
                str(row.get("loaded_liability_context_materiality")),
                _format_millions(
                    pd.to_numeric(row.get("bank_minus_liquid_share_of_bank_residual"), errors="coerce") * 100
                    if pd.notna(row.get("bank_minus_liquid_share_of_bank_residual"))
                    else pd.NA
                ),
                str(bool(row.get("has_bank_only_liquid_deposit_subcomponents"))),
                str(bool(row.get("has_large_time_or_wholesale_deposit_components"))),
                str(bool(row.get("has_credit_union_bridge_side"))),
                str(bool(row.get("has_thrift_savings_bridge_side"))),
                str(bool(row.get("has_bank_vs_broad_depository_bridge"))),
                str(row.get("missing_source_families") or "none"),
                str(row.get("review_rationale")),
            ]
        )
        + " |"
    ]

    return "\n".join([title, "", intro, "", summary, "", *header, *rows, ""])


def write_monetary_bank_perimeter_gap_review(
    *,
    quarterly: pd.DataFrame,
    monetary_bank_target_gap_attribution: pd.DataFrame,
    monetary_nonbank_depository_bridge_attribution: pd.DataFrame | None = None,
    monetary_bank_liability_candidate_audit: pd.DataFrame | None = None,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_monetary_bank_perimeter_gap_review(
        quarterly=quarterly,
        gap_attribution=monetary_bank_target_gap_attribution,
        nonbank_bridge_attribution=monetary_nonbank_depository_bridge_attribution,
        liability_candidate_audit=monetary_bank_liability_candidate_audit,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_bank_perimeter_gap_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
