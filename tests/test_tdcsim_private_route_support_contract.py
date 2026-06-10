from __future__ import annotations

import pandas as pd
import pytest

from tdc_estimator.tdcsim_private_route_allocation_sensitivity import (
    build_tdcsim_private_route_allocation_sensitivity,
)
from tdc_estimator.tdcsim_private_route_support_contract import (
    build_tdcsim_private_route_support_contract,
)

from test_tdcsim_private_route_allocation_sensitivity import (
    _flow_source,
    _mmf_context,
    _stock_source,
)


def test_private_route_support_contract_is_bounded_only() -> None:
    sensitivity = build_tdcsim_private_route_allocation_sensitivity(
        z1_flow=_flow_source(),
        z1_stock=_stock_source(),
        mmf_route_split_context=_mmf_context(),
    )
    rows = build_tdcsim_private_route_support_contract(sensitivity)

    assert len(rows) == len(sensitivity)
    assert set(rows["evidence_tier"]) == {"bounded_proxy"}
    assert set(rows["assumption_status"]) == {"bounded_assumption"}
    assert set(rows["mapping_burden"]) == {"requires_unobserved_actor_split"}
    assert set(rows["source_backed_private_bucket_split_status"]) == {
        "not_source_backed_private_bucket_split"
    }
    assert set(rows["source_backed_private_bucket_split_row"]) == {"false"}
    assert set(rows["admissible_use"]) == {
        "assumption_mode_support_ledger;assumption_mode_sensitivity"
    }
    for blocked in (
        "source_backed_private_bucket_split",
        "canonical_tdc_math",
        "evidence_mode",
        "final_current_demand",
        "holder_allocation",
    ):
        assert rows["blocked_use"].str.contains(blocked, regex=False).all()
    for column in (
        "central_default_eligible",
        "current_demand_eligible",
        "canonical_tdc_math_change",
        "evidence_mode_enabled",
        "holder_allocation_enabled",
        "pricing_output_enabled",
        "incidence_claim_enabled",
        "welfare_claim_enabled",
        "tax_output_enabled",
        "mpc_output_enabled",
        "prior_narrowing_allowed",
    ):
        assert set(rows[column]) == {"false"}


def test_private_route_support_contract_preserves_share_bounds() -> None:
    sensitivity = build_tdcsim_private_route_allocation_sensitivity(
        z1_flow=_flow_source(),
        z1_stock=_stock_source(),
        mmf_route_split_context=_mmf_context(),
    )
    rows = build_tdcsim_private_route_support_contract(sensitivity)

    for _, row in rows.iterrows():
        low = float(row["share_low"])
        central = float(row["share_central"])
        high = float(row["share_high"])
        assert low <= central <= high

    for _, group in rows.groupby(["ref_quarter", "object_family"]):
        central_total = pd.to_numeric(group["share_central"], errors="raise").sum()
        assert central_total == pytest.approx(1.0, abs=2e-6)
