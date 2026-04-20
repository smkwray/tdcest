from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .utils import utc_now_iso, write_json


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str) and value == "NaT":
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, bool):
        return bool(value)
    return value


def _records_by_key(frame: pd.DataFrame | None, key_col: str) -> dict[str, dict[str, Any]]:
    if frame is None or frame.empty or key_col not in frame.columns:
        return {}
    keyed: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        key = row.get(key_col)
        if pd.isna(key):
            continue
        keyed[str(key)] = {column: _normalize_value(row.get(column)) for column in frame.columns}
    return keyed


def _latest_by_key(frame: pd.DataFrame | None, key_col: str, date_col: str = "date") -> dict[str, dict[str, Any]]:
    if frame is None or frame.empty or key_col not in frame.columns or date_col not in frame.columns:
        return {}
    working = frame.copy()
    working[date_col] = pd.to_datetime(working[date_col], errors="coerce")
    working = working.loc[working[date_col].notna()].sort_values(date_col)
    if working.empty:
        return {}
    latest = working.groupby(key_col, as_index=False).tail(1)
    keyed: dict[str, dict[str, Any]] = {}
    for _, row in latest.iterrows():
        key = row.get(key_col)
        if pd.isna(key):
            continue
        keyed[str(key)] = {column: _normalize_value(row.get(column)) for column in latest.columns}
    return keyed


def _top_problem_variables(frame: pd.DataFrame | None, limit: int = 5) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    working = frame.copy()
    if "latest_value_millions" in working.columns:
        working["_abs_value"] = pd.to_numeric(working["latest_value_millions"], errors="coerce").abs()
        working = working.sort_values("_abs_value", ascending=False)
    return [
        {column: _normalize_value(row.get(column)) for column in frame.columns}
        for _, row in working.head(limit).iterrows()
    ]


