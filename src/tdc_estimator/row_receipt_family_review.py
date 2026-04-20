from __future__ import annotations

from pathlib import Path

import pandas as pd


ROW_FAMILY_REVIEW_COLUMNS = [
    "date",
    "candidate_family",
    "family_total_receipt_mil",
    "combined_statement_confirmed_receipt_mil",
    "combined_statement_confirmed_share_pct",
    "combined_statement_confirmation",
    "largest_line_item_nm",
    "family_identity_status",
    "family_concept_status",
    "family_role",
    "review_decision",
    "default_blocker",
    "review_note",
]


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _family_review_metadata(candidate_family: str, confirmation: str) -> dict[str, str]:
    has_confirmation = confirmation != "unmatched"
    notes = {
        "row_mrv_cbsp_primary": {
            "family_identity_status": "narrow_applicant_link_but_not_direct_cash_payer",
            "family_concept_status": "current_receipt_candidate_under_review",
            "family_role": "primary_row_pilot",
            "review_decision": "keep_as_primary_row_pilot_nondefault",
            "default_blocker": "no_public_legal_remitter_or_debited_account_proof_and_proxy_timing",
            "review_note": (
                "MRV remains the strongest recurring public ROW pilot. "
                + (
                    "Broader CBSP account-family confirmation means the binding blocker is now remitter/debited-account proof rather than annual account mapping."
                    if has_confirmation
                    else "Annual account mapping still needs stronger confirmation."
                )
            ),
        },
        "row_secondary_visa_sensitivity": {
            "family_identity_status": "secondary_visa_fee_link_not_primary_cash_payer_proof",
            "family_concept_status": "current_receipt_sensitivity_only",
            "family_role": "secondary_row_sensitivity",
            "review_decision": "keep_as_secondary_visa_sensitivity",
            "default_blocker": "secondary_visa_line_requires_stronger_payer_and_timing_evidence",
            "review_note": (
                "Secondary State visa lines stay outside the main ROW bridge. "
                + (
                    "Shared CBSP family confirmation improves annual reconciliation but does not overcome the weaker payer and timing case."
                    if has_confirmation
                    else "They still lack stronger account-family and payer evidence."
                )
            ),
        },
        "row_dhs_immigration_family_mixed": {
            "family_identity_status": "mixed_applicant_or_domestic_contamination",
            "family_concept_status": "current_receipt_family_but_contaminated",
            "family_role": "contamination_accounting",
            "review_decision": (
                "confirmed_account_family_but_keep_contaminated_nondefault"
                if has_confirmation
                else "keep_contaminated_nondefault"
            ),
            "default_blocker": "domestic_contamination_risk",
            "review_note": (
                "Homeland Security immigration-fee families now have broader annual account-family confirmation, "
                "which strengthens exclusion logic and contamination accounting rather than promotion."
                if has_confirmation
                else "Mixed immigration lines remain contaminated and nondefault."
            ),
        },
        "row_dhs_traveler_family": {
            "family_identity_status": "traveler_program_foreign_link_not_actual_cash_payer",
            "family_concept_status": "current_receipt_family_but_not_cash_payer_proven",
            "family_role": "row_account_bridge",
            "review_decision": (
                "confirmed_traveler_family_but_not_cash_payer"
                if has_confirmation
                else "traveler_family_title_only_nondefault"
            ),
            "default_blocker": "traveler_program_title_without_actual_cash_payer_proof",
            "review_note": (
                "The traveler-program family is now account-confirmed, but that still does not identify the actual Treasury cash payer."
                if has_confirmation
                else "Traveler-program lines remain title-level only and nondefault."
            ),
        },
        "row_mixed_immigration_domestic_sponsor_sensitive": {
            "family_identity_status": "domestic_sponsor_or_employer_risk",
            "family_concept_status": "current_receipt_family_but_sponsor_sensitive",
            "family_role": "contamination_accounting",
            "review_decision": (
                "partly_confirmed_but_keep_sponsor_sensitive_nondefault"
                if has_confirmation
                else "keep_sponsor_sensitive_nondefault"
            ),
            "default_blocker": "domestic_sponsor_or_employer_contamination",
            "review_note": (
                "Sponsor-sensitive lines remain below default even when some account families are now confirmed. "
                "The problem is who actually pays, not whether the title belongs to a real receipt family."
            ),
        },
        "row_passport_domestic_contamination": {
            "family_identity_status": "mixed_or_domestic_payer_exposure",
            "family_concept_status": "current_receipt_family_but_broadly_contaminated",
            "family_role": "excluded_contamination_bucket",
            "review_decision": "keep_excluded_domestic_contamination",
            "default_blocker": "broad_consular_or_passport_contamination",
            "review_note": (
                "Passport and broad-consular lines remain explicit contamination buckets. "
                "Broader CBSP confirmation does not change their domestic-payer exposure."
            ),
        },
        "row_fms_deposit_trust_family": {
            "family_identity_status": "foreign_counterparty_linkage_not_current_receipt_identity",
            "family_concept_status": "deposit_or_trust_nondefault",
            "family_role": "separate_deposit_trust_sensitivity",
            "review_decision": (
                "confirmed_deposit_trust_nondefault"
                if has_confirmation
                else "keep_deposit_trust_nondefault"
            ),
            "default_blocker": "deposit_or_trust_concept_not_current_receipt_default",
            "review_note": (
                "The main FMS advance family is now account-confirmed, which sharpens concept classification. "
                "It remains outside any default ROW current-receipt correction because it is a deposit/trust-style flow."
                if has_confirmation
                else "FMS-style foreign-program lines remain separate deposit/trust sensitivities."
            ),
        },
        "row_foreign_title_bridge": {
            "family_identity_status": "foreign_title_or_program_link_without_actual_cash_payer",
            "family_concept_status": "mixed_foreign_bridge_family",
            "family_role": "row_account_bridge",
            "review_decision": (
                "partial_account_family_confirmation_but_not_cash_payer"
                if has_confirmation
                else "title_only_bridge_nondefault"
            ),
            "default_blocker": "title_level_foreign_link_without_actual_payer_proof",
            "review_note": (
                "Some foreign-title bridge lines are now account-confirmed, especially traveler and foreign-government advance families, "
                "but the family still mixes lines that are unmatched or conceptually unsuitable for a default ROW cash-payer correction."
                if has_confirmation
                else "Foreign-title bridge lines remain title-level only and nondefault."
            ),
        },
    }
    return notes.get(
        candidate_family,
        {
            "family_identity_status": "unclassified",
            "family_concept_status": "review_required",
            "family_role": "review_only",
            "review_decision": "review_required",
            "default_blocker": "unclassified_family",
            "review_note": "Family requires manual review.",
        },
    )


