from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .tdcsim_interest_certification_bridge import file_sha256, quarter_end_from_quarter


BRIDGE_VERSION = "tdcest_tdcsim_sector_interest_bridge_v1"
COMPARISON_SET_ID = "tdcest_component_cash_ex_tips_inflation_v1"
MATCHED_TDCSIM_COMPONENTS = ("bill_discount", "coupon_accrual", "tips_coupon_accrual", "frn_interest")
EXCLUDED_TDCSIM_COMPONENTS = ("tips_inflation_compensation",)
TDCEST_CANDIDATE_COMPONENTS = ("bill_amortized_discount", "coupon_accrual", "frn_accrued_interest")
TDCSIM_SECTORS = ("Banks", "CB", "Foreign", "Private", "Unallocated")
TDCSIM_SCOPES = ("certified_core_ex_tips_coupon_nonbill_dp", "extended_with_timing_caveated_tips_coupon")

EXPECTED_INPUT_RELEASE = {
    "allocation_sha256": "35a02c58b9fb2fbd401872bf8c21184273472ad4d6866354e2118c2a7a05ba95",
    "totals_sha256": "633378a99b54c0202aecddd6efa898ad5f24a5fc69731c89d7ba304d6cc6777e",
    "component_certification_sha256": "6781996de9f74f801b1eade6d152a36bc74cd87a8c320aab5d5a62b8bcc474a7",
    "scope_certification_sha256": "5031f1cdb770cf2514691234c59eb6eef825cf7fcf76512c87e247e46ea62cd2",
    "tdcest_candidate_sha256": "25ce05bc1d484e4927cfb4c84e564365ec063768f4f65c17e9b883549f936c53",
    "fed_support_sha256": "3cba29cde12f0cc9428aff5bb06bfbdea35b3f01330e358c716a28f24eb65d27",
    "allocation_rows": 3357,
    "totals_rows": 1000,
    "quarter_min": "2001Q1",
    "quarter_max": "2025Q4",
}

SECTOR_CONTRACT = {
    "Banks": {
        "tdcest_reference_kind": "tier2_component_candidate_broad_depository_bank_plus_credit_union",
        "tdcest_sector_groups": "bank;credit_union",
        "tdcest_sector_keys": (
            "bank_us_chartered;bank_foreign_banking_offices_us;bank_us_affiliated_areas;"
            "credit_unions_marketable_proxy"
        ),
        "mapping_status": "supported_broad_depository_match",
        "mapping_evidence": "TDCSIM Banks maps to broad depositories; compare TDC-est bank plus credit union.",
        "delta_eligible_default": True,
    },
    "Foreign": {
        "tdcest_reference_kind": "tier2_component_candidate_row_foreigners_total",
        "tdcest_sector_groups": "row",
        "tdcest_sector_keys": "foreigners_total",
        "mapping_status": "provisional_semantic_match_delta_blocked",
        "mapping_evidence": "Foreign/ROW holder-basis, custody, valuation, and timing crosswalk is not yet versioned.",
        "delta_eligible_default": False,
    },
    "CB": {
        "tdcest_reference_kind": "fed_soma_component_support_proxy",
        "tdcest_sector_groups": "fed",
        "tdcest_sector_keys": "fed",
        "mapping_status": "component_specific_support_proxy_delta_blocked",
        "mapping_evidence": "Fed/SOMA support is component-specific and lacks a nonoverlap TIPS-coupon crosswalk.",
        "delta_eligible_default": False,
    },
    "Private": {
        "tdcest_reference_kind": "none",
        "tdcest_sector_groups": "",
        "tdcest_sector_keys": "",
        "mapping_status": "unmatched_no_tdcest_sector_interest_reference",
        "mapping_evidence": "No full TDC-est Private sector-interest counterpart exists.",
        "delta_eligible_default": False,
    },
    "Unallocated": {
        "tdcest_reference_kind": "none",
        "tdcest_sector_groups": "",
        "tdcest_sector_keys": "",
        "mapping_status": "residual_report_only_never_redistributed",
        "mapping_evidence": "TDCSIM residual/unmatched interest is reported separately and not redistributed.",
        "delta_eligible_default": False,
    },
}

