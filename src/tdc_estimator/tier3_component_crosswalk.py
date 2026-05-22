from __future__ import annotations

from pathlib import Path

import pandas as pd

from .tier3_source import (
    BANK_OUTLAY_LABELS,
    AGENCY_ROW_OUTLAY_COMPONENT_KEYS,
    CORE_INSTITUTIONAL_ROW_OUTLAY_COMPONENT_KEYS,
    DEFAULT_ROW_OUTLAY_COMPONENT_KEYS,
    HUMANITARIAN_ROW_OUTLAY_COMPONENT_KEYS,
    MINT_LABELS,
    ROW_OUTLAY_COMPONENT_LABELS,
    SECURITY_ROW_OUTLAY_COMPONENT_KEYS,
)


DATA_SOURCE_TIERS = {
    "A_fiscaldata_api": "Current machine-readable FiscalData/current source",
    "B_treasury_excel_previous_issue": "Treasury previous-issue Excel",
    "C_treasury_ascii_previous_issue": "Treasury previous-issue ASCII",
    "D_pdf_text_parsed": "PDF text extraction from Treasury previous issue",
    "E_official_annual_or_saar_benchmark": "BEA / IRS / State annual or SAAR benchmark",
    "F_interpolated_backcast": "Interpolated or fixed-share backcast",
    "Z_missing_or_zero_default": "Placeholder / default zero",
}
PAYER_IDENTITY_GRADES = {
    "A_direct_cash_payer": "Direct payer-sector cash record",
    "B_program_counterparty_strong": "Program line strongly associated with sector / counterparty",
    "C_sector_share_bridge": "Cash total allocated by official annual sector share",
    "D_macro_economic_counterparty": "BEA / NIPA / ITA economic-accounting benchmark",
    "E_routing_channel_rejected": "Payment channel only; not acceptable as payer identity",
}
CASH_BASIS_GRADES = {
    "A_mts_modified_cash": "Direct MTS cash receipt / outlay",
    "B_mts_net_outlay": "MTS net outlay after offsetting collections",
    "C_cash_total_with_accrual_share": "Cash total allocated by annual tax / statistical share",
    "D_nipa_saar_accrual": "NIPA / SAAR benchmark",
    "E_activity_timing_proxy": "Annual cash / control allocated by activity timing",
    "Z_not_applicable": "Not applicable to this crosswalk row",
}

METHOD_ENUMS = {
    "direct_mts_leaf",
    "stitched_mts_leaf",
    "parent_share_backcast",
    "family_share_backcast",
    "bea_noninterest_fallback_ratio",
    "irs_pub16_sector_share",
    "bea_row_anchor",
    "mrv_cbsp_timing_overlay",
    "zero_default_placeholder",
}
QUALITY_CODES = {"default_eligible", "research_only", "sensitivity_only", "manual_qa_required", "blocked_default"}


def _labels_for(keys: list[str]) -> list[str]:
    return [ROW_OUTLAY_COMPONENT_LABELS[key] for key in keys]


