from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .interest_source_window_validation import ALLOWED_USABLE_CONSTRAINT_STATUSES

from .sector_coupon import (
    DEFAULT_BANK_SECTOR_KEYS,
    DEFAULT_CREDIT_UNION_SECTOR_KEYS,
    DEFAULT_FED_SECTOR_KEYS,
    DEFAULT_ROW_SECTOR_KEYS,
    _build_sector_bill_discount_weight_frame,
    _build_sector_coupon_weight_frame,
    read_sector_maturity_table,
    read_sector_panel_table,
    read_table,
)
from .treasury_interest_components import build_treasury_interest_component_pools_from_file
from .utils import ensure_dir


SECTOR_GROUPS = {
    "bank": tuple(DEFAULT_BANK_SECTOR_KEYS),
    "row": tuple(DEFAULT_ROW_SECTOR_KEYS),
    "credit_union": tuple(DEFAULT_CREDIT_UNION_SECTOR_KEYS),
}

CURRENT_PROXY_COLUMNS = {
    ("bank", "coupon_accrual"): "bank_tsy_coupon_interest_proxy",
    ("row", "coupon_accrual"): "row_tsy_coupon_interest_proxy",
    ("credit_union", "coupon_accrual"): "credit_union_tsy_coupon_interest_proxy",
    ("bank", "bill_amortized_discount"): "bank_tsy_bill_discount_interest_proxy",
    ("row", "bill_amortized_discount"): "row_tsy_bill_discount_interest_proxy",
    ("credit_union", "bill_amortized_discount"): "credit_union_tsy_bill_discount_interest_proxy",
}


def _rename_weight_column(weights: pd.DataFrame, source_column: str, target_column: str) -> pd.DataFrame:
    if weights.empty or source_column not in weights.columns:
        return pd.DataFrame(columns=["date", "sector_key", target_column])
    out = weights.copy()
    rename = {source_column: target_column}
    for suffix in ["_low", "_high"]:
        src = f"{source_column}{suffix}"
        if src in out.columns:
            rename[src] = f"{target_column}{suffix}"
    return out.rename(columns=rename)


def _pool_series(component_pools: pd.DataFrame, flag_column: str) -> pd.Series:
    if component_pools.empty:
        return pd.Series(dtype="float64")
    df = component_pools.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["quarter_expense_mil"] = pd.to_numeric(df["quarter_expense_mil"], errors="coerce")
    mask = df[flag_column].fillna(False).astype(bool)
    out = df.loc[mask].groupby("date")["quarter_expense_mil"].sum(min_count=1).sort_index()
    return out.astype("float64")


def _read_support_series(path: Path | str | None, preferred_column: str | None = None) -> pd.Series:
    if path is None or not Path(path).exists():
        return pd.Series(dtype="float64")
    df = pd.read_csv(path)
    if "date" not in df.columns:
        return pd.Series(dtype="float64")
    value_col = None
    if preferred_column is not None and preferred_column in df.columns:
        value_col = preferred_column
    elif "value" in df.columns:
        value_col = "value"
    else:
        candidates = [col for col in df.columns if col != "date"]
        if candidates:
            value_col = candidates[0]
    if value_col is None:
        return pd.Series(dtype="float64")
    out = pd.Series(
        pd.to_numeric(df[value_col], errors="coerce").values,
        index=pd.to_datetime(df["date"], errors="coerce").dt.normalize(),
        name=value_col,
    )
    return out.dropna().sort_index().astype("float64")


def _current_proxy_map(
    proxy_paths: dict[tuple[str, str], Path | str | None] | None,
) -> dict[tuple[str, str], pd.Series]:
    if not proxy_paths:
        return {}
    out: dict[tuple[str, str], pd.Series] = {}
    for key, path in proxy_paths.items():
        out[key] = _read_support_series(path, CURRENT_PROXY_COLUMNS.get(key))
    return out


