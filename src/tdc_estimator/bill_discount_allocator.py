from __future__ import annotations

from pathlib import Path

import pandas as pd

from .bill_discount_validation import (
    BANK_PROXY_COLUMN,
    BILL_DISCOUNT_BENCHMARK_COLUMN,
    CREDIT_UNION_PROXY_COLUMN,
    ROW_PROXY_COLUMN,
    build_bill_discount_validation_from_files,
)
from .utils import ensure_dir


SECTOR_COLUMNS = {
    "bank": BANK_PROXY_COLUMN,
    "row": ROW_PROXY_COLUMN,
    "credit_union": CREDIT_UNION_PROXY_COLUMN,
}


def build_bill_discount_allocation_table(validation: pd.DataFrame) -> pd.DataFrame:
    if validation.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "sector_key",
                "allocation_basis",
                "bill_discount_proxy_mil",
                "official_bill_discount_pool_mil",
                "proxy_share_of_official_pool",
                "is_selected_tier2_subtraction_sector",
                "allocation_status",
                "allocation_note",
            ]
        )

    df = validation.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df[BILL_DISCOUNT_BENCHMARK_COLUMN] = pd.to_numeric(df[BILL_DISCOUNT_BENCHMARK_COLUMN], errors="coerce")
    rows: list[dict[str, object]] = []

    for _, row in df.dropna(subset=["date"]).iterrows():
        pool = row.get(BILL_DISCOUNT_BENCHMARK_COLUMN)
        sector_sum = 0.0
        has_any_sector = False
        for sector_key, column in SECTOR_COLUMNS.items():
            value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
            if pd.notna(value):
                sector_sum += float(value)
                has_any_sector = True
            share = float(value) / float(pool) if pd.notna(value) and pd.notna(pool) and float(pool) != 0 else pd.NA
            rows.append(
                {
                    "date": row["date"],
                    "sector_key": sector_key,
                    "allocation_basis": "current_wamest_h15_bill_proxy",
                    "bill_discount_proxy_mil": value,
                    "official_bill_discount_pool_mil": pool,
                    "proxy_share_of_official_pool": share,
                    "is_selected_tier2_subtraction_sector": True,
                    "allocation_status": "partial_proxy_slice",
                    "allocation_note": (
                        "Current sector proxy is treated as a partial holder slice of the official bill "
                        "discount pool, not as a full-pool allocation weight."
                    ),
                }
            )

        residual = float(pool) - sector_sum if pd.notna(pool) and has_any_sector else pd.NA
        residual_share = (
            float(residual) / float(pool)
            if pd.notna(residual) and pd.notna(pool) and float(pool) != 0
            else pd.NA
        )
        residual_status = (
            "negative_residual_review"
            if pd.notna(residual) and float(residual) < -1e-9
            else "explicit_unallocated_residual"
        )
        rows.append(
            {
                "date": row["date"],
                "sector_key": "unallocated_residual",
                "allocation_basis": "official_pool_minus_current_selected_sector_proxies",
                "bill_discount_proxy_mil": residual,
                "official_bill_discount_pool_mil": pool,
                "proxy_share_of_official_pool": residual_share,
                "is_selected_tier2_subtraction_sector": False,
                "allocation_status": residual_status,
                "allocation_note": (
                    "Residual prevents bank/ROW/credit-union sectors from being renormalized to the full "
                    "official bill discount pool without MMF and domestic residual holder weights."
                ),
            }
        )

    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    return out.sort_values(["date", "sector_key"]).reset_index(drop=True)


def summarize_bill_discount_allocation(allocation: pd.DataFrame) -> str:
    lines = ["# Bill-Discount Allocation Diagnostic", ""]
    if allocation.empty:
        return "\n".join(lines + ["No allocation rows were available."]) + "\n"

    df = allocation.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    latest_pool_date = df.loc[df["official_bill_discount_pool_mil"].notna(), "date"].max()
    latest_pool = df[df["date"].eq(latest_pool_date)]
    latest_pool_label = latest_pool_date.date().isoformat()
    pool = latest_pool["official_bill_discount_pool_mil"].dropna()
    pool_value = float(pool.iloc[0]) if not pool.empty else float("nan")
    selected_mask = df["is_selected_tier2_subtraction_sector"].fillna(False)
    overlap_dates = df.loc[
        selected_mask & df["official_bill_discount_pool_mil"].notna() & df["bill_discount_proxy_mil"].notna(),
        "date",
    ]
    latest_overlap_date = overlap_dates.max() if not overlap_dates.empty else pd.NaT
    latest = df[df["date"].eq(latest_overlap_date)] if pd.notna(latest_overlap_date) else pd.DataFrame()
    latest_label = latest_overlap_date.date().isoformat() if pd.notna(latest_overlap_date) else "NA"
    selected = latest[latest["is_selected_tier2_subtraction_sector"].fillna(False)] if not latest.empty else latest
    selected_sum = selected["bill_discount_proxy_mil"].sum(skipna=True)
    residual = latest.loc[latest["sector_key"].eq("unallocated_residual"), "bill_discount_proxy_mil"]
    residual_value = float(residual.iloc[0]) if not residual.empty and pd.notna(residual.iloc[0]) else float("nan")
    overlap_pool = selected["official_bill_discount_pool_mil"].dropna()
    overlap_pool_value = float(overlap_pool.iloc[0]) if not overlap_pool.empty else float("nan")
    selected_share = selected_sum / overlap_pool_value if overlap_pool_value else float("nan")

    lines.extend(
        [
            (
                f"Latest official Treasury bill amortized-discount pool is "
                f"${pool_value:,.0f} million in {latest_pool_label}."
            ),
            "",
            (
                f"Latest overlapping sector-proxy quarter is {latest_label}; current bank + ROW + "
                f"credit-union proxies sum to ${selected_sum:,.0f} million "
                f"({selected_share:.1%} of that quarter's official pool)."
            ),
            "",
            f"Explicit unallocated residual is ${residual_value:,.0f} million.",
            "",
            "Interpretation: this diagnostic keeps current selected-sector bill-discount proxies as partial slices.",
            "It deliberately does not renormalize bank, ROW, and credit-union proxies to the whole official pool.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_bill_discount_allocation_from_files(
    *,
    treasury_interest_path: Path | str,
    bank_proxy_path: Path | str,
    row_proxy_path: Path | str,
    credit_union_proxy_path: Path | str,
) -> pd.DataFrame:
    validation = build_bill_discount_validation_from_files(
        treasury_interest_path=treasury_interest_path,
        bank_proxy_path=bank_proxy_path,
        row_proxy_path=row_proxy_path,
        credit_union_proxy_path=credit_union_proxy_path,
    )
    return build_bill_discount_allocation_table(validation)


def write_bill_discount_allocation(
    *,
    treasury_interest_path: Path | str,
    bank_proxy_path: Path | str,
    row_proxy_path: Path | str,
    credit_union_proxy_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None]:
    allocation = build_bill_discount_allocation_from_files(
        treasury_interest_path=treasury_interest_path,
        bank_proxy_path=bank_proxy_path,
        row_proxy_path=row_proxy_path,
        credit_union_proxy_path=credit_union_proxy_path,
    )
    csv_path = Path(out_csv_path)
    ensure_dir(csv_path.parent)
    allocation.to_csv(csv_path, index=False)

    markdown_path = Path(out_markdown_path) if out_markdown_path is not None else None
    if markdown_path is not None:
        ensure_dir(markdown_path.parent)
        markdown_path.write_text(summarize_bill_discount_allocation(allocation), encoding="utf-8")
    return csv_path, markdown_path
