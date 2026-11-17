from __future__ import annotations

import pandas as pd

from .catalog import (
    BANK_DEPOSITORY_LEVEL_KEYS,
    BANK_DEPOSITORY_TX_KEYS,
    CU_COMPONENT_TX_KEYS,
)
from .mmf_rrp import mmf_route_bounds


def _sum_columns(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Sum of every listed column; missing wherever any column or quarter value is missing."""
    if not all(col in df.columns for col in cols):
        return pd.Series(index=df.index, dtype="float64")
    return df[cols].sum(axis=1, min_count=len(cols))


def _mmf_route(components: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """MMF/ON RRP route bounds on the estimator's date index: zero before the ON RRP
    facility existed, missing (with status) when unobserved after it."""
    frame = components[[f"{prefix}_{key}" for key in ("lb", "prop", "ub")]].copy()
    dates = frame.index
    frame.index = pd.to_datetime(dates).to_period("Q")
    route = mmf_route_bounds(frame, prefix=prefix)
    route.index = dates
    return route


def _has_all(df: pd.DataFrame, cols: list[str]) -> bool:
    return all(col in df.columns for col in cols)


def _maybe(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col]
    return pd.Series(index=df.index, dtype="float64")


def _from_date(series: pd.Series, start: str) -> pd.Series:
    out = series.copy()
    out[pd.to_datetime(out.index) < pd.Timestamp(start)] = pd.NA
    return out


# H.8 and money-stock series (M2SL, CURRCIR, TOTBKCR) are published in USD billions.
H8_USD_MILLION_PER_BILLION = 1000.0

# The one headline series. It exists only when component-anchored interest support
# covers banks, the rest of the world and credit unions and the MMF/ON RRP support is
# present; it is never filled from the H.15 coupon-only rows.
CANONICAL_TIER2_METHOD = "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"
CANONICAL_TIER2_REQUIREMENT = (
    "component-anchored Treasury interest support for banks, the rest of the world and credit unions, "
    "plus the MMF fund-month support file"
)


def compute_estimates(quarterly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    remit = quarterly["fed_remit_or_deferred"] if "fed_remit_or_deferred" in quarterly.columns else pd.Series(dtype="float64")
    tx_start = (
        "2002-03-31"
        if not remit.loc[pd.to_datetime(remit.index) < pd.Timestamp("2002-12-31")].dropna().empty
        else "2002-12-31"
    )
    required = [
        "fed_tsy_tx",
        *BANK_DEPOSITORY_TX_KEYS,
        "row_tsy_tx",
        "treasury_operating_cash_tx",
        "treasury_fed_internal_cash_tx",
        "fed_remit_or_deferred",
    ]
    missing = [col for col in required if col not in quarterly.columns]
    if missing:
        raise ValueError(f"Missing required inputs for base estimator: {missing}")
    internal_unobserved = (
        quarterly["treasury_operating_cash_tx"].notna()
        & quarterly["treasury_fed_internal_cash_tx"].isna()
        & (pd.to_datetime(quarterly.index) >= pd.Timestamp(tx_start))
    )
    if internal_unobserved.any():
        raise ValueError(
            "Treasury-Fed internal cash support missing in transaction-era quarters "
            f"{[str(pd.Timestamp(d).date()) for d in quarterly.index[internal_unobserved][:5]]}"
        )

    components = pd.DataFrame(index=quarterly.index)
    components["fed_tsy_tx"] = quarterly["fed_tsy_tx"]
    components["bank_depository_tsy_tx"] = _sum_columns(quarterly, BANK_DEPOSITORY_TX_KEYS)
    components["np_credit_unions_tsy_tx"] = _maybe(quarterly, "np_credit_unions_tsy_tx")
    components["corp_credit_unions_tsy_tx"] = _maybe(quarterly, "corp_credit_unions_tsy_tx")
    components["ncua_capitalization_deposit_tx"] = _maybe(quarterly, "ncua_capitalization_deposit_tx")
    components["credit_unions_total_tsy_tx_reconstructed"] = _sum_columns(quarterly, CU_COMPONENT_TX_KEYS)
    if "credit_unions_total_tsy_tx" in quarterly.columns:
        components["credit_unions_total_tsy_tx_direct"] = quarterly["credit_unions_total_tsy_tx"]
        components["credit_unions_total_gap_tx"] = (
            quarterly["credit_unions_total_tsy_tx"]
            - components["credit_unions_total_tsy_tx_reconstructed"]
        )
    components["broad_depository_np_cu_tsy_tx"] = (
        components["bank_depository_tsy_tx"] + components["np_credit_unions_tsy_tx"]
    )
    components["broad_depository_np_corp_cu_tsy_tx"] = (
        components["broad_depository_np_cu_tsy_tx"] + components["corp_credit_unions_tsy_tx"]
    )
    components["broad_depository_full_cu_tsy_tx"] = (
        components["broad_depository_np_corp_cu_tsy_tx"] + components["ncua_capitalization_deposit_tx"]
    )
    components["row_tsy_tx"] = quarterly["row_tsy_tx"]
    components["ru_bank_only_tsy_tx"] = components[
        ["fed_tsy_tx", "bank_depository_tsy_tx", "row_tsy_tx"]
    ].sum(axis=1, min_count=3)
    components["ru_broad_depository_np_cu_tsy_tx"] = components[
        ["fed_tsy_tx", "broad_depository_np_cu_tsy_tx", "row_tsy_tx"]
    ].sum(axis=1, min_count=3)
    components["ru_broad_depository_np_corp_cu_tsy_tx"] = components[
        ["fed_tsy_tx", "broad_depository_np_corp_cu_tsy_tx", "row_tsy_tx"]
    ].sum(axis=1, min_count=3)
    components["ru_broad_depository_full_cu_tsy_tx"] = components[
        ["fed_tsy_tx", "broad_depository_full_cu_tsy_tx", "row_tsy_tx"]
    ].sum(axis=1, min_count=3)
    # Treasury-Fed internal transfers move Treasury operating cash without reaching a deposit.
    components["minus_treasury_operating_cash_tx"] = -(
        quarterly["treasury_operating_cash_tx"] - quarterly["treasury_fed_internal_cash_tx"]
    )

    # Remittances are missing, not zero, in quarters the remittance series does not cover.
    # Only the historical level-change backfill before the transaction era treats a missing
    # remittance as zero, and the metadata records that.
    components["fed_remit_positive"] = quarterly["fed_remit_or_deferred"]
    remit_observed = quarterly["fed_remit_or_deferred"].dropna()
    remit_coverage_start = remit_observed.index.min() if not remit_observed.empty else None
    before_transaction_era = pd.Series(
        pd.to_datetime(quarterly.index) < pd.Timestamp(tx_start), index=quarterly.index
    )
    remit_for_level_backfill = components["fed_remit_positive"].where(
        ~before_transaction_era, components["fed_remit_positive"].fillna(0.0)
    )

    if "fed_tsy_coupon_interest_proxy" in quarterly.columns:
        components["fed_tsy_coupon_interest_proxy"] = quarterly["fed_tsy_coupon_interest_proxy"]
    if "fed_tier1_component_extension_proxy" in quarterly.columns:
        components["fed_tier1_component_extension_proxy"] = quarterly["fed_tier1_component_extension_proxy"]
    if "bank_tsy_coupon_interest_proxy" in quarterly.columns:
        components["bank_tsy_coupon_interest_proxy"] = quarterly["bank_tsy_coupon_interest_proxy"]
    if "row_tsy_coupon_interest_proxy" in quarterly.columns:
        components["row_tsy_coupon_interest_proxy"] = quarterly["row_tsy_coupon_interest_proxy"]
    if "credit_union_tsy_coupon_interest_proxy" in quarterly.columns:
        components["credit_union_tsy_coupon_interest_proxy"] = quarterly["credit_union_tsy_coupon_interest_proxy"]
    if "bank_tsy_bill_discount_interest_proxy" in quarterly.columns:
        components["bank_tsy_bill_discount_interest_proxy"] = quarterly["bank_tsy_bill_discount_interest_proxy"]
    if "row_tsy_bill_discount_interest_proxy" in quarterly.columns:
        components["row_tsy_bill_discount_interest_proxy"] = quarterly["row_tsy_bill_discount_interest_proxy"]
    if "credit_union_tsy_bill_discount_interest_proxy" in quarterly.columns:
        components["credit_union_tsy_bill_discount_interest_proxy"] = quarterly[
            "credit_union_tsy_bill_discount_interest_proxy"
        ]
    if "bank_tier2_component_interest_proxy" in quarterly.columns:
        components["bank_tier2_component_interest_proxy"] = quarterly["bank_tier2_component_interest_proxy"]
    if "row_tier2_component_interest_proxy" in quarterly.columns:
        components["row_tier2_component_interest_proxy"] = quarterly["row_tier2_component_interest_proxy"]
    if "credit_union_tier2_component_interest_proxy" in quarterly.columns:
        components["credit_union_tier2_component_interest_proxy"] = quarterly[
            "credit_union_tier2_component_interest_proxy"
        ]
    for key in [
        "mmf_rrp_adjustment_lb",
        "mmf_rrp_adjustment_prop",
        "mmf_rrp_adjustment_ub",
        "mmf_rrp_bills_adjustment_lb",
        "mmf_rrp_bills_adjustment_prop",
        "mmf_rrp_bills_adjustment_ub",
    ]:
        if key in quarterly.columns:
            components[key] = quarterly[key]
    mmf_routes: dict[str, pd.DataFrame] = {}
    for prefix in ["mmf_rrp_adjustment", "mmf_rrp_bills_adjustment"]:
        present = [key for key in ("lb", "prop", "ub") if f"{prefix}_{key}" in components.columns]
        if present and len(present) < 3:
            raise ValueError(f"MMF/ON RRP support must carry lb, prop and ub together; {prefix} has only {present}")
        if present:
            mmf_routes[prefix] = _mmf_route(components, prefix)
    if "bank_noninterest_outlay_proxy" in quarterly.columns:
        components["bank_noninterest_outlay_proxy"] = quarterly["bank_noninterest_outlay_proxy"]
    if "row_noninterest_outlay_proxy" in quarterly.columns:
        components["row_noninterest_outlay_proxy"] = quarterly["row_noninterest_outlay_proxy"]
    if "bank_nonborrow_receipt_proxy" in quarterly.columns:
        components["bank_nonborrow_receipt_proxy"] = quarterly["bank_nonborrow_receipt_proxy"]
    if "row_nonborrow_receipt_proxy" in quarterly.columns:
        components["row_nonborrow_receipt_proxy"] = quarterly["row_nonborrow_receipt_proxy"]
    if "mint_cb_cash_factor_proxy" in quarterly.columns:
        components["mint_cb_cash_factor_proxy"] = quarterly["mint_cb_cash_factor_proxy"]

    estimates = pd.DataFrame(index=quarterly.index)
    corrections = pd.DataFrame(index=quarterly.index)
    estimates["tdc_base_bank_only_ru_flow"] = (
        components["ru_bank_only_tsy_tx"]
        + components["minus_treasury_operating_cash_tx"]
        + components["fed_remit_positive"]
    )
    estimates["tdc_base_broad_depository_np_cu_ru_flow"] = (
        components["ru_broad_depository_np_cu_tsy_tx"]
        + components["minus_treasury_operating_cash_tx"]
        + components["fed_remit_positive"]
    )
    estimates["tdc_broad_depository_np_corp_cu_ru_flow"] = (
        components["ru_broad_depository_np_corp_cu_tsy_tx"]
        + components["minus_treasury_operating_cash_tx"]
        + components["fed_remit_positive"]
    )
    estimates["tdc_credit_union_aggregate_sensitivity"] = (
        components["ru_broad_depository_full_cu_tsy_tx"]
        + components["minus_treasury_operating_cash_tx"]
        + components["fed_remit_positive"]
    )
    estimates["tdc_domestic_bank_only_ru_flow"] = (
        components["fed_tsy_tx"]
        + components["bank_depository_tsy_tx"]
        + components["minus_treasury_operating_cash_tx"]
        + components["fed_remit_positive"]
    )
    estimates["tdc_no_remit_bank_only"] = (
        components["ru_bank_only_tsy_tx"] + components["minus_treasury_operating_cash_tx"]
    )

    if "fed_tsy_coupon_interest_proxy" in components.columns:
        corrections["tier1_fed_coupon_correction"] = -components["fed_tsy_coupon_interest_proxy"]
        estimates["tdc_tier1_fed_corrected_bank_only_ru_flow"] = (
            estimates["tdc_base_bank_only_ru_flow"] - components["fed_tsy_coupon_interest_proxy"]
        )
        estimates["tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow"] = (
            estimates["tdc_base_broad_depository_np_cu_ru_flow"] - components["fed_tsy_coupon_interest_proxy"]
        )
        estimates["tdc_tier1_fed_corrected_domestic_bank_only_ru_flow"] = (
            estimates["tdc_domestic_bank_only_ru_flow"] - components["fed_tsy_coupon_interest_proxy"]
        )

    if {
        "fed_tsy_coupon_interest_proxy",
        "bank_tsy_coupon_interest_proxy",
    }.issubset(components.columns):
        corrections["tier2_bank_h15_coupon_correction"] = -components["bank_tsy_coupon_interest_proxy"]
        corrections["tier2_bank_coupon_correction"] = corrections["tier2_bank_h15_coupon_correction"]
        estimates["tdc_tier2_h15_intensity_corrected_domestic_bank_only_ru_flow"] = (
            estimates["tdc_domestic_bank_only_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tsy_coupon_interest_proxy"]
        )
        estimates["tdc_tier2_interest_corrected_domestic_bank_only_ru_flow"] = estimates[
            "tdc_tier2_h15_intensity_corrected_domestic_bank_only_ru_flow"
        ]

    if {
        "fed_tsy_coupon_interest_proxy",
        "bank_tsy_coupon_interest_proxy",
        "row_tsy_coupon_interest_proxy",
    }.issubset(components.columns):
        corrections["tier2_row_h15_coupon_correction"] = -components["row_tsy_coupon_interest_proxy"]
        corrections["tier2_row_coupon_correction"] = corrections["tier2_row_h15_coupon_correction"]
        estimates["tdc_tier2_h15_intensity_corrected_bank_only_ru_flow"] = (
            estimates["tdc_base_bank_only_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tsy_coupon_interest_proxy"]
            - components["row_tsy_coupon_interest_proxy"]
        )
        estimates["tdc_tier2_h15_intensity_corrected_broad_depository_np_cu_ru_flow"] = (
            estimates["tdc_base_broad_depository_np_cu_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tsy_coupon_interest_proxy"]
            - components["row_tsy_coupon_interest_proxy"]
        )
        estimates["tdc_tier2_interest_corrected_bank_only_ru_flow"] = estimates[
            "tdc_tier2_h15_intensity_corrected_bank_only_ru_flow"
        ]
        estimates["tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow"] = estimates[
            "tdc_tier2_h15_intensity_corrected_broad_depository_np_cu_ru_flow"
        ]
        if "credit_union_tsy_coupon_interest_proxy" in components.columns:
            corrections["tier2_credit_union_h15_coupon_correction"] = -components[
                "credit_union_tsy_coupon_interest_proxy"
            ]
            corrections["tier2_credit_union_coupon_correction"] = corrections[
                "tier2_credit_union_h15_coupon_correction"
            ]
            estimates["tdc_tier2_h15_intensity_corrected_depository_institution_np_cu_ru_flow"] = (
                estimates["tdc_tier2_h15_intensity_corrected_broad_depository_np_cu_ru_flow"]
                - components["credit_union_tsy_coupon_interest_proxy"]
            )
            estimates["tdc_tier2_interest_corrected_depository_institution_np_cu_ru_flow"] = estimates[
                "tdc_tier2_h15_intensity_corrected_depository_institution_np_cu_ru_flow"
            ]

        if {
            "bank_tsy_bill_discount_interest_proxy",
            "row_tsy_bill_discount_interest_proxy",
        }.issubset(components.columns):
            corrections["tier2_bank_bill_discount_robustness_correction"] = -components[
                "bank_tsy_bill_discount_interest_proxy"
            ]
            corrections["tier2_row_bill_discount_robustness_correction"] = -components[
                "row_tsy_bill_discount_interest_proxy"
            ]
            estimates["tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow"] = (
                estimates["tdc_tier2_h15_intensity_corrected_bank_only_ru_flow"]
                - components["bank_tsy_bill_discount_interest_proxy"]
                - components["row_tsy_bill_discount_interest_proxy"]
            )
            estimates["tdc_tier2_h15_treasury_interest_robust_broad_depository_np_cu_ru_flow"] = (
                estimates["tdc_tier2_h15_intensity_corrected_broad_depository_np_cu_ru_flow"]
                - components["bank_tsy_bill_discount_interest_proxy"]
                - components["row_tsy_bill_discount_interest_proxy"]
            )
            if (
                "tdc_tier2_h15_intensity_corrected_depository_institution_np_cu_ru_flow" in estimates.columns
                and "credit_union_tsy_bill_discount_interest_proxy" in components.columns
            ):
                corrections["tier2_credit_union_bill_discount_robustness_correction"] = -components[
                    "credit_union_tsy_bill_discount_interest_proxy"
                ]
                estimates["tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow"] = (
                    estimates["tdc_tier2_h15_intensity_corrected_depository_institution_np_cu_ru_flow"]
                    - components["bank_tsy_bill_discount_interest_proxy"]
                    - components["row_tsy_bill_discount_interest_proxy"]
                    - components["credit_union_tsy_bill_discount_interest_proxy"]
                )

        for suffix, component_key in [
            ("lb", "mmf_rrp_adjustment_lb"),
            ("prop", "mmf_rrp_adjustment_prop"),
            ("ub", "mmf_rrp_adjustment_ub"),
        ]:
            if component_key in components.columns:
                adjustment = mmf_routes["mmf_rrp_adjustment"][f"mmf_route_{suffix}"]
                corrections[f"tier2_mmf_rrp_{suffix}_adjustment"] = adjustment
                estimates[f"tdc_tier2_h15_mmf_rrp_{suffix}_bank_only_ru_flow"] = (
                    estimates["tdc_tier2_h15_intensity_corrected_bank_only_ru_flow"]
                    + adjustment
                )
                estimates[f"tdc_tier2_h15_mmf_rrp_{suffix}_broad_depository_np_cu_ru_flow"] = (
                    estimates["tdc_tier2_h15_intensity_corrected_broad_depository_np_cu_ru_flow"]
                    + adjustment
                )
                if "tdc_tier2_h15_intensity_corrected_depository_institution_np_cu_ru_flow" in estimates.columns:
                    estimates[f"tdc_tier2_h15_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"] = (
                        estimates["tdc_tier2_h15_intensity_corrected_depository_institution_np_cu_ru_flow"]
                        + adjustment
                    )
                    estimates[f"tdc_tier2_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"] = estimates[
                        f"tdc_tier2_h15_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"
                    ]
                estimates[f"tdc_tier2_mmf_rrp_{suffix}_bank_only_ru_flow"] = estimates[
                    f"tdc_tier2_h15_mmf_rrp_{suffix}_bank_only_ru_flow"
                ]
                estimates[f"tdc_tier2_mmf_rrp_{suffix}_broad_depository_np_cu_ru_flow"] = estimates[
                    f"tdc_tier2_h15_mmf_rrp_{suffix}_broad_depository_np_cu_ru_flow"
                ]
                if "tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow" in estimates.columns:
                    estimates[f"tdc_tier2_h15_treasury_interest_robust_mmf_rrp_{suffix}_bank_only_ru_flow"] = (
                        estimates["tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow"]
                        + adjustment
                    )
                if "tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow" in estimates.columns:
                    estimates[
                        f"tdc_tier2_h15_treasury_interest_robust_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"
                    ] = (
                        estimates["tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow"]
                        + adjustment
                    )

        for suffix, component_key in [
            ("lb", "mmf_rrp_bills_adjustment_lb"),
            ("prop", "mmf_rrp_bills_adjustment_prop"),
            ("ub", "mmf_rrp_bills_adjustment_ub"),
        ]:
            if component_key in components.columns:
                adjustment = mmf_routes["mmf_rrp_bills_adjustment"][f"mmf_route_{suffix}"]
                corrections[f"tier2_mmf_rrp_bills_{suffix}_adjustment"] = adjustment
                estimates[f"tdc_tier2_h15_mmf_rrp_bills_{suffix}_bank_only_ru_flow"] = (
                    estimates["tdc_tier2_h15_intensity_corrected_bank_only_ru_flow"]
                    + adjustment
                )

    if {
        "fed_tsy_coupon_interest_proxy",
        "bank_tier2_component_interest_proxy",
    }.issubset(components.columns):
        corrections["tier2_bank_component_interest_correction"] = -components[
            "bank_tier2_component_interest_proxy"
        ]
        corrections["tier2_bank_coupon_correction"] = corrections["tier2_bank_component_interest_correction"]
        estimates["tdc_tier2_component_anchored_domestic_bank_only_ru_flow"] = (
            estimates["tdc_domestic_bank_only_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tier2_component_interest_proxy"]
        )
        estimates["tdc_tier2_interest_corrected_domestic_bank_only_ru_flow"] = estimates[
            "tdc_tier2_component_anchored_domestic_bank_only_ru_flow"
        ]
        if "fed_tier1_component_extension_proxy" in components.columns:
            corrections["tier1_fed_component_extension_correction"] = -components[
                "fed_tier1_component_extension_proxy"
            ]
            estimates["tdc_tier2_component_anchored_fed_extension_domestic_bank_only_ru_flow"] = (
                estimates["tdc_tier2_component_anchored_domestic_bank_only_ru_flow"]
                - components["fed_tier1_component_extension_proxy"]
            )

    if {
        "fed_tsy_coupon_interest_proxy",
        "bank_tier2_component_interest_proxy",
        "row_tier2_component_interest_proxy",
    }.issubset(components.columns):
        corrections["tier2_row_component_interest_correction"] = -components[
            "row_tier2_component_interest_proxy"
        ]
        corrections["tier2_row_coupon_correction"] = corrections["tier2_row_component_interest_correction"]
        estimates["tdc_tier2_component_anchored_bank_only_ru_flow"] = (
            estimates["tdc_base_bank_only_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tier2_component_interest_proxy"]
            - components["row_tier2_component_interest_proxy"]
        )
        estimates["tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"] = (
            estimates["tdc_base_broad_depository_np_cu_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tier2_component_interest_proxy"]
            - components["row_tier2_component_interest_proxy"]
        )
        estimates["tdc_tier2_interest_corrected_bank_only_ru_flow"] = estimates[
            "tdc_tier2_component_anchored_bank_only_ru_flow"
        ]
        estimates["tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow"] = estimates[
            "tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"
        ]
        if "fed_tier1_component_extension_proxy" in components.columns:
            estimates["tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow"] = (
                estimates["tdc_tier2_component_anchored_bank_only_ru_flow"]
                - components["fed_tier1_component_extension_proxy"]
            )
            estimates["tdc_tier2_component_anchored_fed_extension_broad_depository_np_cu_ru_flow"] = (
                estimates["tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"]
                - components["fed_tier1_component_extension_proxy"]
            )
        if "credit_union_tier2_component_interest_proxy" in components.columns:
            corrections["tier2_credit_union_component_interest_correction"] = -components[
                "credit_union_tier2_component_interest_proxy"
            ]
            corrections["tier2_credit_union_coupon_correction"] = corrections[
                "tier2_credit_union_component_interest_correction"
            ]
            estimates["tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow"] = (
                estimates["tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"]
                - components["credit_union_tier2_component_interest_proxy"]
            )
            estimates["tdc_tier2_interest_corrected_depository_institution_np_cu_ru_flow"] = estimates[
                "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow"
            ]
            if "fed_tier1_component_extension_proxy" in components.columns:
                estimates["tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow"] = (
                    estimates["tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow"]
                    - components["fed_tier1_component_extension_proxy"]
                )

        for suffix, component_key in [
            ("lb", "mmf_rrp_adjustment_lb"),
            ("prop", "mmf_rrp_adjustment_prop"),
            ("ub", "mmf_rrp_adjustment_ub"),
        ]:
            if component_key in components.columns:
                adjustment = mmf_routes["mmf_rrp_adjustment"][f"mmf_route_{suffix}"]
                estimates[f"tdc_tier2_component_anchored_mmf_rrp_{suffix}_bank_only_ru_flow"] = (
                    estimates["tdc_tier2_component_anchored_bank_only_ru_flow"] + adjustment
                )
                estimates[
                    f"tdc_tier2_component_anchored_mmf_rrp_{suffix}_broad_depository_np_cu_ru_flow"
                ] = estimates["tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"] + adjustment
                if "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow" in estimates.columns:
                    estimates[
                        f"tdc_tier2_component_anchored_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"
                    ] = estimates["tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow"] + adjustment
                    estimates[f"tdc_tier2_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"] = estimates[
                        f"tdc_tier2_component_anchored_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"
                    ]
                    if suffix == "prop":
                        estimates[CANONICAL_TIER2_METHOD] = estimates[
                            "tdc_tier2_component_anchored_mmf_rrp_prop_depository_institution_np_cu_ru_flow"
                        ]
                estimates[f"tdc_tier2_mmf_rrp_{suffix}_bank_only_ru_flow"] = estimates[
                    f"tdc_tier2_component_anchored_mmf_rrp_{suffix}_bank_only_ru_flow"
                ]
                estimates[f"tdc_tier2_mmf_rrp_{suffix}_broad_depository_np_cu_ru_flow"] = estimates[
                    f"tdc_tier2_component_anchored_mmf_rrp_{suffix}_broad_depository_np_cu_ru_flow"
                ]
                if "tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow" in estimates.columns:
                    estimates[
                        f"tdc_tier2_component_anchored_fed_extension_mmf_rrp_{suffix}_bank_only_ru_flow"
                    ] = estimates["tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow"] + adjustment
                if "tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow" in estimates.columns:
                    estimates[
                        f"tdc_tier2_component_anchored_fed_extension_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"
                    ] = (
                        estimates["tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow"]
                        + adjustment
                    )

    if {
        "fed_tsy_coupon_interest_proxy",
        "bank_tsy_coupon_interest_proxy",
        "bank_noninterest_outlay_proxy",
        "bank_nonborrow_receipt_proxy",
        "mint_cb_cash_factor_proxy",
    }.issubset(components.columns):
        corrections["tier3_bank_noninterest_outlay_correction"] = -components["bank_noninterest_outlay_proxy"]
        corrections["tier3_bank_nonborrow_receipt_correction"] = components["bank_nonborrow_receipt_proxy"]
        corrections["tier3_mint_cb_cash_factor_correction"] = components["mint_cb_cash_factor_proxy"]
        estimates["tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow"] = (
            estimates["tdc_domestic_bank_only_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tsy_coupon_interest_proxy"]
            - components["bank_noninterest_outlay_proxy"]
            + components["bank_nonborrow_receipt_proxy"]
            + components["mint_cb_cash_factor_proxy"]
        )

    if {
        "fed_tsy_coupon_interest_proxy",
        "bank_tsy_coupon_interest_proxy",
        "row_tsy_coupon_interest_proxy",
        "bank_noninterest_outlay_proxy",
        "row_noninterest_outlay_proxy",
        "bank_nonborrow_receipt_proxy",
        "row_nonborrow_receipt_proxy",
        "mint_cb_cash_factor_proxy",
    }.issubset(components.columns):
        corrections["tier3_row_noninterest_outlay_correction"] = -components["row_noninterest_outlay_proxy"]
        corrections["tier3_row_nonborrow_receipt_correction"] = components["row_nonborrow_receipt_proxy"]
        estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] = (
            estimates["tdc_base_bank_only_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tsy_coupon_interest_proxy"]
            - components["row_tsy_coupon_interest_proxy"]
            - components["bank_noninterest_outlay_proxy"]
            - components["row_noninterest_outlay_proxy"]
            + components["bank_nonborrow_receipt_proxy"]
            + components["row_nonborrow_receipt_proxy"]
            + components["mint_cb_cash_factor_proxy"]
        )
        estimates["tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow"] = (
            estimates["tdc_base_broad_depository_np_cu_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tsy_coupon_interest_proxy"]
            - components["row_tsy_coupon_interest_proxy"]
            - components["bank_noninterest_outlay_proxy"]
            - components["row_noninterest_outlay_proxy"]
            + components["bank_nonborrow_receipt_proxy"]
            + components["row_nonborrow_receipt_proxy"]
            + components["mint_cb_cash_factor_proxy"]
        )

    if {
        "fed_tsy_coupon_interest_proxy",
        "bank_tier2_component_interest_proxy",
        "bank_noninterest_outlay_proxy",
        "bank_nonborrow_receipt_proxy",
        "mint_cb_cash_factor_proxy",
    }.issubset(components.columns):
        estimates["tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow"] = (
            estimates["tdc_domestic_bank_only_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tier2_component_interest_proxy"]
            - components["bank_noninterest_outlay_proxy"]
            + components["bank_nonborrow_receipt_proxy"]
            + components["mint_cb_cash_factor_proxy"]
        )

    if {
        "fed_tsy_coupon_interest_proxy",
        "bank_tier2_component_interest_proxy",
        "row_tier2_component_interest_proxy",
        "bank_noninterest_outlay_proxy",
        "row_noninterest_outlay_proxy",
        "bank_nonborrow_receipt_proxy",
        "row_nonborrow_receipt_proxy",
        "mint_cb_cash_factor_proxy",
    }.issubset(components.columns):
        estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] = (
            estimates["tdc_base_bank_only_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tier2_component_interest_proxy"]
            - components["row_tier2_component_interest_proxy"]
            - components["bank_noninterest_outlay_proxy"]
            - components["row_noninterest_outlay_proxy"]
            + components["bank_nonborrow_receipt_proxy"]
            + components["row_nonborrow_receipt_proxy"]
            + components["mint_cb_cash_factor_proxy"]
        )
        estimates["tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow"] = (
            estimates["tdc_base_broad_depository_np_cu_ru_flow"]
            - components["fed_tsy_coupon_interest_proxy"]
            - components["bank_tier2_component_interest_proxy"]
            - components["row_tier2_component_interest_proxy"]
            - components["bank_noninterest_outlay_proxy"]
            - components["row_noninterest_outlay_proxy"]
            + components["bank_nonborrow_receipt_proxy"]
            + components["row_nonborrow_receipt_proxy"]
            + components["mint_cb_cash_factor_proxy"]
        )

    for key in [
        "tdc_base_bank_only_ru_flow",
        "tdc_base_broad_depository_np_cu_ru_flow",
        "tdc_broad_depository_np_corp_cu_ru_flow",
        "tdc_credit_union_aggregate_sensitivity",
        "tdc_domestic_bank_only_ru_flow",
        "tdc_no_remit_bank_only",
    ]:
        estimates[key] = _from_date(estimates[key], tx_start)

    for key in [
        "tdc_tier1_fed_corrected_bank_only_ru_flow",
        "tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow",
        "tdc_tier1_fed_corrected_domestic_bank_only_ru_flow",
        "tdc_tier2_interest_corrected_bank_only_ru_flow",
        "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow",
        "tdc_tier2_interest_corrected_depository_institution_np_cu_ru_flow",
        "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow",
        "tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow",
        "tdc_tier2_h15_treasury_interest_robust_broad_depository_np_cu_ru_flow",
        "tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow",
        "tdc_tier2_component_anchored_bank_only_ru_flow",
        "tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow",
        "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow",
        "tdc_tier2_component_anchored_domestic_bank_only_ru_flow",
        "tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow",
        "tdc_tier2_component_anchored_fed_extension_broad_depository_np_cu_ru_flow",
        "tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow",
        "tdc_tier2_component_anchored_fed_extension_domestic_bank_only_ru_flow",
        "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
        "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
        "tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow",
    ]:
        if key in estimates.columns:
            estimates[key] = _from_date(estimates[key], tx_start)
    for key in list(estimates.columns):
        if (
            key.startswith("tdc_tier2_mmf_rrp_")
            or key.startswith("tdc_tier2_h15_")
            or key.startswith("tdc_tier2_component_anchored_mmf_rrp_")
            or key.startswith("tdc_tier2_component_anchored_fed_extension_mmf_rrp_")
        ):
            estimates[key] = _from_date(estimates[key], tx_start)

    level_cols_bank = [
        "fed_tsy_level",
        *BANK_DEPOSITORY_LEVEL_KEYS,
        "row_tsy_level",
        "treasury_operating_cash_level",
    ]
    if _has_all(quarterly, level_cols_bank):
        bank_level_tsy = (
            quarterly["fed_tsy_level"]
            + _sum_columns(quarterly, BANK_DEPOSITORY_LEVEL_KEYS)
            + quarterly["row_tsy_level"]
        )
        estimates["tdc_level_bank_only_sensitivity"] = (
            bank_level_tsy.diff()
            - quarterly["treasury_operating_cash_level"].diff()
            + remit_for_level_backfill
        )

    level_cols_broad_np = [
        "fed_tsy_level",
        *BANK_DEPOSITORY_LEVEL_KEYS,
        "np_credit_unions_tsy_level",
        "row_tsy_level",
        "treasury_operating_cash_level",
    ]
    if _has_all(quarterly, level_cols_broad_np):
        broad_np_level_tsy = (
            quarterly["fed_tsy_level"]
            + _sum_columns(quarterly, BANK_DEPOSITORY_LEVEL_KEYS)
            + quarterly["np_credit_unions_tsy_level"]
            + quarterly["row_tsy_level"]
        )
        estimates["tdc_level_broad_depository_np_cu_sensitivity"] = (
            broad_np_level_tsy.diff()
            - quarterly["treasury_operating_cash_level"].diff()
            + remit_for_level_backfill
        )

    if _has_all(quarterly, ["m2", "currency", "bank_credit", *BANK_DEPOSITORY_LEVEL_KEYS]):
        # M2SL, CURRCIR and TOTBKCR are published in USD billions; Z.1 levels are USD millions.
        m2, currency, bank_credit = (quarterly[key] * H8_USD_MILLION_PER_BILLION for key in ("m2", "currency", "bank_credit"))
        bank_non_tsy = bank_credit - _sum_columns(quarterly, BANK_DEPOSITORY_LEVEL_KEYS)
        estimates["tdc_decomposition_proxy_bank_centric"] = m2.diff() - currency.diff() - bank_non_tsy.diff()

    historical_start = "1990-03-31"
    if "tdc_level_bank_only_sensitivity" in estimates.columns:
        estimates["tdc_bank_only_extended_1990"] = estimates["tdc_base_bank_only_ru_flow"].combine_first(
            _from_date(estimates["tdc_level_bank_only_sensitivity"], historical_start).where(before_transaction_era)
        )

    if "tdc_level_broad_depository_np_cu_sensitivity" in estimates.columns:
        estimates["tdc_broad_depository_extended_1990"] = estimates[
            "tdc_base_broad_depository_np_cu_ru_flow"
        ].combine_first(
            _from_date(estimates["tdc_level_broad_depository_np_cu_sensitivity"], historical_start).where(
                before_transaction_era
            )
        )

    estimates["tdc_base_bank_only_ru_flow_4q"] = estimates["tdc_base_bank_only_ru_flow"].rolling(4).sum()
    estimates["tdc_base_bank_only_ru_flow_cum"] = estimates["tdc_base_bank_only_ru_flow"].cumsum()

    if "tdc_tier1_fed_corrected_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier1_bank_only_delta_from_base"] = (
            estimates["tdc_tier1_fed_corrected_bank_only_ru_flow"] - estimates["tdc_base_bank_only_ru_flow"]
        )
        corrections["tdc_tier1_broad_depository_np_cu_delta_from_base"] = (
            estimates["tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow"]
            - estimates["tdc_base_broad_depository_np_cu_ru_flow"]
        )
        corrections["tdc_tier1_domestic_bank_only_delta_from_base"] = (
            estimates["tdc_tier1_fed_corrected_domestic_bank_only_ru_flow"]
            - estimates["tdc_domestic_bank_only_ru_flow"]
        )

    if "tdc_tier2_interest_corrected_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier2_bank_only_delta_from_base"] = (
            estimates["tdc_tier2_interest_corrected_bank_only_ru_flow"] - estimates["tdc_base_bank_only_ru_flow"]
        )
        corrections["tdc_tier2_bank_only_delta_from_tier1"] = (
            estimates["tdc_tier2_interest_corrected_bank_only_ru_flow"]
            - estimates["tdc_tier1_fed_corrected_bank_only_ru_flow"]
        )
        corrections["tdc_tier2_broad_depository_np_cu_delta_from_base"] = (
            estimates["tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow"]
            - estimates["tdc_base_broad_depository_np_cu_ru_flow"]
        )
        corrections["tdc_tier2_broad_depository_np_cu_delta_from_tier1"] = (
            estimates["tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow"]
            - estimates["tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow"]
        )

    if "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier2_domestic_bank_only_delta_from_base"] = (
            estimates["tdc_tier2_interest_corrected_domestic_bank_only_ru_flow"]
            - estimates["tdc_domestic_bank_only_ru_flow"]
        )
        corrections["tdc_tier2_domestic_bank_only_delta_from_tier1"] = (
            estimates["tdc_tier2_interest_corrected_domestic_bank_only_ru_flow"]
            - estimates["tdc_tier1_fed_corrected_domestic_bank_only_ru_flow"]
        )

    if "tdc_tier2_component_anchored_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier2_component_anchored_bank_only_delta_from_base"] = (
            estimates["tdc_tier2_component_anchored_bank_only_ru_flow"] - estimates["tdc_base_bank_only_ru_flow"]
        )
        corrections["tdc_tier2_component_anchored_bank_only_delta_from_tier1"] = (
            estimates["tdc_tier2_component_anchored_bank_only_ru_flow"]
            - estimates["tdc_tier1_fed_corrected_bank_only_ru_flow"]
        )
        corrections["tdc_tier2_component_anchored_broad_depository_np_cu_delta_from_base"] = (
            estimates["tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"]
            - estimates["tdc_base_broad_depository_np_cu_ru_flow"]
        )
        corrections["tdc_tier2_component_anchored_broad_depository_np_cu_delta_from_tier1"] = (
            estimates["tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"]
            - estimates["tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow"]
        )

    if "tdc_tier2_component_anchored_domestic_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier2_component_anchored_domestic_bank_only_delta_from_base"] = (
            estimates["tdc_tier2_component_anchored_domestic_bank_only_ru_flow"]
            - estimates["tdc_domestic_bank_only_ru_flow"]
        )
        corrections["tdc_tier2_component_anchored_domestic_bank_only_delta_from_tier1"] = (
            estimates["tdc_tier2_component_anchored_domestic_bank_only_ru_flow"]
            - estimates["tdc_tier1_fed_corrected_domestic_bank_only_ru_flow"]
        )

    if "tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier2_component_anchored_fed_extension_bank_only_delta_from_component"] = (
            estimates["tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow"]
            - estimates["tdc_tier2_component_anchored_bank_only_ru_flow"]
        )
        corrections["tdc_tier2_component_anchored_fed_extension_broad_depository_np_cu_delta_from_component"] = (
            estimates["tdc_tier2_component_anchored_fed_extension_broad_depository_np_cu_ru_flow"]
            - estimates["tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"]
        )

    if "tdc_tier2_component_anchored_fed_extension_domestic_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier2_component_anchored_fed_extension_domestic_bank_only_delta_from_component"] = (
            estimates["tdc_tier2_component_anchored_fed_extension_domestic_bank_only_ru_flow"]
            - estimates["tdc_tier2_component_anchored_domestic_bank_only_ru_flow"]
        )

    if "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier3_bank_only_delta_from_base"] = (
            estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] - estimates["tdc_base_bank_only_ru_flow"]
        )
        corrections["tdc_tier3_bank_only_delta_from_tier2"] = (
            estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"]
            - estimates["tdc_tier2_interest_corrected_bank_only_ru_flow"]
        )
        corrections["tdc_tier3_broad_depository_np_cu_delta_from_base"] = (
            estimates["tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow"]
            - estimates["tdc_base_broad_depository_np_cu_ru_flow"]
        )
        corrections["tdc_tier3_broad_depository_np_cu_delta_from_tier2"] = (
            estimates["tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow"]
            - estimates["tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow"]
        )

    if "tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow" in estimates.columns:
        corrections["tdc_tier3_domestic_bank_only_delta_from_base"] = (
            estimates["tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow"]
            - estimates["tdc_domestic_bank_only_ru_flow"]
        )
        corrections["tdc_tier3_domestic_bank_only_delta_from_tier2"] = (
            estimates["tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow"]
            - estimates["tdc_tier2_interest_corrected_domestic_bank_only_ru_flow"]
        )

    components["tdc_base_bank_only_ru_flow"] = estimates["tdc_base_bank_only_ru_flow"]
    components["tdc_base_broad_depository_np_cu_ru_flow"] = estimates[
        "tdc_base_broad_depository_np_cu_ru_flow"
    ]

    # Available means at least one observed quarter, not merely a column of missing values.
    canonical_available = CANONICAL_TIER2_METHOD in estimates.columns and bool(estimates[CANONICAL_TIER2_METHOD].notna().any())
    metadata = {
        "preferred_method": CANONICAL_TIER2_METHOD if canonical_available else None,
        "canonical_tier2_method": CANONICAL_TIER2_METHOD if canonical_available else None,
        "canonical_tier2_status": (
            "available"
            if canonical_available
            else f"unavailable: requires {CANONICAL_TIER2_REQUIREMENT}"
        ),
        "ladder_inputs_by_deposit_concept": {
            "bank_only": "tdc_base_bank_only_ru_flow",
            "broad_depository": "tdc_base_broad_depository_np_cu_ru_flow",
        },
        "available_methods": list(estimates.columns),
        "estimator_ladder": {
            "tier0": [
                "tdc_base_bank_only_ru_flow",
                "tdc_base_broad_depository_np_cu_ru_flow",
                "tdc_domestic_bank_only_ru_flow",
            ],
            "tier1": [
                "tdc_tier1_fed_corrected_bank_only_ru_flow",
                "tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow",
                "tdc_tier1_fed_corrected_domestic_bank_only_ru_flow",
            ],
            "tier2": [
                "tdc_tier2_interest_corrected_bank_only_ru_flow",
                "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow",
                "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow",
            ],
            "tier3": [
                "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
                "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
                "tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow",
            ],
        },
        "correction_series": {
            "tier1_fed_coupon_correction": "Signed Tier 1 Fed coupon-interest correction. Negative values mean the corrected estimator is lower than Tier 0 by that amount in the quarter.",
            "tier2_bank_coupon_correction": "Signed default Tier 2 bank-sector Treasury interest correction layered on top of Tier 1 where available. Uses the promoted component-anchored support series when present, with H15 as fallback.",
            "tier2_row_coupon_correction": "Signed default Tier 2 rest-of-world Treasury interest correction layered on top of Tier 1 where available. Uses the promoted component-anchored support series when present, with H15 as fallback.",
            "tdc_tier1_bank_only_delta_from_base": "Tier 1 bank-only minus Tier 0 bank-only.",
            "tdc_tier1_broad_depository_np_cu_delta_from_base": "Tier 1 broad-depository minus Tier 0 broad-depository.",
            "tdc_tier1_domestic_bank_only_delta_from_base": "Tier 1 domestic-only minus Tier 0 domestic-only.",
            "tdc_tier2_bank_only_delta_from_base": "Tier 2 bank-only minus Tier 0 bank-only.",
            "tdc_tier2_bank_only_delta_from_tier1": "Tier 2 bank-only minus Tier 1 bank-only.",
            "tdc_tier2_broad_depository_np_cu_delta_from_base": "Tier 2 broad-depository minus Tier 0 broad-depository.",
            "tdc_tier2_broad_depository_np_cu_delta_from_tier1": "Tier 2 broad-depository minus Tier 1 broad-depository.",
            "tdc_tier2_domestic_bank_only_delta_from_base": "Tier 2 domestic-only minus Tier 0 domestic-only.",
            "tdc_tier2_domestic_bank_only_delta_from_tier1": "Tier 2 domestic-only minus Tier 1 domestic-only.",
            "tier3_bank_noninterest_outlay_correction": "Signed Tier 3 bank noninterest outlay correction. Negative values mean Treasury noninterest payments to banks lower the corrected estimator relative to Tier 2.",
            "tier3_row_noninterest_outlay_correction": "Signed Tier 3 ROW noninterest outlay correction.",
            "tier3_bank_nonborrow_receipt_correction": "Signed Tier 3 bank nonborrow receipt correction. Positive values mean Treasury receipts from banks raise the corrected estimator relative to Tier 2.",
            "tier3_row_nonborrow_receipt_correction": "Signed Tier 3 ROW nonborrow receipt correction.",
            "tier3_mint_cb_cash_factor_correction": "Signed Tier 3 mint or central-bank cash-factor correction.",
            "tdc_tier3_bank_only_delta_from_base": "Tier 3 bank-only minus Tier 0 bank-only.",
            "tdc_tier3_bank_only_delta_from_tier2": "Tier 3 bank-only minus Tier 2 bank-only.",
            "tdc_tier3_broad_depository_np_cu_delta_from_base": "Tier 3 broad-depository minus Tier 0 broad-depository.",
            "tdc_tier3_broad_depository_np_cu_delta_from_tier2": "Tier 3 broad-depository minus Tier 2 broad-depository.",
            "tdc_tier3_domestic_bank_only_delta_from_base": "Tier 3 domestic-only minus Tier 0 domestic-only.",
            "tdc_tier3_domestic_bank_only_delta_from_tier2": "Tier 3 domestic-only minus Tier 2 domestic-only.",
        },
        "notes": [
            "The headline is the canonical Tier 2 row, tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow. The Tier 0 baseline is a bank-only transaction-based estimator beginning in 2002.",
            "A broad-depository alternative adds natural-person credit-union Treasury transactions and uses the same transaction-era coverage.",
            "Corporate credit unions are included only as an additional sensitivity layer.",
            "The aggregate credit-union sensitivity also includes the NCUA capitalization deposit, which is part of the published aggregate credit-union Treasury series in Z.1.",
            "Negative H.4.1 remittance values are clipped to zero before quarter aggregation, and missing pre-history is treated as zero rather than suppressing older estimates.",
            "The Tier 0 cash term is Treasury operating cash, not a TGA-only concept; historical Treasury Tax and Loan balances belong inside that operating-cash concept when they were material.",
            "Tier 1 subtracts an optional Fed Treasury coupon-interest proxy built from SOMA holdings snapshots.",
            "Tier 2 keeps the same default bank-sector perimeter as Tier 0 and subtracts promoted component-anchored bank-sector and rest-of-world Treasury interest proxies in addition to the Fed proxy when those support files are present. Legacy WAMEST/H.15 intensity rows are retained under explicit H15 sensitivity names.",
            "Tier 3 keeps the Tier 2 interest layer and then applies optional reserve-user fiscal-flow corrections for bank and rest-of-world noninterest outlays, nonborrow receipts, and mint or central-bank cash-factor adjustments.",
            "Separate historical-extension series splice in the level-change analog from 1990 until transaction coverage begins.",
            "Level and decomposition methods are sensitivity checks only.",
        ],
        "method_descriptions": {
            "tdc_base_bank_only_ru_flow": "Bank-only baseline (Tier 0 ladder input). Fed + bank-sector + rest-of-world Treasury transactions minus Treasury operating cash transactions plus positive Fed remittances. Transaction-data era only.",
            "tdc_base_broad_depository_np_cu_ru_flow": "Broad-depository alternative that adds natural-person credit-union Treasury transactions. Transaction-data era only.",
            "tdc_broad_depository_np_corp_cu_ru_flow": "Sensitivity that also adds corporate credit-union Treasury transactions.",
            "tdc_credit_union_aggregate_sensitivity": "Sensitivity that matches the aggregate credit-union Treasury concept by adding natural-person and corporate credit-union Treasury transactions plus the NCUA capitalization deposit term.",
            "tdc_domestic_bank_only_ru_flow": "Bank-only baseline excluding the rest-of-world term.",
            "tdc_no_remit_bank_only": "Bank-only baseline excluding Fed remittances.",
            "tdc_tier1_fed_corrected_bank_only_ru_flow": "Tier 1 bank-only variant. Tier 0 bank-only baseline minus the optional Fed Treasury coupon-interest proxy from SOMA holdings snapshots.",
            "tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow": "Tier 1 broad-depository variant. Broad-depository Tier 0 baseline minus the optional Fed Treasury coupon-interest proxy.",
            "tdc_tier1_fed_corrected_domestic_bank_only_ru_flow": "Tier 1 domestic-only bank variant. Domestic-only Tier 0 baseline minus the optional Fed Treasury coupon-interest proxy.",
            "tdc_tier2_interest_corrected_bank_only_ru_flow": "Tier 2 bank-only variant. Tier 0 bank-only baseline minus Fed coupon plus promoted component-anchored bank and ROW Treasury interest proxies when present; falls back to the H15 intensity proxies when component support is absent.",
            "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow": "Tier 2 broad-depository variant. Broad-depository Tier 0 baseline minus Fed coupon plus promoted component-anchored bank and ROW Treasury interest proxies when present; falls back to the H15 intensity proxies when component support is absent.",
            "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow": "Tier 2 domestic-only bank variant. Domestic-only Tier 0 baseline minus Fed coupon plus promoted component-anchored bank Treasury interest proxy when present; falls back to the H15 intensity proxy when component support is absent.",
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": "Tier 3 bank-only variant. Tier 2 bank-only plus optional bank and rest-of-world reserve-user fiscal-flow corrections and a mint or central-bank cash-factor adjustment.",
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow": "Tier 3 broad-depository variant. Tier 2 broad-depository plus optional bank and rest-of-world reserve-user fiscal-flow corrections and a mint or central-bank cash-factor adjustment.",
            "tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow": "Tier 3 domestic-only bank variant. Tier 2 domestic-only plus optional bank reserve-user fiscal-flow corrections and a mint or central-bank cash-factor adjustment.",
            "tdc_bank_only_extended_1990": "Historical extension that uses the bank-only transaction baseline where available and the bank-only level-change analog from 1990 until transaction coverage begins.",
            "tdc_broad_depository_extended_1990": "Historical extension that uses the broad-depository transaction series where available and the broad-depository level-change analog from 1990 until transaction coverage begins.",
            "tdc_level_bank_only_sensitivity": "Level-change version of the bank-only estimator.",
            "tdc_level_broad_depository_np_cu_sensitivity": "Level-change broad-depository sensitivity with natural-person credit unions.",
            "tdc_decomposition_proxy_bank_centric": "Rough money/bank-balance-sheet proxy. Included for diagnostics only.",
        },
        "method_formulas": {
            "tdc_base_bank_only_ru_flow": "Bank-only baseline = Federal Reserve Treasury transactions + Bank-sector Treasury transactions + Rest-of-world Treasury transactions - Treasury operating cash transactions + Positive Federal Reserve remittances.",
            "tdc_base_broad_depository_np_cu_ru_flow": "Broad-depository baseline = Bank-only baseline + Natural-person credit-union Treasury transactions.",
            "tdc_broad_depository_np_corp_cu_ru_flow": "Broad-depository plus corporate credit unions = Broad-depository baseline + Corporate credit-union Treasury transactions.",
            "tdc_credit_union_aggregate_sensitivity": "Aggregate credit-union sensitivity = Broad-depository plus corporate credit unions + NCUA capitalization deposit term.",
            "tdc_domestic_bank_only_ru_flow": "Domestic-only bank baseline = Federal Reserve Treasury transactions + Bank-sector Treasury transactions - Treasury operating cash transactions + Positive Federal Reserve remittances.",
            "tdc_no_remit_bank_only": "Bank-only excluding remittances = Federal Reserve Treasury transactions + Bank-sector Treasury transactions + Rest-of-world Treasury transactions - Treasury operating cash transactions.",
            "tdc_tier1_fed_corrected_bank_only_ru_flow": "Tier 1 bank-only = Bank-only baseline - Fed Treasury coupon-interest proxy.",
            "tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow": "Tier 1 broad-depository = Broad-depository baseline - Fed Treasury coupon-interest proxy.",
            "tdc_tier1_fed_corrected_domestic_bank_only_ru_flow": "Tier 1 domestic-only = Domestic-only bank baseline - Fed Treasury coupon-interest proxy.",
            "tdc_tier2_interest_corrected_bank_only_ru_flow": "Tier 2 bank-only = Bank-only baseline - Fed Treasury coupon-interest proxy - Bank component-anchored Treasury interest proxy - Rest-of-world component-anchored Treasury interest proxy when component support is present; otherwise uses the H15 coupon-intensity proxies.",
            "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow": "Tier 2 broad-depository = Broad-depository baseline - Fed Treasury coupon-interest proxy - Bank component-anchored Treasury interest proxy - Rest-of-world component-anchored Treasury interest proxy when component support is present; otherwise uses the H15 coupon-intensity proxies.",
            "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow": "Tier 2 domestic-only = Domestic-only bank baseline - Fed Treasury coupon-interest proxy - Bank component-anchored Treasury interest proxy when component support is present; otherwise uses the H15 coupon-intensity proxy.",
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": "Tier 3 bank-only = Tier 2 bank-only - Bank noninterest outlay proxy - Rest-of-world noninterest outlay proxy + Bank nonborrow receipt proxy + Rest-of-world nonborrow receipt proxy + Mint or central-bank cash-factor proxy.",
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow": "Tier 3 broad-depository = Tier 2 broad-depository - Bank noninterest outlay proxy - Rest-of-world noninterest outlay proxy + Bank nonborrow receipt proxy + Rest-of-world nonborrow receipt proxy + Mint or central-bank cash-factor proxy.",
            "tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow": "Tier 3 domestic-only = Tier 2 domestic-only - Bank noninterest outlay proxy + Bank nonborrow receipt proxy + Mint or central-bank cash-factor proxy.",
            "tdc_bank_only_extended_1990": "Bank-only extended series = Bank-only baseline when available; otherwise Bank-only level-change sensitivity, which excludes Fed remittances before the remittance series begins.",
            "tdc_broad_depository_extended_1990": "Broad-depository extended series = Broad-depository baseline when available; otherwise Broad-depository level-change sensitivity, which excludes Fed remittances before the remittance series begins.",
            "tdc_level_bank_only_sensitivity": "Bank-only level-change sensitivity = Change in Federal Reserve Treasury holdings + Change in Bank-sector Treasury holdings + Change in Rest-of-world Treasury holdings - Change in Treasury operating cash + Positive Federal Reserve remittances.",
            "tdc_level_broad_depository_np_cu_sensitivity": "Broad-depository level-change sensitivity = Bank-only level-change sensitivity + Change in natural-person credit-union Treasury holdings.",
            "tdc_decomposition_proxy_bank_centric": "Bank-centric decomposition proxy = Change in M2 - Change in currency - Change in non-Treasury bank assets, with the H.8 and money-stock series converted from USD billions to USD millions.",
            "tdc_base_bank_only_ru_flow_4q": "Bank-only baseline, four-quarter sum = Rolling four-quarter sum of the bank-only baseline.",
            "tdc_base_bank_only_ru_flow_cum": "Bank-only baseline, cumulative = Cumulative sum of the bank-only baseline.",
        },
        "credit_union_policy": {
            "default": "exclude_all_credit_unions_from_bank_only_headline",
            "broad_depository_headline": "include_natural_person_credit_unions_only",
            "corporate_credit_unions": "sensitivity_only",
            "ncua_capitalization_deposit": "aggregate_credit_union_sensitivity_only",
        },
        "bank_perimeter": {
            "default_bank_block": "us_chartered_plus_foreign_offices_plus_affiliated_areas",
            "tier2_coupon_proxy_alignment": "Tier 2 bank coupon corrections should align with the Tier 0 bank-sector block rather than a broader H.8-style perimeter.",
        },
        "historical_backfill": {
            "pre_transaction_history": "level_change_backfill",
            "historical_extension_starts": historical_start,
            "transaction_history_starts": tx_start,
            "fed_remittance_coverage_start": (
                pd.Timestamp(remit_coverage_start).date().isoformat() if remit_coverage_start is not None else None
            ),
            "fed_remittance_backfill_treatment": "The level-change backfill is used only before transaction_history_starts; there it excludes Federal Reserve remittances in quarters without remittance data.",
        },
        "mmf_rrp_route_status_counts": {
            prefix: {str(key): int(value) for key, value in route["mmf_route_status"].value_counts().sort_index().items()}
            for prefix, route in mmf_routes.items()
        },
        "cash_term": {
            "display_name": "Treasury operating cash",
            "transaction_series_key": "treasury_operating_cash_tx",
            "level_series_key": "treasury_operating_cash_level",
            "component_key": "minus_treasury_operating_cash_tx",
            "internal_transfer_series_key": "treasury_fed_internal_cash_tx",
            "definition": "Tier 0 subtracts Treasury operating cash, not a TGA-only cash balance, net of Treasury-Federal Reserve internal transfers: minus_treasury_operating_cash_tx = -(treasury_operating_cash_tx - treasury_fed_internal_cash_tx).",
            "internal_transfer_treatment": "The internal-transfer series is required in every transaction-era quarter; the component is missing in earlier quarters, where it is not defined. The level-change sensitivity columns use raw operating-cash level changes.",
            "historical_treatment": "When historical Treasury Tax and Loan balances were material, they belong inside the operating-cash concept rather than as a separate additive Tier 0 term.",
            "diagnostic_only_series": ["tga_weekly"],
        },
        "correction_inputs": {
            "fed_tsy_coupon_interest_proxy": {
                "series_key": "fed_tsy_coupon_interest_proxy",
                "raw_filename": "support__fed_tsy_coupon_interest_proxy.csv",
                "aggregation": "quarterly sum",
                "units": "Millions of U.S. dollars",
                "usage": "Tier 1 Fed-corrected variants subtract this proxy from Tier 0.",
                "construction": "Optional local support series produced from SOMA holdings snapshots and inferred coupon payment schedules. Raw SOMA par values are normalized to millions of U.S. dollars when needed.",
            },
            "bank_tsy_coupon_interest_proxy": {
                "series_key": "bank_tsy_coupon_interest_proxy",
                "raw_filename": "support__bank_tsy_coupon_interest_proxy.csv",
                "aggregation": "quarterly sum",
                "units": "Millions of U.S. dollars",
                "usage": "Tier 2 corrected variants subtract this proxy from the same bank-sector block used in Tier 0.",
                "construction": "Optional local support series produced outside the FRED downloader. The intended perimeter matches U.S.-chartered depositories, foreign banking offices in the U.S., and banks in U.S.-affiliated areas.",
            },
            "row_tsy_coupon_interest_proxy": {
                "series_key": "row_tsy_coupon_interest_proxy",
                "raw_filename": "support__row_tsy_coupon_interest_proxy.csv",
                "aggregation": "quarterly sum",
                "units": "Millions of U.S. dollars",
                "usage": "Tier 2 bank-only and broad-depository variants subtract this proxy when the rest-of-world Treasury term is included.",
                "construction": "Optional local support series produced outside the FRED downloader for the rest-of-world Treasury coupon-interest correction.",
            },
            "bank_noninterest_outlay_proxy": {
                "series_key": "bank_noninterest_outlay_proxy",
                "raw_filename": "support__bank_noninterest_outlay_proxy.csv",
                "aggregation": "quarterly sum",
                "units": "Millions of U.S. dollars",
                "usage": "Tier 3 variants subtract this proxy as Treasury noninterest payments to the default bank block.",
                "construction": "Optional local support series for Treasury noninterest outlays to banks. Positive values are treated as reserve-user fiscal payments and enter with a negative sign.",
            },
            "row_noninterest_outlay_proxy": {
                "series_key": "row_noninterest_outlay_proxy",
                "raw_filename": "support__row_noninterest_outlay_proxy.csv",
                "aggregation": "quarterly sum",
                "units": "Millions of U.S. dollars",
                "usage": "Tier 3 ROW-inclusive variants subtract this proxy as Treasury noninterest payments to the rest of world.",
                "construction": "Optional local support series for Treasury noninterest outlays to the rest of world. Positive values enter with a negative sign.",
            },
            "bank_nonborrow_receipt_proxy": {
                "series_key": "bank_nonborrow_receipt_proxy",
                "raw_filename": "support__bank_nonborrow_receipt_proxy.csv",
                "aggregation": "quarterly sum",
                "units": "Millions of U.S. dollars",
                "usage": "Tier 3 variants add this proxy as Treasury nonborrow receipts from the default bank block.",
                "construction": "Optional local support series for Treasury nonborrow receipts from banks. Positive values enter with a positive sign.",
            },
            "row_nonborrow_receipt_proxy": {
                "series_key": "row_nonborrow_receipt_proxy",
                "raw_filename": "support__row_nonborrow_receipt_proxy.csv",
                "aggregation": "quarterly sum",
                "units": "Millions of U.S. dollars",
                "usage": "Tier 3 ROW-inclusive variants add this proxy as Treasury nonborrow receipts from the rest of world.",
                "construction": "Optional local support series for Treasury nonborrow receipts from the rest of world. Positive values enter with a positive sign.",
            },
            "mint_cb_cash_factor_proxy": {
                "series_key": "mint_cb_cash_factor_proxy",
                "raw_filename": "support__mint_cb_cash_factor_proxy.csv",
                "aggregation": "quarterly sum",
                "units": "Millions of U.S. dollars",
                "usage": "Tier 3 variants add this proxy as a mint or central-bank cash-factor adjustment.",
                "construction": "Optional local support series for cash-balance changes that should offset Treasury operating-cash movements without being treated as deposit-user taxes or Treasury purchases.",
            },
        },
    }
    metadata["estimator_ladder"]["tier2"].extend(
        [
            "tdc_tier2_interest_corrected_depository_institution_np_cu_ru_flow",
            "tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow",
            "tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow",
            "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow",
            "tdc_tier2_mmf_rrp_prop_bank_only_ru_flow",
            "tdc_tier2_mmf_rrp_lb_bank_only_ru_flow",
            "tdc_tier2_mmf_rrp_ub_bank_only_ru_flow",
            "tdc_tier2_mmf_rrp_prop_depository_institution_np_cu_ru_flow",
            "tdc_tier2_component_anchored_bank_only_ru_flow",
            "tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow",
            "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow",
            "tdc_tier2_component_anchored_domestic_bank_only_ru_flow",
            "tdc_tier2_component_anchored_mmf_rrp_prop_bank_only_ru_flow",
            "tdc_tier2_component_anchored_mmf_rrp_prop_depository_institution_np_cu_ru_flow",
            "tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow",
            "tdc_tier2_component_anchored_fed_extension_broad_depository_np_cu_ru_flow",
            "tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow",
            "tdc_tier2_component_anchored_fed_extension_domestic_bank_only_ru_flow",
            "tdc_tier2_component_anchored_fed_extension_mmf_rrp_prop_bank_only_ru_flow",
            "tdc_tier2_component_anchored_fed_extension_mmf_rrp_prop_depository_institution_np_cu_ru_flow",
        ]
    )
    metadata["correction_series"].update(
        {
            "tier2_credit_union_coupon_correction": "Signed default Tier 2 natural-person credit-union Treasury interest correction for the depository-institution candidate. Uses the promoted component-anchored support series when present, with H15 as fallback.",
            "tier2_bank_h15_coupon_correction": "Signed legacy WAMEST/H15 bank-sector coupon-intensity correction retained as a sensitivity.",
            "tier2_row_h15_coupon_correction": "Signed legacy WAMEST/H15 rest-of-world coupon-intensity correction retained as a sensitivity.",
            "tier2_credit_union_h15_coupon_correction": "Signed legacy WAMEST/H15 credit-union coupon-intensity correction retained as a sensitivity.",
            "tier2_bank_bill_discount_robustness_correction": "Signed Tier 2 bank-sector Treasury bill-discount interest robustness correction.",
            "tier2_row_bill_discount_robustness_correction": "Signed Tier 2 rest-of-world Treasury bill-discount interest robustness correction.",
            "tier2_credit_union_bill_discount_robustness_correction": "Signed Tier 2 credit-union Treasury bill-discount interest robustness correction.",
            "tier2_mmf_rrp_prop_adjustment": "Preferred proportional MMF/RRP source-of-funds adjustment added to Tier 2 candidate rows.",
            "tier2_mmf_rrp_lb_adjustment": "Lower-bound MMF/RRP source-of-funds adjustment added to Tier 2 candidate rows.",
            "tier2_mmf_rrp_ub_adjustment": "Upper-bound MMF/RRP source-of-funds adjustment added to Tier 2 candidate rows.",
            "tier2_mmf_rrp_bills_prop_adjustment": "Bills-only proportional MMF/RRP robustness adjustment added to Tier 2 bank-only rows.",
            "tier2_mmf_rrp_bills_lb_adjustment": "Bills-only lower-bound MMF/RRP robustness adjustment added to Tier 2 bank-only rows.",
            "tier2_mmf_rrp_bills_ub_adjustment": "Bills-only upper-bound MMF/RRP robustness adjustment added to Tier 2 bank-only rows.",
            "tier2_bank_component_interest_correction": "Signed Tier 2 bank-sector component-anchored Treasury interest correction. Negative values mean official-pool allocated bank interest lowers the corrected estimator.",
            "tier2_row_component_interest_correction": "Signed Tier 2 rest-of-world component-anchored Treasury interest correction.",
            "tier2_credit_union_component_interest_correction": "Signed Tier 2 credit-union component-anchored Treasury interest correction.",
            "tdc_tier2_component_anchored_bank_only_delta_from_base": "Component-anchored Tier 2 bank-only minus Tier 0 bank-only.",
            "tdc_tier2_component_anchored_bank_only_delta_from_tier1": "Component-anchored Tier 2 bank-only minus Tier 1 bank-only.",
            "tdc_tier2_component_anchored_broad_depository_np_cu_delta_from_base": "Component-anchored Tier 2 broad-depository minus Tier 0 broad-depository.",
            "tdc_tier2_component_anchored_broad_depository_np_cu_delta_from_tier1": "Component-anchored Tier 2 broad-depository minus Tier 1 broad-depository.",
            "tdc_tier2_component_anchored_domestic_bank_only_delta_from_base": "Component-anchored Tier 2 domestic-only minus Tier 0 domestic-only.",
            "tdc_tier2_component_anchored_domestic_bank_only_delta_from_tier1": "Component-anchored Tier 2 domestic-only minus Tier 1 domestic-only.",
            "tier1_fed_component_extension_correction": "Signed nondefault Fed Tier 1 component extension for exact SOMA bill-discount plus FRN interest.",
            "tdc_tier2_component_anchored_fed_extension_bank_only_delta_from_component": "Fed-extension component-anchored bank-only minus component-anchored bank-only.",
            "tdc_tier2_component_anchored_fed_extension_broad_depository_np_cu_delta_from_component": "Fed-extension component-anchored broad-depository minus component-anchored broad-depository.",
            "tdc_tier2_component_anchored_fed_extension_domestic_bank_only_delta_from_component": "Fed-extension component-anchored domestic-only minus component-anchored domestic-only.",
        }
    )
    metadata["notes"].extend(
        [
            "The canonical Tier 2 row includes the proportional MMF/ON RRP adjustment; the lower- and upper-bound MMF rows and the bills-only MMF rows are sensitivities.",
            "The depository-institution Tier 2 candidate subtracts a separate credit-union Treasury coupon-interest proxy when that optional support series is available.",
            "The canonical Tier 2 row is the component-anchored depository-institution row plus the proportional MMF/ON RRP adjustment. It is written only when component-anchored interest support for banks, the rest of the world and credit unions and the MMF fund-month support are present; it is never filled from the H.15 coupon-only rows.",
            "Component-anchored Tier 2 rows are promoted as the live canonical Tier 2 rows when support files are present. They subtract staged official-pool allocations for bank, ROW, and credit-union Treasury interest components while preserving the existing Fed coupon Tier 1 correction.",
            "Fed-extension component-anchored rows are nondefault rows that additionally subtract exact SOMA bill-discount plus FRN interest. They do not add the separate TIPS coupon diagnostic or TIPS inflation-compensation proxy.",
        ]
    )
    metadata["method_descriptions"].update(
        {
            "tdc_tier2_interest_corrected_depository_institution_np_cu_ru_flow": "Tier 2 depository-institution candidate. Broad-depository NP-CU Tier 2 minus promoted credit-union component-anchored Treasury interest support when present; falls back to the H15 coupon proxy when component support is absent.",
            "tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow": "Legacy H15 sensitivity row subtracting estimated bank and ROW Treasury bill-discount interest from the H15 coupon-intensity Tier 2 bank-only row.",
            "tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow": "Legacy H15 sensitivity row subtracting estimated bank, ROW, and credit-union Treasury bill-discount interest from the H15 DI Tier 2 row.",
            "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow": "Canonical Tier 2 policy target. Depository-institution Treasury-flow row with promoted component-anchored bank, ROW, and credit-union interest corrections plus the preferred proportional MMF/RRP source-of-funds adjustment when support is present.",
            "tdc_tier2_mmf_rrp_prop_bank_only_ru_flow": "Candidate Tier 2 bank-only variant adding the preferred proportional MMF/RRP source-of-funds adjustment.",
            "tdc_tier2_mmf_rrp_lb_bank_only_ru_flow": "Candidate Tier 2 bank-only variant adding the lower-bound MMF/RRP source-of-funds adjustment.",
            "tdc_tier2_mmf_rrp_ub_bank_only_ru_flow": "Candidate Tier 2 bank-only variant adding the upper-bound MMF/RRP source-of-funds adjustment.",
            "tdc_tier2_mmf_rrp_prop_broad_depository_np_cu_ru_flow": "Candidate Tier 2 broad-depository variant adding the preferred proportional MMF/RRP source-of-funds adjustment.",
            "tdc_tier2_mmf_rrp_prop_depository_institution_np_cu_ru_flow": "Candidate Tier 2 depository-institution variant with CU coupon correction and the preferred proportional MMF/RRP source-of-funds adjustment.",
            "tdc_tier2_component_anchored_bank_only_ru_flow": "Promoted Tier 2 bank-only component row. Tier 0 bank-only minus existing Fed coupon correction and staged bank/ROW component-anchored interest corrections.",
            "tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow": "Promoted Tier 2 broad-depository component row using staged bank/ROW component-anchored interest corrections.",
            "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow": "Promoted Tier 2 depository-institution component row using staged bank/ROW/CU component-anchored interest corrections.",
            "tdc_tier2_component_anchored_domestic_bank_only_ru_flow": "Promoted Tier 2 domestic-only component row using the staged bank component-anchored interest correction.",
            "tdc_tier2_component_anchored_mmf_rrp_prop_bank_only_ru_flow": "Promoted component-anchored Tier 2 bank-only row adding the preferred proportional MMF/RRP adjustment.",
            "tdc_tier2_component_anchored_mmf_rrp_prop_depository_institution_np_cu_ru_flow": "Promoted component-anchored Tier 2 depository-institution row adding the preferred proportional MMF/RRP adjustment.",
            "tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow": "Nondefault component-anchored bank-only candidate that also subtracts exact SOMA bill-discount plus FRN interest.",
            "tdc_tier2_component_anchored_fed_extension_broad_depository_np_cu_ru_flow": "Nondefault component-anchored broad-depository candidate that also subtracts exact SOMA bill-discount plus FRN interest.",
            "tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow": "Nondefault component-anchored depository-institution candidate that also subtracts exact SOMA bill-discount plus FRN interest.",
            "tdc_tier2_component_anchored_fed_extension_domestic_bank_only_ru_flow": "Nondefault component-anchored domestic-only candidate that also subtracts exact SOMA bill-discount plus FRN interest.",
            "tdc_tier2_component_anchored_fed_extension_mmf_rrp_prop_bank_only_ru_flow": "Nondefault Fed-extension component-anchored bank-only candidate adding the preferred proportional MMF/RRP adjustment.",
            "tdc_tier2_component_anchored_fed_extension_mmf_rrp_prop_depository_institution_np_cu_ru_flow": "Nondefault Fed-extension component-anchored depository-institution candidate adding the preferred proportional MMF/RRP adjustment.",
        }
    )
    metadata["method_formulas"].update(
        {
            "tdc_tier2_interest_corrected_depository_institution_np_cu_ru_flow": "Tier 2 DI NP-CU = Tier 2 broad-depository NP-CU - Credit-union component-anchored Treasury interest proxy when component support is present; otherwise uses the H15 coupon-intensity proxy.",
            "tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow": "Legacy H15 bill-discount robustness bank-only = H15 Tier 2 bank-only - Bank Treasury bill-discount proxy - ROW Treasury bill-discount proxy.",
            "tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow": "Legacy H15 bill-discount robustness DI NP-CU = H15 Tier 2 DI NP-CU - Bank Treasury bill-discount proxy - ROW Treasury bill-discount proxy - Credit-union Treasury bill-discount proxy.",
            "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow": "Canonical Tier 2 DI + MMF/RRP = promoted component-anchored Tier 2 DI NP-CU + proportional fund-month MMF/RRP adjustment when component support is present.",
            "tdc_tier2_mmf_rrp_prop_bank_only_ru_flow": "Tier 2 + MMF/RRP prop bank-only = Tier 2 bank-only + proportional fund-month MMF/RRP adjustment.",
            "tdc_tier2_mmf_rrp_lb_bank_only_ru_flow": "Tier 2 + MMF/RRP lower bank-only = Tier 2 bank-only + lower-bound fund-month MMF/RRP adjustment.",
            "tdc_tier2_mmf_rrp_ub_bank_only_ru_flow": "Tier 2 + MMF/RRP upper bank-only = Tier 2 bank-only + upper-bound fund-month MMF/RRP adjustment.",
            "tdc_tier2_mmf_rrp_prop_depository_institution_np_cu_ru_flow": "Tier 2 + MMF/RRP prop DI NP-CU = Tier 2 DI NP-CU + proportional fund-month MMF/RRP adjustment.",
            "tdc_tier2_component_anchored_bank_only_ru_flow": "Component-anchored Tier 2 bank-only = Bank-only baseline - Fed Treasury coupon-interest proxy - Bank component-anchored Treasury interest proxy - ROW component-anchored Treasury interest proxy.",
            "tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow": "Component-anchored Tier 2 broad-depository = Broad-depository baseline - Fed Treasury coupon-interest proxy - Bank component-anchored Treasury interest proxy - ROW component-anchored Treasury interest proxy.",
            "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow": "Component-anchored Tier 2 DI NP-CU = Component-anchored Tier 2 broad-depository - Credit-union component-anchored Treasury interest proxy.",
            "tdc_tier2_component_anchored_domestic_bank_only_ru_flow": "Component-anchored Tier 2 domestic-only = Domestic-only bank baseline - Fed Treasury coupon-interest proxy - Bank component-anchored Treasury interest proxy.",
            "tdc_tier2_component_anchored_mmf_rrp_prop_bank_only_ru_flow": "Component-anchored Tier 2 + MMF/RRP prop bank-only = Component-anchored Tier 2 bank-only + proportional fund-month MMF/RRP adjustment.",
            "tdc_tier2_component_anchored_mmf_rrp_prop_depository_institution_np_cu_ru_flow": "Component-anchored Tier 2 + MMF/RRP prop DI NP-CU = Component-anchored Tier 2 DI NP-CU + proportional fund-month MMF/RRP adjustment.",
            "tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow": "Fed-extension component-anchored Tier 2 bank-only = Component-anchored Tier 2 bank-only - Fed bill+FRN component extension.",
            "tdc_tier2_component_anchored_fed_extension_broad_depository_np_cu_ru_flow": "Fed-extension component-anchored Tier 2 broad-depository = Component-anchored Tier 2 broad-depository - Fed bill+FRN component extension.",
            "tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow": "Fed-extension component-anchored Tier 2 DI NP-CU = Component-anchored Tier 2 DI NP-CU - Fed bill+FRN component extension.",
            "tdc_tier2_component_anchored_fed_extension_domestic_bank_only_ru_flow": "Fed-extension component-anchored Tier 2 domestic-only = Component-anchored Tier 2 domestic-only - Fed bill+FRN component extension.",
            "tdc_tier2_component_anchored_fed_extension_mmf_rrp_prop_bank_only_ru_flow": "Fed-extension component-anchored Tier 2 + MMF/RRP prop bank-only = Fed-extension component-anchored Tier 2 bank-only + proportional fund-month MMF/RRP adjustment.",
            "tdc_tier2_component_anchored_fed_extension_mmf_rrp_prop_depository_institution_np_cu_ru_flow": "Fed-extension component-anchored Tier 2 + MMF/RRP prop DI NP-CU = Fed-extension component-anchored Tier 2 DI NP-CU + proportional fund-month MMF/RRP adjustment.",
        }
    )
    metadata["correction_inputs"]["credit_union_tsy_coupon_interest_proxy"] = {
        "series_key": "credit_union_tsy_coupon_interest_proxy",
        "raw_filename": "support__credit_union_tsy_coupon_interest_proxy.csv",
        "aggregation": "quarterly sum",
        "units": "Millions of U.S. dollars",
        "usage": "Depository-institution Tier 2 candidates subtract this proxy when natural-person credit unions are included in the RU block.",
        "construction": "Optional local support series produced outside the FRED downloader for credit-union Treasury coupon-interest correction.",
    }
    metadata["correction_inputs"]["fed_tier1_component_extension_proxy"] = {
        "series_key": "fed_tier1_component_extension_proxy",
        "raw_filename": "support__fed_tier1_component_extension_proxy.csv",
        "aggregation": "quarterly sum",
        "units": "Millions of U.S. dollars",
        "usage": "Nondefault Fed-extension component-anchored rows subtract this support series in addition to the existing Fed coupon Tier 1 correction.",
        "construction": "Exported from support__fed_treasury_interest_components.csv as exact SOMA bill-discount plus FRN interest. TIPS inflation compensation remains excluded, and the separate TIPS coupon diagnostic is not added to avoid double-counting coupon-like SOMA payments.",
    }
    for key, raw_filename, usage in [
        (
            "bank_tsy_bill_discount_interest_proxy",
            "support__bank_tsy_bill_discount_interest_proxy.csv",
            "Bill-discount robustness rows subtract this proxy from the default bank-sector block.",
        ),
        (
            "row_tsy_bill_discount_interest_proxy",
            "support__row_tsy_bill_discount_interest_proxy.csv",
            "Bill-discount robustness rows subtract this proxy when the ROW Treasury term is included.",
        ),
        (
            "credit_union_tsy_bill_discount_interest_proxy",
            "support__credit_union_tsy_bill_discount_interest_proxy.csv",
            "DI bill-discount robustness rows subtract this proxy when natural-person credit unions are included.",
        ),
    ]:
        metadata["correction_inputs"][key] = {
            "series_key": key,
            "raw_filename": raw_filename,
            "aggregation": "quarterly sum",
            "units": "Millions of U.S. dollars",
            "usage": usage,
            "construction": "Optional WAMEST-backed robustness proxy using sector bill shares, sector Treasury levels, Treasury bill WAM support, and interpolated Treasury bill-rate curve points.",
        }
    for key, raw_filename, usage in [
        (
            "bank_tier2_component_interest_proxy",
            "support__bank_tier2_component_interest_proxy.csv",
            "Parallel component-anchored Tier 2 rows subtract this staged bank-sector official-pool allocation.",
        ),
        (
            "row_tier2_component_interest_proxy",
            "support__row_tier2_component_interest_proxy.csv",
            "Parallel component-anchored Tier 2 ROW-inclusive rows subtract this staged rest-of-world official-pool allocation.",
        ),
        (
            "credit_union_tier2_component_interest_proxy",
            "support__credit_union_tier2_component_interest_proxy.csv",
            "Parallel component-anchored depository-institution Tier 2 rows subtract this staged credit-union official-pool allocation.",
        ),
    ]:
        metadata["correction_inputs"][key] = {
            "series_key": key,
            "raw_filename": raw_filename,
            "aggregation": "quarterly sum",
            "units": "Millions of U.S. dollars",
            "usage": usage,
            "construction": "Exported from tier2_interest_component_candidate.csv. Values allocate official Treasury coupon-accrual, bill-discount, and FRN interest pools using source-constrained sector weights; the files are staged promotion inputs and do not overwrite the live coupon proxy supports.",
        }
    metadata["correction_inputs"]["mmf_fund_month_rrp_adjustment"] = {
        "series_key": "mmf_rrp_adjustment_prop",
        "raw_filename": "support__mmf_fund_month.csv",
        "aggregation": "monthly fund-level allocation, then quarterly sum",
        "units": "Millions of U.S. dollars",
        "usage": "Candidate Tier 2 MMF/RRP rows add the lower, proportional, or upper adjustment to the selected Tier 2 base.",
        "construction": "Fund-month Fed RRP runoff is allocated across Treasury increases, other asset increases, and NAV declines.",
    }
    return estimates, components, corrections, metadata
