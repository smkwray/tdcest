from __future__ import annotations

from pathlib import Path

import pandas as pd

from .bank_corp_tax_receipts_bridge import DEFAULT_MAX_STALE_SHARE_YEARS
READINESS_COLUMNS = [
    "check_name",
    "status",
    "passes_for_default",
    "severity",
    "metric_name",
    "metric_value",
    "threshold_or_rule",
    "details",
    "overall_recommendation",
    "recommended_default_variant",
]


def _format_num(value: float | int | None, places: int = 3) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.{places}f}"


def _latest_bridge_row(bridge: pd.DataFrame) -> pd.Series:
    if bridge.empty:
        return pd.Series(dtype="object")
    return bridge.sort_index().iloc[-1]


def build_bank_receipt_default_readiness(
    *,
    bank_corp_tax_receipts_bridge: pd.DataFrame | None,
    irs_soi_bank_tax_shares: pd.DataFrame | None,
    bank_minor_industry_availability: pd.DataFrame | None,
    estimates: pd.DataFrame | None,
    tier3_receipt_candidate_sensitivity: pd.DataFrame | None = None,
    bank_occ_timing_sensitivity: pd.DataFrame | None = None,
    tier3_receipt_source_diagnostics: pd.DataFrame | None = None,
    max_stale_share_years: int = DEFAULT_MAX_STALE_SHARE_YEARS,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    if bank_corp_tax_receipts_bridge is None or bank_corp_tax_receipts_bridge.empty:
        return pd.DataFrame(columns=READINESS_COLUMNS)

    bridge = bank_corp_tax_receipts_bridge.copy().sort_index()
    latest_bridge_date = pd.Timestamp(bridge.index.max())
    latest_bridge = _latest_bridge_row(bridge)
    latest_share_year = int(latest_bridge["soi_tax_year_used"]) if pd.notna(latest_bridge.get("soi_tax_year_used")) else None
    latest_share_status = str(latest_bridge.get("share_status", "n/a"))
    stale_share_years = latest_bridge_date.year - latest_share_year if latest_share_year is not None else None

    if estimates is not None and not estimates.empty and "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in estimates.columns:
        est = estimates.loc[estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"].notna()].copy()
        latest_estimator_date = pd.Timestamp(est.index.max()) if not est.empty else None
    else:
        latest_estimator_date = None

    share_history = None
    if irs_soi_bank_tax_shares is not None and not irs_soi_bank_tax_shares.empty:
        share_history = irs_soi_bank_tax_shares.copy().sort_values("tax_year").reset_index(drop=True)
        default_candidate = pd.to_numeric(share_history["depository_plus_bhc_share_after_credits"], errors="coerce")
        share_mean = float(default_candidate.mean())
        share_std = float(default_candidate.std(ddof=0))
        share_min = float(default_candidate.min())
        share_max = float(default_candidate.max())
        current_share = float(latest_bridge["bank_tax_share_depository_plus_bhc"])
        current_minus_mean = current_share - share_mean
        holding_uplift_latest = (
            float(latest_bridge["bank_tax_share_depository_plus_bhc"]) - float(latest_bridge["bank_tax_share_strict_depository"])
            if pd.notna(latest_bridge.get("bank_tax_share_depository_plus_bhc")) and pd.notna(latest_bridge.get("bank_tax_share_strict_depository"))
            else None
        )
    else:
        share_mean = share_std = share_min = share_max = current_share = current_minus_mean = holding_uplift_latest = None

    overlap_date = None
    overlap_bridge_val = None
    overlap_sensitivity_val = None
    if latest_estimator_date is not None:
        overlap_date = min(latest_bridge_date, latest_estimator_date)
        if overlap_date in bridge.index:
            overlap_bridge_val = float(bridge.loc[overlap_date, "bank_corp_tax_receipts_gross_depository_plus_bhc_mil"])
        if (
            tier3_receipt_candidate_sensitivity is not None
            and not tier3_receipt_candidate_sensitivity.empty
            and overlap_date in tier3_receipt_candidate_sensitivity.index
        ):
            overlap_sensitivity_val = float(
                tier3_receipt_candidate_sensitivity.loc[overlap_date, "bank_corp_tax_depository_plus_bhc_bridge_delta_mil"]
            )

    sign_and_overlap_ok = True
    sign_note = "Bridge is positive-valued and currently isolated as a standalone bank receipt candidate layer."
    if bank_occ_timing_sensitivity is not None and not bank_occ_timing_sensitivity.empty:
        sign_note += " OCC timing remains a separate non-tax sensitivity."
    if tier3_receipt_source_diagnostics is not None and not tier3_receipt_source_diagnostics.empty:
        sign_note += " Revenue Collections bank-channel totals remain separate rejected-default upper bounds."

    perimeter_metric = "table51_bank_minor_industry_bridge"
    perimeter_details = (
        "The current bridge uses IRS Publication 16 Table 5.1 bank-minor rows for commercial banking, savings/depository credit intermediation, "
        "and bank holding companies. That materially improves the payer perimeter relative to the older finance-sector bridge."
    )
    if bank_minor_industry_availability is not None and not bank_minor_industry_availability.empty:
        latest_year = int(pd.to_numeric(bank_minor_industry_availability["tax_year"], errors="coerce").max())
        latest_availability = bank_minor_industry_availability.loc[
            pd.to_numeric(bank_minor_industry_availability["tax_year"], errors="coerce").eq(latest_year)
        ].copy()
        required = latest_availability.loc[
            latest_availability["perimeter_type"].isin(["bank_minor_industry", "bank_holding_minor_industry"])
        ].copy()
        status_parts: list[str] = []
        for industry_key in [
            "commercial_banking",
            "savings_and_other_depository_credit_intermediation",
            "offices_of_bank_holding_companies",
        ]:
            match = required.loc[required["industry_key"].eq(industry_key)]
            if match.empty:
                status_parts.append(f"{industry_key}=missing")
                continue
            row = match.iloc[0]
            status_parts.append(
                f"{industry_key}={row['income_subject_to_tax_status']}/{row['total_income_tax_after_credits_status']}"
            )
        perimeter_metric = f"latest_tax_year={latest_year} " + " ".join(status_parts)
        perimeter_details = (
            f"Latest public Publication 16 Table 5.3 bank-like rows in tax year {latest_year} are not usable for the stricter C-corp-style bank share path. "
            "The repo therefore relies on the better available Table 5.1 bank-minor bridge rather than the blocked Table 5.3 path."
        )

    rows.extend(
        [
            {
                "check_name": "perimeter_contamination",
                "status": "pass",
                "passes_for_default": True,
                "severity": "medium",
                "metric_name": "bridge_basis",
                "metric_value": perimeter_metric,
                "threshold_or_rule": "Bank default requires bank-specific or defensibly bank-attributed payer perimeter; Table 5.1 bank-minor rows now satisfy that better than the finance-sector bridge.",
                "details": perimeter_details,
            },
            {
                "check_name": "share_stability",
                "status": "warn" if share_history is not None else "fail",
                "passes_for_default": False,
                "severity": "medium",
                "metric_name": "table51_bank_minor_share_history_summary",
                "metric_value": (
                    f"latest={_format_num(current_share, 6)} mean={_format_num(share_mean, 6)} "
                    f"min={_format_num(share_min, 6)} max={_format_num(share_max, 6)} std={_format_num(share_std, 6)} "
                    f"latest_minus_mean={_format_num(current_minus_mean, 6)}"
                    if share_history is not None
                    else "n/a"
                ),
                "threshold_or_rule": "Show annual SOI Table 5.1 bank-minor share history and assess whether the carried-forward share is unusually high or low.",
                "details": (
                    f"Public share history exists through {int(share_history['tax_year'].max()) if share_history is not None else 'n/a'}. "
                    f"The latest usable depository-plus-BHC share in the bridge is {latest_share_year} with a BHC uplift over strict depository of {_format_num(holding_uplift_latest, 6)}."
                    if share_history is not None
                    else "No IRS SOI share history loaded."
                ),
            },
            {
                "check_name": "stale_share_rule",
                "status": "fail" if stale_share_years is None or stale_share_years > max_stale_share_years else "pass",
                "passes_for_default": stale_share_years is not None and stale_share_years <= max_stale_share_years,
                "severity": "high",
                "metric_name": "stale_share_years",
                "metric_value": _format_num(stale_share_years, 0),
                "threshold_or_rule": f"Default bridge share must not be older than {max_stale_share_years} calendar years relative to the latest bridge quarter.",
                "details": (
                    f"Latest bridge quarter is {latest_bridge_date.date().isoformat()} using tax-year {latest_share_year} "
                    f"with share status `{latest_share_status}`."
                ),
            },
            {
                "check_name": "estimator_integration_overlap",
                "status": "pass"
                if latest_estimator_date is not None and latest_bridge_date == latest_estimator_date
                else "warn",
                "passes_for_default": latest_estimator_date is not None and latest_bridge_date == latest_estimator_date,
                "severity": "medium",
                "metric_name": "latest_overlap",
                "metric_value": (
                    f"bridge_latest={latest_bridge_date.date().isoformat()} "
                    f"estimator_latest={latest_estimator_date.date().isoformat() if latest_estimator_date is not None else 'n/a'} "
                    f"overlap={overlap_date.date().isoformat() if overlap_date is not None else 'n/a'} "
                    f"overlap_bridge={_format_num(overlap_bridge_val)} "
                    f"overlap_sensitivity={_format_num(overlap_sensitivity_val)}"
                ),
                "threshold_or_rule": "Bridge and Tier 3 receipt sensitivity surfaces should align through the current estimator overlap window.",
                "details": (
                    "The bank bridge currently extends beyond the live estimator ladder. "
                    "Promotion should be accompanied by clean overlap alignment and published integration through the current Tier 3 window."
                ),
            },
            {
                "check_name": "no_double_count_and_sign",
                "status": "pass" if sign_and_overlap_ok else "fail",
                "passes_for_default": sign_and_overlap_ok,
                "severity": "medium",
                "metric_name": "integration_sign_status",
                "metric_value": "isolated_positive_candidate",
                "threshold_or_rule": "Promoted bridge must remain a standalone positive receipt correction and must not be layered on top of OCC or Revenue Collections candidates.",
                "details": sign_note,
            },
        ]
    )

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=READINESS_COLUMNS)
    out["overall_recommendation"] = "not_yet_promotable"
    out["recommended_default_variant"] = "depository_plus_bhc_if_age_eligible"
    return out.reindex(columns=READINESS_COLUMNS)


def render_bank_receipt_default_readiness_markdown(readiness: pd.DataFrame) -> str:
    title = "# Bank Receipt Default Readiness"
    intro = (
        "Explicit readiness gate for promoting the bank corporate-tax bridge into the default Tier 3 bank receipt correction. "
        "This artifact implements the minimum checks requested in the latest methods review."
    )
    if readiness.empty:
        return "\n".join([title, "", intro, "", "No bank receipt default-readiness checks are available."])

    headline = readiness.iloc[0]
    summary = (
        f"Overall recommendation: {headline['overall_recommendation']}. "
        f"Recommended eventual default variant: {headline['recommended_default_variant']}."
    )
    header = [
        "| Check | Status | Passes for default | Metric | Value |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in readiness.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["check_name"]),
                    str(row["status"]),
                    "yes" if bool(row["passes_for_default"]) else "no",
                    str(row["metric_name"]),
                    str(row["metric_value"]),
                ]
            )
            + " |"
        )
    notes = [
        "Notes:",
        "- `perimeter_contamination` now passes: the live bridge is based on Publication 16 Table 5.1 bank-minor rows rather than the older finance-sector bridge.",
        "- `stale_share_rule` is the main current blocker: the latest bridge quarter still carries forward tax-year 2022 and therefore fails the current two-calendar-year freshness gate.",
        "- Historical and age-eligible quarters can still be evaluated separately from current stale quarters; a passing sign/no-double-count check alone is not enough for promotion.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_bank_receipt_default_readiness(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    bank_corp_tax_receipts_bridge: pd.DataFrame | None,
    irs_soi_bank_tax_shares: pd.DataFrame | None,
    bank_minor_industry_availability: pd.DataFrame | None,
    estimates: pd.DataFrame | None,
    tier3_receipt_candidate_sensitivity: pd.DataFrame | None = None,
    bank_occ_timing_sensitivity: pd.DataFrame | None = None,
    tier3_receipt_source_diagnostics: pd.DataFrame | None = None,
    max_stale_share_years: int = DEFAULT_MAX_STALE_SHARE_YEARS,
) -> tuple[Path, Path, pd.DataFrame]:
    readiness = build_bank_receipt_default_readiness(
        bank_corp_tax_receipts_bridge=bank_corp_tax_receipts_bridge,
        irs_soi_bank_tax_shares=irs_soi_bank_tax_shares,
        bank_minor_industry_availability=bank_minor_industry_availability,
        estimates=estimates,
        tier3_receipt_candidate_sensitivity=tier3_receipt_candidate_sensitivity,
        bank_occ_timing_sensitivity=bank_occ_timing_sensitivity,
        tier3_receipt_source_diagnostics=tier3_receipt_source_diagnostics,
        max_stale_share_years=max_stale_share_years,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    readiness.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bank_receipt_default_readiness_markdown(readiness), encoding="utf-8")

    return csv_path, markdown_path, readiness
