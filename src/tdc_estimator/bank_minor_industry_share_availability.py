from __future__ import annotations

from pathlib import Path

import pandas as pd


def _normalize_availability(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    numeric_cols = [
        "tax_year",
        "income_subject_to_tax_thousands",
        "total_income_tax_after_credits_thousands",
    ]
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "usable_for_bank_only_share" in out.columns:
        out["usable_for_bank_only_share"] = out["usable_for_bank_only_share"].astype(str).str.lower().eq("true")
    return out.sort_values(["tax_year", "industry_key"]).reset_index(drop=True)


def build_bank_minor_industry_share_availability(
    availability: pd.DataFrame | None,
) -> pd.DataFrame:
    if availability is None or availability.empty:
        return pd.DataFrame()
    out = _normalize_availability(availability)
    bank_like = out["perimeter_type"].isin(["bank_minor_industry", "bank_holding_minor_industry"])
    out["required_for_bank_only_share"] = bank_like
    out["public_bank_only_share_available"] = bank_like & out["usable_for_bank_only_share"]
    out["review_status"] = out["public_bank_only_share_available"].map(
        lambda flag: "usable_bank_only_minor_industry_row" if flag else "not_usable_for_bank_only_default"
    )
    out["bridge_implication"] = out["required_for_bank_only_share"].map(
        lambda flag: "direct_bank_share_possible" if flag else "context_only"
    )
    return out


def render_bank_minor_industry_share_availability_markdown(availability: pd.DataFrame) -> str:
    title = "# Bank Minor-Industry Share Availability"
    intro = (
        "Official-source check on whether recent IRS Publication 16 Table 5.3 public minor-industry rows are usable "
        "for a bank-only annual corporate-tax share. This artifact is meant to support the bank bridge promotion gate."
    )
    if availability.empty:
        return "\n".join([title, "", intro, "", "No IRS bank minor-industry availability rows are available."])

    latest_year = int(availability["tax_year"].max())
    latest = availability.loc[availability["tax_year"].eq(latest_year)].copy()
    required = latest.loc[latest["required_for_bank_only_share"]].copy()
    usable_count = int(required["public_bank_only_share_available"].sum())
    required_count = int(len(required))
    summary = (
        f"Latest tax year: {latest_year}. "
        f"Usable bank-only rows: {usable_count} of {required_count}. "
        "Current implication: the public Table 5.3 workbook still does not provide a clean bank-only annual share for default promotion."
    )

    header = [
        "| Tax year | Industry | Perimeter | Income subject status | Total tax after credits status | Usable for bank-only share |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in latest.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(int(row["tax_year"])),
                    str(row["industry_label"]),
                    str(row["perimeter_type"]),
                    str(row["income_subject_to_tax_status"]),
                    str(row["total_income_tax_after_credits_status"]),
                    "yes" if bool(row["public_bank_only_share_available"]) else "no",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `commercial_banking`, `savings institutions and other depository credit intermediation`, and `offices of bank holding companies` are the relevant public minor-industry rows for a narrower bank-only share.",
        "- If those rows are suppressed, the repo cannot treat the finance-sector bridge as a bank-only payer measure.",
        "- This artifact supports the `perimeter_contamination` failure in the bank default-readiness gate.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_bank_minor_industry_share_availability(
    *,
    input_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    availability = pd.read_csv(input_path)
    processed = build_bank_minor_industry_share_availability(availability)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    processed.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bank_minor_industry_share_availability_markdown(processed), encoding="utf-8")

    return csv_path, markdown_path, processed
