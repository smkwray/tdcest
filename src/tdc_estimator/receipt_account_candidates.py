from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .io import load_treasury_table


@dataclass(frozen=True)
class ReceiptCandidateRule:
    counterparty_group: str
    pattern: str
    payer_grade: str
    recommended_role: str
    candidate_reason: str
    default_eligible: bool = False


RECEIPT_ACCOUNT_CANDIDATE_RULES: list[ReceiptCandidateRule] = [
    ReceiptCandidateRule(
        counterparty_group="row",
        pattern=r"machine readable visa fee|immigrant visa security surcharge|diversity visa lottery fee",
        payer_grade="B_narrow_foreign_fee_candidate",
        recommended_role="future_row_pilot",
        candidate_reason=(
            "Narrow visa or consular fee line with a stronger foreign-applicant link than broad immigration accounts, "
            "but this annual account table still does not verify the actual cash payer or debited-account residency."
        ),
    ),
    ReceiptCandidateRule(
        counterparty_group="row",
        pattern=r"immigration examinations fee account|immigration user fees|temporary h-1b visa|temporary l-1 visa|j1 visa waiver|affidavit of support fee",
        payer_grade="C_mixed_immigration",
        recommended_role="row_bridge_mixed",
        candidate_reason=(
            "Foreign-related immigration or visa-fee line with material domestic-sponsor, domestic-employer, or domestic-applicant contamination risk."
        ),
    ),
    ReceiptCandidateRule(
        counterparty_group="row",
        pattern=r"passport|western hemisphere travel initiative|immigration, passport, and consular fees",
        payer_grade="D_domestic_contamination",
        recommended_role="reject_default_mixed_domestic",
        candidate_reason=(
            "Broad passport or mixed immigration/passport/consular title. Useful for contamination diagnostics, but too mixed for a ROW default."
        ),
    ),
    ReceiptCandidateRule(
        counterparty_group="row",
        pattern=r"foreign military sales|foreign military financing",
        payer_grade="E_deposit_or_trust_concept",
        recommended_role="separate_row_deposit_trust_sensitivity",
        candidate_reason=(
            "Foreign-government or security-linked cash line that is real and material, but conceptually closer to a separate deposit/trust sensitivity than a clean current-receipt default."
        ),
    ),
    ReceiptCandidateRule(
        counterparty_group="row",
        pattern=r"international registered traveler|international monetary fund|international organization|foreign government",
        payer_grade="C_foreign_related_title_only",
        recommended_role="row_account_bridge",
        candidate_reason=(
            "Foreign or international account title. Useful as a candidate bridge, but title-level annual data do not establish the actual payer account."
        ),
    ),
    ReceiptCandidateRule(
        counterparty_group="bank",
        pattern=r"office of the comptroller of currency|comptroller of currency",
        payer_grade="B_bank_regulatory_specific",
        recommended_role="bank_nontax_sensitivity",
        candidate_reason=(
            "Bank-regulatory-specific Treasury receipt line. Strong bank-sector linkage, but still annual account-based evidence rather than a quarterly cash counterparty series."
        ),
    ),
    ReceiptCandidateRule(
        counterparty_group="bank",
        pattern=r"financial research fund",
        payer_grade="C_large_bhc_specific",
        recommended_role="large_bhc_assessment_sensitivity",
        candidate_reason=(
            "Financial Research Fund assessment line. Useful for large-BHC sensitivity work, but not broad bank-sector cash-payer coverage."
        ),
    ),
    ReceiptCandidateRule(
        counterparty_group="bank",
        pattern=r"federal deposit insurance corporation|fdic",
        payer_grade="C_bank_regulatory_mixed",
        recommended_role="bank_regulatory_penalty_sensitivity",
        candidate_reason=(
            "Bank-regulatory or resolution-linked line with plausible depository linkage, but still mixed and annual at the public account-title level."
        ),
    ),
]


FASTBOOK_GENERAL_MISC_MAJOR_CLASS_LABELS: dict[int, str] = {
    100: "taxes",
    300: "customs_duties",
    400: "gains_resulting_from_government_participation",
    600: "receipts_from_monetary_power",
    800: "fees_for_regulatory_and_judicial_services",
    1000: "fines_penalties_and_forfeitures",
    1400: "interest",
    3200: "general_fund_proprietary_receipts_not_otherwise_classified",
    3800: "budget_clearing_and_suspense",
}


