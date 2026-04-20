from __future__ import annotations

from pathlib import Path

import pandas as pd


TERM_SPECS = [
    {
        "term_key": "bank_credit_additive_proxy_mil",
        "label": "Total bank credit additive proxy",
        "stage_role": "simple_signed_control",
        "overlap_risk": "high",
        "recommendation": "keep_signed_but_coarse",
        "rationale": "Useful as a top-line bank-balance-sheet control, but it mixes Treasury-heavy securities with non-Treasury credit and is therefore too broad for the preferred overlap-aware subtotal.",
    },
    {
        "term_key": "non_treasury_bank_credit_proxy_mil",
        "label": "Loans plus other securities ex Treasury/agency proxy",
        "stage_role": "refined_signed_control",
        "overlap_risk": "medium",
        "recommendation": "keep_signed_preferred_bank_block",
        "rationale": "Preferred bank-credit block because it strips Treasury/agency non-MBS securities out of the bank-credit term, reducing direct overlap with the ladder's Treasury channels.",
    },
    {
        "term_key": "retail_mmf_rotation_proxy_mil",
        "label": "Retail MMF rotation proxy",
        "stage_role": "signed_control",
        "overlap_risk": "low",
        "recommendation": "keep_signed",
        "rationale": "Retail MMF balances are outside the ladder's Treasury-security accounting and provide a clean portfolio-shift proxy for deposit substitution.",
    },
    {
        "term_key": "rrp_drain_proxy_mil",
        "label": "ON RRP drain proxy",
        "stage_role": "signed_control",
        "overlap_risk": "low",
        "recommendation": "keep_signed",
        "rationale": "ON RRP is a distinct liquidity-absorption channel and does not duplicate the ladder's Treasury transaction or cash terms directly.",
    },
    {
        "term_key": "reserve_balance_liquidity_proxy_mil",
        "label": "Reserve-balance liquidity proxy",
        "stage_role": "signed_control",
        "overlap_risk": "medium",
        "recommendation": "keep_signed_with_timing_caution",
        "rationale": "Reserve balances are informative on system liquidity, but they can co-move with Treasury cash and Fed balance-sheet timing, so interpretation should stay cautious.",
    },
    {
        "term_key": "fed_term_deposit_absorption_proxy_mil",
        "label": "Fed term-deposit absorption proxy",
        "stage_role": "signed_control",
        "overlap_risk": "low",
        "recommendation": "keep_signed",
        "rationale": "Fed term deposits are a distinct reserve-absorption tool and do not duplicate Treasury cash or Treasury-security holdings in the ladder.",
    },
    {
        "term_key": "fed_other_deposits_absorption_proxy_mil",
        "label": "Other deposits at Fed absorption proxy",
        "stage_role": "signed_control",
        "overlap_risk": "medium",
        "recommendation": "keep_signed_with_scope_caution",
        "rationale": "Useful as a broader absorption signal, but the category is wider than reserve balances and needs cautious interpretation.",
    },
    {
        "term_key": "fed_liquidity_credit_support_proxy_mil",
        "label": "Fed liquidity-credit support proxy",
        "stage_role": "signed_control",
        "overlap_risk": "medium",
        "recommendation": "keep_signed_with_facility_scope_caution",
        "rationale": "Captures nonfiscal Fed lending/liquidity support, but the category is broad and could overlap narrower facility-specific interpretations if those are added later.",
    },
    {
        "term_key": "bank_borrowing_funding_proxy_mil",
        "label": "Commercial-bank borrowing funding proxy",
        "stage_role": "signed_control",
        "overlap_risk": "medium",
        "recommendation": "keep_signed_with_funding_caution",
        "rationale": "Useful funding-side offset for deposit dynamics, but it is a broad borrowing concept rather than a pure deposit driver.",
    },
    {
        "term_key": "delta_commercial_bank_cash_assets_mil",
        "label": "Commercial-bank cash-assets context",
        "stage_role": "context_only",
        "overlap_risk": "medium",
        "recommendation": "keep_context_only",
        "rationale": "Bank cash assets are informative, but the sign interpretation is weak because they can reflect both liquidity support and defensive balance-sheet repositioning.",
    },
    {
        "term_key": "delta_foreign_official_custody_treasuries_mil",
        "label": "Foreign-official Treasury custody context",
        "stage_role": "context_only",
        "overlap_risk": "high",
        "recommendation": "keep_context_only_due_to_ladder_overlap",
        "rationale": "This is too close to the ladder's own ROW Treasury channels and should not become a signed control without a dedicated overlap audit or alternative mapping.",
    },
    {
        "term_key": "delta_foreign_related_treasury_agency_non_mbs_mil",
        "label": "Foreign-related bank Treasury/agency context",
        "stage_role": "context_only",
        "overlap_risk": "high",
        "recommendation": "keep_context_only_due_to_ladder_overlap",
        "rationale": "This series sits directly on Treasury/agency holdings for foreign-related institutions, so a signed use would risk double counting against the ladder's Treasury-security terms.",
    },
    {
        "term_key": "delta_tga_weekly_level_mil",
        "label": "TGA timing context",
        "stage_role": "context_only",
        "overlap_risk": "high",
        "recommendation": "keep_context_only_due_to_cash_overlap",
        "rationale": "TGA is a narrow cash-timing diagnostic, not a replacement for the ladder's broader Treasury operating-cash term.",
    },
]


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_monetary_control_overlap_audit(controls: pd.DataFrame | None) -> pd.DataFrame:
    if controls is None or controls.empty:
        return pd.DataFrame()

    latest_date = pd.DatetimeIndex(controls.index).max()
    latest = controls.loc[latest_date]
    depository_gap = pd.to_numeric(latest.get("depository_target_minus_tier3_bank_only_flow_mil"), errors="coerce")
    bank_gap = pd.to_numeric(
        latest.get("commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil"), errors="coerce"
    )

    rows: list[dict[str, object]] = []
    for spec in TERM_SPECS:
        latest_value = pd.to_numeric(latest.get(spec["term_key"]), errors="coerce")
        rows.append(
            {
                "latest_quarter": pd.Timestamp(latest_date).date().isoformat(),
                "term_key": spec["term_key"],
                "term_label": spec["label"],
                "stage_role": spec["stage_role"],
                "overlap_risk": spec["overlap_risk"],
                "recommendation": spec["recommendation"],
                "latest_value_mil": latest_value,
                "latest_abs_share_of_depository_gap": (
                    abs(float(latest_value)) / abs(float(depository_gap))
                    if pd.notna(latest_value) and pd.notna(depository_gap) and float(depository_gap) != 0.0
                    else pd.NA
                ),
                "latest_abs_share_of_bank_gap": (
                    abs(float(latest_value)) / abs(float(bank_gap))
                    if pd.notna(latest_value) and pd.notna(bank_gap) and float(bank_gap) != 0.0
                    else pd.NA
                ),
                "rationale": spec["rationale"],
            }
        )

    audit = pd.DataFrame(rows)
    role_rank = {
        "context_only": 0,
        "signed_control": 1,
        "simple_signed_control": 2,
        "refined_signed_control": 3,
    }
    audit["role_rank"] = audit["stage_role"].map(role_rank).fillna(99)
    audit = audit.sort_values(["role_rank", "overlap_risk", "term_label"]).drop(columns=["role_rank"]).reset_index(
        drop=True
    )
    return audit