def _combined_statement_confirmation(family: pd.DataFrame) -> tuple[str, float, float]:
    total = float(pd.to_numeric(family["receipt_amt_mil"], errors="coerce").fillna(0.0).sum())
    confirmed = family.loc[
        family.get("combined_statement_match_level", pd.Series(dtype="object")).isin(["exact_account", "main_account_rollup"])
    ].copy()
    confirmed_amt = float(pd.to_numeric(confirmed.get("receipt_amt_mil", pd.Series(dtype="float64")), errors="coerce").fillna(0.0).sum())
    share = 0.0 if total == 0 else confirmed_amt / total
    levels = set(confirmed.get("combined_statement_match_level", pd.Series(dtype="object")).dropna().astype(str))
    if confirmed.empty:
        return "unmatched", confirmed_amt, share
    if share >= 0.999 and levels == {"exact_account"}:
        return "exact_account", confirmed_amt, share
    if share >= 0.999:
        return "full_main_account_rollup", confirmed_amt, share
    return "partial_main_account_rollup", confirmed_amt, share


def build_row_receipt_family_review(
    *,
    receipt_account_candidates: pd.DataFrame | None,
    receipt_account_crosswalk: pd.DataFrame | None,
) -> pd.DataFrame:
    if receipt_account_candidates is None or receipt_account_candidates.empty:
        return pd.DataFrame(columns=ROW_FAMILY_REVIEW_COLUMNS)

    candidates = receipt_account_candidates.copy()
    candidates["date"] = pd.to_datetime(candidates["date"])
    candidates = candidates.loc[candidates["counterparty_group"].eq("row")].copy()
    if candidates.empty:
        return pd.DataFrame(columns=ROW_FAMILY_REVIEW_COLUMNS)

    latest_date = pd.Timestamp(candidates["date"].max())
    latest = candidates.loc[candidates["date"].eq(latest_date)].copy()

    if receipt_account_crosswalk is not None and not receipt_account_crosswalk.empty:
        crosswalk = receipt_account_crosswalk.copy()
        crosswalk["date"] = pd.to_datetime(crosswalk["date"])
        crosswalk = crosswalk.loc[crosswalk["date"].eq(latest_date)].copy()
        keep_cols = [
            "date",
            "receipt_line_item_nm",
            "candidate_family",
            "combined_statement_title",
            "combined_statement_match_level",
            "match_status",
        ]
        latest = latest.merge(
            crosswalk.loc[:, [col for col in keep_cols if col in crosswalk.columns]],
            on=["date", "receipt_line_item_nm", "candidate_family"],
            how="left",
        )
    else:
        latest["combined_statement_title"] = pd.NA
        latest["combined_statement_match_level"] = pd.NA
        latest["match_status"] = pd.NA

    rows: list[dict[str, object]] = []
    for candidate_family, family in latest.groupby("candidate_family", dropna=False):
        family = family.sort_values("receipt_amt_mil", ascending=False).reset_index(drop=True)
        largest = family.iloc[0]
        confirmation, confirmed_amt, confirmed_share = _combined_statement_confirmation(family)
        meta = _family_review_metadata(str(candidate_family), confirmation)
        rows.append(
            {
                "date": latest_date,
                "candidate_family": candidate_family,
                "family_total_receipt_mil": float(pd.to_numeric(family["receipt_amt_mil"], errors="coerce").fillna(0.0).sum()),
                "combined_statement_confirmed_receipt_mil": confirmed_amt,
                "combined_statement_confirmed_share_pct": confirmed_share * 100.0,
                "combined_statement_confirmation": confirmation,
                "largest_line_item_nm": largest["receipt_line_item_nm"],
                **meta,
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(["family_role", "family_total_receipt_mil"], ascending=[True, False]).reset_index(drop=True)
    return out.reindex(columns=ROW_FAMILY_REVIEW_COLUMNS)


def render_row_receipt_family_review_markdown(review: pd.DataFrame) -> str:
    title = "# ROW Receipt Family Review"
    intro = (
        "Family-level review of current ROW receipt candidates using the annual `Receipts by Department` bridge plus the live `Combined Statement` crosswalk. "
        "This artifact distinguishes primary pilots, contaminated current-receipt families, deposit/trust concepts, and title-only bridges."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No ROW receipt-family review rows are available."])

    latest_date = pd.Timestamp(review["date"].max())
    latest = review.loc[review["date"].eq(latest_date)].copy()
    summary = (
        f"Latest fiscal year-end in view: {latest_date.date().isoformat()}. "
        f"Families reviewed: {len(latest)}. "
        f"Families with at least partial Combined Statement confirmation: {int(latest['combined_statement_confirmation'].ne('unmatched').sum())}."
    )
    header = [
        "| Family | Total receipt (mil) | Confirmed by Combined Statement (mil) | Confirmed share | Confirmation | Decision |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in latest.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["candidate_family"]),
                    _format_millions(row["family_total_receipt_mil"]),
                    _format_millions(row["combined_statement_confirmed_receipt_mil"]),
                    f"{float(row['combined_statement_confirmed_share_pct']):.1f}%",
                    str(row["combined_statement_confirmation"]),
                    str(row["review_decision"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `row_mrv_cbsp_primary` remains the main recurring pilot; its blocker is now remitter/debited-account proof, not annual account-family confirmation.",
        "- Confirmed DHS immigration and traveler families improve exclusion logic and contaminated-family accounting, not default promotion.",
        "- Confirmed FMS advance lines improve concept classification and keep deposit/trust flows explicitly outside current-receipt default treatment.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_row_receipt_family_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    receipt_account_candidates: pd.DataFrame | None,
    receipt_account_crosswalk: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_row_receipt_family_review(
        receipt_account_candidates=receipt_account_candidates,
        receipt_account_crosswalk=receipt_account_crosswalk,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_receipt_family_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
