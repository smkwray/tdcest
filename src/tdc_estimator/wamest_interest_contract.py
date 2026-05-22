from __future__ import annotations

from pathlib import Path

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

DEFAULT_WAMEST_SOMA_BACKTEST_CANDIDATES = [
    Path("outputs/full_coverage_release/soma_interest_proxy_backtest.csv"),
    Path("data/processed/soma_interest_proxy_backtest.csv"),
]

INTEREST_ALLOCATION_REQUIRED_COLUMNS = {
    "date",
    "sector_key",
    "component_key",
    "central_weight",
    "low_weight",
    "high_weight",
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

SOMA_BACKTEST_REQUIRED_COLUMNS = {
    "date",
    "component_key",
    "exact_soma_interest_mil",
    "proxy_soma_interest_mil",
    "proxy_error_mil",
    "proxy_error_pct",
    "proxy_method",
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
        "soma_interest_proxy_backtest": resolve_first_existing_optional(
            wamest_root,
            DEFAULT_WAMEST_SOMA_BACKTEST_CANDIDATES,
        ),
    }


def _read_contract_table(path: Path | str, required_columns: set[str]) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing required WAMEST interest-contract columns: {', '.join(sorted(missing))}")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "component_key" in df.columns:
        unknown = sorted(set(df["component_key"].dropna().astype(str)) - KNOWN_TDCEST_INTEREST_COMPONENT_KEYS)
        if unknown:
            raise ValueError(f"{path} has unknown WAMEST interest component_key values: {', '.join(unknown)}")
    return df


def read_wamest_interest_allocation_weights(path: Path | str) -> pd.DataFrame:
    return _read_contract_table(path, INTEREST_ALLOCATION_REQUIRED_COLUMNS)


def read_wamest_component_bucket_weights(path: Path | str) -> pd.DataFrame:
    return _read_contract_table(path, COMPONENT_BUCKET_REQUIRED_COLUMNS)


def read_wamest_interest_observability_tier(path: Path | str) -> pd.DataFrame:
    return _read_contract_table(path, OBSERVABILITY_REQUIRED_COLUMNS)


def read_wamest_soma_interest_proxy_backtest(path: Path | str) -> pd.DataFrame:
    return _read_contract_table(path, SOMA_BACKTEST_REQUIRED_COLUMNS)


def read_available_wamest_interest_contract(wamest_root: Path | str) -> dict[str, pd.DataFrame | None]:
    paths = resolve_wamest_interest_contract_paths(wamest_root)
    readers = {
        "sector_interest_allocation_weights": read_wamest_interest_allocation_weights,
        "sector_component_bucket_weights": read_wamest_component_bucket_weights,
        "sector_interest_observability_tier": read_wamest_interest_observability_tier,
        "soma_interest_proxy_backtest": read_wamest_soma_interest_proxy_backtest,
    }
    out: dict[str, pd.DataFrame | None] = {}
    for key, path in paths.items():
        out[key] = None if path is None else readers[key](path)
    return out


def has_wamest_interest_contract(wamest_root: Path | str) -> bool:
    paths = resolve_wamest_interest_contract_paths(wamest_root)
    return any(path is not None for path in paths.values())
