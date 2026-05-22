from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re
from typing import Any

import pandas as pd

from .utils import round_if_number, utc_now_iso, write_json


PUBLIC_RESEARCH_FIELD_MAP = {
    "theory_measurement_map": {
        "public_key": "theory_map",
        "columns": {
            "equation_family": "equation_family",
            "display_order": "display_order",
            "display_title": "display_title",
            "equation_key": "equation_key",
            "latex": "latex",
            "plain_english_summary": "plain_english_summary",
            "current_measurement_mapping": "measurement_note",
            "main_caveat": "limit_note",
            "implementation_status": "implementation_status",
            "repo_role": "measurement_role",
        },
    },
    "project_goal_status_review": {
        "public_key": "goal_status",
        "columns": {
            "goal_key": "goal_key",
            "current_status": "current_status",
            "summary_note": "summary_note",
            "latest_relevant_date": "latest_relevant_date",
            "binding_blocker": "binding_blocker",
        },
    },
    "tier3_research_comparison": {
        "public_key": "fiscal_comparison",
        "columns": {
            "comparison_key": "entry_key",
            "reference_date": "reference_date",
            "tier2_bank_only_mil": "tier2_bank_only_mil",
            "tier3_bank_only_mil": "tier3_bank_only_mil",
            "historical_bank_receipt_variant_mil": "historical_bank_receipt_variant_mil",
            "historical_bank_lower_bound_variant_mil": "historical_bank_lower_bound_variant_mil",
            "current_row_mrv_pilot_latest_date": "current_row_mrv_pilot_latest_date",
            "bank_receipt_boundary": "bank_receipt_boundary",
            "row_receipt_boundary": "row_receipt_boundary",
            "interpretation": "interpretation",
        },
    },
    "receipt_unblock_status": {
        "public_key": "receipt_status",
        "columns": {
            "branch_key": "branch_key",
            "latest_relevant_date": "latest_relevant_date",
            "latest_value_millions": "latest_value_millions",
            "summary_note": "summary_note",
            "binding_blocker": "binding_blocker",
            "missing_source_families": "missing_source_families",
        },
    },
    "bank_receipt_stop_gate": {
        "public_key": "bank_receipt_status",
        "columns": {
            "row_type": "row_type",
            "status": "status",
        },
    },
    "row_mrv_stop_gate": {
        "public_key": "foreign_pilot_status",
        "columns": {
            "row_type": "row_type",
            "status": "status",
        },
    },
    "row_mrv_nondefault_evidence_summary": {
        "public_key": "foreign_pilot_evidence",
        "columns": {
            "promotion_checks_complete": "promotion_checks_complete",
            "promotion_checks_missing": "promotion_checks_missing",
        },
    },
    "fiscal_reconciliation_residuals": {
        "public_key": "fiscal_residuals",
        "columns": {
            "date": "date",
            "tier0_reconstruction_residual_mil": "tier0_reconstruction_residual_mil",
            "tier2_reconstruction_residual_mil": "tier2_reconstruction_residual_mil",
            "tier3_reconstruction_residual_mil": "tier3_reconstruction_residual_mil",
        },
    },
    "fiscal_source_quality": {
        "public_key": "fiscal_quality",
        "columns": {
            "row_family": "row_family",
            "included_in_headline": "included_in_headline",
            "notes": "notes",
            "reliability_grade": "reliability_grade",
            "latest_value_millions": "latest_value_millions",
        },
    },
    "fiscal_receipt_boundary_review": {
        "public_key": "fiscal_receipt_boundaries",
        "columns": {
            "boundary_key": "boundary_key",
            "interpretation": "interpretation",
            "binding_blocker": "binding_blocker",
            "latest_value_millions": "latest_value_millions",
        },
    },
    "monetary_target_preference_review": {
        "public_key": "monetary_review",
        "columns": {
            "preferred_target": "preferred_target",
            "depository_residual_after_expanded_mil": "depository_residual_after_expanded_mil",
            "commercial_bank_residual_after_expanded_mil": "commercial_bank_residual_after_expanded_mil",
            "recommendation_status": "recommendation_status",
            "review_rationale": "review_rationale",
        },
    },
    "workstream_end_state_map": {
        "public_key": "next_steps",
        "columns": {
            "recommended_mode": "recommended_mode",
            "workstream_key": "next_step_key",
            "summary_note": "summary_note",
            "binding_blocker": "binding_blocker",
            "next_finite_push": "next_finite_push",
        },
    },
}


def _jsonable(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass
    return value


def _public_copy(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value
    substitutions = [
        (r"\brepo's\b", "site's"),
        (r"\brepo’s\b", "site’s"),
        (r"\brepo\b", "site"),
        (r"\bnondefault\b", "bounded"),
        (r"\bworkstream\b", "line of work"),
        (r"\bsurfaces\b", "views"),
        (r"\bsurface\b", "view"),
        (r"\bartifacts\b", "tables"),
        (r"\bartifact\b", "table"),
        (r"\bbundle\b", "dataset"),
        (r"\bstress-test\b", "stress"),
        (r"\bstress test\b", "stress case"),
        (r"\bstress surface\b", "stress case"),
        (r"\bdiagnostic system\b", "diagnostic cross-check"),
        (r"\bresidual system\b", "residual approach"),
        (r"\bco-equal headline estimate\b", "headline estimate"),
        (r"\bcarried forward\b", "kept visible"),
    ]
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _frame_payload(df: pd.DataFrame) -> dict[str, Any]:
    payload: dict[str, Any] = {"columns": list(df.columns)}
    for column in df.columns:
        payload[column] = [_jsonable(value) for value in df[column].tolist()]
    return payload


def _records_payload(df: pd.DataFrame, *, public_text: bool = False) -> dict[str, Any]:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                column: _jsonable(_public_copy(value) if public_text else value)
                for column, value in row.items()
            }
        )
    return {
        "columns": list(df.columns),
        "rows": rows,
    }


