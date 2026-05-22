from __future__ import annotations

from pathlib import Path

import pandas as pd


def _read(path: Path | str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    return frame


def _latest_component_amount(component_pools: pd.DataFrame, flag_column: str, date: pd.Timestamp) -> float:
    rows = component_pools.loc[pd.to_datetime(component_pools["date"], errors="coerce").dt.normalize().eq(date)].copy()
    if rows.empty or flag_column not in rows.columns:
        return 0.0
    return float(
        pd.to_numeric(rows.loc[rows[flag_column].fillna(False), "quarter_expense_mil"], errors="coerce")
        .fillna(0.0)
        .sum()
    )


def _latest_candidate_totals(candidate: pd.DataFrame) -> pd.DataFrame:
    if candidate.empty:
        return pd.DataFrame(columns=["sector_group", "candidate_total_mil", "current_total_mil", "difference_mil"])
    latest = candidate["date"].max()
    latest_rows = candidate.loc[candidate["date"].eq(latest)].copy()
    latest_rows["component_anchored_interest_mil"] = pd.to_numeric(
        latest_rows["component_anchored_interest_mil"], errors="coerce"
    )
    latest_rows["current_raw_proxy_mil"] = pd.to_numeric(latest_rows["current_raw_proxy_mil"], errors="coerce")
    out = latest_rows.groupby("sector_group", as_index=False).agg(
        candidate_total_mil=("component_anchored_interest_mil", "sum"),
        current_total_mil=("current_raw_proxy_mil", "sum"),
    )
    out["difference_mil"] = out["candidate_total_mil"] - out["current_total_mil"]
    return out


def build_tier2_interest_default_switch_review(
    *,
    candidate: pd.DataFrame,
    source_window_validation: pd.DataFrame,
    component_pools: pd.DataFrame,
    tips_treatment_decision: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if candidate.empty:
        return pd.DataFrame(
            [
                {
                    "gate": "candidate_available",
                    "status": "blocker",
                    "detail": "Tier 2 component candidate is missing or empty.",
                    "recommended_action": "build_tier2_interest_component_candidate",
                }
            ]
        )

    candidate = candidate.copy()
    candidate["date"] = pd.to_datetime(candidate["date"], errors="coerce").dt.normalize()
    latest = candidate["date"].max()
    component_pools = component_pools.copy()
    component_pools["date"] = pd.to_datetime(component_pools["date"], errors="coerce").dt.normalize()

    window = source_window_validation.copy()
    if not window.empty and "promotion_ready_constraint_window" in window.columns:
        ready = window["promotion_ready_constraint_window"].astype(bool)
        ready_count = int(ready.sum())
        total_count = int(len(window))
        status = "pass" if ready_count == total_count and total_count > 0 else "blocker"
        detail = f"{ready_count} / {total_count} candidate-window quarters have the required source constraints."
    else:
        status = "blocker"
        detail = "Source-window validation is missing or does not contain promotion readiness flags."
    rows.append(
        {
            "gate": "source_window_coverage",
            "status": status,
            "detail": detail,
            "recommended_action": "rerun_or_extend_source_window_validation" if status == "blocker" else "none",
        }
    )

    cu_fallback_count = (
        int(window.get("credit_union_has_documented_fallback_split", pd.Series(dtype=bool)).astype(bool).sum())
        if not window.empty
        else 0
    )
    rows.append(
        {
            "gate": "credit_union_split_basis",
            "status": "caveat" if cu_fallback_count else "pass",
            "detail": (
                f"{cu_fallback_count} candidate-window quarters use an explicit WAMEST bill/coupon split fallback "
                "against official NCUA Treasury levels."
            ),
            "recommended_action": "accept_cu_fallback_in_default_memo_or_keep_nondefault" if cu_fallback_count else "none",
        }
    )

    coupon_pool = _latest_component_amount(component_pools, "included_in_coupon_pool", latest)
    bill_pool = _latest_component_amount(component_pools, "included_in_bill_discount_pool", latest)
    frn_pool = _latest_component_amount(component_pools, "included_in_frn_pool", latest)
    tips_comp_pool = _latest_component_amount(component_pools, "included_in_tips_inflation_comp_pool", latest)
    anchored_pool = coupon_pool + bill_pool
    frn_share = abs(frn_pool) / anchored_pool if anchored_pool else 0.0
    tips_share = abs(tips_comp_pool) / anchored_pool if anchored_pool else 0.0
    tips_exclusion_accepted = False
    if tips_treatment_decision is not None and not tips_treatment_decision.empty:
        tips = tips_treatment_decision.copy()
        row = tips.loc[tips["decision_key"].astype(str).eq("tips_inflation_compensation_default_treatment")]
        if not row.empty:
            status = str(row.iloc[0].get("status", ""))
            treatment = str(row.iloc[0].get("default_treatment", ""))
            tips_exclusion_accepted = status == "accepted_default_exclusion" and treatment.startswith(
                "exclude_from_default_interest_correction"
            )

    latest_candidate = candidate.loc[candidate["date"].eq(latest)].copy()
    latest_candidate["component_anchored_interest_mil"] = pd.to_numeric(
        latest_candidate["component_anchored_interest_mil"], errors="coerce"
    )
    frn_candidate = latest_candidate.loc[latest_candidate["component_key"].astype(str).eq("frn_accrued_interest")]
    has_frn_candidate = not frn_candidate.empty
    selected_frn = float(frn_candidate["component_anchored_interest_mil"].fillna(0.0).sum()) if has_frn_candidate else 0.0
    frn_allocator_basis = (
        "; ".join(sorted(frn_candidate.get("allocator_basis", pd.Series(dtype=str)).dropna().astype(str).unique()))
        if has_frn_candidate
        else ""
    )
    frn_uses_fallback = "fallback" in frn_allocator_basis.casefold()
    frn_status = (
        "pass"
        if has_frn_candidate and not frn_uses_fallback
        else ("caveat" if has_frn_candidate else ("blocker" if abs(frn_pool) > 0.0 else "pass"))
    )
    frn_detail = (
        f"Latest candidate quarter {latest.date().isoformat()} has ${frn_pool:,.0f} million of official "
        f"FRN accrued interest; selected Tier 2 sectors receive ${selected_frn:,.0f} million in the candidate "
        f"({frn_share:.1%} of coupon+bill pools). Allocator basis: {frn_allocator_basis or 'none'}."
        if has_frn_candidate
        else (
            f"Latest candidate quarter {latest.date().isoformat()} has ${frn_pool:,.0f} million of official "
            f"FRN accrued interest outside the allocated coupon+bill candidate ({frn_share:.1%} of coupon+bill pools)."
        )
    )
    rows.append(
        {
            "gate": "frn_interest_allocation",
            "status": frn_status,
            "detail": frn_detail,
            "recommended_action": (
                "none"
                if has_frn_candidate and not frn_uses_fallback
                else "replace_coupon_weight_fallback_with_frn_specific_weights"
                if has_frn_candidate
                else (
                    "add_frn_allocation_or_explicitly_exclude_from_default_scope"
                    if abs(frn_pool) > 0.0
                    else "none"
                )
            ),
        }
    )
    rows.append(
        {
            "gate": "tips_inflation_compensation_treatment",
            "status": "caveat" if tips_exclusion_accepted else ("blocker" if abs(tips_comp_pool) > 0.0 else "pass"),
            "detail": (
                (
                    f"Latest candidate quarter {latest.date().isoformat()} has ${tips_comp_pool:,.0f} million of TIPS "
                    f"inflation compensation outside the default candidate ({tips_share:.1%} of coupon+bill pools), "
                    "excluded by accepted treatment decision."
                )
                if tips_exclusion_accepted
                else (
                    f"Latest candidate quarter {latest.date().isoformat()} has ${tips_comp_pool:,.0f} million of TIPS "
                    f"inflation compensation outside the default candidate ({tips_share:.1%} of coupon+bill pools)."
                )
            ),
            "recommended_action": (
                "publish_tips_compensation_diagnostic_sensitivity"
                if tips_exclusion_accepted
                else (
                    "keep_diagnostic_or_define_accrual_target_before_default_switch"
                    if abs(tips_comp_pool) > 0.0
                    else "none"
                )
            ),
        }
    )

    totals = _latest_candidate_totals(candidate)
    if totals.empty:
        rows.append(
            {
                "gate": "live_proxy_scale_comparison",
                "status": "blocker",
                "detail": "Could not compute latest candidate versus current raw proxy comparison.",
                "recommended_action": "regenerate_current_proxy_support_files",
            }
        )
    else:
        pieces = [
            f"{row.sector_group}: candidate ${row.candidate_total_mil:,.0f}m vs live proxy ${row.current_total_mil:,.0f}m"
            for row in totals.itertuples(index=False)
        ]
        rows.append(
            {
                "gate": "live_proxy_scale_comparison",
                "status": "caveat",
                "detail": "; ".join(pieces),
                "recommended_action": "review_headline_delta_before_switch",
            }
        )

    blockers = [row for row in rows if row["status"] == "blocker"]
    rows.append(
        {
            "gate": "overall_default_switch_decision",
            "status": "blocker" if blockers else "ready_with_caveats",
            "detail": (
                "Do not switch live Tier 2 defaults yet; unresolved component-scope blockers remain."
                if blockers
                else "All mechanical gates pass, but caveats still require explicit acceptance."
            ),
            "recommended_action": (
                "keep_component_candidate_nondefault"
                if blockers
                else "write_default_switch_patch_and_release_notes"
            ),
        }
    )

    return pd.DataFrame(rows)


def render_tier2_interest_default_switch_review(review: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 Interest Default-Switch Review",
        "",
        "Decision surface for whether the component-anchored Tier 2 interest candidate should replace the live WAMEST/H.15 defaults.",
        "",
        "| Gate | Status | Detail | Recommended action |",
        "|---|---|---|---|",
    ]
    if review.empty:
        return "\n".join(lines + ["| no_rows | blocker | Review table is empty. | rebuild_review |"]) + "\n"
    for _, row in review.iterrows():
        lines.append(
            "| {gate} | {status} | {detail} | {action} |".format(
                gate=row.get("gate", ""),
                status=row.get("status", ""),
                detail=str(row.get("detail", "")).replace("|", "/"),
                action=row.get("recommended_action", ""),
            )
        )
    final = review.loc[review["gate"].astype(str).eq("overall_default_switch_decision")]
    if not final.empty:
        lines.extend(["", f"Bottom line: {final.iloc[0]['detail']}"])
    return "\n".join(lines) + "\n"


def write_tier2_interest_default_switch_review(
    *,
    candidate_path: Path | str,
    source_window_validation_path: Path | str,
    component_pools_path: Path | str,
    tips_treatment_decision_path: Path | str | None = None,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    tips_decision = (
        _read(tips_treatment_decision_path)
        if tips_treatment_decision_path is not None and Path(tips_treatment_decision_path).exists()
        else None
    )
    review = build_tier2_interest_default_switch_review(
        candidate=_read(candidate_path),
        source_window_validation=_read(source_window_validation_path),
        component_pools=_read(component_pools_path),
        tips_treatment_decision=tips_decision,
    )
    csv_out = Path(csv_path)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_out, index=False)
    md_out = Path(markdown_path)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(render_tier2_interest_default_switch_review(review), encoding="utf-8")
    return csv_out, md_out, review