def _sector_rows(
    *,
    date: pd.Timestamp,
    component_key: str,
    component_family: str,
    official_pool: float,
    allocation_pool: float,
    weights: pd.DataFrame,
    weight_column: str,
    denominator_sector_keys: set[str],
    sector_groups: dict[str, tuple[str, ...]],
    current_proxies: dict[tuple[str, str], pd.Series],
    allocator_basis: str,
    fed_exact_component_mil: float | None = None,
) -> list[dict[str, object]]:
    denominator = float(weights.loc[weights["sector_key"].isin(denominator_sector_keys), weight_column].sum())
    low_column = f"{weight_column}_low"
    high_column = f"{weight_column}_high"
    has_interval = low_column in weights.columns and high_column in weights.columns
    denominator_low = (
        float(weights.loc[weights["sector_key"].isin(denominator_sector_keys), low_column].sum())
        if has_interval
        else denominator
    )
    denominator_high = (
        float(weights.loc[weights["sector_key"].isin(denominator_sector_keys), high_column].sum())
        if has_interval
        else denominator
    )
    status = "candidate_not_default"
    if denominator <= 0.0:
        status = "missing_or_zero_denominator"

    rows: list[dict[str, object]] = []
    for sector_group, sector_keys in sector_groups.items():
        selected_keys = set(sector_keys)
        selected_weight = float(weights.loc[weights["sector_key"].isin(selected_keys), weight_column].sum())
        selected_low = (
            float(weights.loc[weights["sector_key"].isin(selected_keys), low_column].sum())
            if has_interval
            else selected_weight
        )
        selected_high = (
            float(weights.loc[weights["sector_key"].isin(selected_keys), high_column].sum())
            if has_interval
            else selected_weight
        )
        allocated = allocation_pool * selected_weight / denominator if denominator > 0.0 else pd.NA
        allocated_low = (
            allocation_pool * selected_low / denominator_high
            if denominator_high > 0.0
            else pd.NA
        )
        allocated_high = (
            allocation_pool * selected_high / denominator_low
            if denominator_low > 0.0
            else pd.NA
        )
        proxy = current_proxies.get((sector_group, component_key))
        if proxy is None and component_family == "coupon_accrual":
            proxy = current_proxies.get((sector_group, "coupon_accrual"))
        current_value = (
            float(proxy.reindex([date]).iloc[0])
            if proxy is not None and not proxy.reindex([date]).empty and pd.notna(proxy.reindex([date]).iloc[0])
            else pd.NA
        )
        difference = (
            float(allocated) - float(current_value)
            if pd.notna(allocated) and pd.notna(current_value)
            else pd.NA
        )
        rows.append(
            {
                "date": date,
                "sector_group": sector_group,
                "sector_keys": ",".join(sector_keys),
                "component_key": component_key,
                "component_family": component_family,
                "official_component_pool_mil": official_pool,
                "fed_exact_component_mil": fed_exact_component_mil,
                "allocation_pool_mil": allocation_pool,
                "allocator_basis": allocator_basis,
                "selected_raw_weight_mil": selected_weight,
                "denominator_raw_weight_mil": denominator,
                "component_anchored_interest_mil": allocated,
                "component_anchored_interest_low_mil": allocated_low,
                "component_anchored_interest_high_mil": allocated_high,
                "current_raw_proxy_mil": current_value,
                "difference_from_current_raw_proxy_mil": difference,
                "allocation_status": status,
                "candidate_default_status": "diagnostic_only_live_default_unchanged",
            }
        )
    return rows


