# Credit-union treatment

This repo makes credit-union treatment explicit because the right inclusion rule depends on the **deposit concept** being estimated.

## Headline policy

### Bank-only headline

Use:

- `tdc_base_bank_only_ru_flow`

This excludes all credit-union Treasury transactions.

### Broad-depository headline

Use:

- `tdc_base_broad_depository_np_cu_ru_flow`

This adds natural-person credit-union Treasury transactions.

## Sensitivities

- `tdc_broad_depository_np_corp_cu_ru_flow`
- `tdc_credit_union_aggregate_sensitivity`

The aggregate-CU sensitivity includes the NCUA capitalization deposit term so users can compare the clean broad-depository concept against the broad published aggregate credit-union Treasury concept.

## Why this matters

A public TDC repo should not silently assume that:

1. every credit-union Treasury purchase maps one-for-one into the deposit concept on the left-hand side, or
2. the aggregate published credit-union Treasury series is a clean pure marketable-Treasury concept.

The repo therefore publishes the credit-union choice as a visible modeling decision rather than burying it in a hidden sector mapping.
