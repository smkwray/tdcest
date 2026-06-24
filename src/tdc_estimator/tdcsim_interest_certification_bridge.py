from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


BRIDGE_VERSION = "tdcest_tdcsim_interest_certification_bridge_v1"
CERTIFIED_SCOPE_ID = "marketable_quarterly_certified_core_ex_tips_coupon_nonbill_dp_v1"

TDCSIM_INTEREST_CERTIFICATION_BRIDGE_COLUMNS = [
    "bridge_version",
    "quarter",
    "date",
    "tdcsim_scope_id",
    "tdcsim_scope_certification_status",
    "tdcsim_scope_claim",
    "official_scope_total_mil",
    "model_scope_total_mil",
    "scope_gap_mil",
    "scope_ape_pct",
    "official_excluded_amount_mil",
    "expected_components",
    "certified_components",
    "excluded_components",
    "included_component_count",
    "certified_included_component_count",
    "excluded_component_count",
    "timing_caveated_component_count",
    "failed_included_component_count",
    "tdcest_canonical_row_present",
    "tdcest_canonical_value_mil",
    "tdcest_use_status",
    "tdcest_permitted_use",
    "tdcest_blocked_use",
    "sector_bound_eligible",
    "canonical_tdc_math_change",
    "component_certification_sha256",
    "scope_certification_sha256",
    "tdcest_estimates_sha256",
    "tdcest_canonical_column",
    "claim_boundary",
]


def file_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quarter_end_from_quarter(quarter: str) -> str:
    period = pd.Period(str(quarter), freq="Q")
    return period.end_time.normalize().date().isoformat()


def _require_columns(frame: pd.DataFrame, required: set[str], *, label: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {', '.join(missing)}")


def _component_counts(component: pd.DataFrame) -> pd.DataFrame:
    if component.empty:
        return pd.DataFrame(
            columns=[
                "quarter",
                "included_component_count",
                "certified_included_component_count",
                "excluded_component_count",
                "timing_caveated_component_count",
                "failed_included_component_count",
            ]
        )
    frame = component.copy()
    included = frame["included_in_scope"].astype(str).str.lower().isin({"true", "1"})
    certified = frame["certification_status"].eq("certified_quarterly")
    excluded = frame["certification_status"].eq("excluded_selected_scope")
    timing = frame["certification_status"].eq("candidate_timing_caveated")
    failed_included = included & ~certified
    grouped = frame.assign(
        _included=included.astype(int),
        _certified_included=(included & certified).astype(int),
        _excluded=excluded.astype(int),
        _timing=timing.astype(int),
        _failed_included=failed_included.astype(int),
    ).groupby("quarter", as_index=False)[
        ["_included", "_certified_included", "_excluded", "_timing", "_failed_included"]
    ].sum()
    return grouped.rename(
        columns={
            "_included": "included_component_count",
            "_certified_included": "certified_included_component_count",
            "_excluded": "excluded_component_count",
            "_timing": "timing_caveated_component_count",
            "_failed_included": "failed_included_component_count",
        }
    )


def _canonical_by_quarter(estimates: pd.DataFrame | None, canonical_column: str) -> pd.DataFrame:
    if estimates is None or estimates.empty:
        return pd.DataFrame(columns=["quarter", "tdcest_canonical_row_present", "tdcest_canonical_value_mil"])
    _require_columns(estimates, {"date"}, label="tdcest estimates")
    frame = estimates.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])
    frame["quarter"] = frame["date"].dt.to_period("Q").astype(str)
    if canonical_column not in frame.columns:
        frame["tdcest_canonical_value_mil"] = pd.NA
        frame["tdcest_canonical_row_present"] = False
    else:
        frame["tdcest_canonical_value_mil"] = pd.to_numeric(frame[canonical_column], errors="coerce")
        frame["tdcest_canonical_row_present"] = frame["tdcest_canonical_value_mil"].notna()
    return frame[["quarter", "tdcest_canonical_row_present", "tdcest_canonical_value_mil"]]