def build_tier3_component_crosswalk() -> pd.DataFrame:
    rows = [
        {
            "component_key": "outlay_banks",
            "component_family": "outlay",
            "component_role": "subtract_from_tier2",
            "method": "stitched_mts_leaf",
            "data_source_tier": "A_fiscaldata_api|D_pdf_text_parsed",
            "label_paths": "|".join(BANK_OUTLAY_LABELS),
            "payer_identity_grade": "B_program_counterparty_strong",
            "cash_basis_grade": "B_mts_net_outlay",
            "quality_code": "manual_qa_required",
            "default_surface": "tier3_extended_research",
            "structural_break_flags": "2015_03_fiscaldata_cutover|2012_10_bfs_reorganization|2003_2004_fas_manual_qa",
            "fragility_rank": 5,
            "fragility_note": "Direct FAS leaf is usable when present; 2003-2004 archived layouts need explicit manual QA before preferred historical use.",
        },
        {
            "component_key": "outlay_banks_parent_share_fallback",
            "component_family": "outlay",
            "component_role": "subtract_from_tier2_sensitivity",
            "method": "parent_share_backcast",
            "data_source_tier": "F_interpolated_backcast",
            "label_paths": "Financial Management Service / Bureau of the Fiscal Service parent family",
            "payer_identity_grade": "C_sector_share_bridge",
            "cash_basis_grade": "B_mts_net_outlay",
            "quality_code": "manual_qa_required",
            "default_surface": "sensitivity_only",
            "structural_break_flags": "2003_2004_fas_manual_qa|2012_10_bfs_reorganization",
            "fragility_rank": 5,
            "fragility_note": "Fallback only for pre-stable-FAS months; never let this silently replace direct parsed FAS cells.",
        },
        {
            "component_key": "outlay_row_core_institutional",
            "component_family": "outlay",
            "component_role": "subtract_from_tier2_strict_row_proxy",
            "method": "stitched_mts_leaf",
            "data_source_tier": "A_fiscaldata_api|D_pdf_text_parsed",
            "label_paths": "|".join(_labels_for(CORE_INSTITUTIONAL_ROW_OUTLAY_COMPONENT_KEYS)),
            "payer_identity_grade": "B_program_counterparty_strong",
            "cash_basis_grade": "B_mts_net_outlay",
            "quality_code": "research_only",
            "default_surface": "strict_row_institutional_research",
            "structural_break_flags": "2015_03_fiscaldata_cutover|2003_2005_row_label_drift",
            "fragility_rank": 4,
            "fragility_note": "Strictest currently implemented ROW outlay subset: multilateral/institutional lines with the clearest counterparty fit.",
        },
        {
            "component_key": "outlay_row_narrow",
            "component_family": "outlay",
            "component_role": "subtract_from_tier2",
            "method": "stitched_mts_leaf",
            "data_source_tier": "A_fiscaldata_api|D_pdf_text_parsed",
            "label_paths": "|".join(_labels_for(DEFAULT_ROW_OUTLAY_COMPONENT_KEYS)),
            "payer_identity_grade": "B_program_counterparty_strong",
            "cash_basis_grade": "B_mts_net_outlay",
            "quality_code": "research_only",
            "default_surface": "tier3_partial_shell_diagnostic_current_window_only",
            "structural_break_flags": "2015_03_fiscaldata_cutover|2003_2005_row_label_drift",
            "fragility_rank": 4,
            "fragility_note": "Narrow selected foreign/international leaves remain a proxy; Foreign Agricultural Service and disaster lines are weaker counterparty evidence than core institutional rows.",
        },
        {
            "component_key": "outlay_row_humanitarian_addon",
            "component_family": "outlay",
            "component_role": "subtract_from_tier2_sensitivity",
            "method": "stitched_mts_leaf",
            "data_source_tier": "A_fiscaldata_api|D_pdf_text_parsed",
            "label_paths": "|".join(_labels_for(HUMANITARIAN_ROW_OUTLAY_COMPONENT_KEYS)),
            "payer_identity_grade": "B_program_counterparty_strong",
            "cash_basis_grade": "B_mts_net_outlay",
            "quality_code": "sensitivity_only",
            "default_surface": "row_humanitarian_addon_sensitivity",
            "structural_break_flags": "2015_03_fiscaldata_cutover|2003_2005_row_label_drift",
            "fragility_rank": 4,
            "fragility_note": "International Disaster Assistance is foreign-facing but may pass through domestic NGOs, contractors, or implementing partners.",
        },
        {
            "component_key": "outlay_row_agency_addon",
            "component_family": "outlay",
            "component_role": "subtract_from_tier2_sensitivity",
            "method": "stitched_mts_leaf",
            "data_source_tier": "A_fiscaldata_api|D_pdf_text_parsed",
            "label_paths": "|".join(_labels_for(AGENCY_ROW_OUTLAY_COMPONENT_KEYS)),
            "payer_identity_grade": "B_program_counterparty_strong",
            "cash_basis_grade": "B_mts_net_outlay",
            "quality_code": "sensitivity_only",
            "default_surface": "row_agency_addon_sensitivity",
            "structural_break_flags": "2015_03_fiscaldata_cutover|2003_2005_row_label_drift",
            "fragility_rank": 4,
            "fragility_note": "Foreign Agricultural Service is an agency/program label, not direct proof of ultimate ROW cash recipient.",
        },
        {
            "component_key": "outlay_row_broad_sensitivity",
            "component_family": "outlay",
            "component_role": "subtract_from_tier2_sensitivity",
            "method": "stitched_mts_leaf",
            "data_source_tier": "A_fiscaldata_api|D_pdf_text_parsed",
            "label_paths": "|".join(_labels_for(DEFAULT_ROW_OUTLAY_COMPONENT_KEYS + SECURITY_ROW_OUTLAY_COMPONENT_KEYS)),
            "payer_identity_grade": "B_program_counterparty_strong",
            "cash_basis_grade": "B_mts_net_outlay",
            "quality_code": "sensitivity_only",
            "default_surface": "sensitivity_only",
            "structural_break_flags": "2015_03_fiscaldata_cutover|2003_2005_row_label_drift",
            "fragility_rank": 4,
            "fragility_note": "Broad ROW adds security/narcotics leaves for bounds; it must remain outside default promotion.",
        },
        {
            "component_key": "receipt_banks_strict_depository",
            "component_family": "receipt",
            "component_role": "add_to_tier2_lower_bound",
            "method": "irs_pub16_sector_share",
            "data_source_tier": "A_fiscaldata_api|E_official_annual_or_saar_benchmark",
            "label_paths": "MTS Corporation Income Taxes gross cash x IRS Pub 16 depository / historical credit-intermediation share",
            "payer_identity_grade": "C_sector_share_bridge",
            "cash_basis_grade": "C_cash_total_with_accrual_share",
            "quality_code": "research_only",
            "default_surface": "tier3_extended_research",
            "structural_break_flags": "naics_revision|irs_suppression|stale_share_years",
            "fragility_rank": 3,
            "fragility_note": "Historical Table 6 is major-industry credit intermediation, not exact minor-industry bank detail; current rows inherit IRS suppression/staleness limits.",
        },
        {
            "component_key": "receipt_banks_depository_bhc_central",
            "component_family": "receipt",
            "component_role": "add_to_tier2_central_or_broad_historical",
            "method": "irs_pub16_sector_share",
            "data_source_tier": "A_fiscaldata_api|E_official_annual_or_saar_benchmark",
            "label_paths": "MTS Corporation Income Taxes gross cash x IRS Pub 16 depository plus BHC / historical credit plus management share",
            "payer_identity_grade": "C_sector_share_bridge",
            "cash_basis_grade": "C_cash_total_with_accrual_share",
            "quality_code": "research_only",
            "default_surface": "tier3_extended_research",
            "structural_break_flags": "naics_revision|irs_suppression|stale_share_years",
            "fragility_rank": 3,
            "fragility_note": "Central current exact row becomes a broad historical sensitivity when only major-industry management detail is available.",
        },
        {
            "component_key": "receipt_banks_finance_upper",
            "component_family": "receipt",
            "component_role": "add_to_tier2_upper_bound",
            "method": "irs_pub16_sector_share",
            "data_source_tier": "A_fiscaldata_api|E_official_annual_or_saar_benchmark",
            "label_paths": "MTS Corporation Income Taxes gross cash x IRS Pub 16 finance and insurance share",
            "payer_identity_grade": "C_sector_share_bridge",
            "cash_basis_grade": "C_cash_total_with_accrual_share",
            "quality_code": "sensitivity_only",
            "default_surface": "sensitivity_only",
            "structural_break_flags": "naics_revision|irs_suppression|stale_share_years",
            "fragility_rank": 3,
            "fragility_note": "Finance share is an upper-bound benchmark, not a bank-only receipt estimate.",
        },
        {
            "component_key": "receipt_row_bea_anchor",
            "component_family": "receipt",
            "component_role": "add_to_tier2_macro_anchor_research",
            "method": "bea_row_anchor",
            "data_source_tier": "E_official_annual_or_saar_benchmark",
            "label_paths": "BEA/FRED W008RC1Q027SBEA|W781RC1Q027SBEA|LA0000281Q027SBEA",
            "payer_identity_grade": "D_macro_economic_counterparty",
            "cash_basis_grade": "D_nipa_saar_accrual",
            "quality_code": "research_only",
            "default_surface": "tier3_bea_anchored_research",
            "structural_break_flags": "nipa_revision|saar_divide_by_4",
            "fragility_rank": 1,
            "fragility_note": "BEA ROW receipts are useful as a macro anchor but do not prove Treasury cash-payer identity or debited-account residency.",
        },
        {
            "component_key": "receipt_row_mrv_overlay",
            "component_family": "receipt",
            "component_role": "identified_subcomponent_or_timing_refinement_nondefault",
            "method": "mrv_cbsp_timing_overlay",
            "data_source_tier": "E_official_annual_or_saar_benchmark",
            "label_paths": "State MRV / CBSP annual receipt line allocated by monthly NIV issuance shares",
            "payer_identity_grade": "B_program_counterparty_strong",
            "cash_basis_grade": "E_activity_timing_proxy",
            "quality_code": "blocked_default",
            "default_surface": "nondefault_overlay_only",
            "structural_break_flags": "fy2019_plus_visa_methodology_break|preliminary_monthly_state_data",
            "fragility_rank": 2,
            "fragility_note": "MRV is the leading recurring ROW pilot, but remains nondefault and non-additive against the BEA anchor without legal-remitter/debited-account proof.",
        },
        {
            "component_key": "cashfactor_mint",
            "component_family": "cashfactor",
            "component_role": "add_negative_mint_net_outlays",
            "method": "stitched_mts_leaf",
            "data_source_tier": "A_fiscaldata_api|D_pdf_text_parsed",
            "label_paths": "|".join(MINT_LABELS),
            "payer_identity_grade": "A_direct_cash_payer",
            "cash_basis_grade": "A_mts_modified_cash",
            "quality_code": "default_eligible",
            "default_surface": "tier3_extended_research",
            "structural_break_flags": "2015_03_fiscaldata_cutover",
            "fragility_rank": 6,
            "fragility_note": "Cleanest historical Tier 3 term; main remaining risk is sign/netting convention.",
        },
        {
            "component_key": "receipt_row_zero_default",
            "component_family": "receipt",
            "component_role": "missing_live_receipt_cell",
            "method": "zero_default_placeholder",
            "data_source_tier": "Z_missing_or_zero_default",
            "label_paths": "n/a",
            "payer_identity_grade": "D_macro_economic_counterparty",
            "cash_basis_grade": "Z_not_applicable",
            "quality_code": "blocked_default",
            "default_surface": "tier3_partial_shell_missing_cell",
            "structural_break_flags": "not_promoted",
            "fragility_rank": 1,
            "fragility_note": "Live arithmetic may carry a zero placeholder, but governance treats this as missing/not measured until a ROW receipt source clears payer identity, cash treatment, timing, and non-additivity gates.",
        },
    ]
    return pd.DataFrame(rows).sort_values(["component_family", "fragility_rank", "component_key"]).reset_index(drop=True)


