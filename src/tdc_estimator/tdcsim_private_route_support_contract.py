from __future__ import annotations

from pathlib import Path

import pandas as pd


CONTRACT_VERSION = "tdc_tdcsim_private_route_support_contract_v1"

TDCSIM_PRIVATE_ROUTE_SUPPORT_CONTRACT_FIELDS = [
    "support_row_id",
    "contract_version",
    "source_contract_version",
    "producer_project",
    "source_artifact",
    "ref_quarter",
    "object_family",
    "measurement_stage",
    "route_component_id",
    "route_class",
    "route_subclass",
    "tdcsim_holder_bucket",
    "source_family",
    "source_scope",
    "amount_bil",
    "denominator_bil",
    "share_low",
    "share_central",
    "share_high",
    "evidence_tier",
    "mapping_burden",
    "assumption_status",
    "assumption_parameter",
    "assumption_description",
    "source_backed_private_bucket_split_status",
    "source_backed_private_bucket_split_row",
    "admissible_use",
    "blocked_use",
    "central_default_eligible",
    "sensitivity_only",
    "evidence_mode_enabled",
    "canonical_ratio_entry",
    "canonical_tdc_math_change",
    "current_demand_eligible",
    "holder_allocation_enabled",
    "pricing_output_enabled",
    "incidence_claim_enabled",
    "welfare_claim_enabled",
    "tax_output_enabled",
    "mpc_output_enabled",
    "prior_narrowing_allowed",
    "binding_blocker",
    "claim_boundary",
]

_FALSE_FIELDS = [
    "source_backed_private_bucket_split_row",
    "central_default_eligible",
    "evidence_mode_enabled",
    "canonical_ratio_entry",
    "canonical_tdc_math_change",
    "current_demand_eligible",
    "holder_allocation_enabled",
    "pricing_output_enabled",
    "incidence_claim_enabled",
    "welfare_claim_enabled",
    "tax_output_enabled",
    "mpc_output_enabled",
    "prior_narrowing_allowed",
]

_BLOCKED_USE = (
    "source_backed_private_bucket_split;canonical_tdc_math;evidence_mode;"
    "holder_allocation;final_current_demand;pricing_incidence_welfare_tax_mpc;"
    "prior_narrowing"
)


def _measurement_stage(object_family: str) -> str:
    if object_family == "stock_interest_quarter_end":
        return "holder_stock"
    if object_family == "flow_absorption_trailing_4q":
        return "holder_flow"
    return "unknown"


def build_tdcsim_private_route_support_contract(
    sensitivity: pd.DataFrame,
    *,
    source_artifact: str = "tdc_tdcsim_private_route_allocation_sensitivity.csv",
) -> pd.DataFrame:
    """Normalize the private-route sidecar as bounded Assumption Mode support.

    The output is not a new estimator. It wraps the existing lambda sensitivity
    rows with machine-readable evidence tier, mapping burden, and blocked-use
    fields so downstream TDCSim/RateWall consumers cannot mistake the sidecar
    for an empirical Private-bucket route split.
    """

    rows: list[dict[str, str]] = []
    for _, row in sensitivity.iterrows():
        object_family = str(row.get("object_family", ""))
        route_class = str(row.get("route_class", ""))
        out = {
            "support_row_id": (
                f"tdcest_private_route_support::{row.get('ref_quarter', '')}::"
                f"{object_family}::{route_class}"
            ),
            "contract_version": CONTRACT_VERSION,
            "source_contract_version": str(row.get("contract_version", "")),
            "producer_project": "tdcest",
            "source_artifact": source_artifact,
            "ref_quarter": str(row.get("ref_quarter", "")),
            "object_family": object_family,
            "measurement_stage": str(
                row.get("measurement_stage", _measurement_stage(object_family))
            ),
            "route_component_id": "tdcsim_private_bucket_route_sensitivity",
            "route_class": route_class,
            "route_subclass": str(row.get("route_subclass", "")),
            "tdcsim_holder_bucket": "Private",
            "source_family": "z1_holder_vehicle_context;sec_nmfp_mmf_context",
            "source_scope": str(row.get("source_inputs", "")),
            "amount_bil": str(row.get("raw_amount_bil", "")),
            "denominator_bil": str(row.get("denominator_bil", "")),
            "share_low": str(row.get("share_low", "")),
            "share_central": str(row.get("share_central", row.get("share_lambda_0_5", ""))),
            "share_high": str(row.get("share_high", "")),
            "evidence_tier": "bounded_proxy",
            "mapping_burden": str(
                row.get("mapping_burden", "requires_unobserved_actor_split")
            ),
            "assumption_status": str(row.get("assumption_status", "bounded_assumption")),
            "assumption_parameter": "lambda_direct_sector_deposit_funded_fraction",
            "assumption_description": (
                "mechanical lambda sensitivity over ambiguous domestic nonbank "
                "holder vehicles; not an observed funding route"
            ),
            "source_backed_private_bucket_split_status": (
                "not_source_backed_private_bucket_split"
            ),
            "admissible_use": "assumption_mode_support_ledger;assumption_mode_sensitivity",
            "blocked_use": _BLOCKED_USE,
            "sensitivity_only": "true",
            "binding_blocker": str(
                row.get(
                    "exact_blocker",
                    "holder_vehicle_context_does_not_identify_private_bucket_funding_route",
                )
            ),
            "claim_boundary": (
                "tdcest_bounded_proxy_for_tdcsim_assumption_mode_not_empirical_split"
            ),
        }
        for field in _FALSE_FIELDS:
            out[field] = "false"
        rows.append(out)
    return pd.DataFrame(rows, columns=TDCSIM_PRIVATE_ROUTE_SUPPORT_CONTRACT_FIELDS)


def write_tdcsim_private_route_support_contract(
    *,
    sensitivity_path: Path | str,
    csv_path: Path | str,
) -> tuple[Path, pd.DataFrame]:
    sensitivity_path = Path(sensitivity_path)
    frame = build_tdcsim_private_route_support_contract(
        pd.read_csv(sensitivity_path),
        source_artifact=sensitivity_path.name,
    )
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    return target, frame
