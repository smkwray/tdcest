from __future__ import annotations

from pathlib import Path

import pandas as pd


COMPARISON_PAIRS = [
    (
        "domestic_bank_only",
        "tdc_tier2_h15_intensity_corrected_domestic_bank_only_ru_flow",
        "tdc_tier2_component_anchored_domestic_bank_only_ru_flow",
    ),
    (
        "bank_only",
        "tdc_tier2_h15_intensity_corrected_bank_only_ru_flow",
        "tdc_tier2_component_anchored_bank_only_ru_flow",
    ),
    (
        "broad_depository_np_cu",
        "tdc_tier2_h15_intensity_corrected_broad_depository_np_cu_ru_flow",
        "tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow",
    ),
    (
        "depository_institution_np_cu",
        "tdc_tier2_h15_intensity_corrected_depository_institution_np_cu_ru_flow",
        "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow",
    ),
    (
        "mmf_rrp_prop_bank_only",
        "tdc_tier2_h15_mmf_rrp_prop_bank_only_ru_flow",
        "tdc_tier2_component_anchored_mmf_rrp_prop_bank_only_ru_flow",
    ),
    (
        "mmf_rrp_prop_depository_institution_np_cu",
        "tdc_tier2_h15_mmf_rrp_prop_depository_institution_np_cu_ru_flow",
        "tdc_tier2_component_anchored_mmf_rrp_prop_depository_institution_np_cu_ru_flow",
    ),
    (
        "fed_extension_bank_only",
        "tdc_tier2_component_anchored_bank_only_ru_flow",
        "tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow",
    ),
    (
        "fed_extension_depository_institution_np_cu",
        "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow",
        "tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow",
    ),
]


def build_tier2_component_anchor_comparison(estimates: pd.DataFrame) -> pd.DataFrame:
    if estimates.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "comparison_key",
                "live_method",
                "component_method",
                "legacy_h15_value_mil",
                "component_value_mil",
                "component_minus_legacy_h15_mil",
                "component_minus_legacy_h15_pct_of_abs_legacy_h15",
            ]
        )
    df = estimates.copy()
    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    else:
        dates = pd.to_datetime(df.index, errors="coerce").normalize()
    rows: list[pd.DataFrame] = []
    for key, live_col, component_col in COMPARISON_PAIRS:
        if live_col not in df.columns or component_col not in df.columns:
            continue
        live = pd.to_numeric(df[live_col], errors="coerce")
        component = pd.to_numeric(df[component_col], errors="coerce")
        out = pd.DataFrame(
            {
                "date": dates,
                "comparison_key": key,
                "live_method": live_col,
                "component_method": component_col,
                "legacy_h15_value_mil": live,
                "component_value_mil": component,
            }
        )
        out = out.dropna(subset=["date", "legacy_h15_value_mil", "component_value_mil"])
        if out.empty:
            continue
        out["component_minus_legacy_h15_mil"] = out["component_value_mil"] - out["legacy_h15_value_mil"]
        denominator = out["legacy_h15_value_mil"].abs().where(out["legacy_h15_value_mil"].abs().gt(0.0))
        out["component_minus_legacy_h15_pct_of_abs_legacy_h15"] = (
            out["component_minus_legacy_h15_mil"] / denominator
        )
        rows.append(out)
    if not rows:
        return pd.DataFrame(
            columns=[
                "date",
                "comparison_key",
                "live_method",
                "component_method",
                "legacy_h15_value_mil",
                "component_value_mil",
                "component_minus_legacy_h15_mil",
                "component_minus_legacy_h15_pct_of_abs_legacy_h15",
            ]
        )
    return pd.concat(rows, ignore_index=True).sort_values(["comparison_key", "date"]).reset_index(drop=True)


