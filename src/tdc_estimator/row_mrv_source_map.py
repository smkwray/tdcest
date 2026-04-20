from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE_MAP_COLUMNS = [
    "source_family_key",
    "currently_loaded",
    "required_for_default",
    "still_missing_for_default",
    "current_repo_stance",
    "provider",
    "candidate_series_or_product",
    "official_source_family",
    "intended_use",
    "notes",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def build_row_mrv_source_map(
    *,
    row_mrv_promotion_checklist: pd.DataFrame | None,
) -> pd.DataFrame:
    if row_mrv_promotion_checklist is None or row_mrv_promotion_checklist.empty:
        return pd.DataFrame(columns=SOURCE_MAP_COLUMNS)

    checklist = row_mrv_promotion_checklist.copy()
    remitter = _get_row(checklist, "check_name", "legal_remitter_or_debited_account")
    timing = _get_row(checklist, "check_name", "observed_quarterly_cash_timing")
    cash = _get_row(checklist, "check_name", "cash_treatment_and_retained_account")
    account = _get_row(checklist, "check_name", "treasury_receipt_account_identification")

    rows = [
        {
            "source_family_key": "treasury_state_account_mapping",
            "currently_loaded": str(account.get("status")) == "complete",
            "required_for_default": True,
            "still_missing_for_default": str(account.get("status")) != "complete",
            "current_repo_stance": "loaded_account_family_support"
            if str(account.get("status")) == "complete"
            else "needs_stronger_account_mapping",
            "provider": "Treasury + State/FAM",
            "candidate_series_or_product": "Receipts by Department + Combined Statement + FAM retained-fee authority",
            "official_source_family": "Annual Treasury receipt account line plus broader CBSP main-account confirmation",
            "intended_use": "Anchor the MRV / CBSP branch to a reproducible Treasury receipt account family.",
            "notes": "This family is already loaded strongly enough for the current MRV pilot. It is not the binding blocker anymore.",
        },
        {
            "source_family_key": "cash_treatment_and_retention",
            "currently_loaded": str(cash.get("status")) in {"partial", "complete"},
            "required_for_default": True,
            "still_missing_for_default": str(cash.get("status")) != "complete",
            "current_repo_stance": "stronger_nondefault_cash_route_bundle_loaded"
            if str(cash.get("status")) == "partial"
            else ("loaded_cash_treatment_evidence" if str(cash.get("status")) == "complete" else "missing_cash_treatment_evidence"),
            "provider": "State + Treasury + State OIG",
            "candidate_series_or_product": "FAM retained-fee authority; CBSP account structure; FAH/FAM USDO collection mechanics; State OIG post-level MRV deposit-route audits",
            "official_source_family": "Public evidence tying retained MRV / CBSP receipts to USDO collection accounts, sweeps, deposit notifications, and reconciliation",
            "intended_use": "Upgrade cash-treatment support from annual retained-account authority to default-grade cash treatment.",
            "notes": str(
                cash.get("next_evidence_needed")
                or "Loaded FAH/FAM and OIG evidence now supports the MRV cash route into USDO operating accounts, but not yet a public MRV-specific transaction-to-Treasury cash mapping."
            ),
        },
        {
            "source_family_key": "legal_remitter_or_debited_account_proof",
            "currently_loaded": False,
            "required_for_default": True,
            "still_missing_for_default": str(remitter.get("status")) != "complete",
            "current_repo_stance": "post_level_route_examples_loaded_but_no_global_default_clearing_remitter_source"
            if str(remitter.get("status")) != "complete"
            else "loaded_public_remitter_or_debited_account_source",
            "provider": "State + State OIG + Treasury",
            "candidate_series_or_product": "FAH/FAM offsite collection mechanics; OIG post-level bank or contractor sweep examples; any public bank MOU or remitter rule",
            "official_source_family": "Public legal-remitter or debited-account evidence for MRV cash receipts",
            "intended_use": "Clear the binding payer-identity blocker for default promotion.",
            "notes": str(
                remitter.get("next_evidence_needed")
                or "Loaded policy and OIG evidence supports the route into USDO accounts, but no public global legal-remitter or debited-account source has been found."
            ),
        },
        {
            "source_family_key": "observed_quarterly_cash_timing_or_remittance_schedule",
            "currently_loaded": False,
            "required_for_default": True,
            "still_missing_for_default": str(timing.get("status")) != "complete",
            "current_repo_stance": "cadence_examples_loaded_but_no_quarterly_cash_series"
            if str(timing.get("status")) != "complete"
            else "loaded_observed_cash_timing",
            "provider": "State + State OIG + Treasury",
            "candidate_series_or_product": "Observed quarterly Treasury cash series, official MRV remittance schedule, or post-level remittance files beyond daily or weekly example cadence",
            "official_source_family": "Public quarterly cash timing or remittance evidence for MRV receipts",
            "intended_use": "Replace the NIV-issuance timing proxy with cash timing that could support default promotion.",
            "notes": str(
                timing.get("next_evidence_needed")
                or "Loaded FAH/FAM and OIG sources support daily, weekly, next-business-day, and short-lag remittance mechanics, but no public quarterly MRV cash series or global remittance schedule has been found."
            ),
        },
    ]
    return pd.DataFrame(rows).reindex(columns=SOURCE_MAP_COLUMNS)


def render_row_mrv_source_map_markdown(source_map: pd.DataFrame) -> str:
    title = "# ROW MRV Source Map"
    intro = (
        "Concrete source roadmap for the MRV-first / CBSP promotion blockers. "
        "This artifact names which official source families are already loaded and which missing source families would actually clear the remaining default blockers."
    )
    if source_map.empty:
        return "\n".join([title, "", intro, "", "No MRV source map is available."])

    header = [
        "| Source family | Loaded? | Required for default | Still missing? | Stance | Provider | Candidate series/product | Intended use | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in source_map.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["source_family_key"]),
                    str(bool(row["currently_loaded"])),
                    str(bool(row["required_for_default"])),
                    str(bool(row["still_missing_for_default"])),
                    str(row["current_repo_stance"]),
                    str(row["provider"]),
                    str(row["candidate_series_or_product"]),
                    str(row["intended_use"]),
                    str(row["notes"]),
                ]
            )
            + " |"
        )

    return "\n".join([title, "", intro, "", *header, *rows, ""])


def write_row_mrv_source_map(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    row_mrv_promotion_checklist: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    source_map = build_row_mrv_source_map(row_mrv_promotion_checklist=row_mrv_promotion_checklist)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    source_map.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_mrv_source_map_markdown(source_map), encoding="utf-8")

    return csv_path, markdown_path, source_map