def build_tdcsim_interest_certification_bridge(
    scope_certification: pd.DataFrame,
    component_certification: pd.DataFrame,
    *,
    estimates: pd.DataFrame | None = None,
    scope_id: str = CERTIFIED_SCOPE_ID,
    canonical_column: str = "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow",
    component_certification_sha256: str = "",
    scope_certification_sha256: str = "",
    tdcest_estimates_sha256: str = "",
) -> pd.DataFrame:
    """Build a noncanonical TDCSIM aggregate-interest certification bridge for TDC-est.

    This artifact is deliberately not a sector bound. It records whether the
    TDCSIM aggregate interest engine is certified for a quarter and whether a
    TDC-est canonical row exists for ex post review.
    """

    _require_columns(
        scope_certification,
        {
            "quarter",
            "scope_id",
            "scope_claim",
            "expected_components",
            "certified_components",
            "excluded_components",
            "official_scope_total_mil",
            "model_scope_total_mil",
            "official_excluded_amount_mil",
            "gap_mil",
            "ape_pct",
            "certification_status",
        },
        label="tdcsim scope certification",
    )
    _require_columns(
        component_certification,
        {"quarter", "component_id", "certification_status", "included_in_scope"},
        label="tdcsim component certification",
    )
    scope = scope_certification.loc[scope_certification["scope_id"].eq(scope_id)].copy()
    counts = _component_counts(component_certification)
    canonical = _canonical_by_quarter(estimates, canonical_column)
    out = scope.merge(counts, on="quarter", how="left").merge(canonical, on="quarter", how="left")
    out["bridge_version"] = BRIDGE_VERSION
    out["date"] = out["quarter"].map(quarter_end_from_quarter)
    out["tdcsim_scope_id"] = out["scope_id"]
    out["tdcsim_scope_certification_status"] = out["certification_status"]
    out["tdcsim_scope_claim"] = out["scope_claim"]
    out["scope_gap_mil"] = out["gap_mil"]
    out["scope_ape_pct"] = out["ape_pct"]
    out["tdcest_canonical_row_present"] = (
        out["tdcest_canonical_row_present"].fillna(False).astype(bool)
    )
    for column in [
        "included_component_count",
        "certified_included_component_count",
        "excluded_component_count",
        "timing_caveated_component_count",
        "failed_included_component_count",
    ]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)
    certified = out["tdcsim_scope_certification_status"].eq("certified_quarterly")
    out["tdcest_use_status"] = certified.map(
        {True: "aggregate_certified_crosscheck_available", False: "aggregate_certification_not_available"}
    )
    out["tdcest_permitted_use"] = "aggregate_component_contract_crosscheck_only"
    out["tdcest_blocked_use"] = "canonical_estimator_math;sector_interest_bounds;sector_clipping"
    out["sector_bound_eligible"] = False
    out["canonical_tdc_math_change"] = False
    out["component_certification_sha256"] = component_certification_sha256
    out["scope_certification_sha256"] = scope_certification_sha256
    out["tdcest_estimates_sha256"] = tdcest_estimates_sha256
    out["tdcest_canonical_column"] = canonical_column
    out["claim_boundary"] = (
        "tdcsim_aggregate_quarterly_interest_certification_not_holder_or_sector_bound"
    )
    return out.loc[:, TDCSIM_INTEREST_CERTIFICATION_BRIDGE_COLUMNS].sort_values("quarter").reset_index(drop=True)


