from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .utils import utc_now_iso, write_json


ANCHOR_FORMAT_VERSION = "tdc_empirical_anchor_v1"
DEFAULT_CANONICAL_METHOD = "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"
DEFAULT_SCOPE_KEY = "canonical_tier2_depository_institution_mmf_rrp_prop_ru_flow"
UNITS = "millions_of_dollars"
SEASONAL_ADJUSTMENT = "not_seasonally_adjusted_quarterly_flow"
SIGN_CONVENTION = (
    "Signed quarterly contribution to Treasury-attributed deposit change; positive values increase TDC."
)

ANCHOR_COLUMNS = [
    "quarter",
    "date",
    "method_key",
    "scope_key",
    "opening_tdc_level",
    "tdc_change",
    "closing_tdc_level",
    "tdc_fiscal_flow",
    "tdc_debt_service",
    "tdc_auction_absorption_primary_proxy",
    "tdc_secondary_and_reconciliation_residual",
    "tdc_other_named",
    "fiscal_flow_measurement_status",
    "debt_service_measurement_status",
    "auction_absorption_measurement_status",
    "secondary_trades_measurement_status",
    "other_measurement_status",
    "source_vintage_id",
    "source_hashes",
    "units",
    "seasonal_adjustment",
    "sign_convention",
    "known_boundaries",
]

MEASUREMENT_STATUSES = [
    "direct_aggregate_cash_flow",
    "direct_aggregate_allocated_proxy_by_holder",
    "primary_allocation_proxy",
    "residual_unidentified_or_bounded_residual",
    "named_treasury_fed_cash_effect",
]

CLAIM_FLAGS = {
    "historical_empirical_accounting_decomposition": True,
    "conditional_projection_claim_allowed": True,
    "predictive_forecast_claim_allowed": False,
    "public_launch_ready": False,
    "strict_gross_flow_claim_allowed": False,
    "secondary_trades_measured_claim_allowed": False,
    "auction_final_absorption_claim_allowed": False,
}


