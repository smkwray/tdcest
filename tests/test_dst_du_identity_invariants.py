"""Executable Step 0 invariants for the DS^T_DU identity and estimand.

Conventions: DS^T_DU identity note (2026-07-13). These tests bind the identity/estimand
rules that can be checked against the CURRENT release artifacts; B-phase builds
add the closure/mapping gates on the DS exports themselves. Live-data tests skip
when the local release artifacts are absent (fresh clone before `tdc estimate`).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tdc_estimator.du_fiscal_flow_research import (
    DEFAULT_DU_PRIVATE_FINANCIAL_NONBANK_SECTOR_KEYS,
    DEFAULT_DU_PRIVATE_NONFINANCIAL_SECTOR_KEYS,
)

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

CANDIDATE = PROCESSED / "tier2_interest_component_candidate.csv"
FED_COMPONENTS = RAW / "support__fed_treasury_interest_components.csv"
DU_RESEARCH = PROCESSED / "tdc_du_fiscal_flow_research.csv"

CERTIFIED_START = pd.Timestamp("2022-03-31")
CERTIFIED_END = pd.Timestamp("2025-12-31")

INTEREST_ARTIFACTS = [
    PROCESSED / "tier2_interest_component_candidate.csv",
    PROCESSED / "tier2_regression_interest_backcast_wide.csv",
    PROCESSED / "ratewall_du_ru_methodology_panel.csv",
    PROCESSED / "tdc_du_fiscal_flow_research.csv",
    RAW / "support__bank_tier2_component_interest_proxy.csv",
    RAW / "support__credit_union_tier2_component_interest_proxy.csv",
    RAW / "support__row_tier2_component_interest_proxy.csv",
    RAW / "support__fed_treasury_interest_components.csv",
]


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"local release artifact absent: {path.name}")


def _certified_candidate() -> pd.DataFrame:
    _require(CANDIDATE)
    frame = pd.read_csv(CANDIDATE, parse_dates=["date"])
    window = frame[(frame["date"] >= CERTIFIED_START) & (frame["date"] <= CERTIFIED_END)]
    if window.empty:
        pytest.skip("candidate has no certified-window rows")
    return window


def test_modern_complement_is_nonnegative_and_sane():
    """Identity note section 2: DS+U = pool - Fed exact - certified RU allocations
    must be non-negative every certified quarter/component, and the aggregate
    complement share of the pool must stay inside a sane band."""
    window = _certified_candidate()
    per_quarter_pool = {}
    per_quarter_complement = {}
    for (date, component), group in window.groupby(["date", "component_key"]):
        pool = group["official_component_pool_mil"].iloc[0]
        fed = group["fed_exact_component_mil"].iloc[0]
        assert pd.notna(pool), f"missing pool for {component} at {date.date()}"
        fed = 0.0 if pd.isna(fed) else float(fed)
        allocations = pd.to_numeric(group["component_anchored_interest_mil"], errors="coerce")
        assert not allocations.isna().any(), (
            f"NaN RU allocation for {component} at {date.date()}"
        )
        complement = float(pool) - fed - float(allocations.sum())
        assert complement >= 0.0, (
            f"negative DS+U complement for {component} at {date.date()}: {complement:,.3f}M "
            "— failed identity; investigate, never clip"
        )
        per_quarter_pool[date] = per_quarter_pool.get(date, 0.0) + float(pool)
        per_quarter_complement[date] = per_quarter_complement.get(date, 0.0) + complement
    for date, pool in per_quarter_pool.items():
        share = per_quarter_complement[date] / pool
        assert 0.0 < share < 0.6, (
            f"aggregate DS+U complement share {share:.1%} at {date.date()} outside sane band"
        )


def test_du_and_ru_holder_universes_are_disjoint():
    """Identity note section 2: no holder may appear in both DU and RU totals."""
    window = _certified_candidate()
    ru_keys: set[str] = set()
    for joined in window["sector_keys"].dropna():
        ru_keys.update(key.strip() for key in str(joined).split(","))
    du_keys = set(DEFAULT_DU_PRIVATE_NONFINANCIAL_SECTOR_KEYS) | set(
        DEFAULT_DU_PRIVATE_FINANCIAL_NONBANK_SECTOR_KEYS
    )
    overlap = ru_keys & du_keys
    assert not overlap, f"holder keys present in both DU and RU universes: {sorted(overlap)}"


def test_fed_components_are_nonoverlapping_columns_with_isolated_tips_ic():
    """Identity note section 7 item 3: Fed coupon/bill/FRN/TIPS-coupon live in
    distinct columns, dates are unique, and TIPS inflation compensation stays
    isolated in its own column (never folded into a core component)."""
    _require(FED_COMPONENTS)
    fed = pd.read_csv(FED_COMPONENTS, parse_dates=["date"])
    assert not fed["date"].duplicated().any(), "duplicate Fed component dates"
    core_columns = [
        "fed_tsy_coupon_interest_proxy",
        "fed_tsy_bill_discount_interest_proxy",
        "fed_tsy_frn_interest_proxy",
        "fed_tsy_tips_coupon_interest_proxy",
    ]
    for column in core_columns + ["fed_tsy_tips_inflation_comp_proxy"]:
        assert column in fed.columns, f"missing Fed component column {column}"
    for column in core_columns:
        values = pd.to_numeric(fed[column], errors="coerce").dropna()
        assert (values >= 0.0).all(), f"negative values in core Fed component {column}"


def test_direct_broad_exceeds_narrow_when_added_sectors_have_exposure():
    """Identity note section 3 invariant, fixed at B2 (2026-07-13): the broad DU
    direct proxy adds insurers/pensions on top of narrow, so it must strictly
    exceed narrow in every populated quarter (those sectors always hold
    Treasuries in the modern sample)."""
    _require(DU_RESEARCH)
    research = pd.read_csv(DU_RESEARCH)
    narrow = pd.to_numeric(research.get("du_coupon_proxy_direct_narrow"), errors="coerce")
    broad = pd.to_numeric(research.get("du_coupon_proxy_direct_broad"), errors="coerce")
    populated = narrow.notna() & broad.notna()
    if not populated.any():
        pytest.skip("no populated direct DU coupon rows")
    assert (broad[populated] > narrow[populated]).all(), (
        "broad DU direct proxy must strictly exceed narrow in every populated quarter"
    )


def test_no_cash_labeled_columns_in_interest_artifacts():
    """Identity note section 1: no interest artifact may carry a cash-labeled
    column until the cash-received layer (dst_du_cash_*) actually exists."""
    checked = 0
    for path in INTEREST_ARTIFACTS:
        if not path.exists():
            continue
        checked += 1
        columns = pd.read_csv(path, nrows=0).columns
        offenders = [c for c in columns if "cash" in c.lower()]
        assert not offenders, (
            f"{path.name} carries cash-labeled columns {offenders} without a "
            "payment/redemption bridge"
        )
    if checked == 0:
        pytest.skip("no local interest artifacts present")


def test_no_export_column_combines_tier2_family_with_du_terms():
    """Identity note section 4: DS is never additive to Tier 2 — no export column
    may combine a Tier 2 row family with a DU/DS term."""
    checked = 0
    for path in [
        PROCESSED / "tdc_estimates.csv",
        PROCESSED / "tdc_tier2_regression_series.csv",
        PROCESSED / "tdc_components.csv",
    ]:
        if not path.exists():
            continue
        checked += 1
        columns = pd.read_csv(path, nrows=0).columns
        offenders = [
            c
            for c in columns
            if "tier2" in c.lower() and ("du_" in c.lower() or "dst_du" in c.lower())
        ]
        assert not offenders, f"{path.name} mixes Tier 2 and DU/DS namespaces: {offenders}"
    if checked == 0:
        pytest.skip("no local export artifacts present")