def build_tier2_interest_component_candidate(
    *,
    component_pools: pd.DataFrame,
    sector_maturity: pd.DataFrame,
    sector_panel: pd.DataFrame,
    curves: pd.DataFrame,
    bill_wam_support: pd.DataFrame | None = None,
    fed_components: pd.DataFrame | None = None,
    interest_allocation_weights: pd.DataFrame | None = None,
    component_bucket_weights: pd.DataFrame | None = None,
    source_constraints: pd.DataFrame | None = None,
    sector_groups: dict[str, tuple[str, ...]] | None = None,
    fed_sector_keys: Iterable[str] = DEFAULT_FED_SECTOR_KEYS,
    current_proxy_paths: dict[tuple[str, str], Path | str | None] | None = None,
) -> pd.DataFrame:
    groups = sector_groups if sector_groups is not None else SECTOR_GROUPS
    current_proxies = _current_proxy_map(current_proxy_paths)

    coupon_pool = _pool_series(component_pools, "included_in_coupon_pool")
    bill_pool = _pool_series(component_pools, "included_in_bill_discount_pool")
    frn_pool = _pool_series(component_pools, "included_in_frn_pool")
    coupon_weights = _contract_weight_frame(interest_allocation_weights, "coupon_accrual", "raw_coupon_weight")
    bill_weights = _contract_weight_frame(
        interest_allocation_weights,
        "bill_amortized_discount",
        "raw_bill_discount_weight",
    )
    frn_weights = _contract_weight_frame(interest_allocation_weights, "frn_accrued_interest", "raw_frn_weight")
    coupon_allocator_basis = "wamest_interest_contract_central_weight"
    bill_allocator_basis = "wamest_interest_contract_central_weight"
    frn_allocator_basis = "wamest_interest_contract_frn_weight"
    if component_bucket_weights is not None and not component_bucket_weights.empty:
        bucket_coupon = _bucket_weight_frame(
            component_bucket_weights,
            sector_panel,
            "coupon_accrual",
            "raw_coupon_weight",
        )
        bucket_bill = _bucket_weight_frame(
            component_bucket_weights,
            sector_panel,
            "bill_amortized_discount",
            "raw_bill_discount_weight",
        )
        bucket_frn = _bucket_weight_frame(
            component_bucket_weights,
            sector_panel,
            "frn_accrued_interest",
            "raw_frn_weight",
        )
        if not bucket_coupon.empty:
            coupon_weights = _combine_weight_frames(coupon_weights, bucket_coupon, "raw_coupon_weight")
            coupon_allocator_basis = f"{coupon_allocator_basis}_with_bucket_backcast"
        if not bucket_bill.empty:
            bill_weights = _combine_weight_frames(bill_weights, bucket_bill, "raw_bill_discount_weight")
            bill_allocator_basis = f"{bill_allocator_basis}_with_bucket_backcast"
        if not bucket_frn.empty:
            frn_weights = _combine_weight_frames(frn_weights, bucket_frn, "raw_frn_weight")
            frn_allocator_basis = f"{frn_allocator_basis}_with_bucket_backcast"
    if coupon_weights.empty:
        coupon_weights = _build_sector_coupon_weight_frame(sector_maturity, sector_panel, curves)
        coupon_allocator_basis = "official_coupon_pool_allocated_by_current_wamest_h15_coupon_weights"
    if bill_weights.empty:
        bill_weights = _build_sector_bill_discount_weight_frame(sector_maturity, sector_panel, curves, bill_wam_support)
        bill_allocator_basis = "official_bill_pool_allocated_by_current_wamest_h15_bill_weights"
    if frn_weights.empty and not coupon_weights.empty:
        frn_weights = _rename_weight_column(coupon_weights, "raw_coupon_weight", "raw_frn_weight")
        frn_allocator_basis = f"official_frn_pool_allocated_by_coupon_weight_fallback:{coupon_allocator_basis}"
    if source_constraints is not None and not source_constraints.empty:
        coupon_weights, bill_weights = _apply_source_constraints_to_weights(
            coupon_weights,
            bill_weights,
            source_constraints,
        )
        coupon_allocator_basis = f"{coupon_allocator_basis}_with_source_constraints"
        bill_allocator_basis = f"{bill_allocator_basis}_with_source_constraints"
        if frn_allocator_basis.startswith("official_frn_pool_allocated_by_coupon_weight_fallback"):
            frn_weights = _rename_weight_column(coupon_weights, "raw_coupon_weight", "raw_frn_weight")
            frn_allocator_basis = f"official_frn_pool_allocated_by_coupon_weight_fallback:{coupon_allocator_basis}"

    fed_coupon = pd.Series(dtype="float64")
    fed_bill = pd.Series(dtype="float64")
    fed_frn = pd.Series(dtype="float64")
    if fed_components is not None and not fed_components.empty:
        fed_coupon = _series_from_frame(fed_components, "fed_tsy_coupon_interest_proxy")
        fed_bill = _series_from_frame(fed_components, "fed_tsy_bill_discount_interest_proxy")
        fed_frn = _series_from_frame(fed_components, "fed_tsy_frn_interest_proxy")

    fed_keys = set(str(key).strip() for key in fed_sector_keys)
    rows: list[dict[str, object]] = []
    if not coupon_weights.empty:
        for date, frame in coupon_weights.groupby("date", sort=True):
            official_pool = _value_at(coupon_pool, date)
            if official_pool is None:
                continue
            fed_exact = _value_at(fed_coupon, date)
            allocation_pool = max(official_pool - max(fed_exact or 0.0, 0.0), 0.0)
            denominator_keys = set(frame["sector_key"].astype(str).str.strip()) - fed_keys
            rows.extend(
                _sector_rows(
                    date=pd.Timestamp(date).normalize(),
                    component_key="coupon_accrual",
                    component_family="coupon_accrual",
                    official_pool=official_pool,
                    allocation_pool=allocation_pool,
                    weights=frame,
                    weight_column="raw_coupon_weight",
                    denominator_sector_keys=denominator_keys,
                    sector_groups=groups,
                    current_proxies=current_proxies,
                    allocator_basis=coupon_allocator_basis,
                    fed_exact_component_mil=fed_exact,
                )
            )

    if not frn_weights.empty:
        for date, frame in frn_weights.groupby("date", sort=True):
            official_pool = _value_at(frn_pool, date)
            if official_pool is None:
                continue
            fed_exact = _value_at(fed_frn, date)
            allocation_pool = max(official_pool - max(fed_exact or 0.0, 0.0), 0.0)
            denominator_keys = set(frame["sector_key"].astype(str).str.strip()) - fed_keys
            rows.extend(
                _sector_rows(
                    date=pd.Timestamp(date).normalize(),
                    component_key="frn_accrued_interest",
                    component_family="frn_interest",
                    official_pool=official_pool,
                    allocation_pool=allocation_pool,
                    weights=frame,
                    weight_column="raw_frn_weight",
                    denominator_sector_keys=denominator_keys,
                    sector_groups=groups,
                    current_proxies=current_proxies,
                    allocator_basis=frn_allocator_basis,
                    fed_exact_component_mil=fed_exact,
                )
            )

    if not bill_weights.empty:
        for date, frame in bill_weights.groupby("date", sort=True):
            official_pool = _value_at(bill_pool, date)
            if official_pool is None:
                continue
            fed_exact = _value_at(fed_bill, date)
            allocation_pool = max(official_pool - max(fed_exact or 0.0, 0.0), 0.0)
            denominator_keys = set(frame["sector_key"].astype(str).str.strip())
            if fed_exact is not None:
                denominator_keys = denominator_keys - fed_keys
            rows.extend(
                _sector_rows(
                    date=pd.Timestamp(date).normalize(),
                    component_key="bill_amortized_discount",
                    component_family="bill_discount",
                    official_pool=official_pool,
                    allocation_pool=allocation_pool,
                    weights=frame,
                    weight_column="raw_bill_discount_weight",
                    denominator_sector_keys=denominator_keys,
                    sector_groups=groups,
                    current_proxies=current_proxies,
                    allocator_basis=bill_allocator_basis,
                    fed_exact_component_mil=fed_exact,
                )
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "date",
                "sector_group",
                "sector_keys",
                "component_key",
                "component_family",
                "official_component_pool_mil",
                "fed_exact_component_mil",
                "allocation_pool_mil",
                "allocator_basis",
                "selected_raw_weight_mil",
                "denominator_raw_weight_mil",
                "component_anchored_interest_mil",
                "component_anchored_interest_low_mil",
                "component_anchored_interest_high_mil",
                "current_raw_proxy_mil",
                "difference_from_current_raw_proxy_mil",
                "allocation_status",
                "candidate_default_status",
            ]
        )
    return pd.DataFrame(rows).sort_values(["date", "component_key", "sector_group"]).reset_index(drop=True)


