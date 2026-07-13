"""Transitive DS^T_DU release manifest (freeze-bless ingest MUST 4).

Hashes the COMPLETE dependency set of the DS release — every input and every
output — and validates ALL of them at readback (the prior component-support
validator checked only output hashes, which let three stale-release defects
slip: the regression splice, the promotion docs, and the empirical anchor).
Mutating any declared file after manifest build fails validation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__

SCHEMA_VERSION = "dst_du_release_v1"

INPUT_FILES = {
    "processed": [
        "tier2_interest_component_candidate.csv",
        "tier2_interest_source_constraints.csv",
        "tier2_interest_source_window_validation.csv",
        "tier2_regression_interest_backcast_wide.csv",
        "tdc_components.csv",
        "tdc_estimates.csv",
        "tdc_du_fiscal_flow_research.csv",
    ],
    "raw": [
        "support__bank_tier2_component_interest_proxy.csv",
        "support__credit_union_tier2_component_interest_proxy.csv",
        "support__row_tier2_component_interest_proxy.csv",
        "support__tier2_component_release_manifest.json",
        "support__fed_treasury_interest_components.csv",
        "support__mmf_fund_month.csv",
    ],
}
RAW_GLOB_INPUTS = ["fred__du_*_tsy_level.csv"]

OUTPUT_FILES = [
    "dst_du_expense_panel.csv",
    "dst_du_sector_allocation_panel.csv",
    "dst_du_reconciliation.csv",
    "dst_du_reconciliation_manifest.json",
    "dst_du_long_history.csv",
    "dst_du_long_history_manifest.json",
    "nonmarketable_sidecar.csv",
    "tdc_empirical_anchor.csv",
    "tdc_empirical_anchor_manifest.json",
]

METHOD_TIER_SCHEMA = [
    "certified_modern_component_identity",
    "analysis_component_identity",
    "backcast_bounded_ratio_expense_equivalent",
    "frame_only_not_estimated",
]

OPEN_PROMOTION_GATES = {
    "ffiec_002_rcfd0260_pilot": "open_trading_account_inclusion_or_bound_required",
    "shl_a7_annual_validator": "open",
    "row_ita_annual_anchor": "open_bind_by_series_title_code",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _collect(processed_dir: Path, raw_dir: Path) -> tuple[dict[str, str], dict[str, str], list[str]]:
    inputs: dict[str, str] = {}
    missing: list[str] = []
    for name in INPUT_FILES["processed"]:
        path = processed_dir / name
        if path.exists():
            inputs[f"processed/{name}"] = _sha256(path)
        else:
            missing.append(f"processed/{name}")
    for name in INPUT_FILES["raw"]:
        path = raw_dir / name
        if path.exists():
            inputs[f"raw/{name}"] = _sha256(path)
        else:
            missing.append(f"raw/{name}")
    for pattern in RAW_GLOB_INPUTS:
        for path in sorted(raw_dir.glob(pattern)):
            inputs[f"raw/{path.name}"] = _sha256(path)
    outputs: dict[str, str] = {}
    for name in OUTPUT_FILES:
        path = processed_dir / name
        if path.exists():
            outputs[f"processed/{name}"] = _sha256(path)
        else:
            missing.append(f"processed/{name}")
    return inputs, outputs, missing


def build_dst_du_release_manifest(
    *,
    processed_dir: Path | str,
    raw_dir: Path | str,
    manifest_path: Path | str,
    generated_at_utc: str | None = None,
) -> dict[str, object]:
    processed = Path(processed_dir)
    raw = Path(raw_dir)
    inputs, outputs, missing = _collect(processed, raw)
    if missing:
        raise ValueError(f"DS release dependency files are missing: {missing}")

    reconciliation = json.loads((processed / "dst_du_reconciliation_manifest.json").read_text())
    long_history = json.loads((processed / "dst_du_long_history_manifest.json").read_text())
    content_digest = hashlib.sha256(
        json.dumps({"inputs": inputs, "outputs": outputs}, sort_keys=True).encode()
    ).hexdigest()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "build_id": f"dst_du_{content_digest[:16]}",
        "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat(),
        "estimator_version": f"tdc-estimator {__version__}",
        "source_window": {
            "certified": ["2022-03-31", "2025-12-31"],
            "analysis": ["2010-06-30", "2021-12-31"],
            "backcast": ["2002-03-31", "2010-03-31"],
        },
        "method_tier_schema": METHOD_TIER_SCHEMA,
        "estimand_families": {
            "dst_du_expense_*": "expense_control_modified_accrual",
            "dst_du_cash_*": "reserved_unbuilt_requires_payment_redemption_bridge",
        },
        "gate_classification": {
            "residual_vs_direct": reconciliation["gate_results"],
            "automatic_outcome": reconciliation["outcome"],
            "open_source_gates": OPEN_PROMOTION_GATES,
            "nmfp_mapping_gate": "not_evaluated_fund_month_aggregates_only",
            "deterministic_fallback": (
                "all DS rows are research-tier; canonical Tier 2 keys unchanged; "
                "gates are never relaxed"
            ),
        },
        "long_history": {
            "method_exception": long_history["method_exception"],
            "backtest": long_history["rolling_origin_backtest"],
            "seam_flag": long_history["splice_seam_flag"],
        },
        "inputs": inputs,
        "outputs": outputs,
    }
    path = Path(manifest_path)
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def validate_dst_du_release_manifest(
    *,
    processed_dir: Path | str,
    raw_dir: Path | str,
    manifest_path: Path | str,
) -> dict[str, object]:
    """Revalidate EVERY declared input and output hash. Fails closed."""
    processed = Path(processed_dir)
    raw = Path(raw_dir)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unexpected DS release manifest schema: {manifest.get('schema_version')}")
    failures: list[str] = []
    for section in ("inputs", "outputs"):
        for label, expected in manifest.get(section, {}).items():
            zone, name = label.split("/", 1)
            path = (processed if zone == "processed" else raw) / name
            if not path.exists():
                failures.append(f"{section}:{label} missing")
                continue
            actual = _sha256(path)
            if actual != expected:
                failures.append(f"{section}:{label} hash mismatch")
    if failures:
        raise ValueError(
            "DS release manifest validation FAILED (stale or mutated dependency): "
            + "; ".join(failures[:10])
        )
    return manifest