def validate_tier3_component_crosswalk(crosswalk: pd.DataFrame) -> pd.DataFrame:
    required_columns = {
        "component_key",
        "method",
        "data_source_tier",
        "payer_identity_grade",
        "cash_basis_grade",
        "quality_code",
        "fragility_note",
    }
    rows: list[dict[str, object]] = []
    missing_columns = sorted(required_columns - set(crosswalk.columns))
    rows.append(
        {
            "check_name": "required_columns",
            "status": "fail" if missing_columns else "pass",
            "details": "|".join(missing_columns) if missing_columns else "all required columns present",
        }
    )
    if missing_columns:
        return pd.DataFrame(rows)

    required_components = {
        "outlay_banks",
        "outlay_row_core_institutional",
        "outlay_row_narrow",
        "outlay_row_humanitarian_addon",
        "outlay_row_agency_addon",
        "outlay_row_broad_sensitivity",
        "receipt_banks_strict_depository",
        "receipt_banks_depository_bhc_central",
        "receipt_banks_finance_upper",
        "receipt_row_bea_anchor",
        "receipt_row_mrv_overlay",
        "cashfactor_mint",
    }
    missing_components = sorted(required_components - set(crosswalk["component_key"]))
    rows.append(
        {
            "check_name": "required_components",
            "status": "fail" if missing_components else "pass",
            "details": "|".join(missing_components) if missing_components else "all required components present",
        }
    )

    method_bad = sorted(set(crosswalk["method"]) - METHOD_ENUMS)
    rows.append({"check_name": "method_enums", "status": "fail" if method_bad else "pass", "details": "|".join(method_bad) if method_bad else "ok"})

    source_tiers = set()
    for value in crosswalk["data_source_tier"].dropna().astype(str):
        source_tiers.update(part for part in value.split("|") if part)
    source_bad = sorted(source_tiers - set(DATA_SOURCE_TIERS))
    rows.append(
        {"check_name": "data_source_tier_enums", "status": "fail" if source_bad else "pass", "details": "|".join(source_bad) if source_bad else "ok"}
    )

    payer_bad = sorted(set(crosswalk["payer_identity_grade"]) - set(PAYER_IDENTITY_GRADES))
    rows.append(
        {"check_name": "payer_identity_grade_enums", "status": "fail" if payer_bad else "pass", "details": "|".join(payer_bad) if payer_bad else "ok"}
    )

    cash_bad = sorted(set(crosswalk["cash_basis_grade"]) - set(CASH_BASIS_GRADES))
    rows.append(
        {"check_name": "cash_basis_grade_enums", "status": "fail" if cash_bad else "pass", "details": "|".join(cash_bad) if cash_bad else "ok"}
    )

    quality_bad = sorted(set(crosswalk["quality_code"]) - QUALITY_CODES)
    rows.append(
        {"check_name": "quality_code_enums", "status": "fail" if quality_bad else "pass", "details": "|".join(quality_bad) if quality_bad else "ok"}
    )
    return pd.DataFrame(rows)