def _series_from_frame(df: pd.DataFrame, column: str) -> pd.Series:
    if "date" not in df.columns or column not in df.columns:
        return pd.Series(dtype="float64")
    out = pd.Series(
        pd.to_numeric(df[column], errors="coerce").values,
        index=pd.to_datetime(df["date"], errors="coerce").dt.normalize(),
        name=column,
    )
    return out.dropna().sort_index().astype("float64")


def _contract_weight_frame(
    interest_allocation_weights: pd.DataFrame | None,
    component_key: str,
    out_column: str,
) -> pd.DataFrame:
    if interest_allocation_weights is None or interest_allocation_weights.empty:
        return pd.DataFrame(columns=["date", "sector_key", out_column])
    required = {"date", "sector_key", "component_key", "central_weight"}
    if not required.issubset(interest_allocation_weights.columns):
        return pd.DataFrame(columns=["date", "sector_key", out_column])
    frame = interest_allocation_weights.loc[
        interest_allocation_weights["component_key"].astype(str).eq(component_key),
        ["date", "sector_key", "central_weight"],
    ].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["sector_key"] = frame["sector_key"].astype(str).str.strip()
    frame[out_column] = pd.to_numeric(frame["central_weight"], errors="coerce")
    if "low_weight" in interest_allocation_weights.columns:
        source_low = interest_allocation_weights.loc[
            interest_allocation_weights["component_key"].astype(str).eq(component_key),
            "low_weight",
        ]
        frame[f"{out_column}_low"] = pd.to_numeric(source_low.to_numpy(), errors="coerce")
    if "high_weight" in interest_allocation_weights.columns:
        source_high = interest_allocation_weights.loc[
            interest_allocation_weights["component_key"].astype(str).eq(component_key),
            "high_weight",
        ]
        frame[f"{out_column}_high"] = pd.to_numeric(source_high.to_numpy(), errors="coerce")
    columns = ["date", "sector_key", out_column]
    for interval_column in [f"{out_column}_low", f"{out_column}_high"]:
        if interval_column in frame.columns:
            frame[interval_column] = frame[interval_column].fillna(frame[out_column])
            columns.append(interval_column)
    return frame.dropna(subset=["date", "sector_key", out_column]).loc[:, columns]