def _load_receipts_by_department(path: Path | str) -> pd.DataFrame:
    df = load_treasury_table(path).copy()
    required = {
        "record_date",
        "receipt_line_item_nm",
        "aid_cd",
        "a_cd",
        "main_cd",
        "sub_cd",
        "receipt_amt",
        "record_fiscal_year",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Receipts by Department file {path} is missing required columns: {missing}")

    out = df.loc[:, sorted(required | {"src_line_nbr"})].copy() if "src_line_nbr" in df.columns else df.loc[:, sorted(required)].copy()
    out = out.drop_duplicates().copy()
    out["record_date"] = pd.to_datetime(out["record_date"])
    out["receipt_line_item_nm"] = out["receipt_line_item_nm"].fillna("").astype(str).str.strip()
    for col in ["aid_cd", "a_cd", "main_cd", "sub_cd"]:
        out[col] = out[col].fillna("").astype(str).replace({"null": ""}).str.strip()
    out["record_fiscal_year"] = pd.to_numeric(out["record_fiscal_year"], errors="coerce").astype("Int64")
    out["receipt_amt"] = pd.to_numeric(out["receipt_amt"], errors="coerce").fillna(0.0)
    return out


def _match_rule(title: str) -> ReceiptCandidateRule | None:
    for rule in RECEIPT_ACCOUNT_CANDIDATE_RULES:
        if pd.notna(title) and pd.Series([title]).str.contains(rule.pattern, case=False, regex=True, na=False).iloc[0]:
            return rule
    return None


def _availability_type_class(a_cd: str) -> str:
    a_cd = (a_cd or "").strip().upper()
    mapping = {
        "": "blank_or_unavailable_receipt",
        "X": "no_year_account",
        "F": "clearing_or_suspense_account",
        "A": "central_summary_account",
    }
    return mapping.get(a_cd, f"other_availability_type_{a_cd.lower()}")


def _main_account_int(main_cd: str) -> int | None:
    try:
        return int(str(main_cd).strip())
    except Exception:
        return None


def _fastbook_general_major_class_code(main_cd: str, a_cd: str) -> int | None:
    main = _main_account_int(main_cd)
    if main is None:
        return None
    if (a_cd or "").strip().upper() != "":
        return None
    if not (612 <= main <= 3885):
        return None
    return (main // 100) * 100


def _fastbook_general_major_class_label(main_cd: str, a_cd: str) -> str | None:
    code = _fastbook_general_major_class_code(main_cd, a_cd)
    if code is None:
        return None
    return FASTBOOK_GENERAL_MISC_MAJOR_CLASS_LABELS.get(code)


def _fastbook_fund_group_proxy(title: str, a_cd: str, main_cd: str) -> str:
    a_cd = (a_cd or "").strip().upper()
    title_l = (title or "").lower()
    main = _main_account_int(main_cd)
    if a_cd == "F":
        return "clearing_or_suspense"
    if a_cd == "A":
        return "central_summary"
    if a_cd == "X":
        if "trust" in title_l:
            return "trust_fund_no_year"
        if "deposit" in title_l or "advances" in title_l:
            return "deposit_or_advance_no_year"
        return "special_or_trust_like_no_year"
    if main is not None and 612 <= main <= 3885:
        return "general_fund_misc_receipt"
    return "unavailable_or_other_receipt_account"


def _budget_treatment_guess(title: str, a_cd: str, main_cd: str) -> str:
    title_l = (title or "").lower()
    a_cd = (a_cd or "").strip().upper()
    main = _main_account_int(main_cd)
    major_class = _fastbook_general_major_class_code(main_cd, a_cd)

    if a_cd == "F" or major_class == 3800:
        return "clearing_or_suspense_nondefault"
    if "foreign military sales" in title_l or ("deposit" in title_l and "advances" in title_l):
        return "deposit_or_trust_nondefault"
    if "trust fund" in title_l or "trust account" in title_l or "gift fund" in title_l:
        return "trust_fund_or_deposit_review"
    if a_cd == "X":
        return "no_year_receipt_account_review"
    if main is None:
        return "unknown_account_treatment"
    if major_class == 100:
        return "general_fund_tax_receipt"
    if major_class == 300:
        return "general_fund_customs_receipt"
    if major_class == 600:
        return "general_fund_monetary_power_receipt"
    if major_class == 800:
        return "general_fund_fee_receipt"
    if major_class == 1000:
        return "general_fund_fine_penalty_receipt"
    if major_class == 1400:
        return "general_fund_interest_receipt"
    if main in {3200, 3220, 3041}:
        return "general_fund_proprietary_or_recovery_receipt_review"
    return "general_fund_misc_receipt_review"


def _candidate_family(title: str, rule: ReceiptCandidateRule) -> str:
    title_l = (title or "").lower()
    if rule.counterparty_group == "row":
        if "machine readable visa fee" in title_l:
            return "row_mrv_cbsp_primary"
        if "immigrant visa security surcharge" in title_l or "diversity visa lottery fee" in title_l:
            return "row_secondary_visa_sensitivity"
        if "immigration examinations fee account" in title_l or "immigration user fees" in title_l:
            return "row_dhs_immigration_family_mixed"
        if any(token in title_l for token in ["temporary h-1b visa", "temporary l-1 visa", "j1 visa waiver", "affidavit of support fee"]):
            return "row_mixed_immigration_domestic_sponsor_sensitive"
        if "passport" in title_l or "western hemisphere travel initiative" in title_l:
            return "row_passport_domestic_contamination"
        if "foreign military sales" in title_l or "foreign military financing" in title_l:
            return "row_fms_deposit_trust_family"
        if "international registered traveler" in title_l:
            return "row_dhs_traveler_family"
        return "row_foreign_title_bridge"

    if "comptroller of currency" in title_l:
        return "bank_regulatory_specific_occ"
    if "financial research fund" in title_l:
        return "bank_large_bhc_specific_ofr"
    if "fdic" in title_l or "federal deposit insurance corporation" in title_l:
        return "bank_regulatory_mixed_fdic"
    return "bank_regulatory_other"


def _promotion_priority(candidate_family: str, budget_treatment_guess: str) -> str:
    if candidate_family in {"row_mrv_cbsp_primary", "bank_regulatory_specific_occ"}:
        return "high_priority_sensitivity"
    if candidate_family in {
        "row_secondary_visa_sensitivity",
        "row_dhs_traveler_family",
        "bank_large_bhc_specific_ofr",
        "row_foreign_title_bridge",
        "bank_regulatory_mixed_fdic",
    }:
        return "medium_priority_sensitivity"
    if budget_treatment_guess == "deposit_or_trust_nondefault":
        return "conceptual_nondefault"
    if candidate_family == "row_dhs_immigration_family_mixed":
        return "low_priority_contaminated"
    if "domestic_contamination" in candidate_family or "sponsor_sensitive" in candidate_family:
        return "low_priority_contaminated"
    return "review_only"


def _payer_identity_subgrade(candidate_family: str) -> str:
    mapping = {
        "row_mrv_cbsp_primary": "row_applicant_fee_link",
        "row_secondary_visa_sensitivity": "row_secondary_visa_fee_link",
        "row_dhs_immigration_family_mixed": "row_dhs_fee_family_with_domestic_contamination",
        "row_mixed_immigration_domestic_sponsor_sensitive": "row_domestic_sponsor_or_employer_risk",
        "row_passport_domestic_contamination": "domestic_passport_or_broad_consular_risk",
        "row_fms_deposit_trust_family": "foreign_program_counterparty_but_not_current_receipt",
        "row_dhs_traveler_family": "traveler_program_foreign_link_not_actual_cash_payer",
        "row_foreign_title_bridge": "foreign_title_only_not_cash_payer",
        "bank_regulatory_specific_occ": "bank_regulator_specific_depository_link",
        "bank_large_bhc_specific_ofr": "large_bhc_assessment_link",
        "bank_regulatory_mixed_fdic": "bank_regulatory_or_resolution_mixed",
        "bank_regulatory_other": "bank_title_only_mixed_regulatory",
    }
    return mapping.get(candidate_family, "unclassified_title_signal")


def _default_blocker(
    *,
    candidate_family: str,
    budget_treatment_guess: str,
    recommended_role: str,
) -> str:
    if budget_treatment_guess == "deposit_or_trust_nondefault":
        return "deposit_or_trust_concept_not_current_receipt"
    if candidate_family == "row_mrv_cbsp_primary":
        return "needs_cash_payer_and_debited_account_evidence"
    if candidate_family == "row_secondary_visa_sensitivity":
        return "secondary_visa_line_not_primary_recurring_row_candidate"
    if candidate_family == "row_dhs_immigration_family_mixed":
        return "dhs_fee_family_with_domestic_contamination_risk"
    if candidate_family == "row_dhs_traveler_family":
        return "traveler_program_title_without_actual_cash_payer_proof"
    if "domestic_contamination" in candidate_family or "sponsor_sensitive" in candidate_family:
        return "domestic_contamination_risk"
    if candidate_family == "row_foreign_title_bridge":
        return "title_level_foreign_link_without_actual_payer_proof"
    if candidate_family == "bank_large_bhc_specific_ofr":
        return "large_bhc_specific_not_broad_bank_coverage"
    if candidate_family in {"bank_regulatory_specific_occ", "bank_regulatory_mixed_fdic", "bank_regulatory_other"}:
        return "annual_account_title_only_not_quarterly_cash_counterparty"
    if recommended_role.startswith("reject_default"):
        return "mixed_or_rejected_account_title"
    return "annual_account_title_only_requires_manual_review"


def build_receipt_account_candidates(
    receipts_by_department_path: Path | str,
    *,
    start_fiscal_year: int = 2022,
) -> pd.DataFrame:
    receipts = _load_receipts_by_department(receipts_by_department_path)
    rows: list[dict[str, object]] = []

    for _, row in receipts.iterrows():
        rule = _match_rule(str(row["receipt_line_item_nm"]))
        if rule is None:
            continue
        candidate_family = _candidate_family(str(row["receipt_line_item_nm"]), rule)
        budget_treatment_guess = _budget_treatment_guess(
            str(row["receipt_line_item_nm"]),
            str(row["a_cd"]),
            str(row["main_cd"]),
        )
        rows.append(
            {
                "date": pd.Timestamp(row["record_date"]),
                "fiscal_year": int(row["record_fiscal_year"]) if pd.notna(row["record_fiscal_year"]) else None,
                "counterparty_group": rule.counterparty_group,
                "receipt_line_item_nm": str(row["receipt_line_item_nm"]),
                "aid_cd": str(row["aid_cd"]),
                "a_cd": str(row["a_cd"]),
                "main_cd": str(row["main_cd"]),
                "sub_cd": str(row["sub_cd"]),
                "receipt_amt_mil": float(row["receipt_amt"]) / 1_000_000.0,
                "availability_type_class": _availability_type_class(str(row["a_cd"])),
                "fastbook_fund_group_proxy": _fastbook_fund_group_proxy(
                    str(row["receipt_line_item_nm"]),
                    str(row["a_cd"]),
                    str(row["main_cd"]),
                ),
                "fastbook_general_major_class_code": _fastbook_general_major_class_code(
                    str(row["main_cd"]),
                    str(row["a_cd"]),
                ),
                "fastbook_general_major_class_label": _fastbook_general_major_class_label(
                    str(row["main_cd"]),
                    str(row["a_cd"]),
                ),
                "budget_treatment_guess": budget_treatment_guess,
                "payer_grade": rule.payer_grade,
                "candidate_family": candidate_family,
                "promotion_priority": _promotion_priority(candidate_family, budget_treatment_guess),
                "payer_identity_subgrade": _payer_identity_subgrade(candidate_family),
                "default_blocker": _default_blocker(
                    candidate_family=candidate_family,
                    budget_treatment_guess=budget_treatment_guess,
                    recommended_role=rule.recommended_role,
                ),
                "recommended_role": rule.recommended_role,
                "default_eligible": bool(rule.default_eligible),
                "candidate_reason": rule.candidate_reason,
                "source_family": "receipts_by_department",
                "source_basis": "annual_account_symbol_dollars_plus_fastbook_overlay",
                "review_status": "needs_manual_review",
            }
        )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    group_cols = [
        "date",
        "fiscal_year",
        "counterparty_group",
        "receipt_line_item_nm",
        "aid_cd",
        "a_cd",
        "main_cd",
        "sub_cd",
        "availability_type_class",
        "fastbook_fund_group_proxy",
        "fastbook_general_major_class_code",
        "fastbook_general_major_class_label",
        "budget_treatment_guess",
        "payer_grade",
        "candidate_family",
        "promotion_priority",
        "payer_identity_subgrade",
        "default_blocker",
        "recommended_role",
        "default_eligible",
        "candidate_reason",
        "source_family",
        "source_basis",
        "review_status",
    ]
    out = (
        out.groupby(group_cols, dropna=False, as_index=False)["receipt_amt_mil"]
        .sum()
        .sort_values(["date", "counterparty_group", "receipt_amt_mil", "receipt_line_item_nm"], ascending=[False, True, False, True])
        .reset_index(drop=True)
    )
    return out.loc[out["fiscal_year"].ge(start_fiscal_year)].reset_index(drop=True)


def _render_group_table(candidates: pd.DataFrame, *, counterparty_group: str) -> list[str]:
    sub = candidates.loc[candidates["counterparty_group"].eq(counterparty_group)].copy()
    if sub.empty:
        label = "Bank" if counterparty_group == "bank" else "ROW"
        return [f"No {label.lower()} account-title candidates matched the current rules."]

    latest_year = int(sub["fiscal_year"].max())
    latest = sub.loc[sub["fiscal_year"].eq(latest_year)].copy()
    latest = latest.sort_values("receipt_amt_mil", ascending=False).head(12)
    label = "Bank" if counterparty_group == "bank" else "ROW"
    header = [
        f"## {label} Candidates",
        "",
        f"Latest fiscal year in view: {latest_year}.",
        "",
        "| Fiscal year-end | Receipt line item | Amount (mil) | Grade | Recommended role | Treatment guess | FAST proxy | Default eligible | Account code |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    rows = []
    for _, row in latest.iterrows():
        account_code = "-".join(
            [
                str(row["aid_cd"]) or "na",
                str(row["a_cd"]) or "na",
                str(row["main_cd"]) or "na",
                str(row["sub_cd"]) or "na",
            ]
        )
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    str(row["receipt_line_item_nm"]),
                    f"{float(row['receipt_amt_mil']):,.3f}",
                    str(row["payer_grade"]),
                    str(row["recommended_role"]),
                    str(row["budget_treatment_guess"]),
                    str(row["fastbook_fund_group_proxy"]),
                    "yes" if bool(row["default_eligible"]) else "no",
                    account_code,
                ]
            )
            + " |"
        )
    return [*header, *rows]