def _quarter_label(value: pd.Timestamp) -> str:
    quarter = ((int(value.month) - 1) // 3) + 1
    return f"{int(value.year)}-Q{quarter}"


def _read_date_csv(path: Path | str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        raise ValueError(f"{path} must include a date column.")
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    return out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _numeric(frame: pd.DataFrame, column: str, *, fill: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(fill, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(fill)


def _source_hashes(files: list[Path]) -> dict[str, str]:
    return {path.name: _sha256(path) for path in files if path.exists()}


def build_tdc_empirical_anchor(
    *,
    estimates: pd.DataFrame,
    components: pd.DataFrame,
    method_meta: dict[str, Any] | None = None,
    source_hashes_by_file: dict[str, str] | None = None,
    generated_at_utc: str | None = None,
    tdcest_commit_or_version: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    method_meta = method_meta or {}
    canonical_method = str(method_meta.get("canonical_tier2_method") or DEFAULT_CANONICAL_METHOD)
    if canonical_method not in estimates.columns:
        raise ValueError(f"Missing canonical TDC method column: {canonical_method}")

    est = estimates.copy()
    comp = components.copy()
    for frame in [est, comp]:
        if "date" not in frame.columns:
            raise ValueError("estimates and components must include a date column.")
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()

    merged = est[["date", canonical_method]].merge(comp, on="date", how="left")
    merged = merged.loc[pd.to_numeric(merged[canonical_method], errors="coerce").notna()]
    merged = merged.sort_values("date").reset_index(drop=True)
    if merged.empty:
        raise ValueError(f"No non-null rows are available for canonical method {canonical_method}.")

    tdc_change = pd.to_numeric(merged[canonical_method], errors="coerce")
    fiscal_flow = _numeric(merged, "du_noninterest_outlay_proxy") - _numeric(merged, "du_receipt_proxy")
    debt_service = _numeric(merged, "du_coupon_proxy_selected_narrow")
    auction_primary_proxy = pd.Series(0.0, index=merged.index, dtype="float64")
    other_named = _numeric(merged, "minus_treasury_operating_cash_tx") + _numeric(
        merged, "fed_remit_positive"
    )
    residual = tdc_change - fiscal_flow - debt_service - auction_primary_proxy - other_named
    opening = tdc_change.cumsum().shift(1).fillna(0.0)
    closing = opening + tdc_change

    quarter_start = _quarter_label(pd.Timestamp(merged["date"].iloc[0]))
    quarter_end = _quarter_label(pd.Timestamp(merged["date"].iloc[-1]))
    source_vintage_id = f"tdcest_processed_{quarter_start}_through_{quarter_end}"
    source_hashes_by_file = source_hashes_by_file or {}
    source_hashes_json = json.dumps(source_hashes_by_file, sort_keys=True, separators=(",", ":"))
    known_boundaries = (
        "Rows are limited to non-null canonical Tier 2 modern-method observations. "
        "Opening and closing TDC levels are cumulative accounting-index levels, not source-observed stock levels. "
        "Fiscal flow is a tdcest aggregate outlay-minus-receipt proxy; debt service is an allocated coupon proxy. "
        "Primary auction allocation is not populated from investor-class auction data in this export and is held at zero. "
        "Secondary trades are not measured directly; the residual closes the reconciliation identity. "
        "Other is limited to named Treasury/Fed cash effects from the processed component table."
    )

    anchor = pd.DataFrame(
        {
            "quarter": [_quarter_label(pd.Timestamp(value)) for value in merged["date"]],
            "date": merged["date"].dt.date.astype(str),
            "method_key": canonical_method,
            "scope_key": DEFAULT_SCOPE_KEY,
            "opening_tdc_level": opening,
            "tdc_change": tdc_change,
            "closing_tdc_level": closing,
            "tdc_fiscal_flow": fiscal_flow,
            "tdc_debt_service": debt_service,
            "tdc_auction_absorption_primary_proxy": auction_primary_proxy,
            "tdc_secondary_and_reconciliation_residual": residual,
            "tdc_other_named": other_named,
            "fiscal_flow_measurement_status": "direct_aggregate_cash_flow",
            "debt_service_measurement_status": "direct_aggregate_allocated_proxy_by_holder",
            "auction_absorption_measurement_status": "primary_allocation_proxy",
            "secondary_trades_measurement_status": "residual_unidentified_or_bounded_residual",
            "other_measurement_status": "named_treasury_fed_cash_effect",
            "source_vintage_id": source_vintage_id,
            "source_hashes": source_hashes_json,
            "units": UNITS,
            "seasonal_adjustment": SEASONAL_ADJUSTMENT,
            "sign_convention": SIGN_CONVENTION,
            "known_boundaries": known_boundaries,
        },
        columns=ANCHOR_COLUMNS,
    )

    comparison_method_keys = [
        str(key)
        for key in [
            method_meta.get("preferred_method"),
            "tdc_tier2_interest_corrected_bank_only_ru_flow",
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
        ]
        if key and key != canonical_method
    ]
    manifest = {
        "anchor_format_version": ANCHOR_FORMAT_VERSION,
        "generated_at_utc": generated_at_utc or utc_now_iso(),
        "tdcest_commit_or_version": tdcest_commit_or_version or f"tdc-estimator {__version__}",
        "canonical_method_key": canonical_method,
        "comparison_method_keys": list(dict.fromkeys(comparison_method_keys)),
        "scope_key": DEFAULT_SCOPE_KEY,
        "quarter_start": quarter_start,
        "quarter_end": quarter_end,
        "row_count": int(len(anchor)),
        "units": UNITS,
        "seasonal_adjustment": SEASONAL_ADJUSTMENT,
        "sign_convention": SIGN_CONVENTION,
        "source_vintage_id": source_vintage_id,
        "source_hashes_by_file": source_hashes_by_file,
        "channel_measurement_status_allowed_values": MEASUREMENT_STATUSES,
        "known_boundaries": known_boundaries,
        "claim_flags": CLAIM_FLAGS,
    }
    return anchor, manifest


def write_tdc_empirical_anchor(
    *,
    processed_dir: Path | str,
    estimates_file: Path | str | None = None,
    components_file: Path | str | None = None,
    method_meta_file: Path | str | None = None,
    out: Path | str | None = None,
    manifest_out: Path | str | None = None,
    generated_at_utc: str | None = None,
) -> tuple[Path, Path, pd.DataFrame, dict[str, Any]]:
    processed = Path(processed_dir)
    estimates_path = Path(estimates_file) if estimates_file else processed / "tdc_estimates.csv"
    components_path = Path(components_file) if components_file else processed / "tdc_components.csv"
    method_meta_path = Path(method_meta_file) if method_meta_file else processed / "method_meta.json"
    out_path = Path(out) if out else processed / "tdc_empirical_anchor.csv"
    manifest_path = Path(manifest_out) if manifest_out else processed / "tdc_empirical_anchor_manifest.json"

    estimates = _read_date_csv(estimates_path)
    components = _read_date_csv(components_path)
    method_meta = json.loads(method_meta_path.read_text(encoding="utf-8")) if method_meta_path.exists() else {}
    source_hashes = _source_hashes([estimates_path, components_path, method_meta_path])
    anchor, manifest = build_tdc_empirical_anchor(
        estimates=estimates,
        components=components,
        method_meta=method_meta,
        source_hashes_by_file=source_hashes,
        generated_at_utc=generated_at_utc,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    anchor.to_csv(out_path, index=False, float_format="%.17g")
    write_json(manifest_path, manifest)
    return out_path, manifest_path, anchor, manifest
