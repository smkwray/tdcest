from __future__ import annotations

from pathlib import Path

import pandas as pd


STRICT_PATTERNS = [
    r"machine readable visa fee",
]

SECONDARY_VISA_PATTERNS = [
    r"immigrant visa security surcharge",
    r"diversity visa lottery fee",
]

MIXED_PATTERNS = [
    r"affidavit of support fee",
    r"immigration examinations fee account",
    r"immigration user fees",
    r"temporary h-1b visa",
    r"temporary l-1 visa",
    r"j1 visa waiver",
]

EXCLUDED_PATTERNS = [
    r"passport",
    r"western hemisphere travel initiative",
    r"immigration, passport, and consular fees",
]


def _match_bucket(title: str) -> str | None:
    title = title or ""
    checks = [
        ("mrv_cbsp_primary_candidate", STRICT_PATTERNS),
        ("state_visa_secondary_sensitivity", SECONDARY_VISA_PATTERNS),
        ("mixed_immigration_or_sponsor_candidate", MIXED_PATTERNS),
        ("passport_or_broad_consular_excluded", EXCLUDED_PATTERNS),
    ]
    for bucket, patterns in checks:
        for pattern in patterns:
            if pd.Series([title]).str.contains(pattern, case=False, regex=True, na=False).iloc[0]:
                return bucket
    return None


def _bucket_note(bucket: str) -> str:
    notes = {
        "mrv_cbsp_primary_candidate": (
            "Primary MRV / CBSP recurring bridge candidate. The applicant link is relatively strong, but public annual title-level evidence still does not prove the debited account or legal cash remitter."
        ),
        "state_visa_secondary_sensitivity": (
            "Secondary State visa line retained as a nondefault sensitivity. These lines are more exposed to timing and domestic-payer contamination than the MRV / CBSP line."
        ),
        "mixed_immigration_or_sponsor_candidate": (
            "Foreign-related immigration or visa line with material domestic-sponsor, domestic-employer, or domestic-applicant contamination risk."
        ),
        "passport_or_broad_consular_excluded": (
            "Broad passport or mixed consular title kept visible for contamination accounting and excluded from any default ROW receipt correction."
        ),
    }
    return notes[bucket]


def _bucket_metadata(bucket: str) -> dict[str, str]:
    metadata = {
        "mrv_cbsp_primary_candidate": {
            "bridge_priority": "primary",
            "payer_identity_grade": "B_applicant_link_not_debited_account",
            "cash_treatment_grade": "B_cbsp_receipt_account_public_annual",
            "timing_grade": "C_requires_monthly_niv_timing_proxy",
            "default_blocker": "no_public_debited_account_or_actual_cash_payer_proof",
            "recommended_role": "future_row_default_pilot_under_review",
        },
        "state_visa_secondary_sensitivity": {
            "bridge_priority": "secondary",
            "payer_identity_grade": "C_visa_fee_line_not_direct_cash_payer",
            "cash_treatment_grade": "B_state_receipt_account_public_annual",
            "timing_grade": "C_requires_monthly_iv_timing_proxy",
            "default_blocker": "secondary_visa_line_requires_stronger_payer_and_timing_evidence",
            "recommended_role": "secondary_row_sensitivity_only",
        },
        "mixed_immigration_or_sponsor_candidate": {
            "bridge_priority": "mixed",
            "payer_identity_grade": "D_domestic_sponsor_or_employer_contamination",
            "cash_treatment_grade": "B_title_level_public_annual",
            "timing_grade": "D_no_clean_quarterly_cash_timing",
            "default_blocker": "domestic_contamination_and_no_public_debited_account_proof",
            "recommended_role": "mixed_row_sensitivity_only",
        },
        "passport_or_broad_consular_excluded": {
            "bridge_priority": "excluded",
            "payer_identity_grade": "D_mixed_or_domestic_payer_exposure",
            "cash_treatment_grade": "B_title_level_public_annual",
            "timing_grade": "D_no_clean_quarterly_cash_timing",
            "default_blocker": "broad_consular_or_passport_contamination",
            "recommended_role": "excluded_from_row_default",
        },
    }
    return metadata[bucket]