TDCSIM_SECTOR_INTEREST_BRIDGE_COLUMNS = [
    "bridge_version",
    "quarter",
    "date",
    "comparison_set_id",
    "comparison_set_status",
    "tdcsim_sector",
    "tdcest_reference_kind",
    "tdcest_sector_groups",
    "tdcest_sector_keys",
    "mapping_status",
    "mapping_evidence",
    "tdcsim_interest_mil",
    "tdcest_support_interest_mil",
    "delta_tdcsim_minus_tdcest_mil",
    "delta_pct_of_tdcest_support",
    "delta_eligible",
    "comparison_status",
    "tdcsim_component_ids",
    "tdcest_component_ids",
    "required_component_count",
    "matched_component_count",
    "official_component_count",
    "certified_component_count",
    "timing_caveated_component_count",
    "min_attributed_weight_coverage_pct",
    "official_interest_weighted_coverage_pct",
    "unallocated_interest_mil",
    "aggregate_pool_match_status",
    "support_coverage_status",
    "source_overlap_status",
    "tdcsim_allocation_sha256",
    "tdcsim_totals_sha256",
    "tdcsim_component_certification_sha256",
    "tdcsim_scope_certification_sha256",
    "tdcest_candidate_sha256",
    "fed_support_sha256",
    "unallocated_redistributed",
    "canonical_math_change",
    "canonical_use_eligible",
    "interval_use_eligible",
    "future_interval_status",
    "claim_boundary",
]


