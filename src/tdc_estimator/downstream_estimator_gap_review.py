from __future__ import annotations

from pathlib import Path

import pandas as pd


GAP_COLUMNS = [
    "gap_key",
    "reference_date",
    "lhs_estimator",
    "rhs_estimator",
    "lhs_value_millions",
    "rhs_value_millions",
    "net_delta_millions",
    "dominant_component_key",
    "dominant_component_family",
    "dominant_component_role",
    "dominant_component_millions",
    "dominant_component_share_of_gap",
    "secondary_component_key",
    "secondary_component_family",
    "secondary_component_role",
    "secondary_component_millions",
    "secondary_component_share_of_gap",
    "gap_role",
    "interpretation",
]


def _fmt(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _value(df: pd.DataFrame, index: pd.Timestamp, column: str) -> float | None:
    if column not in df.columns or index not in df.index:
        return None
    value = pd.to_numeric(pd.Series([df.loc[index, column]]), errors="coerce").iloc[0]
    if pd.isna(value):
        return None
    return float(value)


def _top_components(
    component_items: list[tuple[str, str, float | None, str]],
    gap: float | None,
) -> tuple[dict[str, object], dict[str, object]]:
    ranked = [item for item in component_items if item[2] is not None and item[2] != 0]
    ranked.sort(key=lambda item: abs(float(item[2])), reverse=True)
    top = ranked[0] if ranked else ("n/a", "n/a", None, "n/a")
    second = ranked[1] if len(ranked) > 1 else ("n/a", "n/a", None, "n/a")

    def _as_dict(item: tuple[str, str, float | None, str]) -> dict[str, object]:
        key, family, value, role = item
        share = None
        if value is not None and gap not in (None, 0):
            share = float(value) / abs(float(gap))
        return {
            "key": key,
            "family": family,
            "role": role,
            "value": value,
            "share": share,
        }

    return _as_dict(top), _as_dict(second)


def build_downstream_estimator_gap_review(
    *,
    estimates: pd.DataFrame | None,
    components: pd.DataFrame | None,
    corrections: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
) -> pd.DataFrame:
    if estimates is None or estimates.empty or corrections is None or corrections.empty:
        return pd.DataFrame(columns=GAP_COLUMNS)

    est = estimates.copy()
    est.index = pd.to_datetime(est.index)
    comp = components.copy() if components is not None else pd.DataFrame(index=est.index)
    if not comp.empty:
        comp.index = pd.to_datetime(comp.index)
    corr = corrections.copy()
    corr.index = pd.to_datetime(corr.index)

    rows: list[dict[str, object]] = []
    latest = est.index.max()

    def append_gap(
        *,
        gap_key: str,
        index: pd.Timestamp,
        lhs: str,
        rhs: str,
        delta: float | None,
        candidates: list[tuple[str, str, float | None, str]],
        gap_role: str,
        interpretation: str,
        lhs_value: float | None = None,
        rhs_value: float | None = None,
    ) -> None:
        top, second = _top_components(candidates, delta)
        rows.append(
            {
                "gap_key": gap_key,
                "reference_date": index.date().isoformat(),
                "lhs_estimator": lhs,
                "rhs_estimator": rhs,
                "lhs_value_millions": _value(est, index, lhs) if lhs_value is None else lhs_value,
                "rhs_value_millions": _value(est, index, rhs) if rhs_value is None else rhs_value,
                "net_delta_millions": delta,
                "dominant_component_key": top["key"],
                "dominant_component_family": top["family"],
                "dominant_component_role": top["role"],
                "dominant_component_millions": top["value"],
                "dominant_component_share_of_gap": top["share"],
                "secondary_component_key": second["key"],
                "secondary_component_family": second["family"],
                "secondary_component_role": second["role"],
                "secondary_component_millions": second["value"],
                "secondary_component_share_of_gap": second["share"],
                "gap_role": gap_role,
                "interpretation": interpretation,
            }
        )

    base_to_tier2 = (_value(est, latest, "tdc_tier2_interest_corrected_bank_only_ru_flow") or 0.0) - (
        _value(est, latest, "tdc_base_bank_only_ru_flow") or 0.0
    )
    append_gap(
        gap_key="latest_live_base_to_tier2_bank_only",
        index=latest,
        lhs="tdc_tier2_interest_corrected_bank_only_ru_flow",
        rhs="tdc_base_bank_only_ru_flow",
        delta=base_to_tier2,
        candidates=[
            ("tier2_row_coupon_correction", "coupon", _value(corr, latest, "tier2_row_coupon_correction"), "additive_driver"),
            ("tier1_fed_coupon_correction", "coupon", _value(corr, latest, "tier1_fed_coupon_correction"), "additive_driver"),
            ("tier2_bank_coupon_correction", "coupon", _value(corr, latest, "tier2_bank_coupon_correction"), "additive_driver"),
        ],
        gap_role="interest_cleanup_gap",
        interpretation="Difference between the base headline and Tier 2 bank-only, dominated by coupon-correction assumptions.",
    )

    tier2_to_tier3 = (_value(est, latest, "tdc_tier3_fiscal_corrected_bank_only_ru_flow") or 0.0) - (
        _value(est, latest, "tdc_tier2_interest_corrected_bank_only_ru_flow") or 0.0
    )
    append_gap(
        gap_key="latest_live_tier2_to_tier3_bank_only",
        index=latest,
        lhs="tdc_tier3_fiscal_corrected_bank_only_ru_flow",
        rhs="tdc_tier2_interest_corrected_bank_only_ru_flow",
        delta=tier2_to_tier3,
        candidates=[
            ("tier3_row_noninterest_outlay_correction", "fiscal", _value(corr, latest, "tier3_row_noninterest_outlay_correction"), "additive_driver"),
            ("tier3_bank_noninterest_outlay_correction", "fiscal", _value(corr, latest, "tier3_bank_noninterest_outlay_correction"), "additive_driver"),
            ("tier3_bank_nonborrow_receipt_correction", "receipt", _value(corr, latest, "tier3_bank_nonborrow_receipt_correction"), "additive_driver"),
            ("tier3_row_nonborrow_receipt_correction", "receipt", _value(corr, latest, "tier3_row_nonborrow_receipt_correction"), "additive_driver"),
            ("tier3_mint_cb_cash_factor_correction", "fiscal", _value(corr, latest, "tier3_mint_cb_cash_factor_correction"), "additive_driver"),
        ],
        gap_role="fiscal_layer_gap",
        interpretation="Difference between Tier 2 and live Tier 3 bank-only, showing which current fiscal-flow adjustments actually move the estimator.",
    )

    bank_to_broad = (_value(est, latest, "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow") or 0.0) - (
        _value(est, latest, "tdc_tier3_fiscal_corrected_bank_only_ru_flow") or 0.0
    )
    append_gap(
        gap_key="latest_live_bank_to_broad_depository_tier3",
        index=latest,
        lhs="tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
        rhs="tdc_tier3_fiscal_corrected_bank_only_ru_flow",
        delta=bank_to_broad,
        candidates=[
            ("np_credit_unions_tsy_tx", "deposit_perimeter", _value(comp, latest, "np_credit_unions_tsy_tx"), "additive_driver"),
        ],
        gap_role="deposit_perimeter_gap",
        interpretation="Difference between live bank-only and live broad-depository Tier 3, dominated by credit-union perimeter treatment.",
    )

    hist = tier3_historical_bank_receipt_research.copy() if tier3_historical_bank_receipt_research is not None else pd.DataFrame()
    if not hist.empty:
        if "date" in hist.columns:
            hist["date"] = pd.to_datetime(hist["date"])
            hist = hist.set_index("date")
        else:
            hist.index = pd.to_datetime(hist.index)
        hist_latest = hist.sort_index().iloc[-1]
        hist_date = pd.Timestamp(hist_latest.name)
        hist_default = pd.to_numeric(hist_latest.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow"), errors="coerce")
        hist_variant = pd.to_numeric(
            hist_latest.get("tdc_tier3_bank_only_plus_historical_bank_receipt_candidate"),
            errors="coerce",
        )
        hist_lower = pd.to_numeric(
            hist_latest.get("tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound"),
            errors="coerce",
        )
        append_gap(
            gap_key="latest_historical_bank_receipt_overlay",
            index=hist_date,
            lhs="tdc_tier3_bank_only_plus_historical_bank_receipt_candidate",
            rhs="tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            delta=None if pd.isna(hist_variant) or pd.isna(hist_default) else float(hist_variant - hist_default),
            candidates=[
                (
                    "bank_receipt_historical_default_candidate_delta_mil",
                    "historical_receipt_overlay",
                    pd.to_numeric(
                        hist_latest.get("bank_receipt_historical_default_candidate_delta_mil"),
                        errors="coerce",
                    ),
                    "additive_driver",
                ),
            ],
            gap_role="historical_receipt_overlay_gap",
            interpretation="Difference between the historical bank receipt candidate overlay and default historical Tier 3 bank-only.",
            lhs_value=None if pd.isna(hist_variant) else float(hist_variant),
            rhs_value=None if pd.isna(hist_default) else float(hist_default),
        )
        append_gap(
            gap_key="latest_historical_candidate_to_lower_bound",
            index=hist_date,
            lhs="tdc_tier3_bank_only_plus_historical_bank_receipt_candidate",
            rhs="tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound",
            delta=None if pd.isna(hist_variant) or pd.isna(hist_lower) else float(hist_variant - hist_lower),
            candidates=[
                (
                    "bank_receipt_historical_default_candidate_delta_mil",
                    "historical_receipt_overlay",
                    pd.to_numeric(
                        hist_latest.get("bank_receipt_historical_default_candidate_delta_mil"),
                        errors="coerce",
                    ),
                    "endpoint_context",
                ),
                (
                    "bank_receipt_historical_lower_bound_delta_mil",
                    "historical_receipt_overlay",
                    -pd.to_numeric(
                        hist_latest.get("bank_receipt_historical_lower_bound_delta_mil"),
                        errors="coerce",
                    ),
                    "endpoint_context",
                ),
            ],
            gap_role="historical_receipt_uncertainty_gap",
            interpretation="Difference between the main historical bank receipt overlay and the stricter historical lower bound, expressed as signed endpoint context rather than as additive live drivers.",
            lhs_value=None if pd.isna(hist_variant) else float(hist_variant),
            rhs_value=None if pd.isna(hist_lower) else float(hist_lower),
        )

    return pd.DataFrame(rows).reindex(columns=GAP_COLUMNS)


def render_downstream_estimator_gap_review_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Estimator Gap Review"
    intro = (
        "Compact gap review for downstream work. It turns the main estimator differences into explicit deltas and names the dominant components behind each gap."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream estimator gap rows are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Gap | Date | LHS | RHS | Net delta (mil) | Dominant component | Dominant share | Secondary component | Gap role |",
        "| --- | --- | --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    for _, row in frame.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["gap_key"]),
                    str(row["reference_date"]),
                    str(row["lhs_estimator"]),
                    str(row["rhs_estimator"]),
                    _fmt(row["net_delta_millions"]),
                    str(row["dominant_component_key"]),
                    _fmt(row["dominant_component_share_of_gap"]),
                    f"{row['secondary_component_key']} ({row['secondary_component_role']})",
                    str(row["gap_role"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Notes", ""])
    for _, row in frame.iterrows():
        lines.append(f"- `{row['gap_key']}`: {row['interpretation']}")

    return "\n".join(lines + [""])


def write_downstream_estimator_gap_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    estimates: pd.DataFrame | None,
    components: pd.DataFrame | None,
    corrections: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_estimator_gap_review(
        estimates=estimates,
        components=components,
        corrections=corrections,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_estimator_gap_review_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
