from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .utils import round_if_number, utc_now_iso, write_json


def _frame_payload(df: pd.DataFrame) -> dict[str, Any]:
    payload: dict[str, Any] = {"columns": list(df.columns)}
    for column in df.columns:
        payload[column] = df[column].tolist()
    return payload


def export_site_bundle(
    estimates: pd.DataFrame,
    components: pd.DataFrame,
    quarterly: pd.DataFrame,
    series_meta: dict[str, Any],
    method_meta: dict[str, Any],
    out_dir: Path | str,
) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for existing in out_dir.iterdir():
        if existing.name == ".gitkeep":
            continue
        if existing.is_file():
            existing.unlink()

    metadata_payload = {
        "generated_at_utc": utc_now_iso(),
        "series_meta": series_meta,
        "method_meta": method_meta,
        "value_units": {
            "nominal": "Millions of U.S. dollars",
            "nominal_example": "60,592 means 60,592 million dollars, or about $60.6 billion.",
            "real_toggle": "Optional latest-quarter-dollar restatement using the GDP implicit price deflator (GDPDEF).",
        },
    }

    latest_date = estimates.index.max()
    latest_methods = {}
    latest_components = {}
    if pd.notna(latest_date):
        latest_methods = {
            col: round_if_number(estimates.loc[latest_date, col], 3)
            for col in estimates.columns
        }
        latest_components = {
            col: round_if_number(components.loc[latest_date, col], 3)
            for col in components.columns
        }

    summary_payload = {
        "generated_at_utc": utc_now_iso(),
        "latest_period": pd.Timestamp(latest_date).date().isoformat() if pd.notna(latest_date) else None,
        "available_methods": list(estimates.columns),
        "latest_methods": latest_methods,
        "latest_base_components": latest_components,
        "preferred_method": method_meta.get("preferred_method"),
        "preferred_methods_by_deposit_concept": method_meta.get("preferred_methods_by_deposit_concept", {}),
        "credit_union_policy": method_meta.get("credit_union_policy", {}),
    }

    bundle_path = out_dir / "bundle.json"
    reference_columns = [column for column in ["gdp_deflator"] if column in quarterly.columns]
    reference_frame = quarterly[reference_columns].copy() if reference_columns else pd.DataFrame(index=estimates.index)
    bundle_payload = {
        "bundle_format": "tdc_site_bundle_v2",
        "generated_at_utc": utc_now_iso(),
        "summary": summary_payload,
        "metadata": metadata_payload,
        "dates": [pd.Timestamp(idx).date().isoformat() for idx in estimates.index],
        "estimates": _frame_payload(estimates),
        "components": _frame_payload(components),
        "references": _frame_payload(reference_frame.reindex(estimates.index)),
    }
    write_json(bundle_path, bundle_payload)

    return {
        "bundle_json": str(bundle_path),
    }