def render_monetary_control_overlap_audit_markdown(audit: pd.DataFrame) -> str:
    title = "# Monetary Control Overlap Audit"
    intro = (
        "Stage 1 overlap audit for the monetary diagnostic. "
        "This artifact grades each signed control or context term by current role, overlap risk, and current recommendation."
    )
    if audit.empty:
        return "\n".join([title, "", intro, "", "No monetary overlap audit is available."])

    latest_quarter = audit["latest_quarter"].iloc[0]
    high_overlap_context = audit[
        (audit["stage_role"] == "context_only") & (audit["overlap_risk"] == "high")
    ]["term_label"].tolist()
    summary = (
        f"Latest quarter: {latest_quarter}. "
        f"High-overlap context-only terms: {', '.join(high_overlap_context)}. "
        "No high-overlap context term is currently recommended for promotion into a signed subtotal."
    )

    header = [
        "| Term | Role | Overlap risk | Recommendation | Latest value (mil) | Abs share of depository gap | Abs share of bank gap |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    rows: list[str] = []
    for _, row in audit.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["term_label"]),
                    str(row["stage_role"]),
                    str(row["overlap_risk"]),
                    str(row["recommendation"]),
                    _format_millions(row.get("latest_value_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("latest_abs_share_of_depository_gap"), errors="coerce") * 100
                        if pd.notna(row.get("latest_abs_share_of_depository_gap"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("latest_abs_share_of_bank_gap"), errors="coerce") * 100
                        if pd.notna(row.get("latest_abs_share_of_bank_gap"))
                        else pd.NA
                    ),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- Percent-share columns are reported as percentages of the latest Tier 3 gap magnitudes.",
        "- `context_only` means visible in Stage 1 outputs but intentionally excluded from signed subtotals.",
        "- High-overlap Treasury-adjacent terms remain context-only until a dedicated overlap-safe mapping exists.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_control_overlap_audit(
    *,
    monetary_stage1_controls: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    audit = build_monetary_control_overlap_audit(monetary_stage1_controls)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_control_overlap_audit_markdown(audit), encoding="utf-8")

    return csv_path, markdown_path, audit
