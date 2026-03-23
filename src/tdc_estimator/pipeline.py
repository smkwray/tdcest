from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .catalog import all_fred_series
from .estimators import compute_estimates
from .io import build_quarterly_frame
from .plots import build_all_figures
from .site_export import export_site_bundle
from .utils import write_json


def run_estimation_pipeline(
    *,
    raw_dir: Path | str,
    processed_dir: Path | str,
    figures_dir: Path | str | None = None,
    site_dir: Path | str | None = None,
) -> dict[str, Any]:
    specs = all_fred_series(include_optional=True)
    quarterly, series_meta = build_quarterly_frame(raw_dir, specs)
    estimates, components, method_meta = compute_estimates(quarterly)

    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    quarterly_path = processed_dir / "quarterly_inputs.csv"
    estimates_path = processed_dir / "tdc_estimates.csv"
    components_path = processed_dir / "tdc_components.csv"
    method_meta_path = processed_dir / "method_meta.json"

    quarterly_to_write = quarterly.copy()
    quarterly_to_write.index.name = "date"
    quarterly_to_write.to_csv(quarterly_path)

    estimates_to_write = estimates.copy()
    estimates_to_write.index.name = "date"
    estimates_to_write.to_csv(estimates_path)

    components_to_write = components.copy()
    components_to_write.index.name = "date"
    components_to_write.to_csv(components_path)

    write_json(method_meta_path, method_meta)

    figure_outputs: list[str] = []
    if figures_dir is not None:
        figure_outputs = build_all_figures(estimates, components, figures_dir)

    site_outputs: dict[str, str] = {}
    if site_dir is not None:
        site_outputs = export_site_bundle(estimates, components, quarterly, series_meta, method_meta, site_dir)

    return {
        "quarterly": quarterly,
        "estimates": estimates,
        "components": components,
        "series_meta": series_meta,
        "method_meta": method_meta,
        "quarterly_path": str(quarterly_path),
        "estimates_path": str(estimates_path),
        "components_path": str(components_path),
        "method_meta_path": str(method_meta_path),
        "figure_outputs": figure_outputs,
        "site_outputs": site_outputs,
    }
