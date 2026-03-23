# Output schema

The `tdc site-export` command writes a static-site-ready bundle to `data/site/`.

## Files

### `bundle.json`

Single-file site payload including:

- `bundle_format`
- `generated_at_utc`
- `summary`
- `metadata`
- `estimates`
- `components`

## Bundle sections

### `summary`

Top-level summary including:

- `generated_at_utc`
- `latest_period`
- `latest_methods`
- `latest_base_components`
- `available_methods`
- `preferred_method`
- `preferred_methods_by_deposit_concept`
- `credit_union_policy`

### `metadata`

Series metadata and pipeline notes.

### `estimates`

Wide-format quarterly records with one row per date and one column per method.

### `components`

Quarterly component records for the estimator family.

## Column conventions

### Estimates

- `tdc_base_bank_only_ru_flow`
- `tdc_base_broad_depository_np_cu_ru_flow`
- `tdc_broad_depository_np_corp_cu_ru_flow`
- `tdc_credit_union_aggregate_sensitivity`
- `tdc_domestic_bank_only_ru_flow`
- `tdc_no_remit_bank_only`
- `tdc_level_bank_only_sensitivity`
- `tdc_level_broad_depository_np_cu_sensitivity`
- `tdc_decomposition_proxy_bank_centric`
- `tdc_base_bank_only_ru_flow_4q`
- `tdc_base_bank_only_ru_flow_cum`

### Components

- `fed_tsy_tx`
- `bank_depository_tsy_tx`
- `np_credit_unions_tsy_tx`
- `corp_credit_unions_tsy_tx`
- `ncua_capitalization_deposit_tx`
- `credit_unions_total_tsy_tx_reconstructed`
- `credit_unions_total_tsy_tx_direct` if downloaded
- `credit_unions_total_gap_tx` if the direct aggregate series was downloaded
- `broad_depository_np_cu_tsy_tx`
- `broad_depository_np_corp_cu_tsy_tx`
- `broad_depository_full_cu_tsy_tx`
- `row_tsy_tx`
- `ru_bank_only_tsy_tx`
- `ru_broad_depository_np_cu_tsy_tx`
- `ru_broad_depository_np_corp_cu_tsy_tx`
- `ru_broad_depository_full_cu_tsy_tx`
- `minus_treasury_operating_cash_tx`
- `fed_remit_positive`
- `tdc_base_bank_only_ru_flow`
- `tdc_base_broad_depository_np_cu_ru_flow`

## Intended front-end usage

The website should treat `tdc_base_bank_only_ru_flow` as the default selected method.

It should also expose a high-level deposit-concept choice:

- **Bank-only** → `tdc_base_bank_only_ru_flow`
- **Broad depository** → `tdc_base_broad_depository_np_cu_ru_flow`
