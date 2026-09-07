"""Frozen, nondefault component-allocation sensitivity; no source acquisition."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .fed_coupon import (
    estimate_quarterly_fed_coupon_interest_from_soma_snapshots,
    prepare_soma_holdings,
)
from .interest_source_window_validation import ALLOWED_USABLE_CONSTRAINT_STATUSES
from .sector_coupon import read_sector_panel_table
from .tier2_interest_component_candidate import (
    SECTOR_GROUPS,
    _constraint_targets,
    _sector_rows,
    build_tier2_interest_component_candidate,
)
from .tier2_regression_series import build_regression_leg_table
from .treasury_interest_components import build_treasury_interest_component_pools

DATES = pd.date_range("2022-03-31", "2025-12-31", freq="QE")
TOLERANCE = 1e-6  # Arithmetic readback tolerance in USD millions, not source resolution.
COMPONENTS = {
    "coupon_accrual": ("fixed_coupon_share", ("notes_accrued_interest", "bonds_accrued_interest"), "fixed_coupon"),
    "tips_accrued_interest": ("tips_share", ("tips_accrued_interest",), "fed_tsy_tips_coupon_interest_proxy"),
    "bill_amortized_discount": ("bill_share", ("bill_amortized_discount",), "fed_tsy_bill_discount_interest_proxy"),
    "frn_accrued_interest": ("frn_share", ("frn_accrued_interest",), "fed_tsy_frn_interest_proxy"),
}
PARITY_COLUMNS = (
    "selected_raw_weight_mil", "denominator_raw_weight_mil", "official_component_pool_mil",
    "fed_exact_component_mil", "allocation_pool_mil", "component_anchored_interest_mil",
)
CLAIM = "Nondefault 2022Q1-2025Q4 allocation sensitivity; no backcast, coefficient refit, or canonical refresh."


def _window(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"], errors="raise").dt.normalize()
    work = work[work.date.isin(DATES)].copy()
    if work.duplicated(["date", *keys]).any():
        raise ValueError(f"Duplicate comparison input cells: {keys}")
    if not pd.DatetimeIndex(work.date.unique()).sort_values().equals(DATES):
        raise ValueError("Comparison requires all 16 certified quarters")
    return work


def _finite(frame: pd.DataFrame, columns: list[str]) -> None:
    if not np.isfinite(frame[columns].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)).all():
        raise ValueError(f"Nonfinite comparison values: {columns}")


def assert_baseline_parity(retained: pd.DataFrame, rebuilt: pd.DataFrame) -> dict:
    keys = ["date", "sector_group", "component_key"]
    merged = retained.merge(rebuilt, on=keys, how="outer", validate="one_to_one", indicator=True,
                            suffixes=("_retained", "_rebuilt"))
    if len(merged) != len(DATES) * len(SECTOR_GROUPS) * 3 or not merged._merge.eq("both").all():
        raise ValueError("Historical baseline component grid differs")
    gaps = {}
    missing = {}
    for column in PARITY_COLUMNS:
        cols = [f"{column}_retained", f"{column}_rebuilt"]
        cells = merged[cols]
        if column == "fed_exact_component_mil":
            if not cells[cols[0]].isna().equals(cells[cols[1]].isna()):
                raise ValueError("Historical Fed missingness differs")
            missing[column] = int(cells[cols[0]].isna().sum())
            cells = cells.dropna()
        _finite(cells, cols)
        gap = float((cells[cols[0]] - cells[cols[1]]).abs().max())
        if gap > TOLERANCE:
            raise ValueError(f"Historical baseline parity failed: {column} gap={gap}")
        gaps[column] = gap
    return {"rows": len(merged), "max_absolute_gaps_usd_million": gaps,
            "matched_missing_cells": missing, "historical_missing_fed_rule": "Legacy allocator used zero; preserved only to reproduce history, not admitted as an observation"}


def partition_fed_schedule(soma: pd.DataFrame, fed: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Zero other coupons on the complete grid; never filter snapshot dates or par."""
    prepared = prepare_soma_holdings(soma)
    if prepared.empty:
        raise ValueError("Missing retained SOMA schedule")
    # Re-express the accepted scheduler's input names after preparation.
    prepared["coupon"] = prepared.coupon_rate_pct
    prepared["security_type"] = prepared.security_text
    total = estimate_quarterly_fed_coupon_interest_from_soma_snapshots(prepared).reindex(DATES)
    pieces = {}
    for kind in ("coupon", "tips", "frn"):
        selected = prepared.copy()
        selected.loc[selected.instrument_type.ne(kind), "coupon"] = 0.0
        schedule = estimate_quarterly_fed_coupon_interest_from_soma_snapshots(selected)
        # A wholly zero coupon schedule has no payment records by construction.
        if selected.coupon.eq(0).all():
            schedule = pd.Series(0.0, index=DATES)
        pieces[kind] = schedule.reindex(DATES)
    partition = pd.DataFrame(pieces, index=DATES)
    partition["retained_generic"] = fed.set_index("date").fed_tsy_coupon_interest_proxy
    partition["recomputed_generic"] = total
    _finite(partition, list(partition.columns))
    gaps = {
        "retained_generic": float((total - partition.retained_generic).abs().max()),
        "instrument_sum": float((partition[["coupon", "tips", "frn"]].sum(axis=1) - total).abs().max()),
    }
    if max(gaps.values()) > TOLERANCE:
        raise ValueError(f"Retained Fed generic schedule does not reproduce: {gaps}")
    partition.index.name = "date"
    return partition.reset_index(), gaps


