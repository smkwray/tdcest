from __future__ import annotations

from pathlib import Path

import pandas as pd

from .utils import ensure_dir


REQUIRED_COLUMNS = {
    "record_date",
    "expense_catg_desc",
    "expense_group_desc",
    "expense_type_desc",
    "month_expense_amt",
}


def _norm(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().casefold().split())


def _component_key(expense_group: str, expense_type: str) -> str:
    group = _norm(expense_group)
    typ = _norm(expense_type)

    if group == "amortized discount" and typ == "treasury bills":
        return "bill_amortized_discount"
    if group == "accrued interest expense" and typ == "treasury notes":
        return "notes_accrued_interest"
    if group == "accrued interest expense" and typ == "treasury bonds":
        return "bonds_accrued_interest"
    if group == "accrued interest expense" and typ == "inflation protected securities (tips)":
        return "tips_accrued_interest"
    if group == "accrued interest expense" and typ == "int. expense inflation compensation (tips)":
        return "tips_inflation_compensation"
    if group == "accrued interest expense" and typ == "treasury floating rate notes (frn)":
        return "frn_accrued_interest"
    if group == "amortized discount":
        return "other_amortized_discount"
    if group == "amortized premium":
        return "other_amortized_premium"
    if group == "accrued interest expense":
        return "other_accrued_interest"
    return "other_interest_expense"


def _component_family(component_key: str) -> str:
    if component_key == "bill_amortized_discount":
        return "bill_discount"
    if component_key in {
        "notes_accrued_interest",
        "bonds_accrued_interest",
        "tips_accrued_interest",
    }:
        return "coupon_accrual"
    if component_key == "frn_accrued_interest":
        return "frn_interest"
    if component_key == "tips_inflation_compensation":
        return "tips_inflation_compensation"
    if component_key == "other_amortized_discount":
        return "other_discount"
    if component_key == "other_amortized_premium":
        return "other_premium"
    if component_key == "other_accrued_interest":
        return "other_accrual"
    return "other"


def _default_tier2_pool_role(component_key: str, category: str) -> str:
    if _norm(category) != "interest expense on public issues":
        return "exclude_non_public_issue_or_nonmarketable"
    if component_key == "bill_amortized_discount":
        return "bill_discount_anchor_candidate"
    if component_key in {"notes_accrued_interest", "bonds_accrued_interest", "tips_accrued_interest"}:
        return "coupon_accrual_anchor_candidate"
    if component_key == "frn_accrued_interest":
        return "frn_anchor_candidate"
    if component_key == "tips_inflation_compensation":
        return "separate_nondefault_tips_inflation_compensation"
    if component_key in {"other_amortized_discount", "other_amortized_premium"}:
        return "separate_nondefault_premium_discount_component"
    return "exclude_or_review"


def _is_marketable_treasury_public_issue(category: object, expense_type: object) -> bool:
    if _norm(category) != "interest expense on public issues":
        return False
    typ = _norm(expense_type)
    return typ in {
        "treasury bills",
        "treasury notes",
        "treasury bonds",
        "treasury floating rate notes (frn)",
        "inflation protected securities (tips)",
        "treasury inflation protected securities (tips)",
        "int. expense inflation compensation (tips)",
    }


def _treatment_note(component_key: str, category: str, expense_type: str) -> str:
    if _norm(category) != "interest expense on public issues":
        return "Excluded from the marketable-public-issue Tier 2 component anchor frame."
    if not _is_marketable_treasury_public_issue(category, expense_type):
        return "Public-issue row is outside the marketable Treasury instrument frame for Tier 2 allocation."
    notes = {
        "bill_amortized_discount": (
            "Official public-issue Treasury bill amortized-discount pool; keep separate from coupon accrual."
        ),
        "notes_accrued_interest": (
            "Official public-issue Treasury note accrued-interest pool; coupon-accrual anchor candidate."
        ),
        "bonds_accrued_interest": (
            "Official public-issue Treasury bond accrued-interest pool; coupon-accrual anchor candidate."
        ),
        "tips_accrued_interest": (
            "Official public-issue TIPS accrued-interest pool; keep separate from TIPS inflation compensation."
        ),
        "tips_inflation_compensation": (
            "TIPS inflation compensation is not ordinary coupon cashflow; keep nondefault until the Tier 2 "
            "target explicitly includes it."
        ),
        "frn_accrued_interest": (
            "Official public-issue FRN accrued-interest pool; separate from fixed-rate coupon instruments."
        ),
        "other_amortized_discount": "Other discount amortization; review before inclusion to avoid component overlap.",
        "other_amortized_premium": "Other premium amortization; review before inclusion to avoid component overlap.",
        "other_accrued_interest": "Other public-issue accrued interest; review before inclusion.",
    }
    return notes.get(component_key, "Public-issue interest row requires review before Tier 2 inclusion.")


