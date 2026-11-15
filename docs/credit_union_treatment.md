# Credit-union treatment

Whether credit unions belong in the estimate depends on the deposit concept being measured, so TDCest makes the choice explicit.

## Perimeters

| Row | Credit-union treatment | Role |
|---|---|---|
| `tdc_base_bank_only_ru_flow` | Excludes all credit-union Treasury transactions | Bank-only baseline (ladder input) |
| `tdc_base_broad_depository_np_cu_ru_flow` | Adds natural-person credit-union Treasury transactions | Broad-depository baseline (ladder input) |
| `tdc_broad_depository_np_corp_cu_ru_flow` | Also adds corporate credit-union Treasury transactions | Sensitivity |
| `tdc_credit_union_aggregate_sensitivity` | Also adds the NCUA share-insurance capitalization deposit | Sensitivity |

The aggregate sensitivity reproduces the published aggregate credit-union Treasury concept, so users can compare it with the clean broad-depository treatment.

At Tier 2, the depository-institution rows (`*_depository_institution_np_cu_*`) use the broad-depository perimeter and also subtract Treasury interest allocated to credit unions. The canonical Tier 2 row uses this perimeter.

## Why the choice is explicit

Two assumptions are avoided:

1. that every credit-union Treasury purchase maps one-for-one into the deposit concept being measured;
2. that the aggregate published credit-union Treasury series is a pure marketable-Treasury concept. It also contains the NCUA capitalization deposit.

Natural-person credit-union transactions, corporate credit-union transactions and the NCUA capitalization deposit are therefore kept as separate inputs.
