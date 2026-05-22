from __future__ import annotations

from pathlib import Path

import pandas as pd


def _status_for_gate(gate: str, source_status: str) -> tuple[str, str]:
    if source_status == "blocker":
        return "blocker", "Upstream default-switch review marks this gate as a blocker."
    if gate == "source_window_coverage" and source_status == "pass":
        return "pass", "Required source constraints cover the candidate window."
    if gate == "tips_inflation_compensation_treatment":
        return "accepted_caveat", "TIPS inflation compensation is excluded under the accepted TIPS treatment decision."
    if gate == "credit_union_split_basis":
        return "default_blocker", "CU split still relies on a WAMEST bill/coupon fallback against NCUA levels."
    if gate == "frn_interest_allocation":
        if source_status == "pass":
            return "pass", "FRN component now uses FRN-specific WAMEST contract weights."
        return "default_blocker", "FRN allocation still uses coupon-weight fallback rather than FRN-specific holder weights."
    if gate == "live_proxy_scale_comparison":
        return "default_blocker", "Live-versus-component deltas are material enough to require explicit release acceptance."
    return source_status or "unknown", "No stricter default decision mapping is defined for this gate."


def _latest_cu_split_sensitivity(cu_split_sensitivity: pd.DataFrame | None) -> dict[str, float] | None:
    if cu_split_sensitivity is None or cu_split_sensitivity.empty:
        return None
    df = cu_split_sensitivity.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"])
    if df.empty:
        return None
    latest = df.loc[df["date"].eq(df["date"].max())].copy()
    current = float(pd.to_numeric(latest["current_component_anchored_interest_mil"], errors="coerce").fillna(0.0).sum())
    alternative = float(
        pd.to_numeric(latest["alternative_component_anchored_interest_mil"], errors="coerce").fillna(0.0).sum()
    )
    delta = alternative - current
    bill_row = latest.loc[latest["component_key"].astype(str).eq("bill_amortized_discount")]
    current_bill_share = (
        float(pd.to_numeric(bill_row.iloc[0].get("current_cu_bill_share"), errors="coerce"))
        if not bill_row.empty
        else float("nan")
    )
    alternative_bill_share = (
        float(pd.to_numeric(bill_row.iloc[0].get("alternative_cu_bill_share"), errors="coerce"))
        if not bill_row.empty
        else float("nan")
    )
    return {
        "current": current,
        "alternative": alternative,
        "delta": delta,
        "abs_delta": abs(delta),
        "delta_share": abs(delta) / abs(current) if current else float("inf"),
        "current_bill_share": current_bill_share,
        "alternative_bill_share": alternative_bill_share,
    }


def _latest_fed_extension_delta(comparison: pd.DataFrame) -> float | None:
    if comparison.empty:
        return None
    df = comparison.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    rows = df.loc[df["comparison_key"].astype(str).eq("fed_extension_bank_only")].copy()
    if rows.empty:
        return None
    latest = rows.loc[rows["date"].eq(rows["date"].max())]
    if latest.empty:
        return None
    return float(
        pd.to_numeric(
            latest.iloc[0].get(
                "component_minus_legacy_h15_mil",
                latest.iloc[0].get("component_minus_live_mil"),
            ),
            errors="coerce",
        )
    )