def build_row_visa_consular_pilot(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates is None or candidates.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    sub = candidates.loc[candidates["counterparty_group"].eq("row")].copy()
    for _, row in sub.iterrows():
        title = str(row["receipt_line_item_nm"])
        bucket = _match_bucket(title)
        if bucket is None:
            continue
        rows.append(
            {
                "date": pd.Timestamp(row["date"]),
                "fiscal_year": int(row["fiscal_year"]),
                "receipt_line_item_nm": title,
                "receipt_amt_mil": float(row["receipt_amt_mil"]),
                "pilot_bucket": bucket,
                **_bucket_metadata(bucket),
                "default_eligible": False,
                "note": _bucket_note(bucket),
            }
        )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out = (
        out.groupby(
            [
                "date",
                "fiscal_year",
                "receipt_line_item_nm",
                "pilot_bucket",
                "bridge_priority",
                "payer_identity_grade",
                "cash_treatment_grade",
                "timing_grade",
                "recommended_role",
                "default_eligible",
                "default_blocker",
                "note",
            ],
            dropna=False,
            as_index=False,
        )["receipt_amt_mil"]
        .sum()
        .sort_values(["date", "pilot_bucket", "receipt_amt_mil", "receipt_line_item_nm"], ascending=[False, True, False, True])
        .reset_index(drop=True)
    )
    return out


def render_row_visa_consular_pilot_markdown(pilot: pd.DataFrame) -> str:
    title = "# ROW Visa And Consular Pilot"
    intro = (
        "Annual narrow-pilot intake from the public `Receipts by Department` account surface. "
        "Amounts are in millions. This artifact is for ROW receipt pilot scoping only and does not promote any line into the default Tier 3 correction."
    )
    if pilot.empty:
        return "\n".join([title, "", intro, "", "No visa, consular, immigration, or passport-related pilot lines matched the current rules."])

    latest_date = pd.Timestamp(pilot["date"].max())
    latest = pilot.loc[pilot["date"].eq(latest_date)].copy()
    mrv_total = latest.loc[latest["pilot_bucket"].eq("mrv_cbsp_primary_candidate"), "receipt_amt_mil"].sum()
    secondary_total = latest.loc[latest["pilot_bucket"].eq("state_visa_secondary_sensitivity"), "receipt_amt_mil"].sum()
    mixed_total = latest.loc[latest["pilot_bucket"].eq("mixed_immigration_or_sponsor_candidate"), "receipt_amt_mil"].sum()
    excluded_total = latest.loc[latest["pilot_bucket"].eq("passport_or_broad_consular_excluded"), "receipt_amt_mil"].sum()
    summary = (
        f"Latest fiscal year-end in view: {latest_date.date().isoformat()}. "
        f"MRV / CBSP primary pilot lines total {mrv_total:,.3f} million; "
        f"secondary State visa lines total {secondary_total:,.3f} million; "
        f"mixed immigration or sponsor-sensitive lines total {mixed_total:,.3f} million; "
        f"passport or broad-consular excluded lines total {excluded_total:,.3f} million."
    )

    header = [
        "| Fiscal year-end | Receipt line item | Amount (mil) | Pilot bucket | Role | Default eligible |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    rows = []
    for _, row in latest.sort_values(["pilot_bucket", "receipt_amt_mil"], ascending=[True, False]).iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    str(row["receipt_line_item_nm"]),
                    f"{float(row['receipt_amt_mil']):,.3f}",
                    str(row["pilot_bucket"]),
                    str(row["recommended_role"]),
                    "yes" if bool(row["default_eligible"]) else "no",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `mrv_cbsp_primary_candidate` is the current best public recurring ROW pilot bucket and should feed the main nondefault quarterly timing bridge.",
        "- `state_visa_secondary_sensitivity` stays visible, but it is not added to the main ROW timing delta that feeds downstream sensitivity stacking.",
        "- `mixed_immigration_or_sponsor_candidate` stays out of the default because domestic sponsors, employers, or U.S.-resident applicants may be the real cash payers.",
        "- `passport_or_broad_consular_excluded` remains a contamination bucket rather than a candidate default.",
    ]

    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_row_visa_consular_pilot(
    candidates: pd.DataFrame,
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    pilot = build_row_visa_consular_pilot(candidates)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pilot.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_visa_consular_pilot_markdown(pilot), encoding="utf-8")

    return csv_path, markdown_path, pilot
