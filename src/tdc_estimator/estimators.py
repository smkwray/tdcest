from __future__ import annotations

import pandas as pd

from .catalog import (
    BANK_DEPOSITORY_LEVEL_KEYS,
    BANK_DEPOSITORY_TX_KEYS,
    CU_COMPONENT_LEVEL_KEYS,
    CU_COMPONENT_TX_KEYS,
)


def _sum_columns(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    available = [col for col in cols if col in df.columns]
    if not available:
        return pd.Series(index=df.index, dtype="float64")
    return df[available].sum(axis=1, min_count=1)


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


def compute_estimates(quarterly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    tx_start = "2002-12-31"
    required = [
        "fed_tsy_tx",
        *BANK_DEPOSITORY_TX_KEYS,
        "row_tsy_tx",
        "treasury_operating_cash_tx",
    ]
    missing = [col for col in required if col not in quarterly.columns]
    if missing:
        raise ValueError(f"Missing required inputs for base estimator: {missing}")

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
    ].sum(axis=1, min_count=1)
    components["ru_broad_depository_np_cu_tsy_tx"] = components[
        ["fed_tsy_tx", "broad_depository_np_cu_tsy_tx", "row_tsy_tx"]
    ].sum(axis=1, min_count=1)
    components["ru_broad_depository_np_corp_cu_tsy_tx"] = components[
        ["fed_tsy_tx", "broad_depository_np_corp_cu_tsy_tx", "row_tsy_tx"]
    ].sum(axis=1, min_count=1)
    components["ru_broad_depository_full_cu_tsy_tx"] = components[
        ["fed_tsy_tx", "broad_depository_full_cu_tsy_tx", "row_tsy_tx"]
    ].sum(axis=1, min_count=1)
    components["minus_treasury_operating_cash_tx"] = -quarterly["treasury_operating_cash_tx"]

    if "fed_remit_or_deferred" in quarterly.columns:
        components["fed_remit_positive"] = quarterly["fed_remit_or_deferred"].fillna(0.0)
    else:
        components["fed_remit_positive"] = 0.0

    estimates = pd.DataFrame(index=quarterly.index)
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

    for key in [
        "tdc_base_bank_only_ru_flow",
        "tdc_base_broad_depository_np_cu_ru_flow",
        "tdc_broad_depository_np_corp_cu_ru_flow",
        "tdc_credit_union_aggregate_sensitivity",
        "tdc_domestic_bank_only_ru_flow",
        "tdc_no_remit_bank_only",
    ]:
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
            + components["fed_remit_positive"]
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
            + components["fed_remit_positive"]
        )

    if _has_all(quarterly, ["m2", "currency", "bank_credit", *BANK_DEPOSITORY_LEVEL_KEYS]):
        bank_non_tsy = quarterly["bank_credit"] - _sum_columns(quarterly, BANK_DEPOSITORY_LEVEL_KEYS)
        estimates["tdc_decomposition_proxy_bank_centric"] = (
            quarterly["m2"].diff()
            - quarterly["currency"].diff()
            - bank_non_tsy.diff()
        )

    historical_start = "1990-03-31"
    if "tdc_level_bank_only_sensitivity" in estimates.columns:
        estimates["tdc_bank_only_extended_1990"] = estimates["tdc_base_bank_only_ru_flow"].combine_first(
            _from_date(estimates["tdc_level_bank_only_sensitivity"], historical_start)
        )

    if "tdc_level_broad_depository_np_cu_sensitivity" in estimates.columns:
        estimates["tdc_broad_depository_extended_1990"] = estimates[
            "tdc_base_broad_depository_np_cu_ru_flow"
        ].combine_first(_from_date(estimates["tdc_level_broad_depository_np_cu_sensitivity"], historical_start))

    estimates["tdc_base_bank_only_ru_flow_4q"] = estimates["tdc_base_bank_only_ru_flow"].rolling(4).sum()
    estimates["tdc_base_bank_only_ru_flow_cum"] = estimates["tdc_base_bank_only_ru_flow"].cumsum()

    components["tdc_base_bank_only_ru_flow"] = estimates["tdc_base_bank_only_ru_flow"]
    components["tdc_base_broad_depository_np_cu_ru_flow"] = estimates[
        "tdc_base_broad_depository_np_cu_ru_flow"
    ]

    metadata = {
        "preferred_method": "tdc_base_bank_only_ru_flow",
        "preferred_methods_by_deposit_concept": {
            "bank_only": "tdc_base_bank_only_ru_flow",
            "broad_depository": "tdc_base_broad_depository_np_cu_ru_flow",
        },
        "available_methods": list(estimates.columns),
        "notes": [
            "The default headline is a bank-only transaction-based estimator beginning in late 2002.",
            "A broad-depository alternative adds natural-person credit-union Treasury transactions and uses the same transaction-era coverage.",
            "Corporate credit unions are included only as an additional sensitivity layer.",
            "The aggregate credit-union sensitivity also includes the NCUA capitalization deposit, which is part of the published aggregate credit-union Treasury series in Z.1.",
            "Negative H.4.1 remittance values are clipped to zero before quarter aggregation, and missing pre-history is treated as zero rather than suppressing older estimates.",
            "Separate historical-extension series splice in the level-change analog from 1990 until transaction coverage begins.",
            "Level and decomposition methods are sensitivity checks only.",
        ],
        "method_descriptions": {
            "tdc_base_bank_only_ru_flow": "Preferred headline. Fed + bank-sector + rest-of-world Treasury transactions minus Treasury operating cash transactions plus positive Fed remittances. Transaction-data era only.",
            "tdc_base_broad_depository_np_cu_ru_flow": "Broad-depository alternative that adds natural-person credit-union Treasury transactions. Transaction-data era only.",
            "tdc_broad_depository_np_corp_cu_ru_flow": "Sensitivity that also adds corporate credit-union Treasury transactions.",
            "tdc_credit_union_aggregate_sensitivity": "Sensitivity that matches the aggregate credit-union Treasury concept by adding natural-person and corporate credit-union Treasury transactions plus the NCUA capitalization deposit term.",
            "tdc_domestic_bank_only_ru_flow": "Bank-only headline excluding the rest-of-world term.",
            "tdc_no_remit_bank_only": "Bank-only headline excluding Fed remittances.",
            "tdc_bank_only_extended_1990": "Historical extension that uses the bank-only transaction headline where available and the bank-only level-change analog from 1990 until transaction coverage begins.",
            "tdc_broad_depository_extended_1990": "Historical extension that uses the broad-depository transaction series where available and the broad-depository level-change analog from 1990 until transaction coverage begins.",
            "tdc_level_bank_only_sensitivity": "Level-change version of the bank-only estimator.",
            "tdc_level_broad_depository_np_cu_sensitivity": "Level-change broad-depository sensitivity with natural-person credit unions.",
            "tdc_decomposition_proxy_bank_centric": "Rough money/bank-balance-sheet proxy. Included for diagnostics only.",
        },
        "method_formulas": {
            "tdc_base_bank_only_ru_flow": "Bank-only headline = Federal Reserve Treasury transactions + Bank-sector Treasury transactions + Rest-of-world Treasury transactions - Treasury operating cash transactions + Positive Federal Reserve remittances.",
            "tdc_base_broad_depository_np_cu_ru_flow": "Broad-depository headline = Bank-only headline + Natural-person credit-union Treasury transactions.",
            "tdc_broad_depository_np_corp_cu_ru_flow": "Broad-depository plus corporate credit unions = Broad-depository headline + Corporate credit-union Treasury transactions.",
            "tdc_credit_union_aggregate_sensitivity": "Aggregate credit-union sensitivity = Broad-depository plus corporate credit unions + NCUA capitalization deposit term.",
            "tdc_domestic_bank_only_ru_flow": "Domestic-only bank headline = Federal Reserve Treasury transactions + Bank-sector Treasury transactions - Treasury operating cash transactions + Positive Federal Reserve remittances.",
            "tdc_no_remit_bank_only": "Bank-only excluding remittances = Federal Reserve Treasury transactions + Bank-sector Treasury transactions + Rest-of-world Treasury transactions - Treasury operating cash transactions.",
            "tdc_bank_only_extended_1990": "Bank-only extended series = Bank-only headline when available; otherwise Bank-only level-change sensitivity.",
            "tdc_broad_depository_extended_1990": "Broad-depository extended series = Broad-depository headline when available; otherwise Broad-depository level-change sensitivity.",
            "tdc_level_bank_only_sensitivity": "Bank-only level-change sensitivity = Change in Federal Reserve Treasury holdings + Change in Bank-sector Treasury holdings + Change in Rest-of-world Treasury holdings - Change in Treasury operating cash + Positive Federal Reserve remittances.",
            "tdc_level_broad_depository_np_cu_sensitivity": "Broad-depository level-change sensitivity = Bank-only level-change sensitivity + Change in natural-person credit-union Treasury holdings.",
            "tdc_decomposition_proxy_bank_centric": "Bank-centric decomposition proxy = Change in M2 - Change in currency - Change in non-Treasury bank assets.",
            "tdc_base_bank_only_ru_flow_4q": "Bank-only headline, four-quarter sum = Rolling four-quarter sum of the bank-only headline.",
            "tdc_base_bank_only_ru_flow_cum": "Bank-only headline, cumulative = Cumulative sum of the bank-only headline.",
        },
        "credit_union_policy": {
            "default": "exclude_all_credit_unions_from_bank_only_headline",
            "broad_depository_headline": "include_natural_person_credit_unions_only",
            "corporate_credit_unions": "sensitivity_only",
            "ncua_capitalization_deposit": "aggregate_credit_union_sensitivity_only",
        },
        "historical_backfill": {
            "pre_transaction_history": "level_change_backfill",
            "historical_extension_starts": historical_start,
            "transaction_history_starts": tx_start,
        },
    }
    return estimates, components, metadata