def build_tier2_component_default_decision(
    *,
    default_switch_review: pd.DataFrame,
    comparison: pd.DataFrame,
    cu_split_sensitivity: pd.DataFrame | None = None,
    live_delta_acceptance: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    review = default_switch_review.copy()
    cu_sensitivity = _latest_cu_split_sensitivity(cu_split_sensitivity)
    live_delta_accepted = False
    live_delta_detail = ""
    if live_delta_acceptance is not None and not live_delta_acceptance.empty:
        accepted = live_delta_acceptance.loc[
            live_delta_acceptance["sector_group"].astype(str).eq("all_selected")
            & live_delta_acceptance["acceptance_status"].astype(str).eq("accepted_caveat")
        ]
        if not accepted.empty:
            live_delta_accepted = True
            live_delta_detail = str(accepted.iloc[0].get("acceptance_basis", ""))
    if not review.empty:
        for row in review.itertuples(index=False):
            gate = str(getattr(row, "gate", ""))
            if gate == "overall_default_switch_decision":
                continue
            source_status = str(getattr(row, "status", ""))
            decision_status, decision_detail = _status_for_gate(gate, source_status)
            source_detail = getattr(row, "detail", "")
            if (
                gate == "credit_union_split_basis"
                and cu_sensitivity is not None
                and cu_sensitivity["abs_delta"] <= 25.0
                and cu_sensitivity["delta_share"] <= 0.05
            ):
                decision_status = "accepted_caveat"
                decision_detail = (
                    "CU split fallback is quantified by the NCUA broad-ladder sensitivity; latest total impact is immaterial, but the broad NCUA maturity ladder is not Treasury-specific."
                )
                source_detail = (
                    f"{source_detail} Latest NCUA broad-ladder alternative moves CU coupon+bill by "
                    f"${cu_sensitivity['delta']:,.0f} million; current bill share "
                    f"{cu_sensitivity['current_bill_share']:.1%}, alternative "
                    f"{cu_sensitivity['alternative_bill_share']:.1%}."
                ).strip()
            if gate == "live_proxy_scale_comparison" and live_delta_accepted:
                decision_status = "accepted_caveat"
                decision_detail = (
                    "Live-versus-component deltas are accepted as the expected method difference from replacing H.15 intensity proxies with component-anchored pools."
                )
                source_detail = f"{source_detail} {live_delta_detail}".strip()
            rows.append(
                {
                    "gate": gate,
                    "source_status": source_status,
                    "default_decision_status": decision_status,
                    "decision_detail": decision_detail,
                    "source_detail": source_detail,
                }
            )

    fed_delta = _latest_fed_extension_delta(comparison)
    rows.append(
        {
            "gate": "fed_bill_frn_extension_scope",
            "source_status": "wired" if fed_delta is not None else "missing",
            "default_decision_status": "accepted_caveat" if fed_delta is not None else "default_blocker",
            "decision_detail": (
                "Fed bill+FRN extension rows are wired as nondefault; promote only if the default target explicitly includes this Tier 1 extension."
                if fed_delta is not None
                else "Fed bill+FRN extension rows are not available."
            ),
            "source_detail": (
                f"Latest fed-extension bank-only delta from component row is ${fed_delta:,.0f} million."
                if fed_delta is not None
                else ""
            ),
        }
    )

    statuses = [str(row["default_decision_status"]) for row in rows]
    blockers = sum(status == "default_blocker" for status in statuses)
    hard_blockers = sum(status == "blocker" for status in statuses)
    final_status = "do_not_switch_default" if blockers or hard_blockers else "approved_for_default_switch"
    rows.append(
        {
            "gate": "final_default_decision",
            "source_status": "",
            "default_decision_status": final_status,
            "decision_detail": (
                "Keep live Tier 2 defaults unchanged; publish component-anchored rows as parallel candidates."
                if final_status == "do_not_switch_default"
                else "Component-anchored rows are approved for promotion and feed the live default when support files are present."
            ),
            "source_detail": f"{blockers} default blockers; {hard_blockers} upstream blockers.",
        }
    )
    return pd.DataFrame(rows)


def render_tier2_component_default_decision(decision: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 Component-Anchored Default Decision",
        "",
    ]
    if decision.empty:
        return "\n".join(lines + ["No decision rows were available."]) + "\n"
    final = decision.loc[decision["gate"].astype(str).eq("final_default_decision")]
    final_status = str(final.iloc[0]["default_decision_status"]) if not final.empty else "unknown"
    lines.extend(
        [
            f"Final status: `{final_status}`.",
            "",
            "| Gate | Source status | Default decision status | Decision detail |",
            "|---|---|---|---|",
        ]
    )
    for row in decision.itertuples(index=False):
        lines.append(
            f"| {row.gate} | {row.source_status} | {row.default_decision_status} | {row.decision_detail} |"
        )
    interpretation = (
        "Interpretation: the component-anchored family has passed the strict default-switch gates. "
        "The estimator now promotes component-anchored rows to the canonical Tier 2 outputs when the support files are present; legacy H15 rows remain named sensitivity outputs."
        if final_status == "approved_for_default_switch"
        else "Interpretation: the component-anchored family is mechanically ready as a nondefault parallel surface, but the live default should not be replaced until default blockers are explicitly accepted or repaired."
    )
    lines.extend(["", interpretation])
    return "\n".join(lines) + "\n"


def write_tier2_component_default_decision(
    *,
    default_switch_review_path: Path | str,
    comparison_path: Path | str,
    cu_split_sensitivity_path: Path | str | None = None,
    live_delta_acceptance_path: Path | str | None = None,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    review = pd.read_csv(default_switch_review_path)
    comparison = pd.read_csv(comparison_path)
    cu_split_sensitivity = (
        pd.read_csv(cu_split_sensitivity_path)
        if cu_split_sensitivity_path is not None and Path(cu_split_sensitivity_path).exists()
        else None
    )
    live_delta_acceptance = (
        pd.read_csv(live_delta_acceptance_path)
        if live_delta_acceptance_path is not None and Path(live_delta_acceptance_path).exists()
        else None
    )
    decision = build_tier2_component_default_decision(
        default_switch_review=review,
        comparison=comparison,
        cu_split_sensitivity=cu_split_sensitivity,
        live_delta_acceptance=live_delta_acceptance,
    )
    csv_path = Path(out_csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    decision.to_csv(csv_path, index=False)
    md_path = Path(out_markdown_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_tier2_component_default_decision(decision), encoding="utf-8")
    return csv_path, md_path, decision