def corrected_exposures(canonical: pd.DataFrame, weights: pd.DataFrame,
                        constraints: pd.DataFrame, *, expected_holders: pd.DataFrame) -> pd.DataFrame:
    """Keep residual exposure unassigned under both level and bill constraints."""
    shares = [v[0] for v in COMPONENTS.values()] + ["other_residual_share"]
    keys = ["date", "sector_key"]
    if set(map(tuple, canonical[keys].to_numpy())) != set(map(tuple, expected_holders[keys].to_numpy())):
        raise ValueError("Holder grid differs from frozen historical contract")
    flags = weights.eligible_for_gross_interest.astype(str).str.lower()
    if not flags.isin(["true", "false"]).all():
        raise ValueError("Malformed gross eligibility flag")
    if weights.groupby(keys).eligible_for_gross_interest.nunique().ne(1).any():
        raise ValueError("Inconsistent component eligibility")
    if set(map(tuple, canonical[keys].to_numpy())) != set(map(tuple, weights[keys].to_numpy())):
        raise ValueError("Canonical/weight holder grid differs")
    eligible = flags.eq("true")
    admitted = weights.loc[eligible]
    if not {s for group in SECTOR_GROUPS.values() for s in group}.issubset(set(admitted.sector_key)):
        raise ValueError("Required allocation recipient missing from gross holders")
    expected_keys = pd.MultiIndex.from_frame(admitted[keys].drop_duplicates())
    if admitted.groupby("sector_key").date.nunique().ne(len(DATES)).any():
        raise ValueError("Incomplete eligible holder date grid")
    canonical = canonical.merge(admitted[keys].drop_duplicates(), on=keys, validate="one_to_one")
    _finite(canonical, ["level", *shares])
    if (canonical[["level", *shares]] < -1e-12).any().any():
        raise ValueError("Negative canonical gross level or share")
    if not np.allclose(canonical[shares].sum(axis=1), 1.0, atol=1e-8, rtol=0):
        raise ValueError("Canonical instrument shares do not add to one")
    if not admitted.weight_class.eq("gross_long_holder_amount").all():
        raise ValueError("Inconsistent gross eligibility classification")
    amounts = admitted[admitted.component_key.isin(COMPONENTS)].pivot(
        index=["date", "sector_key"], columns="component_key", values="gross_interest_weight")
    if not expected_keys.sort_values().equals(amounts.index.sort_values()) or set(amounts.columns) != set(COMPONENTS):
        raise ValueError("Missing eligible component grid")
    amounts = amounts[list(COMPONENTS)].reset_index()
    result = canonical.merge(amounts, on=["date", "sector_key"], how="inner", validate="one_to_one")
    _finite(result, list(COMPONENTS))
    for component, (share, _, _) in COMPONENTS.items():
        if not np.allclose(result[component], result.level * result[share], atol=TOLERANCE, rtol=0):
            raise ValueError(f"Corrected exposure differs from canonical composition: {component}")
    result["unassigned_residual"] = result.level * result.other_residual_share
    result["constraint_application"] = "none"
    result["constraint_source_level_mil"] = np.nan
    constrained = set()
    for _, source in constraints.iterrows():
        if source.constraint_status not in ALLOWED_USABLE_CONSTRAINT_STATUSES:
            continue
        targets = _constraint_targets(str(source.sector_key))
        cells = {(source.date, target) for target in targets}
        if constrained & cells:
            raise ValueError("Overlapping usable source constraints")
        constrained.update(cells)
        mask = result.date.eq(source.date) & result.sector_key.isin(targets)
        if set(result.loc[mask, "sector_key"]) != set(targets):
            raise ValueError(f"Constraint targets missing from gross-holder grid: {targets}")
        level = float(source.level_mil)
        old_level = float(result.loc[mask, "level"].sum())
        if not np.isfinite(level) or level < 0 or old_level <= 0:
            raise ValueError("Invalid constraint level")
        amount_cols = [*COMPONENTS, "unassigned_residual"]
        if source.constraint_status == "usable_level_constraint_wamest_split_fallback":
            if str(source.fallback_split_accepted).lower() != "true":
                raise ValueError("Unaccepted source-level fallback")
            result.loc[mask, amount_cols] *= level / old_level
            role = "source_level_over_canonical_level; residual_unassigned; existing_group_perimeter_assumed"
        elif source.constraint_status == "usable_denominator_constraint" and source.sector_key == "money_market_funds":
            bill = float(source.bill_weight_proxy)
            if not np.isfinite(bill) or not 0 <= bill <= 1 or mask.sum() != 1:
                raise ValueError("Invalid observed MMF bill share")
            nonbill_cols = [c for c in amount_cols if c != "bill_amortized_discount"]
            nonbill = float(result.loc[mask, nonbill_cols].sum(axis=1).iloc[0])
            if nonbill <= 0:
                raise ValueError("MMF nonbill composition unavailable")
            result.loc[mask, "bill_amortized_discount"] = level * bill
            result.loc[mask, nonbill_cols] *= level * (1 - bill) / nonbill
            role = "observed_bill; inferred_nonbill_split_including_unassigned_residual"
        else:
            raise ValueError("Unsupported corrected constraint semantics")
        result.loc[mask, "constraint_application"] = role
        result.loc[mask, "constraint_source_level_mil"] = level
        if abs(float(result.loc[mask, amount_cols].to_numpy().sum()) - level) > TOLERANCE:
            raise ValueError("Constrained exposure plus unassigned residual fails level reconciliation")
    return result


