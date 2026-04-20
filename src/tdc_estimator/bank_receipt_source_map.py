from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE_MAP_COLUMNS = [
    "source_family_key",
    "currently_loaded",
    "required_for_current_default",
    "still_missing_for_current_default",
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


def build_bank_receipt_source_map(
    *,
    bank_receipt_default_readiness: pd.DataFrame | None,
    bank_receipt_historical_promotion: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        bank_receipt_default_readiness is None
        or bank_receipt_default_readiness.empty
        or bank_receipt_historical_promotion is None
        or bank_receipt_historical_promotion.empty
    ):
        return pd.DataFrame(columns=SOURCE_MAP_COLUMNS)

    readiness = bank_receipt_default_readiness.copy()
    historical = bank_receipt_historical_promotion.copy().sort_values("quarter_end")

    stale = _get_row(readiness, "check_name", "stale_share_rule")
    perimeter = _get_row(readiness, "check_name", "perimeter_contamination")
    stability = _get_row(readiness, "check_name", "share_stability")
    eligible = historical.loc[historical["share_age_eligible_for_default"].fillna(False)]
    latest_eligible = eligible.iloc[-1] if not eligible.empty else pd.Series(dtype="object")

    rows = [
        {
            "source_family_key": "publication16_table51_bank_minor_history",
            "currently_loaded": str(perimeter.get("status")) == "pass",
            "required_for_current_default": True,
            "still_missing_for_current_default": False,
            "current_repo_stance": "loaded_and_usable_for_historical_window",
            "provider": "IRS",
            "candidate_series_or_product": "Publication 16 Table 5.1 bank-minor shares",
            "official_source_family": "Annual corporation complete-report bank-minor share history",
            "intended_use": "Provide the bank-minor annual share path for the bridge.",
            "notes": (
                f"Latest official public Publication 16 bank-minor continuation remains TY2022, already loaded and usable through the historical age-eligible window ending {pd.Timestamp(latest_eligible['quarter_end']).date().isoformat()}."
                if not latest_eligible.empty
                else "Latest official public Publication 16 bank-minor continuation remains TY2022 and is already loaded for historical bank-share work."
            ),
        },
        {
            "source_family_key": "fresher_public_irs_bank_minor_shares",
            "currently_loaded": False,
            "required_for_current_default": True,
            "still_missing_for_current_default": str(stale.get("status")) != "pass",
            "current_repo_stance": "missing_fresher_public_share_history",
            "provider": "IRS",
            "candidate_series_or_product": "Publication 16 Table 5.1 or equivalent bank-minor rows beyond TY2022",
            "official_source_family": "Public bank-minor annual share history fresher than the current loaded window",
            "intended_use": "Clear the stale-share blocker for current-quarter bank default use.",
            "notes": (
                "Latest official public Corporation Complete Report bank-minor share path remains Publication 16 Table 5.1 through TY2022. "
                + str(
                    stale.get(
                        "details",
                        "Current-quarter bank default remains blocked until a fresher public IRS bank-minor share is available.",
                    )
                )
            ),
        },
        {
            "source_family_key": "table53_bank_minor_c_corp_path",
            "currently_loaded": False,
            "required_for_current_default": False,
            "still_missing_for_current_default": False,
            "current_repo_stance": "blocked_or_rejected_until_unsuppressed",
            "provider": "IRS",
            "candidate_series_or_product": "Publication 16 Table 5.3 bank-minor rows",
            "official_source_family": "Stricter C-corp-only bank-minor annual share path",
            "intended_use": "Potentially cleaner bank-tax perimeter if public rows become usable.",
            "notes": str(
                perimeter.get(
                    "details",
                    "Current public Table 5.3 bank rows remain suppressed or unusable in the latest workbook, so they do not clear the live blocker today.",
                )
            ),
        },
        {
            "source_family_key": "older_or_subset_irs_alternatives",
            "currently_loaded": False,
            "required_for_current_default": False,
            "still_missing_for_current_default": False,
            "current_repo_stance": "nonclearing_alternatives_documented",
            "provider": "IRS",
            "candidate_series_or_product": "Publication 16 Tables 5.2/5.4; Publication 1053 Source Book; Publication 5108 line-item estimates",
            "official_source_family": "Official IRS alternatives that do not solve current-quarter freshness",
            "intended_use": "Document why tempting official alternatives remain sensitivity-only, historical-only, or rejected.",
            "notes": (
                "Tables 5.2 and 5.4 change the population and latest bank-minor values can be disclosure-deleted; "
                "Publication 1053 is older historical detail, and Publication 5108 is not a bank-minor share table."
            ),
        },
        {
            "source_family_key": "share_stability_history",
            "currently_loaded": str(stability.get("status")) in {"warn", "pass"},
            "required_for_current_default": False,
            "still_missing_for_current_default": False,
            "current_repo_stance": "loaded_context_for_policy_review",
            "provider": "IRS",
            "candidate_series_or_product": "Loaded Table 5.1 share history panel",
            "official_source_family": "Annual bank-minor share history summary",
            "intended_use": "Context for deciding whether a fresher share, if found, is policy-usable.",
            "notes": str(stability.get("details", "Share-stability history is already loaded as context.")),
        },
    ]
    return pd.DataFrame(rows).reindex(columns=SOURCE_MAP_COLUMNS)


def render_bank_receipt_source_map_markdown(source_map: pd.DataFrame) -> str:
    title = "# Bank Receipt Source Map"
    intro = (
        "Concrete source roadmap for the bank corporate-tax bridge. "
        "This artifact separates the already loaded historical share path from the missing source family that would actually clear current-quarter bank default use."
    )
    if source_map.empty:
        return "\n".join([title, "", intro, "", "No bank receipt source map is available."])

    header = [
        "| Source family | Loaded? | Required for current default | Still missing? | Stance | Provider | Candidate series/product | Intended use | Notes |",
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
                    str(bool(row["required_for_current_default"])),
                    str(bool(row["still_missing_for_current_default"])),
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


def write_bank_receipt_source_map(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    bank_receipt_default_readiness: pd.DataFrame | None,
    bank_receipt_historical_promotion: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    source_map = build_bank_receipt_source_map(
        bank_receipt_default_readiness=bank_receipt_default_readiness,
        bank_receipt_historical_promotion=bank_receipt_historical_promotion,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    source_map.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bank_receipt_source_map_markdown(source_map), encoding="utf-8")

    return csv_path, markdown_path, source_map