def _require_columns(frame: pd.DataFrame, required: set[str], *, label: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {', '.join(missing)}")


def _bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def _assert_close(actual: float, expected: float, *, label: str, tol: float = 1e-6) -> None:
    if pd.isna(actual) or abs(float(actual) - float(expected)) > tol:
        raise ValueError(f"{label} mismatch: expected {expected}, got {actual}")


def _selected_control(row: pd.Series) -> float:
    official = pd.to_numeric(pd.Series([row.get("official_interest_mil")]), errors="coerce").iloc[0]
    if pd.notna(official):
        return float(official)
    model = pd.to_numeric(pd.Series([row.get("model_interest_mil")]), errors="coerce").iloc[0]
    return float(model)


def validate_tdcsim_sector_inputs(
    allocation: pd.DataFrame,
    totals: pd.DataFrame,
    *,
    expected_release: dict[str, object] | None = EXPECTED_INPUT_RELEASE,
) -> None:
    _require_columns(
        allocation,
        {
            "quarter",
            "scope_id",
            "tdc_sector",
            "component_id",
            "component_in_certified_core_scope",
            "component_in_extended_scope",
            "aggregate_control_basis",
            "control_quality_tier",
            "component_certification_status",
            "official_interest_mil",
            "model_interest_mil",
            "component_weight_total_mil",
            "residual_weight_mil",
            "attributed_weight_coverage_pct",
            "allocation_share",
            "selected_allocated_interest_mil",
            "allocation_status",
        },
        label="tdcsim sector allocation",
    )
    _require_columns(
        totals,
        {
            "quarter",
            "scope_id",
            "tdc_sector",
            "selected_allocated_interest_mil",
            "allocated_official_interest_mil",
            "allocated_model_interest_mil",
            "component_count",
            "tdcsim_holder_count",
            "official_control_component_count",
            "certified_component_count",
            "min_attributed_weight_coverage_pct",
            "allocation_statuses",
        },
        label="tdcsim sector totals",
    )

    if expected_release is not None:
        if len(allocation) != int(expected_release["allocation_rows"]):
            raise ValueError(f"tdcsim allocation row count mismatch: {len(allocation)}")
        if len(totals) != int(expected_release["totals_rows"]):
            raise ValueError(f"tdcsim totals row count mismatch: {len(totals)}")

    quarters = sorted(allocation["quarter"].astype(str).unique())
    sectors = sorted(allocation["tdc_sector"].astype(str).unique())
    scopes = sorted(totals["scope_id"].astype(str).unique())
    if expected_release is not None:
        if len(quarters) != 100 or quarters[0] != "2001Q1" or quarters[-1] != "2025Q4":
            raise ValueError(f"unexpected TDCSIM quarter range/count: {quarters[0]}..{quarters[-1]} ({len(quarters)})")
        if tuple(sectors) != tuple(sorted(TDCSIM_SECTORS)):
            raise ValueError("unexpected TDCSIM sector set")
        if tuple(scopes) != tuple(sorted(TDCSIM_SCOPES)):
            raise ValueError("unexpected TDCSIM totals scope set")
    if totals.duplicated(["quarter", "scope_id", "tdc_sector"]).any():
        raise ValueError("duplicate TDCSIM totals keys")
    if len(totals) != len(quarters) * len(scopes) * len(sectors):
        raise ValueError("TDCSIM totals grid is incomplete")

    share_sum = allocation.groupby(["quarter", "component_id"])["allocation_share"].sum()
    if (share_sum.sub(1.0).abs() > 1e-12).any():
        raise ValueError("TDCSIM allocation shares do not sum to one by quarter/component")

    control = _component_control_frame(allocation)
    allocated = allocation.groupby(["quarter", "component_id"], as_index=False)["selected_allocated_interest_mil"].sum()
    check = allocated.merge(control[["quarter", "component_id", "selected_control_mil"]], on=["quarter", "component_id"])
    if (check["selected_allocated_interest_mil"].sub(check["selected_control_mil"]).abs() > 1e-6).any():
        raise ValueError("TDCSIM selected component allocations do not conserve")

    rebuilt = _rebuild_totals_from_allocation(allocation)
    joined = totals.merge(
        rebuilt,
        on=["quarter", "scope_id", "tdc_sector"],
        how="outer",
        suffixes=("_total", "_rebuilt"),
        indicator=True,
    )
    if not joined["_merge"].eq("both").all():
        raise ValueError("rebuilt TDCSIM totals keyset does not match totals file")
    if (
        joined["selected_allocated_interest_mil_total"]
        .sub(joined["selected_allocated_interest_mil_rebuilt"])
        .abs()
        .max()
        > 1e-6
    ):
        raise ValueError("rebuilt TDCSIM totals do not match totals file")

    if expected_release is not None:
        sentinels = {
            ("2025Q4", "certified_core_ex_tips_coupon_nonbill_dp", "Private"): 111193.184418,
            ("2025Q4", "certified_core_ex_tips_coupon_nonbill_dp", "Foreign"): 77195.522849,
            ("2025Q4", "certified_core_ex_tips_coupon_nonbill_dp", "CB"): 30390.022321,
            ("2025Q4", "certified_core_ex_tips_coupon_nonbill_dp", "Banks"): 17944.072804,
            ("2025Q4", "certified_core_ex_tips_coupon_nonbill_dp", "Unallocated"): 14486.551822,
            ("2025Q4", "extended_with_timing_caveated_tips_coupon", "Private"): 112178.411155,
            ("2025Q4", "extended_with_timing_caveated_tips_coupon", "Foreign"): 78510.046617,
            ("2025Q4", "extended_with_timing_caveated_tips_coupon", "CB"): 31604.083770,
            ("2025Q4", "extended_with_timing_caveated_tips_coupon", "Banks"): 19484.991492,
            ("2025Q4", "extended_with_timing_caveated_tips_coupon", "Unallocated"): 15289.738214,
        }
        indexed = totals.set_index(["quarter", "scope_id", "tdc_sector"])["selected_allocated_interest_mil"]
        for key, expected in sentinels.items():
            _assert_close(float(indexed.loc[key]), expected, label=f"TDCSIM sentinel {key}")


def _component_control_frame(allocation: pd.DataFrame) -> pd.DataFrame:
    invariant_cols = [
        "component_in_certified_core_scope",
        "component_in_extended_scope",
        "aggregate_control_basis",
        "control_quality_tier",
        "component_certification_status",
        "official_interest_mil",
        "model_interest_mil",
        "component_weight_total_mil",
        "residual_weight_mil",
        "attributed_weight_coverage_pct",
        "allocation_status",
    ]
    bad: list[str] = []
    for column in invariant_cols:
        counts = allocation.groupby(["quarter", "component_id"])[column].nunique(dropna=False)
        if counts.max() > 1:
            bad.append(column)
    if bad:
        raise ValueError(f"component control columns vary within quarter/component: {', '.join(bad)}")
    first = allocation.groupby(["quarter", "component_id"], as_index=False).first()
    first["selected_control_mil"] = first.apply(_selected_control, axis=1)
    return first


def _rebuild_totals_from_allocation(allocation: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for scope, flag in [
        ("certified_core_ex_tips_coupon_nonbill_dp", "component_in_certified_core_scope"),
        ("extended_with_timing_caveated_tips_coupon", "component_in_extended_scope"),
    ]:
        included = allocation.loc[_bool_series(allocation[flag])].copy()
        grouped = (
            included.groupby(["quarter", "tdc_sector"], as_index=False)["selected_allocated_interest_mil"]
            .sum()
            .assign(scope_id=scope)
        )
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True)[
        ["quarter", "scope_id", "tdc_sector", "selected_allocated_interest_mil"]
    ]


def _matched_component_summary(allocation: pd.DataFrame) -> pd.DataFrame:
    control = _component_control_frame(allocation)
    matched = control.loc[control["component_id"].isin(MATCHED_TDCSIM_COMPONENTS)].copy()
    matched["official_interest_mil"] = pd.to_numeric(matched["official_interest_mil"], errors="coerce")
    matched["selected_control_mil"] = pd.to_numeric(matched["selected_control_mil"], errors="coerce")
    matched["attributed_weight_coverage_pct"] = pd.to_numeric(
        matched["attributed_weight_coverage_pct"], errors="coerce"
    )
    matched["official_weight_for_coverage"] = matched["official_interest_mil"].fillna(
        matched["selected_control_mil"]
    )
    matched["official_component"] = matched["control_quality_tier"].astype(str).str.contains("official")
    matched["certified_component"] = matched["component_certification_status"].eq("certified_quarterly")
    matched["timing_caveated_component"] = matched["component_certification_status"].eq(
        "candidate_timing_caveated"
    )
    summary = matched.groupby("quarter", as_index=False).agg(
        required_component_count=("component_id", "nunique"),
        official_component_count=("official_component", "sum"),
        certified_component_count=("certified_component", "sum"),
        timing_caveated_component_count=("timing_caveated_component", "sum"),
        min_attributed_weight_coverage_pct=("attributed_weight_coverage_pct", "min"),
        matched_aggregate_control_mil=("selected_control_mil", "sum"),
    )
    weighted = (
        matched.assign(
            _coverage_weighted=matched["attributed_weight_coverage_pct"]
            * matched["official_weight_for_coverage"]
        )
        .groupby("quarter")
        .agg(_coverage_weighted=("_coverage_weighted", "sum"), _weight=("official_weight_for_coverage", "sum"))
        .reset_index()
    )
    weighted["official_interest_weighted_coverage_pct"] = (
        weighted["_coverage_weighted"] / weighted["_weight"]
    ).where(weighted["_weight"].ne(0))
    return summary.merge(weighted[["quarter", "official_interest_weighted_coverage_pct"]], on="quarter")


def _tdcsim_matched_sector_values(allocation: pd.DataFrame) -> pd.DataFrame:
    matched = allocation.loc[allocation["component_id"].isin(MATCHED_TDCSIM_COMPONENTS)].copy()
    return matched.groupby(["quarter", "tdc_sector"], as_index=False).agg(
        tdcsim_interest_mil=("selected_allocated_interest_mil", "sum")
    )


def _candidate_references(candidate: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        candidate,
        {"date", "sector_group", "component_key", "component_anchored_interest_mil"},
        label="tdcest component candidate",
    )
    frame = candidate.loc[candidate["component_key"].isin(TDCEST_CANDIDATE_COMPONENTS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    frame["quarter"] = frame["date"].dt.to_period("Q").astype(str)
    frame["component_anchored_interest_mil"] = pd.to_numeric(
        frame["component_anchored_interest_mil"], errors="coerce"
    )
    grouped = frame.groupby(["quarter", "sector_group"], as_index=False).agg(
        component_count=("component_key", "nunique"),
        support_interest_mil=("component_anchored_interest_mil", "sum"),
    )
    rows: list[dict[str, object]] = []
    for quarter, qframe in grouped.groupby("quarter", sort=True):
        bank = qframe.loc[qframe["sector_group"].eq("bank")]
        cu = qframe.loc[qframe["sector_group"].eq("credit_union")]
        row = qframe.loc[qframe["sector_group"].eq("row")]
        if not bank.empty or not cu.empty:
            rows.append(
                {
                    "quarter": quarter,
                    "tdcsim_sector": "Banks",
                    "tdcest_support_interest_mil": float(bank["support_interest_mil"].sum() + cu["support_interest_mil"].sum()),
                    "matched_component_count": int(bank["component_count"].max() if not bank.empty else 0),
                    "support_coverage_status": "bank_plus_credit_union_candidate_available",
                }
            )
        if not row.empty:
            rows.append(
                {
                    "quarter": quarter,
                    "tdcsim_sector": "Foreign",
                    "tdcest_support_interest_mil": float(row["support_interest_mil"].sum()),
                    "matched_component_count": int(row["component_count"].max()),
                    "support_coverage_status": "row_candidate_available_crosswalk_pending",
                }
            )
    return pd.DataFrame(rows)


def _fed_references(fed_support: pd.DataFrame) -> pd.DataFrame:
    _require_columns(fed_support, {"date", "fed_tsy_coupon_interest_proxy"}, label="fed support")
    frame = fed_support.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    frame["quarter"] = frame["date"].dt.to_period("Q").astype(str)
    cols = [
        "fed_tsy_coupon_interest_proxy",
        "fed_tsy_bill_discount_interest_proxy",
        "fed_tsy_frn_interest_proxy",
    ]
    for col in cols:
        if col not in frame.columns:
            frame[col] = pd.NA
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["matched_component_count"] = frame[cols].notna().sum(axis=1)
    frame["tdcest_support_interest_mil"] = frame[cols].sum(axis=1, min_count=1)
    frame["tdcsim_sector"] = "CB"
    frame["support_coverage_status"] = "fed_component_support_proxy_crosswalk_pending"
    return frame[
        [
            "quarter",
            "tdcsim_sector",
            "tdcest_support_interest_mil",
            "matched_component_count",
            "support_coverage_status",
        ]
    ]


def _aggregate_pool_match(candidate: pd.DataFrame, component_summary: pd.DataFrame) -> pd.DataFrame:
    frame = candidate.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    frame["quarter"] = frame["date"].dt.to_period("Q").astype(str)
    pools = frame.loc[frame["component_key"].isin(TDCEST_CANDIDATE_COMPONENTS)].copy()
    pools["official_component_pool_mil"] = pd.to_numeric(pools["official_component_pool_mil"], errors="coerce")
    pools = pools.groupby(["quarter", "component_key"], as_index=False)["official_component_pool_mil"].first()
    rows: list[dict[str, object]] = []
    for quarter, qframe in pools.groupby("quarter", sort=True):
        available = set(qframe["component_key"])
        required = {"bill_amortized_discount", "coupon_accrual"}
        if "frn_accrued_interest" in available:
            required.add("frn_accrued_interest")
        if not required.issubset(available):
            status = "tdcest_component_pool_missing"
        else:
            status = "matched_component_pool_pass"
        rows.append({"quarter": quarter, "aggregate_pool_match_status": status})
    return pd.DataFrame(rows).merge(component_summary[["quarter"]], on="quarter", how="right").fillna(
        {"aggregate_pool_match_status": "no_tdcest_reference"}
    )


def build_tdcsim_sector_interest_bridge(
    *,
    allocation: pd.DataFrame,
    totals: pd.DataFrame,
    component_certification: pd.DataFrame,
    scope_certification: pd.DataFrame,
    candidate: pd.DataFrame,
    fed_support: pd.DataFrame,
    hashes: dict[str, str] | None = None,
    expected_release: dict[str, object] | None = EXPECTED_INPUT_RELEASE,
) -> tuple[pd.DataFrame, dict[str, object]]:
    validate_tdcsim_sector_inputs(allocation, totals, expected_release=expected_release)
    hashes = hashes or {}

    tdcsim = _tdcsim_matched_sector_values(allocation)
    component_summary = _matched_component_summary(allocation)
    unallocated = tdcsim.loc[tdcsim["tdc_sector"].eq("Unallocated"), ["quarter", "tdcsim_interest_mil"]].rename(
        columns={"tdcsim_interest_mil": "unallocated_interest_mil"}
    )
    references = pd.concat([_candidate_references(candidate), _fed_references(fed_support)], ignore_index=True)
    references = references.rename(columns={"tdcsim_sector": "reference_tdcsim_sector"})
    pool_status = _aggregate_pool_match(candidate, component_summary)

    out = (
        tdcsim.merge(component_summary, on="quarter", how="left")
        .merge(unallocated, on="quarter", how="left")
        .merge(
            references,
            left_on=["quarter", "tdc_sector"],
            right_on=["quarter", "reference_tdcsim_sector"],
            how="left",
        )
        .merge(pool_status, on="quarter", how="left")
    )
    if "reference_tdcsim_sector" in out.columns:
        out = out.drop(columns=["reference_tdcsim_sector"])
    out = out.rename(columns={"tdc_sector": "tdcsim_sector"})

    for sector, contract in SECTOR_CONTRACT.items():
        mask = out["tdcsim_sector"].eq(sector)
        for key in [
            "tdcest_reference_kind",
            "tdcest_sector_groups",
            "tdcest_sector_keys",
            "mapping_status",
            "mapping_evidence",
        ]:
            out.loc[mask, key] = contract[key]
    out["tdcest_support_interest_mil"] = pd.to_numeric(out["tdcest_support_interest_mil"], errors="coerce")
    out["tdcsim_interest_mil"] = pd.to_numeric(out["tdcsim_interest_mil"], errors="coerce")
    out["delta_eligible"] = False
    bank_delta = (
        out["tdcsim_sector"].eq("Banks")
        & out["tdcest_support_interest_mil"].notna()
        & out["aggregate_pool_match_status"].eq("matched_component_pool_pass")
    )
    out.loc[bank_delta, "delta_eligible"] = True
    out["delta_tdcsim_minus_tdcest_mil"] = pd.NA
    out.loc[bank_delta, "delta_tdcsim_minus_tdcest_mil"] = (
        out.loc[bank_delta, "tdcsim_interest_mil"] - out.loc[bank_delta, "tdcest_support_interest_mil"]
    )
    out["delta_pct_of_tdcest_support"] = pd.NA
    nonzero = bank_delta & out["tdcest_support_interest_mil"].ne(0)
    out.loc[nonzero, "delta_pct_of_tdcest_support"] = (
        out.loc[nonzero, "delta_tdcsim_minus_tdcest_mil"] / out.loc[nonzero, "tdcest_support_interest_mil"]
    )

    out["comparison_status"] = "blocked_no_tdcest_reference"
    out.loc[out["tdcsim_sector"].eq("Banks") & out["delta_eligible"], "comparison_status"] = (
        "descriptive_broad_depository_delta"
    )
    out.loc[out["tdcsim_sector"].eq("Banks") & ~out["delta_eligible"], "comparison_status"] = (
        "blocked_no_tdcest_reference"
    )
    out.loc[out["tdcsim_sector"].eq("Foreign") & out["tdcest_support_interest_mil"].notna(), "comparison_status"] = (
        "blocked_foreign_row_crosswalk_pending"
    )
    out.loc[out["tdcsim_sector"].eq("CB") & out["tdcest_support_interest_mil"].notna(), "comparison_status"] = (
        "blocked_fed_component_crosswalk_pending"
    )
    out.loc[out["tdcsim_sector"].eq("Private"), "comparison_status"] = "blocked_unmatched_private"
    out.loc[out["tdcsim_sector"].eq("Unallocated"), "comparison_status"] = "report_only_unallocated"
    out["support_coverage_status"] = out["support_coverage_status"].fillna("no_tdcest_reference")

    out["bridge_version"] = BRIDGE_VERSION
    out["date"] = out["quarter"].map(quarter_end_from_quarter)
    out["comparison_set_id"] = COMPARISON_SET_ID
    out["comparison_set_status"] = "timing_caveated_due_to_tips_coupon"
    out["tdcsim_component_ids"] = ";".join(MATCHED_TDCSIM_COMPONENTS)
    out["tdcest_component_ids"] = ";".join(TDCEST_CANDIDATE_COMPONENTS)
    out["source_overlap_status"] = "not_independent_holdout"
    out["unallocated_redistributed"] = False
    out["canonical_math_change"] = False
    out["canonical_use_eligible"] = False
    out["interval_use_eligible"] = False
    out["future_interval_status"] = "blocked_prerequisites_unmet"
    out["claim_boundary"] = (
        "diagnostic_component_matched_synthetic_allocation_not_observed_history_not_bound_not_canonical"
    )
    for column in [
        "tdcsim_allocation_sha256",
        "tdcsim_totals_sha256",
        "tdcsim_component_certification_sha256",
        "tdcsim_scope_certification_sha256",
        "tdcest_candidate_sha256",
        "fed_support_sha256",
    ]:
        out[column] = hashes.get(column, "")

    out = out.loc[:, TDCSIM_SECTOR_INTEREST_BRIDGE_COLUMNS].sort_values(["quarter", "tdcsim_sector"]).reset_index(drop=True)
    manifest = {
        "bridge_version": BRIDGE_VERSION,
        "comparison_set_id": COMPARISON_SET_ID,
        "allowed_use": "descriptive_diagnostic_only",
        "blocked_use": [
            "canonical_estimator_math",
            "sector_interest_bounds",
            "sector_clipping",
            "unallocated_redistribution",
        ],
        "matched_tdcsim_components": list(MATCHED_TDCSIM_COMPONENTS),
        "excluded_tdcsim_components": list(EXCLUDED_TDCSIM_COMPONENTS),
        "tdcest_candidate_components": list(TDCEST_CANDIDATE_COMPONENTS),
        "input_hashes": hashes,
        "row_count": int(len(out)),
        "quarter_min": str(out["quarter"].min()),
        "quarter_max": str(out["quarter"].max()),
        "tdcsim_sectors": list(TDCSIM_SECTORS),
        "sector_contract": SECTOR_CONTRACT,
    }
    return out, manifest


def render_tdcsim_sector_interest_bridge_markdown(frame: pd.DataFrame, manifest: dict[str, object]) -> str:
    title = "# TDCSIM / TDC-est Sector-Interest Diagnostic Bridge"
    intro = (
        "This is a diagnostic comparison of TDCSIM's aggregate-constrained synthetic sector allocation "
        "with TDC-est component-anchored support estimates over a component-matched Treasury cash-interest set. "
        "It is not observed holder-by-CUSIP history, not a canonical estimator input, and not a bound or clipping rule."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No bridge rows were produced.", ""])
    latest_q = str(frame["quarter"].max())
    latest = frame.loc[frame["quarter"].eq(latest_q)].copy()
    lines = [
        title,
        "",
        intro,
        "",
        "## Status",
        "",
        "- Status: diagnostic only",
        "- Canonical use: blocked",
        "- Sector-bound use: blocked",
        "- Clipping use: blocked",
        "- Unallocated redistribution: prohibited",
        "",
        "## Component Scope",
        "",
        "The comparison set consists of bill discount, nominal coupon, TIPS coupon, and FRN interest. "
        "TIPS inflation compensation is excluded. This derived set matches the TDC-est component-candidate "
        "aggregate controls but is not identical to either published TDCSIM totals scope. Its TIPS-coupon leg "
        "remains timing-caveated.",
        "",
        "## Latest Quarter",
        "",
        f"Latest overlap/readback quarter: `{latest_q}`.",
        "",
        "| Sector | TDCSIM matched cash, mil | TDC-est support, mil | Difference, mil | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in latest.sort_values("tdcsim_sector").itertuples(index=False):
        tdcest = "" if pd.isna(row.tdcest_support_interest_mil) else f"{float(row.tdcest_support_interest_mil):,.3f}"
        delta = "" if pd.isna(row.delta_tdcsim_minus_tdcest_mil) else f"{float(row.delta_tdcsim_minus_tdcest_mil):,.3f}"
        lines.append(
            f"| {row.tdcsim_sector} | {float(row.tdcsim_interest_mil):,.3f} | {tdcest} | {delta} | {row.comparison_status} |"
        )
    latest_unallocated = latest.loc[latest["tdcsim_sector"].eq("Unallocated"), "tdcsim_interest_mil"]
    if not latest_unallocated.empty:
        lines.extend(["", f"- Latest Unallocated matched interest, mil: `{float(latest_unallocated.iloc[0]):,.3f}`"])
    latest_min_cov = pd.to_numeric(latest["min_attributed_weight_coverage_pct"], errors="coerce").dropna()
    latest_weighted_cov = pd.to_numeric(latest["official_interest_weighted_coverage_pct"], errors="coerce").dropna()
    if not latest_min_cov.empty:
        lines.append(f"- Latest minimum component coverage: `{float(latest_min_cov.iloc[0]):.6f}%`")
    if not latest_weighted_cov.empty:
        lines.append(f"- Latest official-interest-weighted coverage: `{float(latest_weighted_cov.iloc[0]):.6f}%`")
    lines.extend(
        [
            "",
            "## Sector Mapping",
            "",
            "| TDCSIM sector | TDC-est reference | Mapping status | Output rule |",
            "| --- | --- | --- | --- |",
            "| Banks | bank plus credit union | supported broad-depository match | descriptive delta allowed after component gates |",
            "| Foreign | ROW / foreigners_total | provisional semantic match | show values; delta blocked pending crosswalk |",
            "| CB | Fed/SOMA component support | partial component-specific proxy | show support; delta blocked pending component crosswalk |",
            "| Private | none | unmatched | TDCSIM value only |",
            "| Unallocated | none | residual/report-only | TDCSIM value only; never redistribute |",
            "",
            "## Interpretation",
            "",
            "A large difference indicates that the two encoded allocation systems assign the same aggregate component controls differently. "
            "It does not establish which allocation is correct. The systems also share official controls and some source families, so this "
            "bridge is not an independent holdout test.",
            "",
            "## Manifest",
            "",
            f"- Bridge version: `{manifest['bridge_version']}`",
            f"- Comparison set: `{manifest['comparison_set_id']}`",
            f"- Rows: `{manifest['row_count']}`",
            f"- Quarter range: `{manifest['quarter_min']}` to `{manifest['quarter_max']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _manifest_path_label(path: Path | str) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        return resolved.name


def write_tdcsim_sector_interest_bridge(
    *,
    allocation_path: Path | str,
    totals_path: Path | str,
    component_certification_path: Path | str,
    scope_certification_path: Path | str,
    candidate_path: Path | str,
    fed_support_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    manifest_path: Path | str,
    canonical_immutability_paths: list[Path | str] | None = None,
) -> tuple[Path, Path, Path, pd.DataFrame, dict[str, object]]:
    paths = {
        "tdcsim_allocation_sha256": Path(allocation_path),
        "tdcsim_totals_sha256": Path(totals_path),
        "tdcsim_component_certification_sha256": Path(component_certification_path),
        "tdcsim_scope_certification_sha256": Path(scope_certification_path),
        "tdcest_candidate_sha256": Path(candidate_path),
        "fed_support_sha256": Path(fed_support_path),
    }
    hashes = {key: file_sha256(path) for key, path in paths.items()}
    expected_hash_key = {
        "tdcsim_allocation_sha256": "allocation_sha256",
        "tdcsim_totals_sha256": "totals_sha256",
        "tdcsim_component_certification_sha256": "component_certification_sha256",
        "tdcsim_scope_certification_sha256": "scope_certification_sha256",
        "tdcest_candidate_sha256": "tdcest_candidate_sha256",
        "fed_support_sha256": "fed_support_sha256",
    }
    for key, expected_key in expected_hash_key.items():
        expected = EXPECTED_INPUT_RELEASE[expected_key]
        if hashes[key] != expected:
            raise ValueError(f"{key} mismatch: expected {expected}, got {hashes[key]}")

    before = {
        _manifest_path_label(path): file_sha256(path)
        for path in (canonical_immutability_paths or [])
        if Path(path).exists()
    }
    frame, manifest = build_tdcsim_sector_interest_bridge(
        allocation=pd.read_csv(allocation_path),
        totals=pd.read_csv(totals_path),
        component_certification=pd.read_csv(component_certification_path),
        scope_certification=pd.read_csv(scope_certification_path),
        candidate=pd.read_csv(candidate_path),
        fed_support=pd.read_csv(fed_support_path),
        hashes=hashes,
        expected_release=EXPECTED_INPUT_RELEASE,
    )
    after = {
        _manifest_path_label(path): file_sha256(path)
        for path in (canonical_immutability_paths or [])
        if Path(path).exists()
    }
    if before != after:
        raise ValueError("canonical artifact hash changed while building TDCSIM sector bridge")
    manifest["canonical_immutability_hashes"] = after

    target_csv = Path(csv_path)
    target_md = Path(markdown_path)
    target_manifest = Path(manifest_path)
    target_csv.parent.mkdir(parents=True, exist_ok=True)
    target_md.parent.mkdir(parents=True, exist_ok=True)
    target_manifest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target_csv, index=False)
    target_md.write_text(render_tdcsim_sector_interest_bridge_markdown(frame, manifest), encoding="utf-8")
    target_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target_csv, target_md, target_manifest, frame, manifest