def build_treasury_interest_component_pools(treasury_interest_expense: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(treasury_interest_expense.columns)
    if missing:
        raise ValueError("Treasury interest expense data missing required columns: " + ", ".join(sorted(missing)))

    df = treasury_interest_expense.copy()
    df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce")
    df["month_expense_amt"] = pd.to_numeric(df["month_expense_amt"], errors="coerce")
    df = df.dropna(subset=["record_date", "month_expense_amt"])
    if df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "expense_catg_desc",
                "expense_group_desc",
                "expense_type_desc",
                "component_key",
                "component_family",
                "quarter_expense_mil",
                "included_in_marketable_public_issue_pool",
                "included_in_coupon_pool",
                "included_in_bill_discount_pool",
                "included_in_tips_inflation_comp_pool",
                "included_in_frn_pool",
                "default_tier2_pool_role",
                "treatment_note",
            ]
        )

    for col in ["expense_catg_desc", "expense_group_desc", "expense_type_desc"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    df["component_key"] = [
        _component_key(group, typ)
        for group, typ in zip(df["expense_group_desc"], df["expense_type_desc"], strict=False)
    ]
    df["component_family"] = df["component_key"].map(_component_family)
    df["date"] = df["record_date"].dt.to_period("Q").dt.end_time.dt.normalize()

    grouped = (
        df.groupby(
            [
                "date",
                "expense_catg_desc",
                "expense_group_desc",
                "expense_type_desc",
                "component_key",
                "component_family",
            ],
            dropna=False,
            as_index=False,
        )["month_expense_amt"]
        .sum()
        .rename(columns={"month_expense_amt": "quarter_expense_amt"})
    )
    grouped["quarter_expense_mil"] = grouped["quarter_expense_amt"] / 1_000_000.0
    grouped = grouped.drop(columns=["quarter_expense_amt"])

    grouped["included_in_marketable_public_issue_pool"] = [
        _is_marketable_treasury_public_issue(category, typ)
        for category, typ in zip(grouped["expense_catg_desc"], grouped["expense_type_desc"], strict=False)
    ]
    grouped["included_in_coupon_pool"] = grouped["component_key"].isin(
        ["notes_accrued_interest", "bonds_accrued_interest", "tips_accrued_interest"]
    ) & grouped["included_in_marketable_public_issue_pool"]
    grouped["included_in_bill_discount_pool"] = grouped["component_key"].eq("bill_amortized_discount") & grouped[
        "included_in_marketable_public_issue_pool"
    ]
    grouped["included_in_tips_inflation_comp_pool"] = grouped["component_key"].eq(
        "tips_inflation_compensation"
    ) & grouped["included_in_marketable_public_issue_pool"]
    grouped["included_in_frn_pool"] = grouped["component_key"].eq("frn_accrued_interest") & grouped[
        "included_in_marketable_public_issue_pool"
    ]
    grouped["default_tier2_pool_role"] = [
        (
            _default_tier2_pool_role(component, category)
            if included
            else "exclude_nonmarketable_or_non_treasury_public_issue"
        )
        for component, category, included in zip(
            grouped["component_key"],
            grouped["expense_catg_desc"],
            grouped["included_in_marketable_public_issue_pool"],
            strict=False,
        )
    ]
    grouped["treatment_note"] = [
        _treatment_note(component, category, typ)
        for component, category, typ in zip(
            grouped["component_key"],
            grouped["expense_catg_desc"],
            grouped["expense_type_desc"],
            strict=False,
        )
    ]

    ordered = [
        "date",
        "expense_catg_desc",
        "expense_group_desc",
        "expense_type_desc",
        "component_key",
        "component_family",
        "quarter_expense_mil",
        "included_in_marketable_public_issue_pool",
        "included_in_coupon_pool",
        "included_in_bill_discount_pool",
        "included_in_tips_inflation_comp_pool",
        "included_in_frn_pool",
        "default_tier2_pool_role",
        "treatment_note",
    ]
    return grouped.loc[:, ordered].sort_values(["date", "component_key", "expense_type_desc"]).reset_index(drop=True)


def summarize_treasury_interest_component_pools(component_pools: pd.DataFrame) -> str:
    lines = ["# Treasury Interest Component Pools", ""]
    if component_pools.empty:
        return "\n".join(lines + ["No component rows were available."]) + "\n"

    df = component_pools.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    first = df["date"].min().date().isoformat()
    latest = df["date"].max().date().isoformat()
    latest_rows = df[df["date"].eq(df["date"].max())]

    def _sum(flag: str) -> float:
        return float(latest_rows.loc[latest_rows[flag].fillna(False), "quarter_expense_mil"].sum())

    public_issue = float(
        latest_rows.loc[
            latest_rows["included_in_marketable_public_issue_pool"].fillna(False), "quarter_expense_mil"
        ].sum()
    )
    coupon = _sum("included_in_coupon_pool")
    bills = _sum("included_in_bill_discount_pool")
    tips_comp = _sum("included_in_tips_inflation_comp_pool")
    frn = _sum("included_in_frn_pool")

    lines.extend(
        [
            f"Coverage runs from {first} through {latest}.",
            "",
            (
                f"Latest quarter ({latest}) marketable Treasury public-issue components total "
                f"${public_issue:,.0f} million."
            ),
            "",
            "| Latest-quarter component pool | Amount (mil) |",
            "| --- | ---: |",
            f"| Coupon-accrual anchor candidates | ${coupon:,.0f} |",
            f"| Treasury bill amortized discount | ${bills:,.0f} |",
            f"| FRN accrued interest | ${frn:,.0f} |",
            f"| TIPS inflation compensation | ${tips_comp:,.0f} |",
            "",
            "Interpretation: this is an official interest-expense component ledger, not a holder-sector allocation.",
            "It is the diagnostic base for replacing broad/gross Tier 2 anchors with instrument-separated pools.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_treasury_interest_component_pools_from_file(treasury_interest_path: Path | str) -> pd.DataFrame:
    return build_treasury_interest_component_pools(pd.read_csv(treasury_interest_path))


def write_treasury_interest_component_pools(
    *,
    treasury_interest_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None]:
    pools = build_treasury_interest_component_pools_from_file(treasury_interest_path)
    csv_path = Path(out_csv_path)
    ensure_dir(csv_path.parent)
    pools.to_csv(csv_path, index=False)

    markdown_path = Path(out_markdown_path) if out_markdown_path is not None else None
    if markdown_path is not None:
        ensure_dir(markdown_path.parent)
        markdown_path.write_text(summarize_treasury_interest_component_pools(pools), encoding="utf-8")
    return csv_path, markdown_path
