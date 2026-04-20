from __future__ import annotations

from pathlib import Path

import pandas as pd


CROSSWALK_COLUMNS = [
    "date",
    "fiscal_year",
    "counterparty_group",
    "receipt_line_item_nm",
    "receipt_amt_mil",
    "aid_cd",
    "a_cd",
    "main_cd",
    "sub_cd",
    "account_code",
    "candidate_family",
    "promotion_priority",
    "default_blocker",
    "budget_treatment_guess",
    "combined_statement_title",
    "combined_statement_amt_mil",
    "combined_statement_metric_basis",
    "combined_statement_match_scope",
    "combined_statement_match_level",
    "match_status",
    "amount_alignment_status",
    "source_coverage_status",
]


def _normalize_code(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "null":
        return ""
    if text.isdigit():
        return str(int(text))
    return text


def _account_code(row: pd.Series) -> str:
    return "-".join(
        [
            _normalize_code(row.get("aid_cd")),
            _normalize_code(row.get("a_cd")),
            _normalize_code(row.get("main_cd")),
            _normalize_code(row.get("sub_cd")),
        ]
    )


def _load_combined_statement_accounts(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path).copy()
    rename_map = {
        "record_fiscal_year": "fiscal_year",
        "receipt_line_item_nm": "combined_statement_title",
        "amount_mil": "combined_statement_amt_mil",
        "receipt_amt_mil": "combined_statement_amt_mil",
    }
    df = df.rename(columns=rename_map)
    required = {
        "fiscal_year",
        "aid_cd",
        "a_cd",
        "main_cd",
        "sub_cd",
        "combined_statement_title",
        "combined_statement_amt_mil",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Combined Statement support file {path} is missing required columns: {missing}")

    extra_cols = [col for col in ["combined_statement_metric_basis", "combined_statement_match_scope"] if col in df.columns]
    out = df.loc[:, sorted(required) + extra_cols].copy()
    out["fiscal_year"] = pd.to_numeric(out["fiscal_year"], errors="coerce").astype("Int64")
    for col in ["aid_cd", "a_cd", "main_cd", "sub_cd", "combined_statement_title"]:
        out[col] = out[col].map(_normalize_code)
    out["combined_statement_amt_mil"] = pd.to_numeric(out["combined_statement_amt_mil"], errors="coerce")
    if "combined_statement_metric_basis" not in out.columns:
        out["combined_statement_metric_basis"] = "receipt_amount_mil"
    if "combined_statement_match_scope" not in out.columns:
        out["combined_statement_match_scope"] = "exact_account"
    out["account_code"] = out.apply(_account_code, axis=1)
    return out


def _match_status(receipt_title: str, combined_title: str | None, match_level: str) -> str:
    if not combined_title:
        return "combined_statement_unmatched"
    if match_level == "main_account_rollup":
        return "main_account_rollup_match"
    if receipt_title.strip().lower() == combined_title.strip().lower():
        return "exact_code_exact_title_match"
    return "exact_code_title_mismatch"


def _amount_alignment_status(
    receipt_amt: float,
    combined_amt: float | None,
    *,
    match_level: str,
    metric_basis: str,
    match_scope: str,
) -> str:
    if combined_amt is None or pd.isna(combined_amt):
        return "combined_statement_amount_unavailable"
    if match_level != "exact_account":
        return "aggregate_context_not_receipt_comparable"
    if metric_basis != "receipt_amount_mil" or match_scope != "exact_account":
        return "nonreceipt_metric_context"
    if receipt_amt == 0 and combined_amt == 0:
        return "exact_zero_alignment"
    diff = abs(float(receipt_amt) - float(combined_amt))
    scale = max(abs(float(receipt_amt)), abs(float(combined_amt)), 1.0)
    ratio = diff / scale
    if ratio <= 0.001:
        return "exact_or_near_exact_alignment"
    if ratio <= 0.05:
        return "moderate_alignment"
    return "divergent_amounts"


def build_receipt_account_crosswalk(
    receipt_account_candidates: pd.DataFrame | None,
    *,
    combined_statement_accounts_path: Path | str | None = None,
) -> pd.DataFrame:
    if receipt_account_candidates is None or receipt_account_candidates.empty:
        return pd.DataFrame(columns=CROSSWALK_COLUMNS)

    candidates = receipt_account_candidates.copy()
    candidates["date"] = pd.to_datetime(candidates["date"])
    for col in ["aid_cd", "a_cd", "main_cd", "sub_cd"]:
        candidates[col] = candidates[col].map(_normalize_code)
    candidates["account_code"] = candidates.apply(_account_code, axis=1)

    combined = None
    if combined_statement_accounts_path is not None and Path(combined_statement_accounts_path).exists():
        combined = _load_combined_statement_accounts(combined_statement_accounts_path)

    rows: list[dict[str, object]] = []
    for _, row in candidates.iterrows():
        combined_row = None
        match_level = "unmatched"
        if combined is not None:
            matches = combined.loc[
                combined["fiscal_year"].eq(row["fiscal_year"]) & combined["account_code"].eq(row["account_code"])
            ]
            if not matches.empty:
                combined_row = matches.sort_values("combined_statement_amt_mil", ascending=False).iloc[0]
                match_level = "exact_account"
            else:
                main_matches = combined.loc[
                    combined["fiscal_year"].eq(row["fiscal_year"])
                    & combined["aid_cd"].eq(row["aid_cd"])
                    & combined["main_cd"].eq(row["main_cd"])
                ]
                if not main_matches.empty:
                    combined_row = main_matches.sort_values("combined_statement_amt_mil", ascending=False).iloc[0]
                    match_level = "main_account_rollup"

        combined_title = None if combined_row is None else combined_row["combined_statement_title"]
        combined_amt = None if combined_row is None else combined_row["combined_statement_amt_mil"]
        combined_metric_basis = None if combined_row is None else combined_row.get("combined_statement_metric_basis")
        combined_match_scope = None if combined_row is None else combined_row.get("combined_statement_match_scope")
        rows.append(
            {
                "date": row["date"],
                "fiscal_year": row["fiscal_year"],
                "counterparty_group": row["counterparty_group"],
                "receipt_line_item_nm": row["receipt_line_item_nm"],
                "receipt_amt_mil": row["receipt_amt_mil"],
                "aid_cd": row["aid_cd"],
                "a_cd": row["a_cd"],
                "main_cd": row["main_cd"],
                "sub_cd": row["sub_cd"],
                "account_code": row["account_code"],
                "candidate_family": row.get("candidate_family"),
                "promotion_priority": row.get("promotion_priority"),
                "default_blocker": row.get("default_blocker"),
                "budget_treatment_guess": row.get("budget_treatment_guess"),
                "combined_statement_title": combined_title,
                "combined_statement_amt_mil": combined_amt,
                "combined_statement_metric_basis": combined_metric_basis,
                "combined_statement_match_scope": combined_match_scope,
                "combined_statement_match_level": match_level,
                "match_status": (
                    _match_status(
                        str(row["receipt_line_item_nm"]),
                        None if combined_title is None else str(combined_title),
                        match_level,
                    )
                    if combined is not None
                    else "no_combined_statement_support_loaded"
                ),
                "amount_alignment_status": (
                    _amount_alignment_status(
                        float(row["receipt_amt_mil"]),
                        None if combined_amt is None else float(combined_amt),
                        match_level=match_level,
                        metric_basis="receipt_amount_mil" if combined_metric_basis is None else str(combined_metric_basis),
                        match_scope="exact_account" if combined_match_scope is None else str(combined_match_scope),
                    )
                    if combined is not None
                    else "no_combined_statement_support_loaded"
                ),
                "source_coverage_status": (
                    "receipts_by_department_plus_combined_statement"
                    if combined is not None
                    else "receipts_by_department_only"
                ),
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(["date", "counterparty_group", "receipt_amt_mil"], ascending=[False, True, False]).reset_index(drop=True)
    return out.reindex(columns=CROSSWALK_COLUMNS)


def render_receipt_account_crosswalk_markdown(crosswalk: pd.DataFrame) -> str:
    title = "# Receipt Account Crosswalk"
    intro = (
        "Annual account crosswalk around the Treasury receipt candidate bridge. "
        "This artifact keeps `Receipts by Department` as the backbone and adds `Combined Statement` matching when a "
        "normalized local support file is available."
    )
    if crosswalk.empty:
        return "\n".join([title, "", intro, "", "No receipt-account crosswalk rows are available."])

    latest_date = pd.Timestamp(crosswalk["date"].max())
    latest = crosswalk.loc[crosswalk["date"].eq(latest_date)].copy()
    with_combined = latest.loc[latest["match_status"].ne("no_combined_statement_support_loaded")]
    summary = (
        f"Latest fiscal year-end in view: {latest_date.date().isoformat()}. "
        f"Rows in scope: {len(latest)}. "
        f"Source coverage: {latest['source_coverage_status'].mode().iloc[0]}."
    )
    if not with_combined.empty:
        exact_count = int(with_combined["match_status"].eq("exact_code_exact_title_match").sum())
        summary += f" Exact-code exact-title matches in latest year: {exact_count}."

    header = [
        "| Fiscal year-end | Account code | Receipt title | Candidate family | RBD amount (mil) | Combined Statement amount (mil) | Match level | Match | Amount alignment |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in latest.head(20).iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    str(row["account_code"]),
                    str(row["receipt_line_item_nm"]),
                    str(row["candidate_family"]),
                    f"{float(row['receipt_amt_mil']):,.3f}",
                    "n/a" if pd.isna(row["combined_statement_amt_mil"]) else f"{float(row['combined_statement_amt_mil']):,.3f}",
                    str(row["combined_statement_match_level"]),
                    str(row["match_status"]),
                    str(row["amount_alignment_status"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `receipts_by_department_only` means the crosswalk is ready for Combined Statement support, but no normalized support file is loaded yet.",
        "- `exact_code_exact_title_match` is the strongest annual account-system alignment currently tracked here.",
        "- `main_account_rollup_match` means the Combined Statement confirms the broader department/main-account family, but not the exact receipt sub-account line.",
        "- This crosswalk improves annual account reconciliation; it does not solve payer identity or quarterly cash timing by itself.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_receipt_account_crosswalk(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    receipt_account_candidates: pd.DataFrame | None,
    combined_statement_accounts_path: Path | str | None = None,
) -> tuple[Path, Path, pd.DataFrame]:
    crosswalk = build_receipt_account_crosswalk(
        receipt_account_candidates,
        combined_statement_accounts_path=combined_statement_accounts_path,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_receipt_account_crosswalk_markdown(crosswalk), encoding="utf-8")

    return csv_path, markdown_path, crosswalk
