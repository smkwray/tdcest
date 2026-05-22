from __future__ import annotations

from pathlib import Path

import pandas as pd


CU_SPLIT_COMPONENTS = {"coupon_accrual", "bill_amortized_discount"}


def _read(path: Path | str) -> pd.DataFrame:
    return pd.read_csv(path)


def _format_mil(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"${float(value):,.0f}"


def build_tier2_cu_split_sensitivity(
    *,
    candidate: pd.DataFrame,
    ncua_constraints: pd.DataFrame,
) -> pd.DataFrame:
    if candidate.empty or ncua_constraints.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "component_key",
                "current_selected_raw_weight_mil",
                "alternative_selected_raw_weight_mil",
                "current_denominator_raw_weight_mil",
                "alternative_denominator_raw_weight_mil",
                "allocation_pool_mil",
                "current_component_anchored_interest_mil",
                "alternative_component_anchored_interest_mil",
                "alternative_minus_current_mil",
                "current_cu_bill_share",
                "alternative_cu_bill_share",
                "sensitivity_status",
                "sensitivity_basis",
            ]
        )

    cand = candidate.copy()
    cand["date"] = pd.to_datetime(cand["date"], errors="coerce").dt.normalize()
    cand = cand.loc[
        cand["sector_group"].astype(str).eq("credit_union")
        & cand["component_key"].astype(str).isin(CU_SPLIT_COMPONENTS)
    ].copy()
    for column in [
        "selected_raw_weight_mil",
        "denominator_raw_weight_mil",
        "allocation_pool_mil",
        "component_anchored_interest_mil",
    ]:
        cand[column] = pd.to_numeric(cand[column], errors="coerce")
    cand = cand.dropna(subset=["date", "selected_raw_weight_mil", "denominator_raw_weight_mil"])
    if cand.empty:
        return pd.DataFrame()

    ncua = ncua_constraints.copy()
    ncua["date"] = pd.to_datetime(ncua["date"], errors="coerce").dt.normalize()
    if "investment_short_share_le_1y" not in ncua.columns:
        ncua["investment_short_share_le_1y"] = pd.NA
    if "total_treasuries_level_proxy" not in ncua.columns:
        ncua["total_treasuries_level_proxy"] = pd.NA
    ncua["investment_short_share_le_1y"] = pd.to_numeric(ncua["investment_short_share_le_1y"], errors="coerce")
    ncua["total_treasuries_level_proxy"] = pd.to_numeric(ncua["total_treasuries_level_proxy"], errors="coerce")
    ncua = ncua.dropna(subset=["date", "investment_short_share_le_1y", "total_treasuries_level_proxy"])
    ncua = ncua.loc[ncua["investment_short_share_le_1y"].between(0.0, 1.0, inclusive="both")].copy()
    if ncua.empty:
        return pd.DataFrame()

    split = ncua.loc[:, ["date", "investment_short_share_le_1y", "total_treasuries_level_proxy"]].drop_duplicates(
        subset=["date"], keep="last"
    )
    # Existing component-candidate constraints convert NCUA dollar levels to
    # millions, then divide by 1000 to match the WAMEST raw-weight scale.
    split["cu_level_raw_weight_mil"] = split["total_treasuries_level_proxy"] / 1_000_000.0 / 1000.0

    current_split = cand.pivot_table(
        index="date",
        columns="component_key",
        values="selected_raw_weight_mil",
        aggfunc="sum",
    )
    current_split["current_cu_bill_share"] = current_split.get("bill_amortized_discount", 0.0) / (
        current_split.get("bill_amortized_discount", 0.0) + current_split.get("coupon_accrual", 0.0)
    )
    cand = cand.merge(current_split[["current_cu_bill_share"]].reset_index(), on="date", how="left")
    cand = cand.merge(split, on="date", how="inner")

    shares = {
        "bill_amortized_discount": cand["investment_short_share_le_1y"],
        "coupon_accrual": 1.0 - cand["investment_short_share_le_1y"],
    }
    alt_share = pd.Series(index=cand.index, dtype="float64")
    for component_key, share in shares.items():
        alt_share.loc[cand["component_key"].eq(component_key)] = share.loc[cand["component_key"].eq(component_key)]
    cand["alternative_selected_raw_weight_mil"] = cand["cu_level_raw_weight_mil"] * alt_share
    cand["alternative_denominator_raw_weight_mil"] = (
        cand["denominator_raw_weight_mil"]
        - cand["selected_raw_weight_mil"]
        + cand["alternative_selected_raw_weight_mil"]
    )
    cand["alternative_component_anchored_interest_mil"] = cand["allocation_pool_mil"] * (
        cand["alternative_selected_raw_weight_mil"] / cand["alternative_denominator_raw_weight_mil"]
    )
    cand["alternative_minus_current_mil"] = (
        cand["alternative_component_anchored_interest_mil"] - cand["component_anchored_interest_mil"]
    )
    cand["sensitivity_status"] = "sensitivity_not_default"
    cand["sensitivity_basis"] = (
        "ncua_broad_all_investment_le_1y_share_applied_to_cu_treasury_level;"
        "not_treasury_specific_maturity_evidence"
    )

    out = cand.rename(
        columns={
            "selected_raw_weight_mil": "current_selected_raw_weight_mil",
            "denominator_raw_weight_mil": "current_denominator_raw_weight_mil",
            "component_anchored_interest_mil": "current_component_anchored_interest_mil",
            "investment_short_share_le_1y": "alternative_cu_bill_share",
        }
    )
    ordered = [
        "date",
        "component_key",
        "current_selected_raw_weight_mil",
        "alternative_selected_raw_weight_mil",
        "current_denominator_raw_weight_mil",
        "alternative_denominator_raw_weight_mil",
        "allocation_pool_mil",
        "current_component_anchored_interest_mil",
        "alternative_component_anchored_interest_mil",
        "alternative_minus_current_mil",
        "current_cu_bill_share",
        "alternative_cu_bill_share",
        "sensitivity_status",
        "sensitivity_basis",
    ]
    return out.loc[:, ordered].sort_values(["date", "component_key"]).reset_index(drop=True)