def _normalize_date_scalar(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return pd.Timestamp(ts).date().isoformat()


def build_downstream_handoff_bundle(
    *,
    project_goal_status_review: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    downstream_estimator_contract: pd.DataFrame | None,
    downstream_deposit_effect_use_case_review: pd.DataFrame | None,
    downstream_problem_variable_review: pd.DataFrame | None,
    fiscal_receipt_boundary_review: pd.DataFrame | None,
    downstream_deposit_effect_series_panel: pd.DataFrame | None,
    downstream_deposit_effect_comparison_panel: pd.DataFrame | None,
    backend_closeout_review: pd.DataFrame | None = None,
    backend_release_check: pd.DataFrame | None = None,
) -> dict[str, Any]:
    goals = _records_by_key(project_goal_status_review, "goal_key")
    receipt = _records_by_key(receipt_unblock_status, "branch_key")
    contract = _records_by_key(downstream_estimator_contract, "artifact_key")
    use_cases = _records_by_key(downstream_deposit_effect_use_case_review, "use_case_key")
    receipt_boundaries = _records_by_key(fiscal_receipt_boundary_review, "boundary_key")
    closeout = _records_by_key(backend_closeout_review, "review_key")
    release_check = _records_by_key(backend_release_check, "check_key")
    latest_series = _latest_by_key(downstream_deposit_effect_series_panel, "series_key")
    latest_comparisons = _latest_by_key(downstream_deposit_effect_comparison_panel, "comparison_key")

    current_headline = contract.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow", {})
    historical_bank = contract.get("bank_receipt_historical_default_view", {})
    row_mrv_series = latest_series.get("row_mrv_primary_nondefault_pilot_series", {})

    bundle = {
        "bundle_format": "tdc_downstream_handoff_v1",
        "generated_at_utc": utc_now_iso(),
        "distribution_scope": {
            "full_repo_regeneration_required": True,
            "partial_pack_status": "snapshot_only_unless_explicitly_marked_full_repo",
            "preferred_downstream_entrypoint": "tdc_downstream_handoff_bundle.json",
            "summary_note": (
                "This handoff bundle is the preferred downstream contract entrypoint, but regeneration requires the full "
                "repo plus its documented source inputs. A partial audit pack should be treated as a bounded snapshot "
                "unless it is explicitly labeled as a full regenerable repo export."
            ),
        },
        "summary": {
            "bank_receipts_status": goals.get("bank_receipts", {}).get("current_status"),
            "row_receipts_status": goals.get("row_receipts", {}).get("current_status"),
            "fiscal_flow_status": goals.get("fiscal_flow_tdc_equation", {}).get("current_status"),
            "monetary_status": goals.get("monetary_disaggregated_tdc_equation", {}).get("current_status"),
            "current_bank_headline_latest_date": _normalize_date_scalar(current_headline.get("latest_reference_date")),
            "current_bank_headline_latest_value_millions": current_headline.get("latest_value_millions"),
            "historical_bank_overlay_latest_date": _normalize_date_scalar(historical_bank.get("latest_reference_date")),
            "historical_bank_overlay_latest_value_millions": historical_bank.get("latest_value_millions"),
            "row_mrv_latest_date": _normalize_date_scalar(row_mrv_series.get("latest_nonzero_date")),
            "row_mrv_latest_value_millions": row_mrv_series.get("latest_nonzero_value_millions"),
        },
        "goal_status": goals,
        "receipt_unblock_status": receipt,
        "estimator_contract": contract,
        "use_cases": use_cases,
        "receipt_boundaries": receipt_boundaries,
        "backend_closeout_review": closeout,
        "backend_release_check": release_check,
        "problem_variables": {
            "top_rows": _top_problem_variables(downstream_problem_variable_review),
            "all_rows": (
                [] if downstream_problem_variable_review is None or downstream_problem_variable_review.empty
                else [
                    {column: _normalize_value(row.get(column)) for column in downstream_problem_variable_review.columns}
                    for row in downstream_problem_variable_review.to_dict(orient="records")
                ]
            ),
        },
        "series_panel": {
            "latest_by_series_key": latest_series,
            "historical_only_series_keys": sorted(
                [
                    key
                    for key, row in latest_series.items()
                    if bool(row.get("historical_only"))
                ]
            ),
            "nondefault_only_series_keys": sorted(
                [
                    key
                    for key, row in latest_series.items()
                    if bool(row.get("nondefault_only"))
                ]
            ),
        },
        "comparison_panel": {
            "latest_by_comparison_key": latest_comparisons,
            "historical_only_comparison_keys": sorted(
                [
                    key
                    for key, row in latest_comparisons.items()
                    if bool(row.get("historical_only"))
                ]
            ),
            "nondefault_only_comparison_keys": sorted(
                [
                    key
                    for key, row in latest_comparisons.items()
                    if bool(row.get("nondefault_only"))
                ]
            ),
        },
    }
    return bundle


def render_downstream_handoff_bundle_markdown(bundle: dict[str, Any]) -> str:
    title = "# Downstream Handoff Bundle"
    intro = (
        "Single backend handoff bundle for downstream repos. It keys the estimator contract, latest panel snapshots, "
        "receipt boundaries, and use-case routing into one machine-readable package."
    )
    summary = bundle.get("summary", {})
    lines = [
        title,
        "",
        intro,
        "",
        "## Distribution Scope",
        "",
        "- `full_repo_regeneration_required`: "
        + str(bundle.get("distribution_scope", {}).get("full_repo_regeneration_required", "n/a")),
        "- `partial_pack_status`: "
        + str(bundle.get("distribution_scope", {}).get("partial_pack_status", "n/a")),
        "- `preferred_downstream_entrypoint`: "
        + str(bundle.get("distribution_scope", {}).get("preferred_downstream_entrypoint", "n/a")),
        "- "
        + str(bundle.get("distribution_scope", {}).get("summary_note", "")),
        "",
        "## Summary",
        "",
        f"- `bank_receipts_status`: {summary.get('bank_receipts_status', 'n/a')}",
        f"- `row_receipts_status`: {summary.get('row_receipts_status', 'n/a')}",
        f"- `fiscal_flow_status`: {summary.get('fiscal_flow_status', 'n/a')}",
        f"- `monetary_status`: {summary.get('monetary_status', 'n/a')}",
        f"- `current_bank_headline_latest`: {summary.get('current_bank_headline_latest_date', 'n/a')} / {summary.get('current_bank_headline_latest_value_millions', 'n/a')}",
        f"- `historical_bank_overlay_latest`: {summary.get('historical_bank_overlay_latest_date', 'n/a')} / {summary.get('historical_bank_overlay_latest_value_millions', 'n/a')}",
        f"- `row_mrv_latest`: {summary.get('row_mrv_latest_date', 'n/a')} / {summary.get('row_mrv_latest_value_millions', 'n/a')}",
        "",
        "## Included Sections",
        "",
        "- `distribution_scope`",
        "- `goal_status`",
        "- `receipt_unblock_status`",
        "- `estimator_contract`",
        "- `use_cases`",
        "- `receipt_boundaries`",
        "- `backend_closeout_review`",
        "- `backend_release_check`",
        "- `problem_variables`",
        "- `series_panel.latest_by_series_key`",
        "- `comparison_panel.latest_by_comparison_key`",
        "",
    ]
    return "\n".join(lines)


def write_downstream_handoff_bundle(
    *,
    json_path: Path | str,
    markdown_path: Path | str,
    project_goal_status_review: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    downstream_estimator_contract: pd.DataFrame | None,
    downstream_deposit_effect_use_case_review: pd.DataFrame | None,
    downstream_problem_variable_review: pd.DataFrame | None,
    fiscal_receipt_boundary_review: pd.DataFrame | None,
    downstream_deposit_effect_series_panel: pd.DataFrame | None,
    downstream_deposit_effect_comparison_panel: pd.DataFrame | None,
    backend_closeout_review: pd.DataFrame | None = None,
    backend_release_check: pd.DataFrame | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    bundle = build_downstream_handoff_bundle(
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_deposit_effect_use_case_review=downstream_deposit_effect_use_case_review,
        downstream_problem_variable_review=downstream_problem_variable_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        downstream_deposit_effect_series_panel=downstream_deposit_effect_series_panel,
        downstream_deposit_effect_comparison_panel=downstream_deposit_effect_comparison_panel,
        backend_closeout_review=backend_closeout_review,
        backend_release_check=backend_release_check,
    )

    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(json_path, bundle)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_handoff_bundle_markdown(bundle), encoding="utf-8")

    return json_path, markdown_path, bundle