def render_tier2_component_anchor_comparison_summary(comparison: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 Component-Anchored Estimator Comparison",
        "",
        "This compares the legacy WAMEST/H.15 Tier 2 sensitivity rows with the component-anchored rows.",
        "",
    ]
    if comparison.empty:
        return "\n".join(lines + ["No comparable rows were available."]) + "\n"
    df = comparison.copy()
    latest_date = pd.to_datetime(df["date"], errors="coerce").max()
    latest = df.loc[pd.to_datetime(df["date"], errors="coerce").eq(latest_date)].copy()
    lines.extend(
        [
            f"Latest comparable quarter: {latest_date.date().isoformat()}.",
            "",
            "| Comparison | Legacy H15 value (mil) | Component value (mil) | Component minus legacy H15 (mil) |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in latest.sort_values("comparison_key").itertuples(index=False):
        lines.append(
            f"| {row.comparison_key} | ${float(row.legacy_h15_value_mil):,.0f} | "
            f"${float(row.component_value_mil):,.0f} | ${float(row.component_minus_legacy_h15_mil):,.0f} |"
        )
    lines.extend(
        [
            "",
            "Acceptance status: comparison rows are wired. Component-anchored rows are the promoted default when the support files are present; the legacy H15 rows remain explicit sensitivity outputs.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_tier2_component_anchor_acceptance_memo(
    comparison: pd.DataFrame,
    default_switch_review: pd.DataFrame | None = None,
    default_decision: pd.DataFrame | None = None,
) -> str:
    blockers = 0
    caveats = 0
    if default_switch_review is not None and not default_switch_review.empty and "status" in default_switch_review.columns:
        statuses = default_switch_review["status"].astype(str)
        blockers = int(statuses.eq("blocker").sum())
        caveats = int(statuses.eq("caveat").sum())
    final_decision = ""
    if default_decision is not None and not default_decision.empty:
        final = default_decision.loc[default_decision["gate"].astype(str).eq("final_default_decision")]
        if not final.empty:
            final_decision = str(final.iloc[0].get("default_decision_status", ""))
    status = (
        "approved_for_default_switch"
        if final_decision == "approved_for_default_switch" and not comparison.empty
        else "ready_with_caveats_not_default"
        if not comparison.empty and blockers == 0
        else "not_ready"
    )
    decision = (
        "Component-anchored rows have passed strict default-switch gates and are promoted as the live Tier 2 defaults when support files are present."
        if status == "approved_for_default_switch"
        else "keep the existing H15-backed Tier 2 defaults unchanged and publish the component-anchored rows as explicit parallel candidates."
    )
    lines = [
        "# Tier 2 Component-Anchored Promotion Acceptance",
        "",
        f"Status: `{status}`.",
        "",
        f"Decision: {decision}",
        "",
        f"Default-switch review gates: {blockers} blockers, {caveats} caveats.",
        "",
    ]
    if comparison.empty:
        lines.append("No estimator comparison rows were available, so promotion is blocked until `tdc estimate` emits the component-anchored columns.")
    else:
        latest_date = pd.to_datetime(comparison["date"], errors="coerce").max()
        latest = comparison.loc[pd.to_datetime(comparison["date"], errors="coerce").eq(latest_date)].copy()
        abs_delta = pd.to_numeric(latest["component_minus_legacy_h15_mil"], errors="coerce").abs().sum()
        lines.extend(
            [
                f"Latest comparable quarter: {latest_date.date().isoformat()}.",
                f"Sum of absolute latest-row deltas versus legacy H15 rows across comparison rows: ${float(abs_delta):,.0f} million.",
                "",
                "Promotion posture:",
                "- component-anchored bank, ROW, and CU support files now feed the canonical Tier 2 rows when present;",
                "- legacy WAMEST/H.15 intensity rows remain available under explicit `tdc_tier2_h15_*` names;",
                "- Fed bill/FRN extension rows remain nondefault because they expand Tier 1 scope;",
                "- TIPS inflation compensation remains diagnostic-only under the accepted TIPS treatment decision.",
            ]
        )
    return "\n".join(lines) + "\n"


def write_tier2_component_anchor_comparison(
    *,
    estimates_path: Path | str,
    comparison_csv_path: Path | str,
    comparison_markdown_path: Path | str,
    acceptance_markdown_path: Path | str,
    default_switch_review_path: Path | str | None = None,
    default_decision_path: Path | str | None = None,
) -> tuple[Path, Path, Path, pd.DataFrame]:
    estimates = pd.read_csv(estimates_path)
    comparison = build_tier2_component_anchor_comparison(estimates)
    csv_path = Path(comparison_csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out = comparison.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date.astype(str)
    out.to_csv(csv_path, index=False)

    md_path = Path(comparison_markdown_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_tier2_component_anchor_comparison_summary(comparison), encoding="utf-8")

    review = None
    if default_switch_review_path is not None and Path(default_switch_review_path).exists():
        review = pd.read_csv(default_switch_review_path)
    decision = None
    if default_decision_path is not None and Path(default_decision_path).exists():
        decision = pd.read_csv(default_decision_path)
    acceptance_path = Path(acceptance_markdown_path)
    acceptance_path.parent.mkdir(parents=True, exist_ok=True)
    acceptance_path.write_text(
        render_tier2_component_anchor_acceptance_memo(comparison, review, decision),
        encoding="utf-8",
    )
    return csv_path, md_path, acceptance_path, comparison