def _bucket_weight_frame(
    component_bucket_weights: pd.DataFrame | None,
    sector_panel: pd.DataFrame,
    component_key: str,
    out_column: str,
) -> pd.DataFrame:
    if component_bucket_weights is None or component_bucket_weights.empty:
        return pd.DataFrame(columns=["date", "sector_key", out_column])
    required = {"date", "sector_key", "component_key", "bucket_weight"}
    if not required.issubset(component_bucket_weights.columns):
        return pd.DataFrame(columns=["date", "sector_key", out_column])
    if sector_panel.empty or not {"date", "sector_key", "level"}.issubset(sector_panel.columns):
        return pd.DataFrame(columns=["date", "sector_key", out_column])

    panel = sector_panel.loc[:, ["date", "sector_key", "level"]].copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel["sector_key"] = panel["sector_key"].astype(str).str.strip()
    panel["level"] = pd.to_numeric(panel["level"], errors="coerce")

    buckets = component_bucket_weights.loc[
        component_bucket_weights["component_key"].astype(str).eq(component_key),
        ["date", "sector_key", "bucket_weight"],
    ].copy()
    buckets["date"] = pd.to_datetime(buckets["date"], errors="coerce").dt.normalize()
    buckets["sector_key"] = buckets["sector_key"].astype(str).str.strip()
    buckets["bucket_weight"] = pd.to_numeric(buckets["bucket_weight"], errors="coerce")

    merged = buckets.merge(panel, on=["date", "sector_key"], how="left")
    merged[out_column] = merged["bucket_weight"] * merged["level"]
    return (
        merged.dropna(subset=["date", "sector_key", out_column])
        .loc[:, ["date", "sector_key", out_column]]
        .sort_values(["date", "sector_key"])
        .reset_index(drop=True)
    )


