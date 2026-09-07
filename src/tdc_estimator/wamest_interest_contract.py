from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_WAMEST_INTEREST_ALLOCATION_CANDIDATES = [
    Path("outputs/full_coverage_release/sector_interest_allocation_weights.csv"),
    Path("data/processed/sector_interest_allocation_weights.csv"),
]

DEFAULT_WAMEST_COMPONENT_BUCKET_CANDIDATES = [
    Path("outputs/full_coverage_release/sector_component_bucket_weights.csv"),
    Path("data/processed/sector_component_bucket_weights.csv"),
]

DEFAULT_WAMEST_OBSERVABILITY_CANDIDATES = [
    Path("outputs/full_coverage_release/sector_interest_observability_tier.csv"),
    Path("data/processed/sector_interest_observability_tier.csv"),
]

INTEREST_ALLOCATION_REQUIRED_COLUMNS = {
    "date",
    "sector_key",
    "component_key",
    "central_weight",
    "low_weight",
    "high_weight",
    "gross_interest_weight",
    "gross_interest_low_weight",
    "gross_interest_high_weight",
    "weight_class",
    "eligible_for_gross_interest",
    "weight_unit",
    "weight_basis",
    "source_family",
    "observability_tier",
}

COMPONENT_BUCKET_REQUIRED_COLUMNS = {
    "date",
    "sector_key",
    "component_key",
    "bucket_key",
    "bucket_weight",
    "bucket_weight_unit",
    "bucket_basis",
    "source_family",
    "observability_tier",
}

OBSERVABILITY_REQUIRED_COLUMNS = {
    "date",
    "sector_key",
    "component_key",
    "observability_tier",
    "source_family",
    "uses_revaluation_inference",
    "uses_tic_anchor",
    "uses_regulatory_constraint",
    "uses_peer_fallback",
}

ACTIVE_TDCEST_INTEREST_COMPONENT_KEYS = {
    "coupon_accrual",
    "bill_amortized_discount",
    "frn_accrued_interest",
}

RESERVED_TDCEST_INTEREST_COMPONENT_KEYS = {
    "notes_accrued_interest",
    "bonds_accrued_interest",
    "tips_accrued_interest",
    "tips_inflation_compensation",
}

KNOWN_TDCEST_INTEREST_COMPONENT_KEYS = (
    ACTIVE_TDCEST_INTEREST_COMPONENT_KEYS | RESERVED_TDCEST_INTEREST_COMPONENT_KEYS
)


def resolve_first_existing_optional(base_dir: Path | str, candidates: list[Path]) -> Path | None:
    base = Path(base_dir)
    for candidate in candidates:
        path = base / candidate
        if path.exists():
            return path
    return None


def resolve_wamest_interest_contract_paths(wamest_root: Path | str) -> dict[str, Path | None]:
    return {
        "sector_interest_allocation_weights": resolve_first_existing_optional(
            wamest_root,
            DEFAULT_WAMEST_INTEREST_ALLOCATION_CANDIDATES,
        ),
        "sector_component_bucket_weights": resolve_first_existing_optional(
            wamest_root,
            DEFAULT_WAMEST_COMPONENT_BUCKET_CANDIDATES,
        ),
        "sector_interest_observability_tier": resolve_first_existing_optional(
            wamest_root,
            DEFAULT_WAMEST_OBSERVABILITY_CANDIDATES,
        ),
    }


def _validate_contract_table(df: pd.DataFrame, required_columns: set[str], label: str) -> pd.DataFrame:
    df = df.copy()
    path = label
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing required WAMEST interest-contract columns: {', '.join(sorted(missing))}")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "component_key" in df.columns:
        unknown = sorted(set(df["component_key"].dropna().astype(str)) - KNOWN_TDCEST_INTEREST_COMPONENT_KEYS)
        if unknown:
            raise ValueError(f"{path} has unknown WAMEST interest component_key values: {', '.join(unknown)}")
    for column, expected in [
        ("weight_unit", "usd_millions"),
        ("bucket_weight_unit", "fraction"),
    ]:
        if column in df.columns:
            observed = set(df[column].dropna().astype(str))
            if observed != {expected}:
                raise ValueError(
                    f"{path} requires {column}={expected}; observed {', '.join(sorted(observed)) or 'missing'}"
                )
    keys = ["date", "sector_key", "component_key"]
    if "bucket_key" in required_columns:
        keys.append("bucket_key")
    if df[keys].isna().any().any() or df.duplicated(keys).any():
        raise ValueError(f"{path} requires unique, complete date/sector/component keys")
    return df


def _read_contract_table(path: Path | str, required_columns: set[str]) -> pd.DataFrame:
    return _validate_contract_table(pd.read_csv(path), required_columns, str(path))


def read_wamest_interest_allocation_weights(path: Path | str) -> pd.DataFrame:
    return validate_wamest_interest_allocation_weights(pd.read_csv(path), str(path))


def validate_wamest_interest_allocation_weights(df: pd.DataFrame, label: str = "WAMEST weights") -> pd.DataFrame:
    frame = _validate_contract_table(df, INTEREST_ALLOCATION_REQUIRED_COLUMNS, label)
    path = label
    gross = pd.to_numeric(frame["gross_interest_weight"], errors="raise")
    if not np.isfinite(gross.dropna()).all():
        raise ValueError(f"{path} has nonfinite gross_interest_weight values")
    if gross.dropna().lt(0.0).any():
        raise ValueError(f"{path} has negative gross_interest_weight values")
    flags = frame["eligible_for_gross_interest"].astype(str).str.lower()
    if not flags.isin({"true", "false", "1", "0"}).all():
        raise ValueError(f"{path} requires explicit gross-interest eligibility booleans")
    eligible = flags.isin({"true", "1"})
    frame["eligible_for_gross_interest"] = eligible
    if gross[~eligible].notna().any():
        raise ValueError(f"{path} assigns gross-interest weights to ineligible rows")
    return frame


def read_wamest_component_bucket_weights(path: Path | str) -> pd.DataFrame:
    return validate_wamest_component_bucket_weights(pd.read_csv(path), str(path))


def validate_wamest_component_bucket_weights(df: pd.DataFrame, label: str = "WAMEST buckets") -> pd.DataFrame:
    frame = _validate_contract_table(df, COMPONENT_BUCKET_REQUIRED_COLUMNS, label)
    weights = pd.to_numeric(frame["bucket_weight"], errors="raise")
    if not np.isfinite(weights).all() or not weights.between(0.0, 1.0).all():
        raise ValueError(f"{label} requires finite bucket fractions between zero and one")
    return frame


def read_wamest_interest_observability_tier(path: Path | str) -> pd.DataFrame:
    return _read_contract_table(path, OBSERVABILITY_REQUIRED_COLUMNS)


def read_available_wamest_interest_contract(wamest_root: Path | str) -> dict[str, pd.DataFrame | None]:
    paths = resolve_wamest_interest_contract_paths(wamest_root)
    readers = {
        "sector_interest_allocation_weights": read_wamest_interest_allocation_weights,
        "sector_component_bucket_weights": read_wamest_component_bucket_weights,
        "sector_interest_observability_tier": read_wamest_interest_observability_tier,
    }
    out: dict[str, pd.DataFrame | None] = {}
    for key, path in paths.items():
        out[key] = None if path is None else readers[key](path)
    return out


def has_wamest_interest_contract(wamest_root: Path | str) -> bool:
    paths = resolve_wamest_interest_contract_paths(wamest_root)
    return any(path is not None for path in paths.values())
