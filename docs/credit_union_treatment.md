# Credit Union Treatment

The main TDC series (`tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` in `data/processed/tdc_tier2_regression_series.csv`) covers the Federal Reserve, banks (US-chartered depository institutions, US offices of foreign banks, and banks in US territories), and foreign holders. It excludes credit unions. Credit-union Treasury transactions and interest appear in comparison columns.

## Z.1 credit-union series

In the Federal Reserve's Financial Accounts (Z.1), aggregate credit-union Treasury transactions (`BOGZ1FU473061105Q`, optional) equal the sum of three required lines up to rounding (`credit_unions_total_gap_tx` in `data/processed/tdc_components.csv`):

- `np_credit_unions_tsy_tx` (`BOGZ1FU473061103Q`): natural-person credit union Treasury transactions, whose member shares sit alongside bank deposits.
- `corp_credit_unions_tsy_tx` (`BOGZ1FU473061153Q`): corporate credit union Treasury transactions; corporate credit unions serve natural-person credit unions.
- `ncua_capitalization_deposit_tx` (`BOGZ1FU473061203Q`): NCUA share insurance capitalization deposit transactions, an insurance fund deposit separate from marketable Treasury purchases.

## Comparison columns (USD millions per quarter)

- `data/processed/tdc_tier2_regression_series.csv`: `tdc_tier2_regression_mmf_rrp_prop_depository_institution_np_cu_ru_flow` adds natural-person credit union purchases and allocated interest (`credit_union_tier2_component_interest_proxy`); `tdc_tier2_regression_mmf_rrp_prop_broad_depository_np_cu_ru_flow` adds purchases only. Both have `lb` and `ub` money-fund counterparts.
- `data/processed/tdc_estimates.csv`: partial sums without interest or money-fund terms include `tdc_base_bank_only_ru_flow`, `tdc_base_broad_depository_np_cu_ru_flow` (plus natural-person credit unions), `tdc_broad_depository_np_corp_cu_ru_flow` (plus corporate credit unions), and `tdc_credit_union_aggregate_sensitivity` (full Z.1 credit-union aggregate including the NCUA deposit).

When comparing a series that includes natural-person credit unions against deposits, add NCUA Call Report shares (`data/raw/support__credit_union_deposits.csv`) to commercial-bank deposits so both sides cover the same depository group.
