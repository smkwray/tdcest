# Data Sources

`tdcest` builds TDC and its reserve-side counterpart (TRC) from public Federal Reserve, US Treasury, SEC, OFR, NCUA, FDIC, IRS, and State Department data. Series definitions live in `src/tdc_estimator/catalog.py`.

## Required FRED series

Running `tdc download` fetches ten required series (`BASE_FRED_SERIES` in `catalog.py`) into `data/raw/fred__<key>.csv`. The Z.1 series are quarterly unadjusted transactions in USD millions; the H.4.1 remittance series is a weekly Wednesday level in USD millions clipped at zero (`clip_positive`) before summing to quarters so negative deferred-asset balances do not enter as negative remittances.

| Key | FRED ID | Role | Aggregation |
|---|---|---|---|
| `fed_tsy_tx` | `BOGZ1FU713061103Q` | Federal Reserve Treasury security transactions | `sum` |
| `us_chartered_tsy_tx` | `BOGZ1FU763061100Q` | US-chartered depository institution Treasury transactions | `sum` |
| `foreign_offices_tsy_tx` | `BOGZ1FU753061103Q` | Foreign banking offices in the US Treasury transactions | `sum` |
| `affiliated_areas_tsy_tx` | `BOGZ1FU743061103Q` | Banks in US-affiliated areas Treasury transactions | `sum` |
| `np_credit_unions_tsy_tx` | `BOGZ1FU473061103Q` | Natural-person credit union Treasury transactions (comparison) | `sum` |
| `corp_credit_unions_tsy_tx` | `BOGZ1FU473061153Q` | Corporate credit union Treasury transactions (comparison) | `sum` |
| `ncua_capitalization_deposit_tx` | `BOGZ1FU473061203Q` | NCUA share insurance capitalization deposit (comparison) | `sum` |
| `row_tsy_tx` | `BOGZ1FU263061105Q` | Foreign (rest of the world) Treasury transactions | `sum` |
| `treasury_operating_cash_tx` | `BOGZ1FU313024000Q` | Federal government Treasury operating cash transactions | `sum` |
| `fed_remit_or_deferred` | `RESPPLLOPNWW` | H.4.1 Federal Reserve earnings remittances due to Treasury (`clip_positive`) | `sum` |

## Optional FRED series

`OPTIONAL_FRED_SERIES` in `catalog.py` adds reference and checking series when `--required-only` is not set:

- Z.1 deposit and Treasury holdings levels and transactions: US-chartered total deposits (`BOGZ1FL764100005Q`), checkable deposits (`BOGZ1FL763127005Q`), time and savings deposits (`BOGZ1FL763130005Q`), credit-union total Treasury transactions (`BOGZ1FU473061105Q`), sector Treasury holdings levels for banks, foreign holders, credit unions, money market funds, mutual funds, ETFs, insurers, pensions, households, nonfinancial businesses, and state and local governments.
- H.8 commercial bank balance-sheet series and money stock (`M2SL`, `CURRCIR`, `TOTBKCR`, published in USD billions and multiplied by `1000` inside `estimators.py`).
- Daily H.15 nominal Treasury constant-maturity yields (`DGS1MO` through `DGS30`) and daily ON RRP take-up (`RRPONTSYD`, USD billions).

In `src/tdc_estimator/io.py` and `utils.py`, quarterly resampling uses calendar quarter-end (`QE-DEC`): flow series aggregate by `sum` (`min_count=1`) and stock series by `last`.

By default `tdc download` fetches FRED CSVs from the public `fredgraph.csv` endpoint; setting `FRED_API_KEY` switches to the FRED JSON API. Download outcomes are logged in `data/raw/manifest_fred.json`. Missing a required series stops the build.

## Local support files

`tdc estimate` reads optional local support CSVs from `data/raw/support__<key>.csv` (`LOCAL_SUPPORT_SERIES` in `catalog.py`):

- Treasury–Federal Reserve internal transfers: `support__treasury_fed_internal_cash_tx.csv`, built by `tdc treasury-fed-transfer-export`. Required across the transaction era so internal equity transfers and credit-facility LLC nonmarketable Treasury transactions leave the Treasury operating-cash term.
- Treasury interest terms: `support__fed_tsy_coupon_interest_proxy.csv` (from NY Fed SOMA holdings via `tdc fed-coupon-support`, with pre-SOMA backcast from `wamest`), `support__bank_tier2_component_interest_proxy.csv`, `support__row_tier2_component_interest_proxy.csv`, and `support__credit_union_tier2_component_interest_proxy.csv` (exported from `tdc tier2-interest-component-candidate` using `wamest` weight tables; see `docs/wamest_interest_output_contract.md`), plus H.15 coupon and bill-discount comparison files and the SOMA extension check (`support__fed_tier1_component_extension_proxy.csv`).
- Money-market-fund ON RRP term: `support__mmf_fund_month.csv` built from SEC Form N-MFP bulk ZIPs via `tdc sec-nmfp-mmf-support`, optional OFR aggregate check `support__mmf_fund_month_ofr_aggregate.csv` via `tdc mmf-rrp-support`, and NY Fed GSE ON RRP check `support__gse_on_rrp.csv` via `tdc gse-on-rrp-support` (see `docs/mmf_rrp_adjustment.md`).
- Historical Federal Reserve remittances: `support__fed_remit_mts.csv` parsed from archived Monthly Treasury Statement PDFs (`tdc fed-remit-mts-support`) for 2002Q1–2002Q3 before `RESPPLLOPNWW` begins and for cross-checking Fiscal Data MTS receipts.
- Deposit, tax, and receipt-side comparison files: NCUA Call Report credit-union deposit bridge (`data/raw/ncua__credit_union_deposit_bridge.csv`, `support__credit_union_deposits.csv` via `scripts/build_ncua_credit_union_deposits.py`), FDIC savings-institution bridge (`data/raw/fdic__savings_institution_deposit_bridge.csv`, `support__thrift_deposits.csv` via `scripts/build_fdic_savings_institution_deposits.py`), IRS SOI bank corporate tax shares (`irs__soi_bank_tax_shares.csv`, `irs__soi_bank_minor_industry_availability.csv`), Treasury Combined Statement account rollups (`support__combined_statement_receipt_accounts.csv`), State Department monthly visa issuances (`state__visa_issuances_monthly.csv`), and non-interest outlay, receipt, and coin/currency support files.

