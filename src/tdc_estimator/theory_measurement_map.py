from __future__ import annotations

from pathlib import Path

import pandas as pd


THEORY_MEASUREMENT_COLUMNS = [
    "display_order",
    "equation_key",
    "equation_family",
    "display_title",
    "repo_role",
    "latex",
    "plain_english_summary",
    "current_measurement_mapping",
    "implementation_status",
    "main_caveat",
    "primary_artifact",
]


def build_theory_measurement_map() -> pd.DataFrame:
    rows = [
        {
            "display_order": 1,
            "equation_key": "theory_du_facing_identity",
            "equation_family": "theoretical_identity",
            "display_title": "DU-Facing Definition of TDC",
            "repo_role": "informational_identity",
            "latex": r"\Delta D^{TDC}_{DU} = (G^{ND}_{DU}-R^T_{DU}) + DS^T_{DU} + (Q^T_{DU\to RU}-Q^T_{RU\to DU})",
            "plain_english_summary": (
                "The most direct theory statement: TDC is the Treasury-driven part of deposit change seen from the domestic nonbank deposit-user side."
            ),
            "current_measurement_mapping": (
                "The repo does not directly observe every DU-side term. The live ladder approximates this identity from Treasury-security transactions, Treasury operating cash, remittances, and bounded fiscal corrections."
            ),
            "implementation_status": "theory_only",
            "main_caveat": (
                "This is the conceptual accounting identity. Current estimates are narrower measurement approximations, not a full direct DU ledger."
            ),
            "primary_artifact": "docs/equations.md",
        },
        {
            "display_order": 2,
            "equation_key": "theory_treasury_cash_constraint",
            "equation_family": "theoretical_identity",
            "display_title": "Treasury-Cash Constraint Version",
            "repo_role": "informational_identity",
            "latex": r"\Delta D^{TDC}_{DU} = (Q^T_{DU\to RU}-Q^T_{RU\to DU}) + (I^T + R^T_{RU} + \Pi^F_T - G^{ND}_{RU} - DS^T_{RU}) - \Delta TOC",
            "plain_english_summary": (
                "The main Treasury-cash identity: TDC depends on Treasury-security settlement with reserve-side counterparties, Treasury-related cash flows with those counterparties, and the change in Treasury operating cash."
            ),
            "current_measurement_mapping": (
                "This is the closest theory frame for the current live estimator ladder. The repo explicitly uses Treasury operating cash (TOC), Treasury-security transaction terms, and positive Fed remittances, then layers in narrower fiscal-flow corrections."
            ),
            "implementation_status": "partially_measured",
            "main_caveat": (
                "The repo does not yet directly measure every RU-side issuance, receipt, outlay, and debt-service term in this exact symbolic form."
            ),
            "primary_artifact": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
        },
        {
            "display_order": 3,
            "equation_key": "theory_fed_remittance_deferred_asset",
            "equation_family": "theoretical_identity",
            "display_title": "Fed Remittances and Deferred Asset Treatment",
            "repo_role": "informational_identity",
            "latex": r"\Pi^F_{T,t} = \max(0,\;E^F_t-DA^F_{t-1}), \qquad DA^F_t = \max(0,\;DA^F_{t-1}-E^F_t)",
            "plain_english_summary": (
                "Negative Fed earnings do not imply Treasury pays the Fed. They build a deferred asset and suppress future remittances until that deferred asset is worked off."
            ),
            "current_measurement_mapping": (
                "The repo already reflects this by clipping Fed remittances at zero before quarter aggregation and treating negative H.4.1 values as deferred-asset accounting rather than negative Treasury cash flow."
            ),
            "implementation_status": "implemented_conceptually",
            "main_caveat": (
                "The live measurement uses the public remittance series as a practical proxy rather than reconstructing the full Fed earnings identity term by term."
            ),
            "primary_artifact": "tdc_base_bank_only_ru_flow",
        },
        {
            "display_order": 4,
            "equation_key": "theory_residual_deposit_decomposition",
            "equation_family": "theoretical_identity",
            "display_title": "Residual Deposit-Decomposition Version",
            "repo_role": "informational_identity",
            "latex": r"\Delta D^{TDC}_{DU} = (\Delta M-\Delta C-\Delta X) - (\Delta L^B_{DU}+\Delta A^{B,NT}_{DU}) - \Delta A^{CB,NT}_{DU} - \Delta F^{NT}_{DU} - \varepsilon",
            "plain_english_summary": (
                "A residual version of TDC: start from total deposit change, subtract major non-Treasury drivers, and treat the remainder as the Treasury contribution."
            ),
            "current_measurement_mapping": (
                "This maps to the repo’s monetary/disaggregated branch and decomposition proxies, which are used as diagnostics and cross-checks rather than as the headline estimator."
            ),
            "implementation_status": "diagnostic_only",
            "main_caveat": (
                "The repo does not treat this residual system as a co-equal headline estimate because large perimeter and measurement wedges still remain."
            ),
            "primary_artifact": "monetary_depository_crosscheck",
        },
        {
            "display_order": 5,
            "equation_key": "implemented_bank_only_headline",
            "equation_family": "implemented_estimate",
            "display_title": "Implemented Bank-Only Headline",
            "repo_role": "headline_estimate",
            "latex": r"\widehat{\Delta D}^{mkt,bank}_{TDC,t} = \Delta TS^{tx}_{Fed,t} + \Delta TS^{tx}_{Banks,t} + \Delta TS^{tx}_{ROW,t} - \Delta TOC^{tx}_{Treasury,t} + Remit^{+}_{Fed,t}",
            "plain_english_summary": (
                "The simplest live estimate: Treasury-security transactions plus positive Fed remittances minus Treasury operating cash."
            ),
            "current_measurement_mapping": (
                "This is the repo’s live bank-only base headline and the main implemented approximation to the Treasury-cash-constraint identity in the transaction-data era."
            ),
            "implementation_status": "implemented_live",
            "main_caveat": (
                "It is still a measurement approximation. It is bank-only, marketable-Treasury-focused, and not a full direct implementation of the theory identities."
            ),
            "primary_artifact": "tdc_base_bank_only_ru_flow",
        },
        {
            "display_order": 6,
            "equation_key": "implemented_tier2_interest_correction",
            "equation_family": "implemented_estimate",
            "display_title": "Implemented Tier 2 Interest-Corrected Estimate",
            "repo_role": "live_corrected_estimate",
            "latex": r"\widehat{\Delta D}^{Tier2,bank}_{TDC,t} = \widehat{\Delta D}^{mkt,bank}_{TDC,t} - Coupon^F_t - Coupon^{Banks}_t - Coupon^{ROW}_t",
            "plain_english_summary": (
                "The bank-only headline after removing coupon-interest distortions from Fed, banks, and ROW Treasury holdings."
            ),
            "current_measurement_mapping": (
                "This is the repo’s strongest transfer-side cleanup layer and one of the most informative live comparisons for downstream work."
            ),
            "implementation_status": "implemented_live",
            "main_caveat": (
                "Coupon terms are still proxies built from public holdings and maturity inputs, not observed cash-settlement flows."
            ),
            "primary_artifact": "tdc_tier2_interest_corrected_bank_only_ru_flow",
        },
        {
            "display_order": 7,
            "equation_key": "implemented_tier3_fiscal_correction",
            "equation_family": "implemented_estimate",
            "display_title": "Tier 3 Partial Fiscal-Shell Diagnostic",
            "repo_role": "partial_fiscal_shell_diagnostic",
            "latex": r"\widehat{\Delta D}^{Tier3,bank}_{TDC,t} = \widehat{\Delta D}^{Tier2,bank}_{TDC,t} - Outlay^{Banks}_t - Outlay^{ROW}_t + Receipt^{Banks}_t + Receipt^{ROW}_t + CashFactor_t",
            "plain_english_summary": (
                "The intended Tier 3 formula is Tier 2 plus paired fiscal-flow corrections, but the current live artifact is only the outlay-backed partial shell because receipt cells have not cleared default gates."
            ),
            "current_measurement_mapping": (
                "The live numeric series subtracts measured bank/FAS and narrow ROW outlays and adds the Mint cash factor. Bank and ROW receipts remain missing/not measured default cells rather than economic zeros."
            ),
            "implementation_status": "diagnostic_partial_shell",
            "main_caveat": (
                "Do not treat this as a promoted fiscal-corrected point estimate until bank and ROW receipt measures clear comparable source, timing, and payer-identity gates."
            ),
            "primary_artifact": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
        },
        {
            "display_order": 8,
            "equation_key": "implemented_historical_bank_receipt_overlay",
            "equation_family": "bounded_measurement",
            "display_title": "Historical Bank-Receipt Overlay",
            "repo_role": "historical_default_view",
            "latex": r"\widehat{\Delta D}^{HistBank}_{TDC,t} = \widehat{\Delta D}^{Tier3,bank}_{TDC,t} + \Delta Receipt^{Bank,Table5.1}_{t}",
            "plain_english_summary": (
                "A historical-only Tier 3 variant that adds the age-eligible IRS Table 5.1 bank receipt correction."
            ),
            "current_measurement_mapping": (
                "This is the repo’s strongest bank receipt result. It shows how Tier 3 changes when the bank receipt bridge is allowed inside the historical age-eligible window."
            ),
            "implementation_status": "historical_only",
            "main_caveat": (
                "The current-quarter bridge remains blocked by stale public IRS bank-minor shares, so this cannot be promoted into the live default estimate."
            ),
            "primary_artifact": "bank_receipt_historical_default_view",
        },
        {
            "display_order": 9,
            "equation_key": "implemented_mrv_nondefault_pilot",
            "equation_family": "bounded_measurement",
            "display_title": "MRV Nondefault ROW Pilot",
            "repo_role": "bounded_nondefault_pilot",
            "latex": r"\widehat{\Delta Receipt}^{ROW,MRV}_{t} \subset \widehat{\Delta D}^{Tier3,bank}_{TDC,t}",
            "plain_english_summary": (
                "A bounded rest-of-world receipt sensitivity using the MRV / CBSP recurring fee branch."
            ),
            "current_measurement_mapping": (
                "This is the only serious recurring ROW receipt branch currently carried forward. It is kept separate from the live default estimate and used as a boundary marker."
            ),
            "implementation_status": "nondefault_only",
            "main_caveat": (
                "It remains blocked by legal-remitter or debited-account proof and by the lack of public quarterly MRV cash timing."
            ),
            "primary_artifact": "row_mrv_primary_nondefault_pilot",
        },
        {
            "display_order": 10,
            "equation_key": "implemented_monetary_crosscheck",
            "equation_family": "diagnostic_measurement",
            "display_title": "Monetary Cross-Check and Residual Audit",
            "repo_role": "diagnostic_crosscheck",
            "latex": r"\widehat{\Delta D}^{decomp}_{TDC,t} \approx \Delta M_t - \Delta C_t - \Delta X_t - \text{non-Treasury deposit drivers}",
            "plain_english_summary": (
                "A diagnostic residual framework used to see whether the ladder is directionally plausible against broader deposit targets."
            ),
            "current_measurement_mapping": (
                "The repo uses the depository target as the main monetary cross-check and the commercial-bank target as a stress test."
            ),
            "implementation_status": "diagnostic_only",
            "main_caveat": (
                "This branch is intentionally not treated as the headline estimator because the unresolved wedge is still too large and too perimeter-dependent."
            ),
            "primary_artifact": "monetary_depository_crosscheck",
        },
    ]
    frame = pd.DataFrame(rows).reindex(columns=THEORY_MEASUREMENT_COLUMNS)
    return frame.sort_values(["display_order", "equation_key"]).reset_index(drop=True)


def render_theory_measurement_map_markdown(frame: pd.DataFrame) -> str:
    title = "# Theory Measurement Map"
    intro = (
        "Canonical theory-to-measurement map for TDC. It distinguishes the theoretical accounting identities from the narrower live estimators, bounded historical overlays, and diagnostic cross-checks."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No theory-to-measurement rows are available."])

    lines = [title, "", intro, ""]
    for _, row in frame.iterrows():
        lines.extend(
            [
                f"## {row['display_title']}",
                "",
                f"- `equation_key`: `{row['equation_key']}`",
                f"- `equation_family`: `{row['equation_family']}`",
                f"- `repo_role`: `{row['repo_role']}`",
                f"- `implementation_status`: `{row['implementation_status']}`",
                f"- `primary_artifact`: `{row['primary_artifact']}`",
                "",
                "```text",
                str(row["latex"]),
                "```",
                "",
                str(row["plain_english_summary"]),
                "",
                f"Current measurement mapping: {row['current_measurement_mapping']}",
                "",
                f"Main caveat: {row['main_caveat']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_theory_measurement_map(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_theory_measurement_map()

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_theory_measurement_map_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