def summarize_tier2_cu_split_sensitivity(frame: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 CU Split Sensitivity",
        "",
        "This diagnostic compares the current CU WAMEST bill/coupon split fallback with a nondefault alternative that applies NCUA's broad all-investment <=1y share to the CU Treasury level.",
        "",
    ]
    if frame.empty:
        return "\n".join(lines + ["No comparable CU split rows were available."]) + "\n"

    df = frame.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    latest = df["date"].max()
    latest_rows = df.loc[df["date"].eq(latest)].copy()
    current_total = latest_rows["current_component_anchored_interest_mil"].sum()
    alternative_total = latest_rows["alternative_component_anchored_interest_mil"].sum()
    delta_total = latest_rows["alternative_minus_current_mil"].sum()
    bill_row = latest_rows.loc[latest_rows["component_key"].eq("bill_amortized_discount")]
    current_bill_share = bill_row["current_cu_bill_share"].iloc[0] if not bill_row.empty else pd.NA
    alternative_bill_share = bill_row["alternative_cu_bill_share"].iloc[0] if not bill_row.empty else pd.NA

    lines.extend(
        [
            f"Latest quarter: {latest.date().isoformat()}.",
            "",
            f"Current CU coupon+bill correction: {_format_mil(current_total)} million.",
            f"NCUA broad-ladder alternative: {_format_mil(alternative_total)} million.",
            f"Alternative minus current: {_format_mil(delta_total)} million.",
            f"Current implied CU bill share: {float(current_bill_share):.1%}.",
            f"NCUA broad all-investment <=1y share: {float(alternative_bill_share):.1%}.",
            "",
            "| Component | Current (mil) | Alternative (mil) | Alt minus current (mil) |",
            "|---|---:|---:|---:|",
        ]
    )
    for _, row in latest_rows.iterrows():
        lines.append(
            "| {component} | {current} | {alternative} | {delta} |".format(
                component=row["component_key"],
                current=_format_mil(row["current_component_anchored_interest_mil"]),
                alternative=_format_mil(row["alternative_component_anchored_interest_mil"]),
                delta=_format_mil(row["alternative_minus_current_mil"]),
            )
        )
    lines.extend(
        [
            "",
            "Interpretation: this narrows the CU blocker by quantifying it. The alternative is not promoted to default because NCUA's available maturity ladder is for total investments, not Treasury-specific holdings.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tier2_cu_split_sensitivity(
    *,
    candidate_path: Path | str,
    ncua_constraints_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_tier2_cu_split_sensitivity(
        candidate=_read(candidate_path),
        ncua_constraints=_read(ncua_constraints_path),
    )
    csv_path = Path(out_csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)
    markdown_path = Path(out_markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(summarize_tier2_cu_split_sensitivity(frame), encoding="utf-8")
    return csv_path, markdown_path, frame