def _combine_weight_frames(primary: pd.DataFrame, fallback: pd.DataFrame, weight_column: str) -> pd.DataFrame:
    if fallback.empty:
        return primary
    if primary.empty:
        return fallback
    left = primary.copy()
    right = fallback.copy()
    left["date"] = pd.to_datetime(left["date"], errors="coerce").dt.normalize()
    right["date"] = pd.to_datetime(right["date"], errors="coerce").dt.normalize()
    left["sector_key"] = left["sector_key"].astype(str).str.strip()
    right["sector_key"] = right["sector_key"].astype(str).str.strip()
    primary_keys = set(zip(left["date"], left["sector_key"], strict=False))
    right_keys = pd.Series(list(zip(right["date"], right["sector_key"], strict=False)), index=right.index)
    right = right.loc[~right_keys.isin(primary_keys)].copy()

    columns = ["date", "sector_key", weight_column]
    for interval_column in [f"{weight_column}_low", f"{weight_column}_high"]:
        if interval_column in left.columns or interval_column in right.columns:
            if interval_column not in left.columns:
                left[interval_column] = left[weight_column]
            if interval_column not in right.columns:
                right[interval_column] = right[weight_column]
            columns.append(interval_column)
    return pd.concat([left.loc[:, columns], right.loc[:, columns]], ignore_index=True).sort_values(
        ["date", "sector_key"]
    )


def _constraint_targets(sector_key: str) -> tuple[str, ...]:
    if sector_key == "bank_broad_private_depositories_marketable_proxy":
        return tuple(DEFAULT_BANK_SECTOR_KEYS)
    return (sector_key,)


def _apply_component_constraint(
    weights: pd.DataFrame,
    *,
    date: pd.Timestamp,
    sector_keys: tuple[str, ...],
    value: float,
    weight_column: str,
) -> pd.DataFrame:
    if weights.empty or pd.isna(value):
        return weights
    out = weights.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    mask = out["date"].eq(date) & out["sector_key"].astype(str).isin(sector_keys)
    if not mask.any():
        return out
    current = pd.to_numeric(out.loc[mask, weight_column], errors="coerce").fillna(0.0)
    total = float(current.sum())
    shares = current / total if total > 0 else pd.Series(1.0 / len(current), index=current.index)
    out.loc[mask, weight_column] = shares.to_numpy() * float(value)
    for suffix in ["_low", "_high"]:
        column = f"{weight_column}{suffix}"
        if column in out.columns:
            out.loc[mask, column] = out.loc[mask, weight_column]
    return out