def render_receipt_account_candidates_markdown(candidates: pd.DataFrame) -> str:
    title = "# Receipt Account Candidate Bridge"
    intro = (
        "Annual account-title candidate bridge from Treasury `Receipts by Department`. "
        "Amounts are converted from raw annual dollars to millions. This artifact is for account-symbol reconnaissance only: "
        "it does not establish payer identity, quarter timing, or default Tier 3 eligibility by itself."
    )
    if candidates.empty:
        return "\n".join([title, "", intro, "", "No candidate account titles matched the current bank or ROW scanning rules."])

    latest_date = pd.Timestamp(candidates["date"].max())
    latest = candidates.loc[candidates["date"].eq(latest_date)].copy()
    latest_bank = latest.loc[latest["counterparty_group"].eq("bank"), "receipt_amt_mil"].sum()
    latest_row = latest.loc[latest["counterparty_group"].eq("row"), "receipt_amt_mil"].sum()
    summary = (
        f"Latest fiscal year-end in view: {latest_date.date().isoformat()}. "
        f"Bank-account candidates in that year sum to {latest_bank:,.3f} million across "
        f"{int(latest['counterparty_group'].eq('bank').sum())} rows; "
        f"ROW-account candidates sum to {latest_row:,.3f} million across "
        f"{int(latest['counterparty_group'].eq('row').sum())} rows."
    )

    notes = [
        "Notes:",
        "- `Receipts by Department` is an annual account-title surface. It is useful for candidate discovery, but it does not prove who actually paid Treasury or which account was debited.",
        "- The bridge now carries a public FAST Book / CARS overlay: availability type, general-fund major-class logic where applicable, and a first budget-treatment guess.",
        "- `default_eligible` stays `false` for this first public bridge because title-level annual evidence is still weaker than the project's strict deposit-account identity.",
        "- The strongest current public uses are: bank non-tax reconnaissance through OCC/OFR-style lines, and ROW reconnaissance through narrow visa/consular lines plus separate foreign-military-sales deposit/trust sensitivities.",
    ]

    return "\n".join(
        [
            title,
            "",
            intro,
            "",
            summary,
            "",
            *_render_group_table(candidates, counterparty_group="bank"),
            "",
            *_render_group_table(candidates, counterparty_group="row"),
            "",
            *notes,
            "",
        ]
    )


def write_receipt_account_candidates(
    *,
    receipts_by_department_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start_fiscal_year: int = 2022,
) -> tuple[Path, Path, pd.DataFrame]:
    candidates = build_receipt_account_candidates(
        receipts_by_department_path=receipts_by_department_path,
        start_fiscal_year=start_fiscal_year,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_receipt_account_candidates_markdown(candidates), encoding="utf-8")

    return csv_path, markdown_path, candidates
