from __future__ import annotations

from pathlib import Path

import pandas as pd


CONTRIBUTION_COLUMNS = [
    "scenario_key",
    "reference_date",
    "estimator_key",
    "estimator_role",
    "estimator_value_millions",
    "component_family",
    "component_key",
    "signed_contribution_millions",
    "share_of_absolute_estimator",
    "inclusion_role",
    "boundary_note",
]


def _value(frame: pd.DataFrame | None, index: pd.Timestamp, column: str) -> float | None:
    if frame is None or frame.empty or column not in frame.columns or index not in frame.index:
        return None
    value = pd.to_numeric(pd.Series([frame.loc[index, column]]), errors="coerce").iloc[0]
    if pd.isna(value):
        return None
    return float(value)


def _share(component: float | None, total: float | None) -> float | None:
    if component is None or total is None or total == 0:
        return None
    return float(component) / abs(float(total))


def _rows_for_scenario(
    *,
    scenario_key: str,
    reference_date: pd.Timestamp,
    estimator_key: str,
    estimator_role: str,
    estimator_value: float | None,
    components: list[tuple[str, str, float | None, str, str]],
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for family, key, value, inclusion_role, boundary_note in components:
        out.append(
            {
                "scenario_key": scenario_key,
                "reference_date": reference_date.date().isoformat(),
                "estimator_key": estimator_key,
                "estimator_role": estimator_role,
                "estimator_value_millions": estimator_value,
                "component_family": family,
                "component_key": key,
                "signed_contribution_millions": value,
                "share_of_absolute_estimator": _share(value, estimator_value),
                "inclusion_role": inclusion_role,
                "boundary_note": boundary_note,
            }
        )
    return out


def build_downstream_component_contribution_review(
    *,
    estimates: pd.DataFrame | None,
    components: pd.DataFrame | None,
    corrections: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
) -> pd.DataFrame:
    if estimates is None or estimates.empty or components is None or components.empty:
        return pd.DataFrame(columns=CONTRIBUTION_COLUMNS)

    est = estimates.copy()
    est.index = pd.to_datetime(est.index)
    comp = components.copy()
    comp.index = pd.to_datetime(comp.index)
    corr = corrections.copy() if corrections is not None else pd.DataFrame()
    if not corr.empty:
        corr.index = pd.to_datetime(corr.index)

    hist = tier3_historical_bank_receipt_research.copy() if tier3_historical_bank_receipt_research is not None else pd.DataFrame()
    if not hist.empty:
        if "date" in hist.columns:
            hist["date"] = pd.to_datetime(hist["date"])
            hist = hist.set_index("date")
        else:
            hist.index = pd.to_datetime(hist.index)

    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    bank_current = pd.Series(dtype="object")
    row_mrv = pd.Series(dtype="object")
    if not receipt.empty and "branch_key" in receipt.columns:
        current_match = receipt.loc[receipt["branch_key"].eq("bank_table51_current_window")]
        if not current_match.empty:
            bank_current = current_match.iloc[0]
        row_match = receipt.loc[receipt["branch_key"].eq("row_mrv_cbsp_primary")]
        if not row_match.empty:
            row_mrv = row_match.iloc[0]

    latest_live = est.index.max()
    latest_live_value = _value(est, latest_live, "tdc_tier3_fiscal_corrected_bank_only_ru_flow")
    latest_broad_value = _value(est, latest_live, "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow")

    base_common = [
        ("base", "fed_tsy_tx", _value(comp, latest_live, "fed_tsy_tx"), "included", "Core Treasury transaction term."),
        ("base", "bank_depository_tsy_tx", _value(comp, latest_live, "bank_depository_tsy_tx"), "included", "Core bank-sector Treasury transaction term."),
        ("base", "row_tsy_tx", _value(comp, latest_live, "row_tsy_tx"), "included", "Core rest-of-world Treasury transaction term."),
        ("base", "minus_treasury_operating_cash_tx", _value(comp, latest_live, "minus_treasury_operating_cash_tx"), "included", "Cash drag term subtracted in the estimator."),
        ("base", "fed_remit_positive", _value(comp, latest_live, "fed_remit_positive"), "included", "Positive remittance add-back."),
        ("coupon", "tier1_fed_coupon_correction", _value(corr, latest_live, "tier1_fed_coupon_correction"), "included", "Fed coupon correction layer."),
        ("coupon", "tier2_bank_coupon_correction", _value(corr, latest_live, "tier2_bank_coupon_correction"), "included", "Bank coupon correction layer."),
        ("coupon", "tier2_row_coupon_correction", _value(corr, latest_live, "tier2_row_coupon_correction"), "included", "ROW coupon correction layer."),
        ("fiscal", "tier3_bank_noninterest_outlay_correction", _value(corr, latest_live, "tier3_bank_noninterest_outlay_correction"), "included", "Bank outlay correction inside live Tier 3."),
        ("fiscal", "tier3_row_noninterest_outlay_correction", _value(corr, latest_live, "tier3_row_noninterest_outlay_correction"), "included", "ROW outlay correction inside live Tier 3."),
        ("fiscal", "tier3_bank_nonborrow_receipt_correction", _value(corr, latest_live, "tier3_bank_nonborrow_receipt_correction"), "included", str(bank_current.get("summary_note", "Current bank receipt correction remains nondefault."))),
        ("fiscal", "tier3_row_nonborrow_receipt_correction", _value(corr, latest_live, "tier3_row_nonborrow_receipt_correction"), "included", str(row_mrv.get("summary_note", "Current ROW receipt correction remains nondefault."))),
        ("fiscal", "tier3_mint_cb_cash_factor_correction", _value(corr, latest_live, "tier3_mint_cb_cash_factor_correction"), "included", "Mint/cash-factor correction."),
    ]

    rows = _rows_for_scenario(
        scenario_key="latest_live_bank_tier3_default",
        reference_date=latest_live,
        estimator_key="tdc_tier3_fiscal_corrected_bank_only_ru_flow",
        estimator_role="live_default",
        estimator_value=latest_live_value,
        components=base_common,
    )

    rows.extend(
        _rows_for_scenario(
            scenario_key="latest_live_broad_tier3_default",
            reference_date=latest_live,
            estimator_key="tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
            estimator_role="broad_depository_default",
            estimator_value=latest_broad_value,
            components=base_common
            + [
                (
                    "base",
                    "np_credit_unions_tsy_tx",
                    _value(comp, latest_live, "np_credit_unions_tsy_tx"),
                    "included",
                    "Natural-person credit unions are included only in the broad-depository view.",
                )
            ],
        )
    )

    if not hist.empty:
        latest_hist = hist.sort_index().iloc[-1]
        hist_date = pd.Timestamp(latest_hist.name)
        hist_default = _value(est, hist_date, "tdc_tier3_fiscal_corrected_bank_only_ru_flow")
        hist_variant = pd.to_numeric(
            latest_hist.get("tdc_tier3_bank_only_plus_historical_bank_receipt_candidate"),
            errors="coerce",
        )
        hist_lower = pd.to_numeric(
            latest_hist.get("tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound"),
            errors="coerce",
        )
        hist_common = [
            ("base", "fed_tsy_tx", _value(comp, hist_date, "fed_tsy_tx"), "included", "Core Treasury transaction term."),
            ("base", "bank_depository_tsy_tx", _value(comp, hist_date, "bank_depository_tsy_tx"), "included", "Core bank-sector Treasury transaction term."),
            ("base", "row_tsy_tx", _value(comp, hist_date, "row_tsy_tx"), "included", "Core rest-of-world Treasury transaction term."),
            ("base", "minus_treasury_operating_cash_tx", _value(comp, hist_date, "minus_treasury_operating_cash_tx"), "included", "Cash drag term subtracted in the estimator."),
            ("base", "fed_remit_positive", _value(comp, hist_date, "fed_remit_positive"), "included", "Positive remittance add-back."),
            ("coupon", "tier1_fed_coupon_correction", _value(corr, hist_date, "tier1_fed_coupon_correction"), "included", "Fed coupon correction layer."),
            ("coupon", "tier2_bank_coupon_correction", _value(corr, hist_date, "tier2_bank_coupon_correction"), "included", "Bank coupon correction layer."),
            ("coupon", "tier2_row_coupon_correction", _value(corr, hist_date, "tier2_row_coupon_correction"), "included", "ROW coupon correction layer."),
            ("fiscal", "tier3_bank_noninterest_outlay_correction", _value(corr, hist_date, "tier3_bank_noninterest_outlay_correction"), "included", "Bank outlay correction inside live Tier 3."),
            ("fiscal", "tier3_row_noninterest_outlay_correction", _value(corr, hist_date, "tier3_row_noninterest_outlay_correction"), "included", "ROW outlay correction inside live Tier 3."),
            ("fiscal", "tier3_bank_nonborrow_receipt_correction", _value(corr, hist_date, "tier3_bank_nonborrow_receipt_correction"), "included", "Default live bank receipt correction remains zero or nondefault."),
            ("fiscal", "tier3_row_nonborrow_receipt_correction", _value(corr, hist_date, "tier3_row_nonborrow_receipt_correction"), "included", "Default live ROW receipt correction remains zero or nondefault."),
            ("fiscal", "tier3_mint_cb_cash_factor_correction", _value(corr, hist_date, "tier3_mint_cb_cash_factor_correction"), "included", "Mint/cash-factor correction."),
        ]
        rows.extend(
            _rows_for_scenario(
                scenario_key="latest_historical_bank_tier3_default",
                reference_date=hist_date,
                estimator_key="tdc_tier3_fiscal_corrected_bank_only_ru_flow",
                estimator_role="historical_reference_default",
                estimator_value=hist_default,
                components=hist_common,
            )
        )
        rows.extend(
            _rows_for_scenario(
                scenario_key="latest_historical_bank_receipt_variant",
                reference_date=hist_date,
                estimator_key="tdc_tier3_bank_only_plus_historical_bank_receipt_candidate",
                estimator_role="historical_default_view",
                estimator_value=None if pd.isna(hist_variant) else float(hist_variant),
                components=hist_common
                + [
                    (
                        "historical_overlay",
                        "bank_receipt_historical_default_candidate_delta_mil",
                        pd.to_numeric(
                            latest_hist.get("bank_receipt_historical_default_candidate_delta_mil"),
                            errors="coerce",
                        ),
                        "included",
                        "Historical age-eligible bank receipt overlay added only inside the historical window.",
                    )
                ],
            )
        )
        rows.extend(
            _rows_for_scenario(
                scenario_key="latest_historical_bank_receipt_lower_bound",
                reference_date=hist_date,
                estimator_key="tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound",
                estimator_role="historical_lower_bound",
                estimator_value=None if pd.isna(hist_lower) else float(hist_lower),
                components=hist_common
                + [
                    (
                        "historical_overlay",
                        "bank_receipt_historical_lower_bound_delta_mil",
                        pd.to_numeric(
                            latest_hist.get("bank_receipt_historical_lower_bound_delta_mil"),
                            errors="coerce",
                        ),
                        "included",
                        "Historical lower-bound overlay using the stricter depository-only share.",
                    )
                ],
            )
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=CONTRIBUTION_COLUMNS)
    return out.reindex(columns=CONTRIBUTION_COLUMNS)


def render_downstream_component_contribution_review_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Component Contribution Review"
    intro = (
        "Long-form additive contribution table for the main live and historical-backtest scenarios. "
        "This is intended for downstream deposit-effect work that needs explicit signed component terms and shares."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream component contribution rows are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Scenario | Date | Estimator | Component family | Component | Signed contribution (mil) | Share of | Inclusion role |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for _, row in frame.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["scenario_key"]),
                    str(row["reference_date"]),
                    str(row["estimator_key"]),
                    str(row["component_family"]),
                    str(row["component_key"]),
                    "n/a" if pd.isna(row["signed_contribution_millions"]) else f"{float(row['signed_contribution_millions']):,.3f}",
                    "n/a" if pd.isna(row["share_of_absolute_estimator"]) else f"{float(row['share_of_absolute_estimator']):.3f}",
                    str(row["inclusion_role"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "Notes:",
            "- Shares are computed relative to the absolute estimator value for that scenario.",
            "- Historical overlay components appear only in the historical bank receipt scenarios.",
            "- Live default bank and ROW receipt corrections remain visible as zero or nondefault placeholders where appropriate.",
        ]
    )
    return "\n".join(lines + [""])


def write_downstream_component_contribution_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    estimates: pd.DataFrame | None,
    components: pd.DataFrame | None,
    corrections: pd.DataFrame | None,
    tier3_historical_bank_receipt_research: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_component_contribution_review(
        estimates=estimates,
        components=components,
        corrections=corrections,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
        receipt_unblock_status=receipt_unblock_status,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_component_contribution_review_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
