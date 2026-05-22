from __future__ import annotations

from pathlib import Path

import pandas as pd


def _amount(component_pools: pd.DataFrame, flag_column: str, date: pd.Timestamp) -> float:
    rows = component_pools.loc[pd.to_datetime(component_pools["date"], errors="coerce").dt.normalize().eq(date)].copy()
    if rows.empty or flag_column not in rows.columns:
        return 0.0
    return float(
        pd.to_numeric(rows.loc[rows[flag_column].fillna(False), "quarter_expense_mil"], errors="coerce")
        .fillna(0.0)
        .sum()
    )


def _component_amount(component_pools: pd.DataFrame, component_key: str, date: pd.Timestamp) -> float:
    rows = component_pools.loc[pd.to_datetime(component_pools["date"], errors="coerce").dt.normalize().eq(date)].copy()
    if rows.empty or "component_key" not in rows.columns:
        return 0.0
    return float(
        pd.to_numeric(
            rows.loc[rows["component_key"].astype(str).eq(component_key), "quarter_expense_mil"],
            errors="coerce",
        )
        .fillna(0.0)
        .sum()
    )


def build_tier2_tips_treatment_decision(component_pools: pd.DataFrame) -> pd.DataFrame:
    if component_pools.empty or "date" not in component_pools.columns:
        return pd.DataFrame(
            [
                {
                    "decision_key": "tips_inflation_compensation_default_treatment",
                    "status": "blocker_missing_component_ledger",
                    "default_treatment": "undecided",
                    "rationale": "Treasury component ledger is missing, so TIPS compensation treatment cannot be evaluated.",
                }
            ]
        )
    pools = component_pools.copy()
    pools["date"] = pd.to_datetime(pools["date"], errors="coerce").dt.normalize()
    latest = pools["date"].max()
    tips_coupon = _component_amount(pools, "tips_accrued_interest", latest)
    tips_comp = _amount(pools, "included_in_tips_inflation_comp_pool", latest)
    return pd.DataFrame(
        [
            {
                "date": latest,
                "decision_key": "tips_coupon_accrual_default_treatment",
                "status": "accepted_default_component",
                "default_treatment": "include_in_coupon_accrual_pool",
                "latest_component_amount_mil": tips_coupon,
                "rationale": (
                    "TIPS coupon accrual is ordinary interest expense on coupon-bearing Treasury securities and "
                    "is already included in the coupon-accrual allocation pool."
                ),
                "required_followup": "none",
            },
            {
                "date": latest,
                "decision_key": "tips_inflation_compensation_default_treatment",
                "status": "accepted_default_exclusion",
                "default_treatment": "exclude_from_default_interest_correction_keep_diagnostic",
                "latest_component_amount_mil": tips_comp,
                "rationale": (
                    "TIPS inflation compensation is principal indexation/accrual rather than ordinary coupon cash. "
                    "It should remain a separate diagnostic/accrual sensitivity unless the Tier 2 target is expanded "
                    "from interest carry to indexed-principal accrual."
                ),
                "required_followup": "publish_diagnostic_sensitivity_before_any_accrual_target_expansion",
            },
        ]
    )


def render_tier2_tips_treatment_decision(decision: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 TIPS Treatment Decision",
        "",
        "Decision surface for separating TIPS coupon accrual from TIPS inflation compensation in the component-anchored Tier 2 interest candidate.",
        "",
        "| Decision | Status | Default treatment | Latest amount (mil) | Rationale | Follow-up |",
        "|---|---|---|---:|---|---|",
    ]
    if decision.empty:
        return "\n".join(lines + ["| no_rows | blocker | undecided | NA | Decision table is empty. | rebuild_decision |"]) + "\n"
    for _, row in decision.iterrows():
        amount = row.get("latest_component_amount_mil")
        amount_text = "NA" if pd.isna(amount) else f"${float(amount):,.0f}"
        lines.append(
            "| {key} | {status} | {treatment} | {amount} | {rationale} | {followup} |".format(
                key=row.get("decision_key", ""),
                status=row.get("status", ""),
                treatment=row.get("default_treatment", ""),
                amount=amount_text,
                rationale=str(row.get("rationale", "")).replace("|", "/"),
                followup=row.get("required_followup", ""),
            )
        )
    lines.extend(
        [
            "",
            "Bottom line: include TIPS coupon accrual in the default component candidate; keep TIPS inflation compensation out of the default interest correction and publish it only as a diagnostic sensitivity.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tier2_tips_treatment_decision(
    *,
    component_pools_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    pools = pd.read_csv(component_pools_path)
    decision = build_tier2_tips_treatment_decision(pools)
    csv_out = Path(csv_path)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    decision.to_csv(csv_out, index=False)
    md_out = Path(markdown_path)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(render_tier2_tips_treatment_decision(decision), encoding="utf-8")
    return csv_out, md_out, decision
