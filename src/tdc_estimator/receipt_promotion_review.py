from __future__ import annotations

from pathlib import Path

import pandas as pd


def _latest_nonzero(series: pd.Series | None) -> float | None:
    if series is None:
        return None
    s = pd.to_numeric(series, errors="coerce").dropna()
    s = s.loc[s.ne(0.0)]
    if s.empty:
        return None
    return float(s.iloc[-1])


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _latest_nonzero_date(series: pd.Series | None) -> pd.Timestamp | pd.NaT:
    if series is None:
        return pd.NaT
    s = pd.to_numeric(series, errors="coerce").dropna()
    s = s.loc[s.ne(0.0)]
    if s.empty:
        return pd.NaT
    return pd.Timestamp(s.index[-1])


def build_receipt_promotion_review(
    *,
    bea_row_receipts_benchmark: pd.DataFrame | None = None,
    bank_corp_tax_receipts_bridge: pd.DataFrame | None = None,
    receipt_account_candidates: pd.DataFrame | None = None,
    receipt_account_crosswalk: pd.DataFrame | None = None,
    row_receipt_family_review: pd.DataFrame | None = None,
    row_recurring_pilot_review: pd.DataFrame | None = None,
    row_mrv_promotion_checklist: pd.DataFrame | None = None,
    row_mrv_stop_gate: pd.DataFrame | None = None,
    bank_receipt_stop_gate: pd.DataFrame | None = None,
    bank_occ_timing_sensitivity: pd.DataFrame | None = None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None = None,
    tier3_receipt_source_diagnostics: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    bank_stop_gate_note = ""
    if bank_receipt_stop_gate is not None and not bank_receipt_stop_gate.empty:
        summary = bank_receipt_stop_gate.loc[
            bank_receipt_stop_gate.get("row_type", pd.Series(dtype="object")).eq("summary")
        ]
        if not summary.empty:
            row = summary.iloc[0]
            bank_stop_gate_note = f" Stop gate: {row['status']}."

    if bank_corp_tax_receipts_bridge is not None and not bank_corp_tax_receipts_bridge.empty:
        latest_val = _latest_nonzero(bank_corp_tax_receipts_bridge.get("bank_corp_tax_receipts_gross_depository_plus_bhc_mil"))
        latest_date = _latest_nonzero_date(bank_corp_tax_receipts_bridge.get("bank_corp_tax_receipts_gross_depository_plus_bhc_mil"))
        rows.append(
            {
                "candidate_name": "bank_corporate_tax_bridge_depository_plus_bhc",
                "counterparty_group": "bank",
                "basis": "MTS quarterly corporate-tax cash totals x IRS Publication 16 Table 5.1 depository-plus-BHC annual share",
                "payer_identity_status": "indirect_sector_bridge",
                "timing_status": "quarterly_cash_aligned",
                "budget_treatment_status": "general_receipt_like",
                "current_role": "benchmark_bridge",
                "latest_reference_date": latest_date,
                "promotion_status": (
                    "best_bank_default_candidate_under_review"
                    if bool(bank_corp_tax_receipts_bridge.iloc[-1].get("share_age_eligible_for_default", False))
                    else "best_bank_default_candidate_under_review_but_share_too_stale"
                ),
                "latest_value_millions": latest_val,
                "review_note": (
                    "Strongest current public path to a nonzero bank receipt correction: quarterly MTS cash anchored to IRS Table 5.1 bank-minor shares, with bank holding companies included."
                    if bool(bank_corp_tax_receipts_bridge.iloc[-1].get("share_age_eligible_for_default", False))
                    else "Strongest current public path to a nonzero bank receipt correction, but the latest carried-forward Table 5.1 share is already outside the bridge's age-eligibility rule."
                ),
            }
        )
        if bank_stop_gate_note:
            rows[-1]["review_note"] = str(rows[-1]["review_note"]) + bank_stop_gate_note
        rows.append(
            {
                "candidate_name": "bank_corporate_tax_bridge_strict_depository",
                "counterparty_group": "bank",
                "basis": "MTS quarterly corporate-tax cash totals x IRS Publication 16 Table 5.1 strict-depository annual share",
                "payer_identity_status": "indirect_sector_bridge_lower_bound",
                "timing_status": "quarterly_cash_aligned",
                "budget_treatment_status": "general_receipt_like",
                "current_role": "sensitivity",
                "latest_reference_date": _latest_nonzero_date(
                    bank_corp_tax_receipts_bridge.get("bank_corp_tax_receipts_gross_strict_depository_mil")
                ),
                "promotion_status": "lower_bound_sensitivity_under_review",
                "latest_value_millions": _latest_nonzero(
                    bank_corp_tax_receipts_bridge.get("bank_corp_tax_receipts_gross_strict_depository_mil")
                ),
                "review_note": "Cleaner depository-only perimeter, but likely undercounts bank-group tax paid at the holding-company level.",
            }
        )
        rows.append(
            {
                "candidate_name": "bank_corporate_tax_bridge_finance_share_upper_benchmark",
                "counterparty_group": "bank",
                "basis": "MTS quarterly corporate-tax cash totals x IRS finance-sector annual share",
                "payer_identity_status": "broad_sector_upper_benchmark",
                "timing_status": "quarterly_cash_aligned",
                "budget_treatment_status": "general_receipt_like",
                "current_role": "benchmark",
                "latest_reference_date": _latest_nonzero_date(
                    bank_corp_tax_receipts_bridge.get("bank_corp_tax_receipts_gross_finance_share_mil")
                ),
                "promotion_status": "keep_nondefault_upper_benchmark",
                "latest_value_millions": _latest_nonzero(
                    bank_corp_tax_receipts_bridge.get("bank_corp_tax_receipts_gross_finance_share_mil")
                ),
                "review_note": "Retained as a reproducibility and scale check only; no longer the preferred bank-side default candidate.",
            }
        )

    if bank_occ_timing_sensitivity is not None and not bank_occ_timing_sensitivity.empty:
        latest_val = _latest_nonzero(bank_occ_timing_sensitivity.get("occ_due_date_allocated_receipt_mil"))
        rows.append(
            {
                "candidate_name": "occ_due_date_timing_sensitivity",
                "counterparty_group": "bank",
                "basis": "Annual OCC-linked public account lines split across the official semiannual assessment due dates",
                "payer_identity_status": "direct_bank_linkage_but_annual_public_surface",
                "timing_status": "quarterly_due_date_convention",
                "budget_treatment_status": "general_fund_fine_penalty_receipt",
                "current_role": "sensitivity",
                "latest_reference_date": _latest_nonzero_date(bank_occ_timing_sensitivity.get("occ_due_date_allocated_receipt_mil")),
                "promotion_status": "keep_nondefault_until_budget_treatment_is_stronger",
                "latest_value_millions": latest_val,
                "review_note": "Useful as a bank non-tax quarterly sensitivity, but still too dependent on annual public account evidence and timing convention for default use.",
            }
        )

    latest_row_family_review = pd.DataFrame()
    if row_receipt_family_review is not None and not row_receipt_family_review.empty:
        family_review = row_receipt_family_review.copy()
        if "date" in family_review.columns:
            family_review["date"] = pd.to_datetime(family_review["date"])
            latest_row_family_review = family_review.loc[family_review["date"].eq(family_review["date"].max())].copy()

    latest_recurring_pilot_review = pd.DataFrame()
    if row_recurring_pilot_review is not None and not row_recurring_pilot_review.empty:
        recurring = row_recurring_pilot_review.copy()
        if "date" in recurring.columns:
            recurring["date"] = pd.to_datetime(recurring["date"])
            latest_recurring_pilot_review = recurring.loc[recurring["date"].eq(recurring["date"].max())].copy()

    mrv_checklist_note = ""
    if row_mrv_promotion_checklist is not None and not row_mrv_promotion_checklist.empty:
        checklist = row_mrv_promotion_checklist.copy()
        required = checklist.loc[checklist.get("required_for_default", pd.Series(dtype="bool")).fillna(False)]
        if not required.empty:
            complete = int(required["status"].eq("complete").sum())
            partial = int(required["status"].eq("partial").sum())
            missing = int(required["status"].eq("missing").sum())
            mrv_checklist_note = (
                f" Promotion checklist: {complete} complete, {partial} partial default blocker, {missing} missing required checks."
            )
    mrv_stop_gate_note = ""
    if row_mrv_stop_gate is not None and not row_mrv_stop_gate.empty:
        summary = row_mrv_stop_gate.loc[row_mrv_stop_gate.get("row_type", pd.Series(dtype="object")).eq("summary")]
        if not summary.empty:
            row = summary.iloc[0]
            mrv_stop_gate_note = (
                f" Stop gate: {row['status']}."
            )

    if receipt_account_candidates is not None and not receipt_account_candidates.empty:
        fdic = receipt_account_candidates.loc[
            receipt_account_candidates["receipt_line_item_nm"].str.contains("Federal Deposit Insurance Corporation", case=False, na=False)
        ]
        if not fdic.empty:
            rows.append(
                {
                    "candidate_name": "fdic_penalty_lines",
                    "counterparty_group": "bank",
                    "basis": "Annual public Receipts by Department lines with FAST Book / CARS treatment overlay",
                    "payer_identity_status": "bank_regulatory_mixed",
                    "timing_status": "annual_only",
                    "budget_treatment_status": "general_fund_fine_penalty_receipt",
                    "current_role": "sensitivity",
                    "latest_reference_date": pd.Timestamp(fdic.sort_values("date").iloc[-1]["date"]),
                    "promotion_status": "keep_nondefault_no_quarterly_timing",
                    "latest_value_millions": float(fdic.sort_values("date").iloc[-1]["receipt_amt_mil"]),
                    "review_note": "General-fund penalty treatment is clearer now, but the public surface is still annual and mixed for direct default use.",
                }
            )

        fms = receipt_account_candidates.loc[
            receipt_account_candidates["receipt_line_item_nm"].str.contains("Foreign Military Sales", case=False, na=False)
        ]
        if not fms.empty:
            fms_family_note = ""
            if not latest_row_family_review.empty:
                fms_family = latest_row_family_review.loc[
                    latest_row_family_review["candidate_family"].eq("row_fms_deposit_trust_family")
                ]
                if not fms_family.empty:
                    latest_fms_family = fms_family.iloc[0]
                    fms_family_note = (
                        f" Latest family review: {latest_fms_family['combined_statement_confirmation']} confirmation over "
                        f"{_format_millions(latest_fms_family['combined_statement_confirmed_receipt_mil'])} million, "
                        f"decision `{latest_fms_family['review_decision']}`."
                    )
            rows.append(
                {
                    "candidate_name": "foreign_military_sales_receipts",
                    "counterparty_group": "row",
                    "basis": "Annual public Receipts by Department lines with FAST Book / CARS treatment overlay",
                    "payer_identity_status": "foreign_customer_linkage_but_not_current_receipt_default",
                    "timing_status": "annual_only",
                    "budget_treatment_status": "deposit_or_trust_nondefault",
                    "current_role": "sensitivity",
                    "latest_reference_date": pd.Timestamp(fms.sort_values("date").iloc[-1]["date"]),
                    "promotion_status": "reject_default_deposit_trust_concept",
                    "latest_value_millions": float(fms.sort_values("receipt_amt_mil", ascending=False).iloc[0]["receipt_amt_mil"]),
                    "review_note": "The overlay confirms these are deposit or advance style lines and should stay out of any default ROW current-receipt correction." + fms_family_note,
                }
            )

    if not latest_row_family_review.empty:
        dsh_immigration = latest_row_family_review.loc[
            latest_row_family_review["candidate_family"].eq("row_dhs_immigration_family_mixed")
        ]
        if not dsh_immigration.empty:
            family = dsh_immigration.iloc[0]
            rows.append(
                {
                    "candidate_name": "row_dhs_immigration_family_mixed",
                    "counterparty_group": "row",
                    "basis": "Annual public DHS immigration-fee families crosswalked to broader Combined Statement main-account families",
                    "payer_identity_status": "contaminated_domestic_and_mixed_fee_family",
                    "timing_status": "annual_only",
                    "budget_treatment_status": "family_confirmed_but_not_clean_cash_payer",
                    "current_role": "contamination_accounting",
                    "latest_reference_date": pd.Timestamp(family["date"]),
                    "promotion_status": "confirmed_contaminated_nondefault",
                    "latest_value_millions": float(family["family_total_receipt_mil"]),
                    "review_note": (
                        "DHS immigration-fee families are now account-confirmed at the annual family level, "
                        f"but stay nondefault because contamination remains the blocker. "
                        f"Confirmed share: {float(family['combined_statement_confirmed_share_pct']):.1f}%."
                    ),
                }
            )

        traveler = latest_row_family_review.loc[
            latest_row_family_review["candidate_family"].eq("row_dhs_traveler_family")
        ]
        if not traveler.empty:
            family = traveler.iloc[0]
            rows.append(
                {
                    "candidate_name": "row_dhs_traveler_family",
                    "counterparty_group": "row",
                    "basis": "Annual public traveler-program line crosswalked to broader Combined Statement main-account family",
                    "payer_identity_status": "traveler_program_foreign_link_not_actual_cash_payer",
                    "timing_status": "annual_only",
                    "budget_treatment_status": "account_family_confirmed_but_not_cash_payer",
                    "current_role": "row_account_bridge",
                    "latest_reference_date": pd.Timestamp(family["date"]),
                    "promotion_status": "confirmed_traveler_family_nondefault",
                    "latest_value_millions": float(family["family_total_receipt_mil"]),
                    "review_note": (
                        "The traveler-program family is now account-confirmed, but the actual Treasury cash payer is still not identified. "
                        f"Confirmed share: {float(family['combined_statement_confirmed_share_pct']):.1f}%."
                    ),
                }
            )

    if row_state_visa_timing_sensitivity is not None and not row_state_visa_timing_sensitivity.empty:
        latest_val = _latest_nonzero(row_state_visa_timing_sensitivity.get("row_state_visa_allocated_receipt_mil"))
        secondary_val = _latest_nonzero(row_state_visa_timing_sensitivity.get("row_state_visa_secondary_allocated_receipt_mil"))
        mrv_crosswalk_note = ""
        if receipt_account_crosswalk is not None and not receipt_account_crosswalk.empty:
            mrv_crosswalk = receipt_account_crosswalk.loc[
                receipt_account_crosswalk.get("candidate_family", pd.Series(dtype="object")).eq("row_mrv_cbsp_primary")
            ]
            if not mrv_crosswalk.empty:
                latest_crosswalk = mrv_crosswalk.sort_values("date").iloc[-1]
                level = str(latest_crosswalk.get("combined_statement_match_level", "unmatched"))
                if level == "main_account_rollup":
                    mrv_crosswalk_note = " Combined Statement now confirms the broader CBSP main-account family, but not the exact MRV sub-account."
        rows.append(
            {
                "candidate_name": "row_state_mrv_cbsp_bridge",
                "counterparty_group": "row",
                "basis": "Annual MRV / CBSP line allocated with official monthly NIV issuance shares; secondary visa lines tracked separately",
                "payer_identity_status": "narrow_applicant_linkage_but_not_direct_cash_payer_proof",
                "timing_status": "quarterly_niv_share_bridge",
                "budget_treatment_status": "cbsp_receipt_account_review",
                "current_role": "sensitivity",
                "latest_reference_date": (
                    pd.Timestamp(
                        latest_recurring_pilot_review.loc[
                            latest_recurring_pilot_review["branch_name"].eq("mrv_cbsp_primary"),
                            "date",
                        ].iloc[0]
                    )
                    if not latest_recurring_pilot_review.empty
                    and latest_recurring_pilot_review["branch_name"].eq("mrv_cbsp_primary").any()
                    else _latest_nonzero_date(row_state_visa_timing_sensitivity.get("row_state_visa_allocated_receipt_mil"))
                ),
                "promotion_status": "future_row_mrv_default_pilot_under_review",
                "latest_value_millions": latest_val,
                "review_note": (
                    "Best current public recurring ROW pilot. The main bridge is now MRV-first, while secondary visa lines stay outside the main ROW delta until payer identity and cash timing are stronger."
                    + (
                        f" Latest secondary visa sensitivity: {_format_millions(secondary_val)} million."
                        if secondary_val is not None
                        else ""
                    )
                    + mrv_crosswalk_note
                    + mrv_checklist_note
                    + mrv_stop_gate_note
                ),
            }
        )
        if not latest_recurring_pilot_review.empty:
            secondary_branch = latest_recurring_pilot_review.loc[
                latest_recurring_pilot_review["branch_name"].eq("secondary_state_visa")
            ]
            if not secondary_branch.empty:
                branch = secondary_branch.iloc[0]
                rows.append(
                    {
                        "candidate_name": "row_secondary_state_visa_branch",
                        "counterparty_group": "row",
                        "basis": "Annual secondary State visa lines allocated with official monthly IV issuance shares",
                        "payer_identity_status": "secondary_visa_fee_link_not_direct_cash_payer",
                        "timing_status": "quarterly_iv_share_bridge",
                        "budget_treatment_status": "secondary_visa_receipt_account_review",
                        "current_role": "sensitivity",
                        "latest_reference_date": pd.Timestamp(branch["date"]),
                        "promotion_status": "keep_secondary_visa_nondefault",
                        "latest_value_millions": float(branch["latest_quarter_amount_mil"]),
                        "review_note": str(branch["review_note"]),
                    }
                )

    if bea_row_receipts_benchmark is not None and not bea_row_receipts_benchmark.empty:
        latest_val = _latest_nonzero(bea_row_receipts_benchmark.get("bea_row_current_receipts_total_q_mil"))
        rows.append(
            {
                "candidate_name": "bea_row_current_receipts_benchmark",
                "counterparty_group": "row",
                "basis": "BEA/NIPA Table 3.2 ROW current receipts benchmark",
                "payer_identity_status": "economic_counterparty_not_cash_payer",
                "timing_status": "quarterly_saar_benchmark",
                "budget_treatment_status": "benchmark_only",
                "current_role": "benchmark",
                "latest_reference_date": _latest_nonzero_date(bea_row_receipts_benchmark.get("bea_row_current_receipts_total_q_mil")),
                "promotion_status": "never_default_cash_payer_series",
                "latest_value_millions": latest_val,
                "review_note": "Useful for scale checks and coverage ratios, but not for direct default Treasury cash-payer correction.",
            }
        )

    if tier3_receipt_source_diagnostics is not None and not tier3_receipt_source_diagnostics.empty:
        latest_val = _latest_nonzero(tier3_receipt_source_diagnostics.get("rcm_bank_channel_total_candidate"))
        rows.append(
            {
                "candidate_name": "revenue_collections_bank_channel",
                "counterparty_group": "bank",
                "basis": "Treasury Revenue Collections channel totals",
                "payer_identity_status": "routing_channel_not_payer_sector",
                "timing_status": "quarterly_cash_aggregation",
                "budget_treatment_status": "routing_upper_bound_only",
                "current_role": "sensitivity",
                "latest_reference_date": _latest_nonzero_date(tier3_receipt_source_diagnostics.get("rcm_bank_channel_total_candidate")),
                "promotion_status": "rejected_default",
                "latest_value_millions": latest_val,
                "review_note": "Material and visible, but still a routing channel rather than a bank-sector payer series.",
            }
        )

    return pd.DataFrame(rows)


def render_receipt_promotion_review_markdown(review: pd.DataFrame) -> str:
    title = "# Receipt Promotion Review"
    intro = (
        "Explicit promotion-review table for the current receipt-side candidates. "
        "Amounts are in millions where a live latest value exists. This artifact does not change the default estimator. "
        "It records which current candidates are benchmarks, which remain sensitivities, and which are closest to default promotion."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No receipt-side review rows are available."])

    header = [
        "| Candidate | Group | Current role | Promotion status | Latest value (mil) |",
        "| --- | --- | --- | --- | ---: |",
    ]
    rows: list[str] = []
    for _, row in review.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["candidate_name"]),
                    str(row["counterparty_group"]),
                    str(row["current_role"]),
                    str(row["promotion_status"]),
                    _format_millions(row.get("latest_value_millions")),
                ]
            )
            + " |"
        )

    best = review.loc[
        review["promotion_status"].isin(
            ["best_bank_default_candidate_under_review", "best_bank_default_candidate_under_review_but_share_too_stale"]
        )
    ]
    summary = "No candidate is currently flagged as a near-default promotion."
    if not best.empty:
        best_row = best.iloc[0]
        summary = (
            f"Current strongest default-promotion candidate: {best_row['candidate_name']} "
            f"at {_format_millions(best_row.get('latest_value_millions'))} million in its latest quarter."
        )

    notes = [
        "Notes:",
        "- `best_bank_default_candidate_under_review` means strongest current path to the first nonzero default bank receipt correction, not that promotion has already happened.",
        "- `best_bank_default_candidate_under_review_but_share_too_stale` means the candidate remains the best bank-side bridge, but the latest share is already outside the bridge's own age-eligibility rule.",
        "- `future_row_mrv_default_pilot_under_review` means the MRV / CBSP bridge is the leading recurring ROW pilot, not that it is default-ready.",
        "- `rejected_default` and `reject_default_deposit_trust_concept` indicate candidates that should remain outside the default receipt correction even if they are large.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_receipt_promotion_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    bea_row_receipts_benchmark: pd.DataFrame | None = None,
    bank_corp_tax_receipts_bridge: pd.DataFrame | None = None,
    receipt_account_candidates: pd.DataFrame | None = None,
    receipt_account_crosswalk: pd.DataFrame | None = None,
    row_receipt_family_review: pd.DataFrame | None = None,
    row_recurring_pilot_review: pd.DataFrame | None = None,
    row_mrv_promotion_checklist: pd.DataFrame | None = None,
    row_mrv_stop_gate: pd.DataFrame | None = None,
    bank_receipt_stop_gate: pd.DataFrame | None = None,
    bank_occ_timing_sensitivity: pd.DataFrame | None = None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None = None,
    tier3_receipt_source_diagnostics: pd.DataFrame | None = None,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_receipt_promotion_review(
        bea_row_receipts_benchmark=bea_row_receipts_benchmark,
        bank_corp_tax_receipts_bridge=bank_corp_tax_receipts_bridge,
        receipt_account_candidates=receipt_account_candidates,
        receipt_account_crosswalk=receipt_account_crosswalk,
        row_receipt_family_review=row_receipt_family_review,
        row_recurring_pilot_review=row_recurring_pilot_review,
        row_mrv_promotion_checklist=row_mrv_promotion_checklist,
        row_mrv_stop_gate=row_mrv_stop_gate,
        bank_receipt_stop_gate=bank_receipt_stop_gate,
        bank_occ_timing_sensitivity=bank_occ_timing_sensitivity,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        tier3_receipt_source_diagnostics=tier3_receipt_source_diagnostics,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_receipt_promotion_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