## Treasury Fiscal Data API datasets

Running `tdc download --include-treasury-support` (or `scripts/build_all.py --include-treasury-support`) fetches six datasets (`TREASURY_DATASETS` in `catalog.py`) from `https://api.fiscaldata.treasury.gov/services/api/fiscal_service` into `data/raw/treasury__<key>.csv` and logs `data/raw/manifest_treasury.json`:

| Key | Endpoint | Output file |
|---|---|---|
| `dts_operating_cash` | `v1/accounting/dts/operating_cash_balance` | `data/raw/treasury__dts_operating_cash.csv` |
| `dts_deposits_withdrawals` | `v1/accounting/dts/deposits_withdrawals_operating_cash` | `data/raw/treasury__dts_deposits_withdrawals.csv` |
| `mts_receipts` | `v1/accounting/mts/mts_table_4` | `data/raw/treasury__mts_receipts.csv` |
| `mts_outlays` | `v1/accounting/mts/mts_table_5` | `data/raw/treasury__mts_outlays.csv` |
| `interest_expense` | `v2/accounting/od/interest_expense` | `data/raw/treasury__interest_expense.csv` |
| `receipts_by_department` | `v1/accounting/od/receipts_by_department` | `data/raw/treasury__receipts_by_department.csv` |

`treasury__interest_expense.csv` supplies the official marketable interest-expense pools (coupon accrual on notes, bonds, and TIPS; amortized bill discount; floating-rate note interest) used by `tdc tier2-interest-component-candidate` and `tdc bill-discount-validation`.

## Reserve-side and accounting input registries

Reserve-side and accounting exports acquire their inputs through `fiscus` using `scripts/acquire_trc_inputs.py --registry <name>`. The script strips `FRED_API_KEY` from the child environment so FRED pulls use the keyless public route, exports cached CSVs, verifies SHA-256 digests, and writes a registry manifest. Pass `--vintage` (`v1` closes `2025Q4` quarterly and `2025-12-31` weekly; `2026q2` closes `2026Q2` and `2026-09-30`) and `--root` to build into a separate data tree.

| Registry | Primary sources | Consuming export command |
|---|---|---|
| `trc` | Z.1 reserve balances (`BOGZ1FU713113003Q`), H.4.1 Wednesday TGA (`WDTGAL`), reserve balances (`WRBWFRBL`), RRP others (`WLRRAOL`), foreign-official deposits (`WDFOL`), custody Treasuries (`WMTSECL1`, zero before 2007Q4), DTS Table I operating cash, H.3 total reserves (`TOTRESNS`) | `tdc trc-export` |
| `h41-ledger` | H.4.1 Table 1 Wednesday levels from `2002-12-18` (`H41_TABLE1_ROWS`), plus term deposits (`TERMT`) and Z.1 reserve balances level (`BOGZ1FL713113003Q`) | `tdc reserve-factor-ledger-export` |
| `weekly-trc` | NY Fed SOMA weekly Treasury snapshots (`soma.treasury_holdings` via `config/fiscus_weekly_trc.yml`), Fiscal Data `auctions_query` and `frn_daily_indexes`, DTS Table II remittances and ESF economic-recovery lines, CPI-U (`CPIAUCNS`), daily ON RRP (`RRPONTSYD`) | `tdc weekly-trc-export` |
| `treasury-fed-transfers` | DTS Table III-A Domestic Series (`dts_public_debt_transactions`), MSPD Table 3 nonmarketable Domestic Series (`SPV Demand` and zero-coupon maturities), Z.1 credit-facility LLC Treasury holdings (`FL503069203.Q`), paired with `weekly-trc` DTS ESF cash and `h41-ledger` Treasury contributions (`WLTCFLL`) | `tdc treasury-fed-transfer-export` |
| `bank-composition` | Z.1 Table S.122.1 US-chartered bank transactions and levels plus H.8 Table 4 commercial-bank monthly levels | `tdc bank-composition-export` |
| `deficit` | MTS Table 1 summary (`mts_table_1`) | `tdc deficit-comparison-export` |
| `interest-rate-debt` | Fiscal Data `interest_expense` and MSPD Table 3 marketable debt (`Total Marketable` less `Federal Financing Bank`) | `tdc interest-rate-debt-export` |

## WAMEST inputs

When building interest terms from a sibling `wamest` checkout, `tdcest` reads:

- SOMA holdings: `data/external/normalized/soma_holdings_fed.csv` (see `src/tdc_estimator/fed_coupon.py`).
- Sector interest weights: `outputs/full_coverage_release/sector_interest_allocation_weights.csv` and `sector_component_bucket_weights.csv` (fallback paths and schema in `docs/wamest_interest_output_contract.md`).
- Fallback maturity, holdings, and curve files when weight tables are absent: `canonical_sector_maturity.csv`, `z1_series_auto_full.csv`, and `h15_curves_auto_nominal_treasury_constant_maturity.csv` (see `src/tdc_estimator/sector_coupon.py`).