def residual_only_contracts(old_weights: pd.DataFrame, old_buckets: pd.DataFrame,
                            new_weights: pd.DataFrame, new_buckets: pd.DataFrame,
                            canonical: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The retained scalar bucket schema has exactly one named share per component."""
    expected = {"coupon_accrual": "fixed_coupon_share", "tips_accrued_interest": "tips_share"}
    for source, labels in [(new_buckets, expected), (old_buckets, {"coupon_accrual": "coupon_accrual_pool_share_excluding_frn"})]:
        subset = source[source.component_key.isin(labels)]
        if subset.duplicated(["date", "sector_key", "component_key"]).any():
            raise ValueError("Residual-only comparison requires one scalar bucket per component")
        if any(not rows.bucket_key.eq(labels[key]).all() for key, rows in subset.groupby("component_key")):
            raise ValueError("Unexpected scalar bucket identity")
    outputs = []
    for original, source, columns in [
        (old_weights, new_weights, ["gross_interest_weight"]),
        (old_buckets, new_buckets, ["bucket_weight"]),
    ]:
        target = original.copy()
        bucket = columns == ["bucket_weight"]
        value = "bucket_weight" if bucket else "central_weight"
        other = original[original.component_key.isin(["bill_amortized_discount", "frn_accrued_interest"])]
        joined = other.merge(source, on=["date", "sector_key", "component_key"], how="outer",
                             suffixes=("_old", "_new"), indicator=True)
        joined = joined[joined.component_key.isin(["bill_amortized_discount", "frn_accrued_interest"])]
        if not joined._merge.eq("both").all() or not np.allclose(joined[value+"_old"], joined[value+"_new"], atol=TOLERANCE, rtol=0):
            raise ValueError("Noncoupon exposure changed in residual-only comparison")
        named = source[source.component_key.isin(expected)].groupby(["date", "sector_key"])[value].sum(min_count=1)
        old = original[original.component_key.eq("coupon_accrual")].set_index(["date", "sector_key"])[value]
        residual = canonical.set_index(["date", "sector_key"]).other_residual_share
        if not bucket:
            residual = residual * canonical.set_index(["date", "sector_key"]).level
        if not old.index.sort_values().equals(named.index.sort_values()) or not np.allclose(
                old - named.reindex(old.index), residual.reindex(old.index), atol=TOLERANCE, rtol=0):
            raise ValueError("Coupon change is not exactly canonical residual exposure")
        source = source[source.component_key.isin(expected)]
        if source.groupby(["date", "sector_key"]).component_key.nunique().ne(2).any():
            raise ValueError("Missing fixed/TIPS pooled exposure")
        combined = source.groupby(["date", "sector_key"])[columns].sum(min_count=1)
        mask = target.component_key.eq("coupon_accrual")
        keys = pd.MultiIndex.from_frame(target.loc[mask, ["date", "sector_key"]])
        if not keys.sort_values().equals(combined.index.sort_values()):
            raise ValueError("Pooled coupon holder grid differs")
        target.loc[mask, columns] = combined.reindex(keys).to_numpy()
        outputs.append(target)
    return tuple(outputs)


def allocate_corrected(pools: pd.DataFrame, exposures: pd.DataFrame, fed: pd.DataFrame,
                       partition: pd.DataFrame) -> pd.DataFrame:
    fed = fed.merge(partition[["date", "coupon"]].rename(columns={"coupon": "fixed_coupon"}),
                    on="date", validate="one_to_one").set_index("date")
    rows = []
    for component, (_, pool_keys, fed_key) in COMPONENTS.items():
        official = pools[pools.included_in_marketable_public_issue_pool & pools.component_key.isin(pool_keys)]
        expected = {(date, key) for date in DATES for key in pool_keys}
        if set(zip(official.date, official.component_key)) != expected:
            raise ValueError(f"Missing component payment pool: {component}")
        _finite(official, ["quarter_expense_mil"])
        official = official.groupby("date").quarter_expense_mil.sum(min_count=1)
        for date, frame in exposures.groupby("date"):
            total, fed_amount = float(official.loc[date]), float(fed.loc[date, fed_key])
            missing_fed = np.isnan(fed_amount)
            if (not np.isfinite(total) or total < 0 or not missing_fed and
                    (not np.isfinite(fed_amount) or fed_amount < 0 or fed_amount > total)):
                raise ValueError(f"Invalid matched official/Fed payment pool: {component} {date}")
            weights = frame[["date", "sector_key", component]].rename(columns={component: "weight"})
            denominator = set(frame.sector_key) - {"fed"}
            if weights.loc[weights.sector_key.isin(denominator), "weight"].sum() <= 0:
                raise ValueError("Nonpositive corrected allocation denominator")
            allocated = _sector_rows(date=date, component_key=component, component_family=component,
                                     official_pool=total, allocation_pool=total-fed_amount, weights=weights,
                                     weight_column="weight", denominator_sector_keys=denominator,
                                     sector_groups=SECTOR_GROUPS, current_proxies={},
                                     allocator_basis="corrected_matched_component_comparison",
                                     fed_exact_component_mil=fed_amount)
            for row in allocated:
                row["allocation_status"] = "unavailable_fed_component" if missing_fed else "conditional_on_retained_fed_proxy_coverage_unverified"
            rows.extend(allocated)
    return pd.DataFrame(rows)


def build_comparison(*, old_weights: pd.DataFrame, old_buckets: pd.DataFrame,
                     new_weights: pd.DataFrame, new_buckets: pd.DataFrame,
                     canonical: pd.DataFrame, historical_levels: pd.DataFrame,
                     retained: pd.DataFrame, treasury: pd.DataFrame, fed: pd.DataFrame,
                     constraints: pd.DataFrame, soma: pd.DataFrame,
                     legs: pd.DataFrame, regression: pd.DataFrame,
                     quarterly: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict]:
    old_weights = _window(old_weights, ["sector_key", "component_key"])
    old_buckets = _window(old_buckets, ["sector_key", "component_key", "bucket_key"])
    new_weights = _window(new_weights, ["sector_key", "component_key"])
    new_buckets = _window(new_buckets, ["sector_key", "component_key", "bucket_key"])
    canonical = _window(canonical, ["sector_key"])
    historical_levels = _window(historical_levels, ["sector_key"])
    retained = _window(retained, ["sector_group", "component_key"])
    fed, constraints = _window(fed, []), _window(constraints, ["sector_key"])
    pools = _window(build_treasury_interest_component_pools(treasury),
                    ["expense_catg_desc", "expense_group_desc", "expense_type_desc"])
    kwargs = {"component_pools": pools, "sector_maturity": canonical, "sector_panel": historical_levels,
                  "curves": pd.DataFrame(), "fed_components": fed, "source_constraints": constraints}
    baseline = build_tier2_interest_component_candidate(**kwargs, interest_allocation_weights=old_weights,
                                                       component_bucket_weights=old_buckets)
    parity = assert_baseline_parity(retained, baseline)
    # Preserve all legacy rules except residual exposure in the combined coupon weight.
    pooled_weights, pooled_buckets = residual_only_contracts(old_weights, old_buckets, new_weights, new_buckets, canonical)
    residual = build_tier2_interest_component_candidate(**kwargs, interest_allocation_weights=pooled_weights,
                                                       component_bucket_weights=pooled_buckets)
    partition, fed_parity = partition_fed_schedule(soma, fed)
    exposures = corrected_exposures(canonical, new_weights, constraints,
                                    expected_holders=old_weights[["date", "sector_key"]].drop_duplicates())
    corrected = allocate_corrected(pools, exposures, fed, partition)
    lanes = {"historical": baseline, "residual_only_pooled": residual, "corrected_components": corrected}
    component_rows = pd.concat([frame.assign(lane=lane) for lane, frame in lanes.items()], ignore_index=True)
    component_rows["candidate_default_status"] = "nondefault_comparison_only"
    component_rows = component_rows.drop(columns=["component_anchored_interest_low_mil", "component_anchored_interest_high_mil"])
    component_rows["uncertainty_status"] = "point_comparison_only; no_new_uncertainty_estimated"
    ineligible = old_weights[old_weights.eligible_for_gross_interest.astype(str).str.lower().eq("false")][["date", "sector_key", "component_key"]]
    excluded = old_buckets.merge(ineligible, on=["date", "sector_key", "component_key"], validate="one_to_one").merge(
        historical_levels[["date", "sector_key", "level"]], on=["date", "sector_key"], how="inner", validate="many_to_one")
    excluded["excluded_legacy_bucket_weight_mil"] = excluded.bucket_weight * excluded.level
    excluded = excluded.groupby(["date", "component_key"]).excluded_legacy_bucket_weight_mil.sum().to_dict()
    component_rows["historical_comparison_pool"] = component_rows.component_key.replace({"tips_accrued_interest": "coupon_accrual"})
    component_rows["excluded_legacy_bucket_weight_mil"] = [
        excluded.get((date, component), 0.0) for date, component in zip(component_rows.date, component_rows.historical_comparison_pool)
    ]
    old_denominators = baseline[["date", "sector_group", "component_key", "denominator_raw_weight_mil"]].rename(
        columns={"component_key": "historical_comparison_pool", "denominator_raw_weight_mil": "historical_pool_denominator_mil"})
    component_rows = component_rows.merge(old_denominators, on=["date", "sector_group", "historical_comparison_pool"], validate="many_to_one")
    totals = pd.concat([frame.groupby(["lane", "date", "sector_group"], as_index=False).component_anchored_interest_mil.sum(
        min_count=4 if lane == "corrected_components" else 3) for lane, frame in component_rows.groupby("lane")])
    partial = pd.concat([frame[frame.component_key.ne("frn_accrued_interest")].groupby(
        ["lane", "date", "sector_group"], as_index=False).component_anchored_interest_mil.sum(
            min_count=3 if lane == "corrected_components" else 2)
        for lane, frame in component_rows.groupby("lane")]).rename(columns={"component_anchored_interest_mil": "nonfrn_interest_mil"})
    totals = totals.merge(partial, on=["lane", "date", "sector_group"], validate="one_to_one")
    totals["comparison_status"] = np.where(totals.component_anchored_interest_mil.isna(),
        "unavailable_missing_component", "conditional_on_retained_component_proxies")
    old_total = totals[totals.lane.eq("historical")][["date", "sector_group", "component_anchored_interest_mil", "nonfrn_interest_mil"]].rename(
        columns={"component_anchored_interest_mil": "historical_interest_mil", "nonfrn_interest_mil": "historical_nonfrn_interest_mil"})
    totals = totals.merge(old_total, on=["date", "sector_group"], validate="many_to_one")
    totals["delta_interest_mil"] = totals.component_anchored_interest_mil - totals.historical_interest_mil
    totals["delta_nonfrn_interest_mil"] = totals.nonfrn_interest_mil - totals.historical_nonfrn_interest_mil
    reg = _window(regression, []).set_index("date")
    historical_totals = old_total.pivot(index="date", columns="sector_group", values="historical_interest_mil")
    for sector in ("bank", "row"):
        column = f"{sector}_tier2_regression_interest_proxy"
        _finite(reg, [column])
        if not np.allclose(historical_totals[sector], reg[column], atol=TOLERANCE, rtol=0):
            raise ValueError(f"Historical allocation does not match frozen regression {sector} interest")
    rebuilt_legs = build_regression_leg_table(quarterly, regression)
    leg_check = legs.merge(rebuilt_legs[["quarter", "C", "R", "J", "O"]], on="quarter",
                           validate="one_to_one", how="outer", suffixes=("", "_rebuilt"))
    if len(leg_check) != 96:
        raise ValueError("Frozen leg grid differs")
    for component in ("C", "R", "J", "O"):
        _finite(leg_check, [component, component+"_rebuilt"])
        if not np.allclose(leg_check[component], leg_check[component+"_rebuilt"], atol=TOLERANCE, rtol=0):
            raise ValueError("Frozen leg construction differs")
    legs = legs.copy()
    legs["date"] = pd.PeriodIndex(legs.quarter, freq="Q").to_timestamp(how="end").normalize()
    legs = _window(legs, []).set_index("date")
    _finite(legs, ["C", "R", "J", "O"])
    deltas = []
    for lane, frame in totals.groupby("lane"):
        pivot = frame.pivot(index="date", columns="sector_group", values="delta_interest_mil")
        partial_pivot = frame.pivot(index="date", columns="sector_group", values="delta_nonfrn_interest_mil")
        for date in DATES:
            dr, dj = -float(pivot.loc[date, "row"]), -float(pivot.loc[date, "bank"])
            partial_r, partial_j = -float(partial_pivot.loc[date, "row"]), -float(partial_pivot.loc[date, "bank"])
            original = legs.loc[date]
            deltas.append({"lane": lane, "date": date, "delta_R_mil": dr, "delta_J_mil": dj,
                           "delta_C_mil": dr+dj, "delta_O_mil": 0.0,
                           **{f"historical_{c}_mil": float(original[c]) for c in ("C", "R", "J")},
                           "conditional_C_mil": float(original.C)+dr+dj,
                           "partial_nonfrn_delta_R_mil": partial_r, "partial_nonfrn_delta_J_mil": partial_j,
                           "partial_nonfrn_delta_C_mil": partial_r+partial_j,
                           "partial_nonfrn_scope": "Fixed/TIPS coupon and bill allocation changes only; FRN allocation and direct Fed term held at historical values",
                           "comparison_status": "unavailable_missing_component" if not np.isfinite(dr+dj) else "conditional_on_retained_component_proxies",
                           "claim": "Allocator-only; Fed term and all other inputs fixed; CU excluded from canonical bank perimeter"})
    outputs = {"component_allocations": component_rows, "sector_interest": totals,
               "quarterly_deltas": pd.DataFrame(deltas), "corrected_exposures": exposures,
               "fed_schedule_partition": partition}
    summary = {"historical_parity": parity, "fed_schedule_parity": fed_parity, "claim": CLAIM,
               "corrected_change_scope": "Compound component/Fed-pool/constraint/gross-eligibility correction; not solely TIPS split",
               "historical_defect": "Bucket fallback can restore household statistical-residual weights despite gross ineligibility",
               "residual_only_scope": "Only coupon central weights/bucket shares change by canonical residual; legacy constraints propagate that change. Historical uncertainty bounds are not reinterpreted as corrected bounds.",
               "inflation_compensation": "Separate nondefault component; excluded from every compared total",
               "allocation_boundary": "Conditional proportional allocation over covered eligible weights; those holders are not proved to exhaust recipients. Not observed sector interest or cash, nor automatic evidence of a superior/default estimator.",
               "fed_frn_boundary": "Missing retained Fed FRN values remain unavailable; nonmissing values are coverage-unverified daily-index proxies. Their producer uses start_of_accrual_period as accrual_date rather than record_date, an unresolved clock/matching seam. No missing component is zero-filled or omitted from totals.",
               "partial_comparison": "16-quarter non-FRN delta holds FRN allocation unchanged; not a completed all-component correction",
               "corrected_quarters_with_numeric_totals": int(totals[totals.lane.eq("corrected_components") & totals.component_anchored_interest_mil.notna()].date.nunique()),
               "constraint_perimeter": "Existing source-to-sector grouping held as a disclosed assumption, not newly verified sector equivalence"}
    return outputs, summary


def run(plan_path: Path, destination: Path, producer_commit: str) -> dict:
    root = Path(__file__).resolve().parents[2]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if producer_commit != head or subprocess.check_output(["git", "diff", "HEAD", "--", "src"], cwd=root):
        raise ValueError("Comparison requires the exact clean committed producer")
    module = Path(__file__).resolve()
    committed = subprocess.check_output(["git", "show", f"HEAD:{module.relative_to(root)}"], cwd=root)
    if committed != module.read_bytes():
        raise ValueError("Comparison module differs from committed producer")
    if destination.exists():
        raise ValueError("Refusing to replace an existing comparison destination")
    plan = json.loads(plan_path.read_text())
    paths = {}
    for key, record in plan["inputs"].items():
        path = Path(record["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Frozen input hash differs: {key}")
        paths[key] = path
    def read(key):
        return pd.read_csv(paths[key], low_memory=False)
    with zipfile.ZipFile(paths["old_archive"]) as archive:
        old_weights = pd.read_csv(io.BytesIO(archive.read("sector_interest_allocation_weights.csv")))
        old_buckets = pd.read_csv(io.BytesIO(archive.read("sector_component_bucket_weights.csv")))
    # The existing source reader resolves this exact dependency; pin it explicitly.
    from .sector_coupon import _resolve_inventory_path
    if _resolve_inventory_path(paths["historical_levels"]) != paths["inventory"]:
        raise ValueError("Historical level reader inventory differs from pinned inventory")
    outputs, summary = build_comparison(old_weights=old_weights, old_buckets=old_buckets,
        historical_levels=read_sector_panel_table(paths["historical_levels"]),
        **{key: read(key) for key in ("new_weights", "new_buckets", "canonical", "retained", "treasury", "fed",
                                      "constraints", "soma", "legs", "regression", "quarterly")})
    destination.mkdir(parents=True)
    receipts = {}
    for key, frame in outputs.items():
        path = destination / f"{key}.csv"
        frame.to_csv(path, index=False)
        receipts[key] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(frame)}
    # Inputs, including protected admitted outputs, must still match after computation.
    for key, path in paths.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != plan["inputs"][key]["sha256"]:
            raise ValueError(f"Frozen input changed during comparison: {key}")
    if (subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() != head
            or subprocess.check_output(["git", "diff", "HEAD", "--", "src"], cwd=root)
            or committed != module.read_bytes()):
        raise ValueError("Producer source changed during comparison")
    receipt = {"producer_commit": head, "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
               "inputs": plan["inputs"], "outputs": receipts, "summary": summary,
               "runtime": {"python": sys.version, "executable": sys.executable, "pandas": pd.__version__,
                           "numpy": np.__version__, "argv": sys.argv}}
    (destination / "receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--producer-commit", required=True)
    args = parser.parse_args()
    run(args.plan, args.output, args.producer_commit)


if __name__ == "__main__":
    main()
