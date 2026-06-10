from __future__ import annotations

from pathlib import Path

import pandas as pd


MONETARY_ROUTE_BRIDGE_FIELDS = [
    "date",
    "quarter",
    "route_id",
    "route_label",
    "source_family",
    "amount_source_field",
    "amount_bil",
    "amount_status",
    "m1_scope",
    "m2_scope",
    "deposit_pass_through_scope",
    "tdc_estimator_treatment",
    "ratewall_treatment",
    "current_demand_eligible",
    "canonical_tdc_math_change",
    "exact_blocker",
    "source_status",
    "notes",
]


ROUTE_SPECS = [
    {
        "route_id": "retail_mmf_m2_non_deposit_scope",
        "route_label": "Retail MMF balances are inside M2 but not bank deposits.",
        "source_family": "h6_monetary_aggregate",
        "amount_source_field": "retail_money_market_funds_qoq",
        "m1_scope": "false",
        "m2_scope": "true",
        "deposit_pass_through_scope": "false",
        "tdc_estimator_treatment": "excluded_from_depository_target_by_definition",
        "ratewall_treatment": "context_only_not_deposit_pass_through",
        "current_demand_eligible": "false",
        "exact_blocker": (
            "retail_mmf_shares_are_m2_but_not_bank_deposits_or_current_demand_"
            "evidence"
        ),
        "notes": (
            "H.6 M2 includes retail MMFs; TDC-EST's preferred depository target "
            "subtracts retail MMFs before deposit-scope comparison."
        ),
    },
    {
        "route_id": "mmf_onrrp_runoff_non_m2_plumbing",
        "route_label": "MMF Treasury buying funded by Fed RRP runoff.",
        "source_family": "tdcest_mmf_rrp_adjustment",
        "amount_source_field": "mmf_rrp_adjustment_prop",
        "m1_scope": "false",
        "m2_scope": "false",
        "deposit_pass_through_scope": "false",
        "tdc_estimator_treatment": (
            "current_canonical_tier2_source_of_funds_adjustment_not_deposit_"
            "pass_through_evidence"
        ),
        "ratewall_treatment": "source_backed_plumbing_context_excluded_from_deposit_pass_through",
        "current_demand_eligible": "false",
        "exact_blocker": "fed_rrp_runoff_is_not_bank_deposit_pass_through",
        "notes": (
            "Measured from fund-month MMF Fed RRP runoff allocated to Treasury "
            "increases; forward baseline should be zero unless an explicit "
            "ON-RRP shock path first rebuilds the stock."
        ),
    },
    {
        "route_id": "z1_domestic_nonbank_mixed_unknown_m2_scope",
        "route_label": "Z.1 domestic nonbank Treasury absorption, mixed funding route.",
        "source_family": "z1_holder_absorption",
        "amount_source_field": "z1_security_absorption_du_bil",
        "m1_scope": "unknown",
        "m2_scope": "unknown_or_mixed",
        "deposit_pass_through_scope": "unknown_or_mixed",
        "tdc_estimator_treatment": "context_not_clean_deposit_scope",
        "ratewall_treatment": "blocked_until_m2_or_deposit_funding_split_exists",
        "current_demand_eligible": "false",
        "exact_blocker": "domestic_nonbank_z1_bucket_mixes_m2_and_non_m2_funding_routes",
        "notes": (
            "This is the broad domestic-nonbank holder proxy; it is not a clean "
            "deposit-funded or current-demand recipient measure."
        ),
    },
    {
        "route_id": "z1_mmf_plumbing_mixed_retail_institutional_onrrp_scope",
        "route_label": "Z.1 MMF plumbing bucket, mixed retail/institutional/ON-RRP route.",
        "source_family": "z1_holder_absorption",
        "amount_source_field": "z1_security_absorption_mmf_plumbing_bil",
        "m1_scope": "false",
        "m2_scope": "mixed_retail_mmf_and_non_m2_mmf",
        "deposit_pass_through_scope": "false",
        "tdc_estimator_treatment": "context_or_mmf_rrp_adjustment_only",
        "ratewall_treatment": "context_only_until_retail_institutional_onrrp_split_exists",
        "current_demand_eligible": "false",
        "exact_blocker": "mmf_plumbing_bucket_does_not_identify_retail_m2_vs_institutional_non_m2",
        "notes": (
            "Use the MMF/RRP adjustment for the Fed-RRP-runoff subroute; do not "
            "treat aggregate MMF plumbing as deposit pass-through."
        ),
    },
    {
        "route_id": "z1_dealer_repo_bridge_non_m2_or_unknown_scope",
        "route_label": "Dealer/repo bridge Treasury absorption.",
        "source_family": "z1_holder_absorption",
        "amount_source_field": "z1_security_absorption_dealer_bridge_bil",
        "m1_scope": "false",
        "m2_scope": "false_or_unknown",
        "deposit_pass_through_scope": "false",
        "tdc_estimator_treatment": "context_only_not_depository_target",
        "ratewall_treatment": "context_only_not_current_demand",
        "current_demand_eligible": "false",
        "exact_blocker": "dealer_repo_bridge_is_market_plumbing_not_household_or_deposit_claim",
        "notes": "Keep dealer/repo bridge separate from deposit-funded domestic demand.",
    },
    {
        "route_id": "z1_other_financial_non_m2_scope",
        "route_label": "Other financial domestic nonbank Treasury absorption.",
        "source_family": "z1_holder_absorption",
        "amount_source_field": "z1_security_absorption_other_financial_bil",
        "m1_scope": "false",
        "m2_scope": "false",
        "deposit_pass_through_scope": "false",
        "tdc_estimator_treatment": "context_only_not_depository_target",
        "ratewall_treatment": "context_only_not_current_demand",
        "current_demand_eligible": "false",
        "exact_blocker": (
            "other_financial_claims_are_not_m1_m2_deposit_scope_without_a_"
            "specific_source_split"
        ),
        "notes": "Examples include pension, insurance, mutual-fund, and similar portfolio routes.",
    },
    {
        "route_id": "institutional_mmf_non_m2_target_not_split",
        "route_label": "Institutional MMF route, outside M2 but not separately split here.",
        "source_family": "target_route_contract",
        "amount_source_field": "",
        "m1_scope": "false",
        "m2_scope": "false",
        "deposit_pass_through_scope": "false",
        "tdc_estimator_treatment": "not_separately_observed_current_export",
        "ratewall_treatment": "future_split_target_context_only",
        "current_demand_eligible": "false",
        "exact_blocker": "requires_retail_vs_institutional_mmf_split_before_amount_use",
        "notes": (
            "Included as an explicit target route because institutional MMF "
            "shares are outside M2; current TDC-EST uses MMF/RRP and aggregate "
            "MMF context rather than a full retail/institutional holder split."
        ),
    },
]


