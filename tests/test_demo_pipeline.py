from __future__ import annotations

import json
from pathlib import Path

from tdc_estimator.demo import generate_synthetic_raw_bundle
from tdc_estimator.pipeline import run_estimation_pipeline


def test_demo_pipeline_runs(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    figures_dir = tmp_path / "figures"
    site_dir = tmp_path / "site"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    result = run_estimation_pipeline(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        figures_dir=figures_dir,
        site_dir=site_dir,
    )

    assert "tdc_base_bank_only_ru_flow" in result["estimates"].columns
    assert "tdc_base_broad_depository_np_cu_ru_flow" in result["estimates"].columns
    assert (processed_dir / "tdc_estimates.csv").exists()
    assert (figures_dir / "tdc_method_comparison.png").exists()
    assert (figures_dir / "tdc_credit_union_increments.png").exists()
    assert (site_dir / "bundle.json").exists()

    bundle = json.loads((site_dir / "bundle.json").read_text())
    assert bundle["metadata"]["value_units"]["nominal"] == "Millions of U.S. dollars"
    assert "gdp_deflator" in bundle["references"]["columns"]
