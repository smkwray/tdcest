from __future__ import annotations

from pathlib import Path

import pandas as pd


ALLOWED_USABLE_CONSTRAINT_STATUSES = {
    "usable_constraint",
    "usable_denominator_constraint",
    "usable_level_constraint_wamest_split_fallback",
}


def _read(path: Path | str) -> pd.DataFrame:
    table = pd.read_csv(path)
    if "date" in table.columns:
        table["date"] = pd.to_datetime(table["date"], errors="coerce").dt.normalize()
    return table


def _sector_constraint(constraints: pd.DataFrame, sector_key: str) -> pd.DataFrame:
    if constraints.empty or "sector_key" not in constraints.columns:
        return pd.DataFrame()
    return constraints.loc[constraints["sector_key"].astype(str).eq(sector_key)].copy()


def _quarter_flags(source: pd.DataFrame, dates: pd.Series, *, require_bill_split: bool = False) -> pd.DataFrame:
    if source.empty:
        return pd.DataFrame(
            {
                "date": dates,
                "has_constraint": False,
                "has_bill_coupon_split": False,
                "has_documented_fallback_split": False,
            }
        )
    usable = source.loc[
        source["constraint_status"].astype(str).isin(ALLOWED_USABLE_CONSTRAINT_STATUSES)
    ].copy()
    usable["date"] = pd.to_datetime(usable["date"], errors="coerce").dt.normalize()
    usable = usable.dropna(subset=["date"])
    usable["has_constraint"] = True
    bill = pd.to_numeric(usable.get("bill_weight_proxy"), errors="coerce")
    coupon = pd.to_numeric(usable.get("coupon_weight_proxy"), errors="coerce")
    usable["has_bill_coupon_split"] = bill.notna() & coupon.notna()
    if "fallback_split_accepted" in usable.columns:
        usable["has_documented_fallback_split"] = usable["fallback_split_accepted"].astype(str).str.lower().isin(
            {"true", "1", "yes"}
        )
    else:
        usable["has_documented_fallback_split"] = False
    out = pd.DataFrame({"date": dates}).merge(
        usable[["date", "has_constraint", "has_bill_coupon_split", "has_documented_fallback_split"]],
        on="date",
        how="left",
    )
    out["has_constraint"] = out["has_constraint"].fillna(False).astype(bool)
    out["has_bill_coupon_split"] = out["has_bill_coupon_split"].fillna(False).astype(bool)
    out["has_documented_fallback_split"] = out["has_documented_fallback_split"].fillna(False).astype(bool)
    if require_bill_split:
        out["has_constraint"] = out["has_constraint"] & (
            out["has_bill_coupon_split"] | out["has_documented_fallback_split"]
        )
    return out


def build_interest_source_window_validation(
    *,
    candidate: pd.DataFrame,
    constraints: pd.DataFrame,
) -> pd.DataFrame:
    if candidate.empty or "date" not in candidate.columns:
        return pd.DataFrame()
    dates = pd.Series(sorted(pd.to_datetime(candidate["date"], errors="coerce").dropna().dt.normalize().unique()))
    out = pd.DataFrame({"date": dates})

    sources = {
        "bank": ("bank_broad_private_depositories_marketable_proxy", True),
        "credit_union": ("credit_unions_marketable_proxy", True),
        "money_market_funds": ("money_market_funds", True),
        "row": ("foreigners_total", True),
    }
    for prefix, (sector_key, require_split) in sources.items():
        flags = _quarter_flags(_sector_constraint(constraints, sector_key), dates, require_bill_split=require_split)
        out[f"{prefix}_has_constraint"] = flags["has_constraint"].to_numpy()
        out[f"{prefix}_has_bill_coupon_split"] = flags["has_bill_coupon_split"].to_numpy()
        out[f"{prefix}_has_documented_fallback_split"] = flags["has_documented_fallback_split"].to_numpy()

    out["promotion_ready_constraint_window"] = (
        out["bank_has_constraint"]
        & out["credit_union_has_constraint"]
        & out["money_market_funds_has_constraint"]
        & out["row_has_constraint"]
    )
    return out


def summarize_interest_source_window_validation(validation: pd.DataFrame) -> str:
    lines = ["# Tier 2 Interest Source Window Validation", ""]
    if validation.empty:
        return "\n".join(lines + ["No validation rows were available."]) + "\n"
    df = validation.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    total = len(df)
    lines.extend(
        [
            f"Candidate window: {df['date'].min().date().isoformat()} through {df['date'].max().date().isoformat()} ({total} quarters).",
            "",
            "| Source | Quarters with usable split | Share |",
            "|---|---:|---:|",
        ]
    )
    for label, column in [
        ("FFIEC bank", "bank_has_constraint"),
        ("NCUA credit union", "credit_union_has_constraint"),
        ("MMF", "money_market_funds_has_constraint"),
        ("TIC SLT ROW", "row_has_constraint"),
    ]:
        count = int(df[column].sum())
        lines.append(f"| {label} | {count} / {total} | {count / total:.1%} |")
    ready = int(df["promotion_ready_constraint_window"].sum())
    fallback_cols = [col for col in df.columns if col.endswith("_has_documented_fallback_split")]
    fallback_quarters = int(df[fallback_cols].any(axis=1).sum()) if fallback_cols else 0
    lines.extend(
        [
            "",
            f"Promotion-ready constraint quarters: {ready} / {total}.",
            f"Quarters using an accepted documented split fallback: {fallback_quarters} / {total}.",
            "",
            "Decision: source-window coverage is promotion-ready only where all required sources have an official split or an accepted documented fallback.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_interest_source_window_validation(
    *,
    candidate_path: Path | str,
    constraints_path: Path | str,
    out_path: Path | str,
    markdown_out_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    validation = build_interest_source_window_validation(
        candidate=_read(candidate_path),
        constraints=_read(constraints_path),
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    validation.to_csv(out, index=False)
    markdown = Path(markdown_out_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(summarize_interest_source_window_validation(validation), encoding="utf-8")
    return out, markdown, validation