def render_tdcsim_interest_certification_bridge_markdown(frame: pd.DataFrame) -> str:
    title = "# TDCSIM Interest Certification Bridge"
    intro = (
        "This is a noncanonical TDC-est diagnostic. It ingests TDCSIM aggregate "
        "interest certification and does not change estimator math or create sector bounds."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No TDCSIM certification rows were available.", ""])
    certified = frame["tdcsim_scope_certification_status"].eq("certified_quarterly")
    ordered = frame.sort_values("quarter")
    latest = ordered.iloc[-1]
    certified_frame = ordered.loc[certified].copy()
    latest_certified = certified_frame.iloc[-1] if not certified_frame.empty else latest
    certified_mape = pd.to_numeric(certified_frame.get("scope_ape_pct"), errors="coerce").mean()
    certified_max_gap = pd.to_numeric(certified_frame.get("scope_gap_mil"), errors="coerce").abs().max()
    recent = ordered.loc[ordered["quarter"].between("2022Q1", "2025Q4")].copy()
    recent_certified = recent["tdcsim_scope_certification_status"].eq("certified_quarterly")
    recent_mape = pd.to_numeric(recent.get("scope_ape_pct"), errors="coerce").mean()
    recent_max_gap = pd.to_numeric(recent.get("scope_gap_mil"), errors="coerce").abs().max()
    lines = [
        title,
        "",
        intro,
        "",
        f"- Bridge version: `{BRIDGE_VERSION}`",
        f"- Scope: `{latest['tdcsim_scope_id']}`",
        f"- Rows: `{len(frame)}`",
        f"- Certified rows overall: `{int(certified.sum())}`",
        f"- Certified 2022Q1-2025Q4 rows: `{int(recent_certified.sum())}` / `{len(recent)}`",
        f"- Latest row: `{latest['quarter']}` (`{latest['tdcsim_scope_certification_status']}`)",
        f"- Latest certified quarter: `{latest_certified['quarter']}`",
        f"- Certified-row MAPE overall: `{certified_mape}`",
        f"- Certified-row max absolute gap overall (mil): `{certified_max_gap}`",
        f"- 2022Q1-2025Q4 MAPE: `{recent_mape}`",
        f"- 2022Q1-2025Q4 max absolute gap (mil): `{recent_max_gap}`",
        f"- Latest certified official/model/gap (mil): `{latest_certified['official_scope_total_mil']}` / `{latest_certified['model_scope_total_mil']}` / `{latest_certified['scope_gap_mil']}`",
        f"- Latest certified excluded official amount (mil): `{latest_certified['official_excluded_amount_mil']}`",
        "",
        "Permitted use: aggregate component-contract cross-check only.",
        "",
        "Blocked use: canonical estimator math, sector interest bounds, and sector clipping.",
        "",
    ]
    return "\n".join(lines)


def write_tdcsim_interest_certification_bridge(
    *,
    scope_certification_path: Path | str,
    component_certification_path: Path | str,
    estimates_path: Path | str | None,
    csv_path: Path | str,
    markdown_path: Path | str,
    scope_id: str = CERTIFIED_SCOPE_ID,
    canonical_column: str = "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow",
) -> tuple[Path, Path, pd.DataFrame]:
    scope_path = Path(scope_certification_path)
    component_path = Path(component_certification_path)
    estimates = pd.read_csv(estimates_path) if estimates_path is not None and Path(estimates_path).exists() else None
    estimates_sha256 = file_sha256(estimates_path) if estimates_path is not None and Path(estimates_path).exists() else ""
    frame = build_tdcsim_interest_certification_bridge(
        pd.read_csv(scope_path),
        pd.read_csv(component_path),
        estimates=estimates,
        scope_id=scope_id,
        canonical_column=canonical_column,
        component_certification_sha256=file_sha256(component_path),
        scope_certification_sha256=file_sha256(scope_path),
        tdcest_estimates_sha256=estimates_sha256,
    )
    target_csv = Path(csv_path)
    target_md = Path(markdown_path)
    target_csv.parent.mkdir(parents=True, exist_ok=True)
    target_md.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target_csv, index=False)
    target_md.write_text(render_tdcsim_interest_certification_bridge_markdown(frame), encoding="utf-8")
    return target_csv, target_md, frame