def _quarter_from_date(value: object) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return f"{timestamp.year}Q{((timestamp.month - 1) // 3) + 1}"


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _date_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["date", "quarter"])
    out = frame.copy()
    if "date" in out.columns:
        date = pd.to_datetime(out["date"], errors="coerce")
    else:
        date = pd.to_datetime(out.index, errors="coerce")
    out["date"] = date
    out = out.loc[out["date"].notna()].copy()
    out["quarter"] = out["date"].map(_quarter_from_date)
    return out


def _source_amount(row: pd.Series, source_field: str) -> tuple[str, str]:
    if not source_field:
        return "", "not_separately_observed_current_export"
    value = row.get(source_field)
    if value is None or pd.isna(value):
        return "", "missing_source_field"
    return f"{float(value):.6f}".rstrip("0").rstrip("."), "observed_or_derived"


def build_monetary_route_bridge(
    quarterly: pd.DataFrame,
    *,
    ratewall_du_ru_methodology: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build a route-level monetary-scope bridge for downstream TDC users.

    The bridge is classification-only. It makes M1/M2/deposit-pass-through
    scope explicit without changing any canonical TDC estimator value.
    """

    q = _date_frame(quarterly)
    if q.empty:
        return pd.DataFrame(columns=MONETARY_ROUTE_BRIDGE_FIELDS)

    q = q.sort_values("date").copy()
    q["retail_money_market_funds_qoq"] = _numeric(
        q, "retail_money_market_funds"
    ).diff()
    for column in [
        "mmf_rrp_adjustment_prop",
        "mmf_rrp_adjustment_lb",
        "mmf_rrp_adjustment_ub",
    ]:
        if column in q.columns:
            q[column] = _numeric(q, column) / 1000.0

    methodology = _date_frame(
        ratewall_du_ru_methodology
        if ratewall_du_ru_methodology is not None
        else pd.DataFrame()
    )
    if not methodology.empty:
        keep = [
            "quarter",
            "z1_security_absorption_du_bil",
            "z1_security_absorption_mmf_plumbing_bil",
            "z1_security_absorption_dealer_bridge_bil",
            "z1_security_absorption_other_financial_bil",
            "z1_domestic_nonbank_proxy_caveat",
            "z1_mmf_plumbing_label",
            "methodology_status",
        ]
        methodology = methodology.reindex(columns=keep)
        q = q.merge(methodology, on="quarter", how="left")
    else:
        for column in [
            "z1_security_absorption_du_bil",
            "z1_security_absorption_mmf_plumbing_bil",
            "z1_security_absorption_dealer_bridge_bil",
            "z1_security_absorption_other_financial_bil",
            "z1_domestic_nonbank_proxy_caveat",
            "z1_mmf_plumbing_label",
            "methodology_status",
        ]:
            q[column] = pd.NA

    rows: list[dict[str, str]] = []
    for _, base in q.iterrows():
        for spec in ROUTE_SPECS:
            amount, amount_status = _source_amount(base, spec["amount_source_field"])
            source_status = (
                "route_bridge_source_available"
                if amount_status == "observed_or_derived"
                else amount_status
            )
            if spec["source_family"] == "z1_holder_absorption":
                raw_status = base.get("methodology_status", "")
                methodology_status = "" if pd.isna(raw_status) else str(raw_status)
                if methodology_status and not methodology_status.startswith("pass_"):
                    source_status = methodology_status
            rows.append(
                {
                    "date": base["date"].strftime("%Y-%m-%d"),
                    "quarter": str(base["quarter"]),
                    "route_id": spec["route_id"],
                    "route_label": spec["route_label"],
                    "source_family": spec["source_family"],
                    "amount_source_field": spec["amount_source_field"],
                    "amount_bil": amount,
                    "amount_status": amount_status,
                    "m1_scope": spec["m1_scope"],
                    "m2_scope": spec["m2_scope"],
                    "deposit_pass_through_scope": spec["deposit_pass_through_scope"],
                    "tdc_estimator_treatment": spec["tdc_estimator_treatment"],
                    "ratewall_treatment": spec["ratewall_treatment"],
                    "current_demand_eligible": spec["current_demand_eligible"],
                    "canonical_tdc_math_change": "false",
                    "exact_blocker": spec["exact_blocker"],
                    "source_status": source_status,
                    "notes": spec["notes"],
                }
            )

    return pd.DataFrame(rows, columns=MONETARY_ROUTE_BRIDGE_FIELDS)


def render_monetary_route_bridge_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "# TDC Monetary Route Bridge\n\nNo rows were generated.\n"
    latest_quarter = frame["quarter"].dropna().iloc[-1]
    latest = frame.loc[frame["quarter"].eq(latest_quarter)].copy()
    counts = latest["deposit_pass_through_scope"].value_counts().to_dict()
    non_m2 = latest.loc[latest["m2_scope"].astype(str).str.contains("false", na=False)]
    return "\n".join(
        [
            "# TDC Monetary Route Bridge",
            "",
            f"- Latest quarter: `{latest_quarter}`.",
            f"- Latest deposit-pass-through scope counts: `{counts}`.",
            f"- Latest non-M2/non-M2-like route rows: `{len(non_m2)}`.",
            "- Purpose: classify M1/M2/deposit-pass-through scope for domestic nonbank and MMF routes.",
            "- Boundary: classification-only; this bridge does not change canonical TDC math.",
            "- RateWall use: import route labels and keep non-M2 routes out of deposit-pass-through/current-demand math unless a future source-backed split clears the blocker.",
            "",
        ]
    )


def write_monetary_route_bridge(
    *,
    quarterly: pd.DataFrame,
    ratewall_du_ru_methodology: pd.DataFrame | None,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None, pd.DataFrame]:
    frame = build_monetary_route_bridge(
        quarterly,
        ratewall_du_ru_methodology=ratewall_du_ru_methodology,
    )
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    md_target: Path | None = None
    if markdown_path is not None:
        md_target = Path(markdown_path)
        md_target.parent.mkdir(parents=True, exist_ok=True)
        md_target.write_text(render_monetary_route_bridge_markdown(frame), encoding="utf-8")
    return target, md_target, frame