def export_site_bundle(
    estimates: pd.DataFrame,
    components: pd.DataFrame,
    corrections: pd.DataFrame,
    quarterly: pd.DataFrame,
    series_meta: dict[str, Any],
    method_meta: dict[str, Any],
    out_dir: Path | str,
    research_frames: dict[str, pd.DataFrame] | None = None,
) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    metadata_payload = {
        "generated_at_utc": utc_now_iso(),
        "value_units": {
            "nominal": "Millions of U.S. dollars",
            "nominal_example": "60,592 means 60,592 million dollars, or about $60.6 billion.",
            "real_toggle": "Optional latest-quarter-dollar restatement using the GDP implicit price deflator (GDPDEF).",
            "percent_of_gdp_toggle": "Optional percent-of-GDP view. Annualizes the quarterly TDC flow (in millions) and divides by nominal GDP (SAAR, billions): percent = value_millions * 4 / (nominal_gdp_saar_bil * 1000) * 100.",
        },
    }

    latest_date = estimates.index.max()
    latest_methods = {}
    latest_components = {}
    latest_corrections = {}
    if pd.notna(latest_date):
        latest_methods = {
            col: round_if_number(estimates.loc[latest_date, col], 3)
            for col in estimates.columns
        }
        latest_components = {
            col: round_if_number(components.loc[latest_date, col], 3)
            for col in components.columns
        }
        latest_corrections = {
            col: round_if_number(corrections.loc[latest_date, col], 3)
            for col in corrections.columns
        }

    summary_payload = {
        "generated_at_utc": utc_now_iso(),
        "latest_period": pd.Timestamp(latest_date).date().isoformat() if pd.notna(latest_date) else None,
        "available_methods": list(estimates.columns),
        "latest_methods": latest_methods,
        "preferred_method": method_meta.get("preferred_method"),
        "preferred_methods_by_deposit_concept": method_meta.get("preferred_methods_by_deposit_concept", {}),
        "credit_union_policy": method_meta.get("credit_union_policy", {}),
    }

    research_payload: dict[str, Any] = {}
    research_frames = research_frames or {}
    for key, frame in research_frames.items():
        config = PUBLIC_RESEARCH_FIELD_MAP.get(key)
        if frame is None or config is None:
            continue
        available = {src: dest for src, dest in config["columns"].items() if src in frame.columns}
        public_frame = frame.loc[:, list(available.keys())].rename(columns=available).copy()
        research_payload[config["public_key"]] = _records_payload(public_frame, public_text=True)

    latest_ladder = {}
    if latest_methods:
        latest_ladder = {
            "bank_only": {
                "tier0": latest_methods.get("tdc_base_bank_only_ru_flow"),
                "tier1": latest_methods.get("tdc_tier1_fed_corrected_bank_only_ru_flow"),
                "tier2": latest_methods.get("tdc_tier2_interest_corrected_bank_only_ru_flow"),
                "tier3": latest_methods.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow"),
            },
            "broad_depository": {
                "tier0": latest_methods.get("tdc_base_broad_depository_np_cu_ru_flow"),
                "tier1": latest_methods.get("tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow"),
                "tier2": latest_methods.get("tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow"),
                "tier3": latest_methods.get("tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow"),
            },
        }

    bundle_path = out_dir / "bundle.json"
    site_bundle_path = data_dir / "bundle.json"
    reference_columns = [
        column
        for column in ["gdp_deflator", "nominal_gdp_saar_bil"]
        if column in quarterly.columns
    ]
    reference_frame = quarterly[reference_columns].copy() if reference_columns else pd.DataFrame(index=estimates.index)
    bundle_payload = {
        "bundle_format": "tdc_site_bundle_v4",
        "generated_at_utc": utc_now_iso(),
        "summary": summary_payload,
        "metadata": metadata_payload,
        "site": {
            "title": "TDCest",
            "tagline": "Treasury Deposit Component: estimator ladder, canonical Tier 2 row, receipt boundaries, fiscal shell, and monetary cross-checks.",
            "thesis": "TDC should either add to deposits one-for-one or offset another deposit component one-for-one; this site compares the transaction ladder, fiscal-flow estimates, and monetary cross-checks to show where that identity is strongest and where the remaining boundaries still sit.",
            "latest_ladder": latest_ladder,
        },
        "dates": [pd.Timestamp(idx).date().isoformat() for idx in estimates.index],
        "estimates": _frame_payload(estimates),
        "components": _frame_payload(components),
        "corrections": _frame_payload(corrections),
        "references": _frame_payload(reference_frame.reindex(estimates.index)),
        "research": research_payload,
    }
    write_json(bundle_path, bundle_payload)
    write_json(site_bundle_path, bundle_payload)

    return {
        "bundle_json": str(bundle_path),
        "site_bundle_json": str(site_bundle_path),
    }
