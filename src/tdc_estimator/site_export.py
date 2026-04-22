from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .utils import round_if_number, utc_now_iso, write_json


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


def _frame_payload(df: pd.DataFrame) -> dict[str, Any]:
    payload: dict[str, Any] = {"columns": list(df.columns)}
    for column in df.columns:
        payload[column] = [_jsonable(value) for value in df[column].tolist()]
    return payload


def _records_payload(df: pd.DataFrame) -> dict[str, Any]:
    rows = []
    for _, row in df.iterrows():
        rows.append({column: _jsonable(value) for column, value in row.items()})
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
        "series_meta": series_meta,
        "method_meta": method_meta,
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
        "latest_base_components": latest_components,
        "latest_corrections": latest_corrections,
        "preferred_method": method_meta.get("preferred_method"),
        "preferred_methods_by_deposit_concept": method_meta.get("preferred_methods_by_deposit_concept", {}),
        "credit_union_policy": method_meta.get("credit_union_policy", {}),
    }

    research_payload: dict[str, Any] = {}
    research_frames = research_frames or {}
    for key, frame in research_frames.items():
        if frame is None:
            continue
        research_payload[key] = _records_payload(frame)

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
            "tagline": "Treasury-attributed component of deposits: estimator ladder, receipt boundaries, fiscal shell, and monetary cross-checks.",
            "thesis": "TDC should either add to deposits one-for-one or offset another deposit component one-for-one; this site compares the repo's transaction, fiscal-flow, and diagnostic proxy surfaces to show where that identity is strongest and where the remaining boundaries still sit.",
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