def _apply_source_constraints_to_weights(
    coupon_weights: pd.DataFrame,
    bill_weights: pd.DataFrame,
    source_constraints: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    constraints = source_constraints.copy()
    if "date" not in constraints.columns or "sector_key" not in constraints.columns:
        return coupon_weights, bill_weights
    constraints["date"] = pd.to_datetime(constraints["date"], errors="coerce").dt.normalize()
    for _, row in constraints.dropna(subset=["date", "sector_key"]).iterrows():
        status = str(row.get("constraint_status", ""))
        if status not in ALLOWED_USABLE_CONSTRAINT_STATUSES:
            continue
        level = pd.to_numeric(pd.Series([row.get("level_mil")]), errors="coerce").iloc[0]
        bill_share = pd.to_numeric(pd.Series([row.get("bill_weight_proxy")]), errors="coerce").iloc[0]
        coupon_share = pd.to_numeric(pd.Series([row.get("coupon_weight_proxy")]), errors="coerce").iloc[0]
        if pd.isna(level):
            continue
        targets = _constraint_targets(str(row["sector_key"]))
        date = pd.Timestamp(row["date"]).normalize()
        fallback_accepted = str(row.get("fallback_split_accepted", "")).lower() in {"true", "1", "yes"}
        if (pd.isna(bill_share) or pd.isna(coupon_share)) and fallback_accepted:
            current_bill = _current_component_weight(
                bill_weights,
                date=date,
                sector_keys=targets,
                weight_column="raw_bill_discount_weight",
            )
            current_coupon = _current_component_weight(
                coupon_weights,
                date=date,
                sector_keys=targets,
                weight_column="raw_coupon_weight",
            )
            current_total = current_bill + current_coupon
            if current_total <= 0.0:
                continue
            bill_share = current_bill / current_total
            coupon_share = current_coupon / current_total
        if pd.isna(bill_share) or pd.isna(coupon_share):
            continue
        # `tier2_interest_source_constraints.csv` stores all source levels in
        # millions of dollars (`level_mil`). Keep those units when replacing
        # WAMEST weights; another /1000 would make constrained sectors
        # artificially tiny beside the residual WAMEST denominator.
        weight_level = float(level)
        bill_weights = _apply_component_constraint(
            bill_weights,
            date=date,
            sector_keys=targets,
            value=weight_level * float(bill_share),
            weight_column="raw_bill_discount_weight",
        )
        coupon_weights = _apply_component_constraint(
            coupon_weights,
            date=date,
            sector_keys=targets,
            value=weight_level * float(coupon_share),
            weight_column="raw_coupon_weight",
        )
    return coupon_weights, bill_weights


def _current_component_weight(
    weights: pd.DataFrame,
    *,
    date: pd.Timestamp,
    sector_keys: tuple[str, ...],
    weight_column: str,
) -> float:
    if weights.empty or weight_column not in weights.columns:
        return 0.0
    work = weights.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    mask = work["date"].eq(date) & work["sector_key"].astype(str).isin(sector_keys)
    if not mask.any():
        return 0.0
    return float(pd.to_numeric(work.loc[mask, weight_column], errors="coerce").fillna(0.0).sum())


def _value_at(series: pd.Series, date: object) -> float | None:
    if series.empty:
        return None
    key = pd.Timestamp(date).normalize()
    values = series.reindex([key])
    if values.empty or pd.isna(values.iloc[0]):
        return None
    return float(values.iloc[0])


def summarize_tier2_interest_component_candidate(candidate: pd.DataFrame) -> str:
    lines = ["# Tier 2 Interest Component Candidate", ""]
    if candidate.empty:
        return "\n".join(lines + ["No candidate rows were available."]) + "\n"

    df = candidate.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    latest = df["date"].max()
    latest_rows = df[df["date"].eq(latest)]
    pivot = latest_rows.pivot_table(
        index="sector_group",
        columns="component_key",
        values="component_anchored_interest_mil",
        aggfunc="sum",
    ).fillna(0.0)
    for column in ["coupon_accrual", "bill_amortized_discount", "frn_accrued_interest"]:
        if column not in pivot.columns:
            pivot[column] = 0.0
    pivot["candidate_total_mil"] = (
        pivot["coupon_accrual"] + pivot["bill_amortized_discount"] + pivot["frn_accrued_interest"]
    )
    totals = latest_rows.groupby("sector_group").agg(
        candidate_total_low_mil=("component_anchored_interest_low_mil", "sum"),
        candidate_total_high_mil=("component_anchored_interest_high_mil", "sum"),
    )
    pivot = pivot.join(totals, how="left")

    lines.extend(
        [
            f"Coverage runs from {df['date'].min().date().isoformat()} through {latest.date().isoformat()}.",
            "",
            (
                "This is a diagnostic candidate. It allocates official Treasury interest-expense component "
                "pools with WAMEST interest-contract weights when available, otherwise current WAMEST/H.15 "
                "weights. It does not replace live Tier 2 defaults."
            ),
            "",
            f"Latest-quarter read ({latest.date().isoformat()}):",
            "",
            "| Sector | Coupon accrual (mil) | Bill discount (mil) | FRN interest (mil) | Candidate total (mil) | Range (mil) |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for sector, row in pivot.sort_index().iterrows():
        low = row.get("candidate_total_low_mil")
        high = row.get("candidate_total_high_mil")
        range_text = "NA" if pd.isna(low) or pd.isna(high) else f"${low:,.0f} - ${high:,.0f}"
        lines.append(
            f"| {sector} | ${row['coupon_accrual']:,.0f} | "
            f"${row['bill_amortized_discount']:,.0f} | ${row['frn_accrued_interest']:,.0f} | "
            f"${row['candidate_total_mil']:,.0f} | {range_text} |"
        )
    lines.extend(
        [
            "",
            "Promotion note: this table is useful for scale comparison only.",
            (
                "When `tier2_interest_source_constraints.csv` is present, usable FFIEC, NCUA, MMF, and TIC "
                "constraints override matching first-pass WAMEST weights."
            ),
            (
                "The remaining method blocker is TIPS-compensation treatment; FRN interest is allocated as a "
                "separate component using the current coupon-weight fallback until FRN-specific holder weights exist."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def build_tier2_interest_component_candidate_from_files(
    *,
    treasury_interest_path: Path | str,
    sector_maturity_path: Path | str,
    sector_panel_path: Path | str,
    curve_path: Path | str,
    bill_wam_path: Path | str | None = None,
    fed_components_path: Path | str | None = None,
    interest_allocation_weights_path: Path | str | None = None,
    component_bucket_weights_path: Path | str | None = None,
    source_constraints_path: Path | str | None = None,
    current_proxy_paths: dict[tuple[str, str], Path | str | None] | None = None,
) -> pd.DataFrame:
    bill_wam_support = read_table(bill_wam_path) if bill_wam_path is not None and Path(bill_wam_path).exists() else None
    fed_components = (
        pd.read_csv(fed_components_path)
        if fed_components_path is not None and Path(fed_components_path).exists()
        else None
    )
    interest_allocation_weights = (
        pd.read_csv(interest_allocation_weights_path)
        if interest_allocation_weights_path is not None and Path(interest_allocation_weights_path).exists()
        else None
    )
    component_bucket_weights = (
        pd.read_csv(component_bucket_weights_path)
        if component_bucket_weights_path is not None and Path(component_bucket_weights_path).exists()
        else None
    )
    source_constraints = (
        pd.read_csv(source_constraints_path)
        if source_constraints_path is not None and Path(source_constraints_path).exists()
        else None
    )
    return build_tier2_interest_component_candidate(
        component_pools=build_treasury_interest_component_pools_from_file(treasury_interest_path),
        sector_maturity=read_sector_maturity_table(sector_maturity_path),
        sector_panel=read_sector_panel_table(sector_panel_path),
        curves=read_table(curve_path),
        bill_wam_support=bill_wam_support,
        fed_components=fed_components,
        interest_allocation_weights=interest_allocation_weights,
        component_bucket_weights=component_bucket_weights,
        source_constraints=source_constraints,
        current_proxy_paths=current_proxy_paths,
    )


def write_tier2_interest_component_candidate(
    *,
    treasury_interest_path: Path | str,
    sector_maturity_path: Path | str,
    sector_panel_path: Path | str,
    curve_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str | None = None,
    bill_wam_path: Path | str | None = None,
    fed_components_path: Path | str | None = None,
    interest_allocation_weights_path: Path | str | None = None,
    component_bucket_weights_path: Path | str | None = None,
    source_constraints_path: Path | str | None = None,
    current_proxy_paths: dict[tuple[str, str], Path | str | None] | None = None,
) -> tuple[Path, Path | None]:
    candidate = build_tier2_interest_component_candidate_from_files(
        treasury_interest_path=treasury_interest_path,
        sector_maturity_path=sector_maturity_path,
        sector_panel_path=sector_panel_path,
        curve_path=curve_path,
        bill_wam_path=bill_wam_path,
        fed_components_path=fed_components_path,
        interest_allocation_weights_path=interest_allocation_weights_path,
        component_bucket_weights_path=component_bucket_weights_path,
        source_constraints_path=source_constraints_path,
        current_proxy_paths=current_proxy_paths,
    )
    csv_path = Path(out_csv_path)
    ensure_dir(csv_path.parent)
    candidate.to_csv(csv_path, index=False)

    markdown_path = Path(out_markdown_path) if out_markdown_path is not None else None
    if markdown_path is not None:
        ensure_dir(markdown_path.parent)
        markdown_path.write_text(summarize_tier2_interest_component_candidate(candidate), encoding="utf-8")
    return csv_path, markdown_path