def render_tier3_component_crosswalk_markdown(crosswalk: pd.DataFrame, validation: pd.DataFrame | None = None) -> str:
    title = "# Tier 3 Component Crosswalk"
    intro = (
        "Private research crosswalk for Tier 3 historical-extension components. "
        "It records component methods, source tiers, quality grades, structural-break flags, and fragility notes while keeping Tier 2 as the headline and Tier 3 as a partial-shell / research surface."
    )
    if crosswalk.empty:
        return "\n".join([title, "", intro, "", "No crosswalk rows are available."])

    validation = validate_tier3_component_crosswalk(crosswalk) if validation is None else validation
    validation_counts = validation["status"].value_counts(dropna=False).to_dict() if not validation.empty else {}
    summary = f"Rows: {len(crosswalk)}. Validation status counts: {validation_counts}."
    header = "| Component | Method | Source tier | Payer grade | Cash grade | Quality | Surface | Fragility note |\n| --- | --- | --- | --- | --- | --- | --- | --- |"
    def md_cell(value: object) -> str:
        return str(value).replace("|", "<br>")

    rows = [
        "| "
        + " | ".join(
            [
                md_cell(row["component_key"]),
                md_cell(row["method"]),
                md_cell(row["data_source_tier"]),
                md_cell(row["payer_identity_grade"]),
                md_cell(row["cash_basis_grade"]),
                md_cell(row["quality_code"]),
                md_cell(row["default_surface"]),
                md_cell(row["fragility_note"]),
            ]
        )
        + " |"
        for _, row in crosswalk.iterrows()
    ]
    notes = [
        "Notes:",
        "- ROW receipt BEA and MRV rows are explicitly research / nondefault surfaces, not live-default corrections.",
        "- Live receipt placeholders are missing/not-measured cells, not evidence of economic zero receipts.",
        "- The ROW outlay family is now nested: core institutional, humanitarian add-on, agency add-on, and broad security sensitivity.",
        "- Broad ROW outlays and finance-tax receipts are sensitivity rows only.",
        "- `cashfactor_mint` is the cleanest historical row; `receipt_row_bea_anchor` is the weakest payer-identity row.",
    ]
    return "\n".join([title, "", intro, "", summary, "", header, *rows, "", *notes, ""])


def write_tier3_component_crosswalk(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    validation_path: Path | str | None = None,
) -> tuple[Path, Path, pd.DataFrame]:
    crosswalk = build_tier3_component_crosswalk()
    validation = validate_tier3_component_crosswalk(crosswalk)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_tier3_component_crosswalk_markdown(crosswalk, validation), encoding="utf-8")

    if validation_path is not None:
        validation_path = Path(validation_path)
        validation_path.parent.mkdir(parents=True, exist_ok=True)
        validation.to_csv(validation_path, index=False)
    return csv_path, markdown_path, crosswalk
