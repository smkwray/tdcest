# Output Schema

This document describes the CSV and JSON files written by `tdcest`.

## Conventions

- Location: outputs go to `data/processed/` unless stated otherwise. `tdc site-export` writes to `site/bundle.json` and `site/data/bundle.json`. `tdc treasury-fed-transfer-export` also writes `data/raw/support__treasury_fed_internal_cash_tx.csv`. `scripts/export_trc_monthly.py` writes to the directory passed via `--out-dir`.
- Units: USD millions, unless a section states USD billions (`bank_composition_*` and `interest_rate_debt_*`).
- Dates: `date` uses `YYYY-MM-DD` (quarter-end for quarterly tables, Wednesday date for weekly H.4.1 tables, month-end for monthly N-MFP tables, posting date for daily tables). `quarter` uses `YYYYQ#` and `month` uses `YYYY-MM`.
- Vintages: hash-pinned exports accept `--vintage v1` (quarterly sample through `2025Q4`, weekly through `2026-04-08`) or `--vintage 2026q2` (quarterly through `2026Q2`, weekly through `2026-09-30`).
- Receipts: hash-pinned exports write a companion `*_receipt.json` containing `schema_version`, `producer_commit`, `vintage`, input and output SHA-256 hashes, coverage bounds, and reconciliation checks.
- Code identifiers: some column and JSON key names retain legacy strings (`tier1`, `tier2`, `tier3`, `ru_flow`, `canonical`, `preferred`, `variant`, `perimeter`) for compatibility with downstream readers.

## Main TDC Outputs

### `tdc_tier2_regression_series.csv` (and `.md`)

Written by `tdc tier2-regression-series`. Quarterly Treasury Deposit Component (TDC) series from `2002Q1` onward, in USD millions.

The main TDC series is `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow`: net Treasury purchases by the Federal Reserve, banks (US-chartered depository institutions, US offices of foreign banks, banks in US territories), and foreign holders, minus Treasury interest paid to those holders, plus Federal Reserve remittances, minus the increase in Treasury operating cash (excluding Treasury–Federal Reserve internal transfers), plus Treasury purchases money market funds pay for out of the Overnight Reverse Repurchase Agreement (ON RRP) facility (proportional allocation from `2013Q3` onward; `0.0` before `2013-09-30`).

| Column | Meaning |
| --- | --- |
| `date` | Quarter-end date (`YYYY-MM-DD`). |
| `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` | Main TDC series (banks exclude credit unions; proportional money-fund ON RRP term). |
| `tdc_tier2_regression_mmf_rrp_lb_bank_only_ru_flow`, `tdc_tier2_regression_mmf_rrp_ub_bank_only_ru_flow` | Same calculation using the lower-bound and upper-bound money-fund ON RRP terms. |
| `tdc_tier2_regression_mmf_rrp_{lb,prop,ub}_broad_depository_np_cu_ru_flow` | Comparison calculation adding natural-person credit union Treasury purchases alongside banks (without separate credit-union interest subtraction). |
| `tdc_tier2_regression_mmf_rrp_{lb,prop,ub}_depository_institution_np_cu_ru_flow` | Comparison calculation including natural-person credit union Treasury purchases and subtracting credit-union Treasury interest. |
| `tdc_tier2_regression_{bank_only,domestic_bank_only,broad_depository_np_cu,depository_institution_np_cu}_ru_flow` | Partial sums before adding the money-fund ON RRP term (`domestic_bank_only` omits foreign holders). |
| `tdc_base_bank_only_ru_flow`, `tdc_base_broad_depository_np_cu_ru_flow`, `tdc_domestic_bank_only_ru_flow` | Partial sums before subtracting Treasury interest or adding the money-fund ON RRP term. |
| `fed_tsy_coupon_interest_proxy` | Federal Reserve Treasury coupon interest term. |
| `{bank,row,credit_union,bank_row,di}_tier2_regression_interest_proxy` | Sector Treasury interest terms (`bank_row` sums bank and foreign; `di` sums bank, foreign, and credit union). |
| `mmf_rrp_adjustment_{lb,prop,ub}` | Money-fund ON RRP term (lower bound, proportional, upper bound; `0.0` before `2013-09-30`). |
| `{bank,row,credit_union}_method_tier`, `tier2_regression_bank_row_method_tier`, `tier2_regression_di_method_tier` | Interest estimation source label per quarter (`component_anchored` from `2010Q2` onward; `h15_scale_bridged` through `2010Q1`). |

### `tdc_regression_legs_v1.csv` (and `tdc_regression_legs_v1_receipt.json`)

Written by `tdc regression-leg-export`. Quarterly decomposition of the main TDC series $C$ over `2002Q1` through `vintage.quarter_end` into three additive legs, $C = R + O + J$:

- $R$: foreign Treasury purchases minus foreign Treasury interest (`row_tsy_tx - row_tier2_regression_interest_proxy`).
- $O$: operating-cash leg excluding Treasury–Federal Reserve internal transfers (`-(treasury_operating_cash_tx - treasury_fed_internal_cash_tx)`).
- $J$: remaining domestic bank, Federal Reserve, remittance, and money-fund terms (`C - R - O`), checked against the expanded sum `J_expanded`.

| Column group | Columns |
| --- | --- |
| Identifier | `quarter`, `date` |
| Z.1 and remittance inputs | `fed_tsy_tx`, `us_chartered_di_tsy_tx`, `foreign_banking_offices_tsy_tx`, `banks_us_territories_tsy_tx`, `row_tsy_tx`, `treasury_operating_cash_tx`, `treasury_fed_internal_cash_tx`, `fed_remit_or_deferred`, `fed_remit_positive` |
| Interest and money-fund inputs | `fed_tsy_coupon_interest_proxy`, `bank_tier2_regression_interest_proxy`, `row_tier2_regression_interest_proxy`, `mmf_rrp_adjustment_prop`, `effective_mmf_rrp_adjustment_prop` |
| Main series and legs | `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow`, `C`, `R`, `O`, `J`, `J_expanded` |
| Checks and provenance | `R_reconstruction_gap`, `J_reconstruction_gap`, `C_adding_up_gap`, `any_input_missing`, `mmf_rrp_raw_missing`, `quarterly_source_sha256`, `regression_source_sha256` |

### `tier2_regression_interest_backcast.csv` and `tier2_regression_interest_backcast_wide.csv` (and `.md`)

Written by `tdc tier2-regression-backcast`. Quarterly Treasury interest series for `bank`, `row`, and `credit_union` combining component-allocated official pools (`2010Q2` onward) with scale-bridged H.15 yield estimates (through `2010Q1`).

- Long table (`tier2_regression_interest_backcast.csv`): `date`, `sector`, `interest_proxy_mil`, `method_tier`, `method_grade`, `source_observability_tiers`, `source_families`, `denominator_observability_tiers`, `component_interest_mil`, `h15_interest_mil`, `component_minus_h15_mil`, `overlap_ratio_component_to_h15`, `overlap_ratio_count`, `overlap_scale_factor`.
- Wide table (`tier2_regression_interest_backcast_wide.csv`): `date`, `{sector}_tier2_regression_interest_proxy`, `{sector}_method_tier`, `{sector}_method_grade`, `{sector}_source_observability_tiers`, `{sector}_source_families`, `{sector}_denominator_observability_tiers` for each of `bank`, `row`, and `credit_union`, plus `bank_row_tier2_regression_interest_proxy` and `di_tier2_regression_interest_proxy`.

## Core Quarterly Pipeline Tables

Written by `tdc estimate` (or `tdc build`).

### `quarterly_inputs.csv`

Merged quarterly input series indexed by `date`. Contains Z.1 transactions (`*_tx`) and levels (`*_level`), Federal Reserve remittances (`fed_remit_or_deferred`, replaced by `fed_remit_mts` when `data/raw/support__fed_remit_mts.csv` is present), optional support inputs (interest proxies, internal transfers, GSE ON RRP, fiscal proxies), and derived quarterly money-fund ON RRP columns (`mmf_rrp_adjustment_{lb,prop,ub}`, `mmf_rrp_bills_adjustment_{lb,prop,ub}`).

### `tdc_estimates.csv`

Wide quarterly table of partial sums and comparison calculations kept for checking. Columns appear only when their required inputs are present.

| Column family | Meaning |
| --- | --- |
| `tdc_base_bank_only_ru_flow`, `tdc_base_broad_depository_np_cu_ru_flow`, `tdc_domestic_bank_only_ru_flow`, `tdc_no_remit_bank_only` | Partial sums before interest and money-fund terms (`no_remit` omits remittances; `domestic_bank_only` omits foreign holders). |
| `tdc_tier1_fed_corrected_{bank_only,broad_depository_np_cu,domestic_bank_only}_ru_flow` | Partial sums subtracting Federal Reserve Treasury coupon interest only. |
| `tdc_tier2_interest_corrected_*`, `tdc_tier2_h15_*`, `tdc_tier2_component_anchored_*`, `tdc_tier2_mmf_rrp_*`, `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow` | Interest- and money-fund-included comparison calculations using H.15 coupon estimates, bill-discount additions, component-allocated pools, Federal Reserve bill/FRN extensions, and credit-union or bills-only money-fund variations. |
| `tdc_tier3_fiscal_corrected_*`, `tdc_du_fiscal_flow_first_pass_{narrow,broad}`, `tdc_du_residual_proxy_{bank_only,np_cu,np_corp_cu,full_cu}_ru` | Direct fiscal-flow and residual comparison calculations built from Monthly Treasury Statement (MTS) outlays, receipts, and optional sector proxies. |
| `tdc_level_{bank_only,broad_depository_np_cu}_sensitivity`, `tdc_decomposition_proxy_bank_centric`, `tdc_{bank_only,broad_depository}_extended_1990` | Level-change, decomposition, and pre-2002 extended comparison checks. |
| `tdc_base_bank_only_ru_flow_4q`, `tdc_base_bank_only_ru_flow_cum` | Four-quarter rolling sum and cumulative sum of `tdc_base_bank_only_ru_flow`. |

### `tdc_components.csv`, `tdc_corrections.csv`, and `method_meta.json`

- `tdc_components.csv`: quarterly input terms entering the sums in `tdc_estimates.csv`, plus residual fiscal-flow terms (`du_residual_*`, `du_noninterest_outlay_proxy`, `du_receipt_proxy`, `du_coupon_proxy_*`).
- `tdc_corrections.csv`: signed differences between partial sums and interest-, money-fund-, or fiscal-adjusted comparison columns (for example `tier1_fed_coupon_correction`, `tier2_{bank,row,credit_union}_component_interest_correction`, `tier2_mmf_rrp_{lb,prop,ub}_adjustment`, and pairwise `*_delta_from_*` columns).
- `method_meta.json`: machine-readable column inventory with keys `preferred_method`, `canonical_tier2_method`, `canonical_tier2_status`, `available_methods`, `estimator_ladder`, `ladder_inputs_by_deposit_concept`, `correction_series`, `method_descriptions`, `method_formulas`, and `notes`.

## Treasury–Federal Reserve Internal Transfers

Written by `tdc treasury-fed-transfer-export` in USD millions (effect on Treasury operating cash: negative when equity leaves Treasury cash or an LLC redeems Domestic Series securities; positive when equity returns or an LLC purchases).

- `treasury_fed_transfers_postings_v1.csv`: dated Daily Treasury Statement (DTS) postings matched against H.4.1 Treasury contributions to credit facilities and Monthly Statement of the Public Debt (MSPD) Domestic Series records. Columns: `date`, `family`, `source`, `dts_line`, `amount`, `cash_effect`, `match_wednesday`, `classification`, `equity_principal_cash`, `equity_reduced_without_cash`, `documented_fed_cash`, `documented_retained_cash`, `internal_cash_effect`, `retained_cash_effect`, `settlement_status`, `quarter`, `week_ending`.
- `treasury_fed_transfers_quarterly_v1.csv`: calendar-quarter sums reconciled to Z.1 LLC Treasury holdings. Columns: `quarter`, `date`, `facility_internal_cash_tx`, `llc_treasury_securities_cash_tx`, `llc_capitalized_interest_memo`, `other_domestic_series_cash_tx`, `n_internal_postings`, `esf_cash_tx`, `esf_retained_cash_tx`, `esf_retained_abs`, `facility_receipt_retained_tx`, `esf_unclassified_cash_tx`, `esf_retained_dates`, `internal_cash_tx`, `equity_basis`, `llc_basis`, `z1_llc_treasury_level`, `dts_llc_treasury_level`, `reconciliation_gap`, `reconciliation_tolerance`, `reconciliation_status`.
- `treasury_fed_transfers_weekly_v1.csv`: Thursday-through-Wednesday sums on the H.4.1 weekly calendar. Columns: `date`, `start_wednesday`, `facility_internal_cash_tx`, `llc_treasury_securities_cash_tx`, `llc_capitalized_interest_memo`, `other_domestic_series_cash_tx`, `n_internal_postings`, `esf_cash_tx`, `esf_retained_cash_tx`, `esf_retained_abs`, `facility_receipt_retained_tx`, `esf_unclassified_cash_tx`, `esf_retained_dates`, `internal_cash_tx`, `equity_basis`, `llc_basis`.
- `data/raw/support__treasury_fed_internal_cash_tx.csv`: two-column support file (`date`, `value` = `internal_cash_tx`) read by `tdc estimate` and `tdc regression-leg-export`.
- `treasury_fed_transfers_v1_receipt.json`: receipt with matched posting details and Z.1 reconciliation bounds.

## Reserve-Side Outputs

### Quarterly TRC (`tdc trc-export`)

Exports the Treasury Reserve Component (TRC) and its reconciliation with TDC over `2002Q1` through `vintage.quarter_end`, in USD millions.

- `trc_quarterly_components_v1.csv`: wide quarterly table with one record per quarter.

| Column group | Columns |
| --- | --- |
| Treasury cash and internal transfers | `quarter`, `tga_level`, `tga_source_key`, `tga_clock`, `delta_tga`, `sfp_level`, `sfp_status`, `delta_sfp`, `ttl_level`, `ttl_status`, `delta_ttl`, `ttl_change_status`, `treasury_fed_internal_cash_tx`, `trc_cash_leg`, `cash_leg_status` |
| Federal Reserve and money-fund terms | `fed_tsy_tx`, `fed_remit_positive`, `fed_tsy_coupon_interest_proxy`, `trc_fed_bridge`, `mmf_route_raw_missing`, `mmf_route_status`, `mmf_route_{lb,prop,ub}` |
| TRC totals and reserve residual | `trc_core`, `trc_preferred`, `trc_mmf_lower`, `trc_mmf_upper`, `trc_status`, `trc_clock`, `delta_rb_z1`, `nontreasury_residual`, `nontreasury_residual_lower`, `nontreasury_residual_upper`, `residual_status` |
| TDC–TRC wedge | `tdc_canonical`, `wedge_measured`, `wedge_bank_leg`, `wedge_row_leg`, `wedge_ttl_leg`, `wedge_ttl_plus_residual`, `wedge_residual_u`, `z1_treasury_operating_cash_tx`, `cash_partition_gap`, `wedge_status`, `wedge_residual_status`, `z1_sfp_tx` |
| Additional bounds and diagnostics | `gse_route_{lower,upper,status}`, `delta_custody`, `delta_fo_cash`, `fo_route_{lower,upper,status}`, `trc_route_bounded_{lower,upper}`, `delta_rrp_others_h41`, `remainder_on_rrp_{lower,central,upper}`, `remainder_foreign_official_{lower,central,upper}`, `remainder_status`, `remainder_fo_status`, `delta_rb_h41`, `memo_reserves_plus_rrp_others`, `memo_h3_total_reserves_change`, `h3_status`, `delta_tga_h41`, `delta_sfp_h41_date`, `diag_trc_h41_{preferred,lower,upper}`, `h41_status`, `memo_us_chartered_reserves_z1` |

- `trc_quarterly_series_v1.csv`: long-format table of 25 named `series_id` series (`z1_reserve_change`, `trc_leg_treasury_fed_deposits`, `trc_leg_fed_treasury_bridge`, `route_adj_mmf_on_rrp`, `trc_core`, `trc_preferred`, `trc_core_mmf_lower`, `trc_core_mmf_upper`, `nontreasury_residual`, `tdc_canonical`, `tdc_trc_wedge`, `wedge_{bank,row,ttl}_leg`, `wedge_residual_u`, `route_bound_{gse_on_rrp,foreign_official}`, `trc_route_bounded_nondefault`, `remainder_{on_rrp,foreign_official}`, `memo_{reserves_plus_rrp_others,h3_total_reserves,us_chartered_reserves}`, `diag_h41_reserve_change`, `diag_trc_h41_tga`). Columns: `quarter`, `object`, `perimeter`, `series_id`, `value_lower`, `value_central`, `value_upper`, `units`, `clock`, `source_id`, `source_hash`, `route_coverage`, `measurement_status`, `default_eligible`, `legacy_artifact_hash_set`.
- `trc_route_registry_v1.csv`: settlement-route definitions shared by TDC and TRC. Columns: `route_id`, `holder_sector`, `settlement_claim`, `fed_account`, `tdc_incidence`, `trc_incidence`, `direction_policy`, `evidence_tier`, `default_eligible`, `coverage_start`, `coverage_end`, `status`, `treasury_account`.
- `trc_quarterly_series_v1_receipt.json`: receipt with hashes and cross-check statistics.

### H.4.1 Reserve-Factor Ledger and Bridges (`tdc reserve-factor-ledger-export`)

Exports signed Federal Reserve H.4.1 reserve-factor flows and exact bridges to quarterly TRC, in USD millions.

- `reserve_factor_ledger_weekly_v1.csv`: Wednesday-level H.4.1 factor changes. Columns: `date`, `quarter`, `reserve_balances`, `delta_reserve_balances`, `c_h`, `s_h`, `f_<factor>` (signed weekly change for each H.4.1 factor), `memo_f_<memo>`, `rho` (change rounding residual), `rho_level` (level rounding residual), `level_bound`, `change_bound`, `gap_<check>`, `published_identity_gap`, `structural_zero_rows`, `ledger_status`.
- `reserve_factor_ledger_quarterly_v1.csv`: last-Wednesday-to-last-Wednesday quarterly ledger telescoping from the weekly table. Columns: `quarter`, `start_wednesday`, `end_wednesday`, `n_weeks`, `reserve_balances_start`, `reserve_balances_end`, `delta_reserve_balances`, `c_h`, `s_h`, `f_<factor>`, `memo_f_<memo>`, `rho`, `change_bound`, `structural_zero_rows`, `ledger_status`.
- `reserve_factor_bridges_quarterly_v1.csv`: exact reconciliation of Z.1 reserve change `y_z` against each TRC series `x` (`trc_variant` in `trc_core`, `trc_preferred`, `trc_mmf_lower`, `trc_mmf_upper`), where `gap = y_z - x` equals `identity_rhs = sum_other_factors + n_rrp_others + bridge_outcome + bridge_cash + bridge_internal_transfers + bridge_securities + rho`. Columns: `quarter`, `trc_variant`, `x`, `gamma`, `y_z`, `y_h`, `c_h`, `c_m`, `c_m_clock`, `i`, `s_h`, `b`, `f_reverse_repos_others`, `f_<other_factor>`, `sum_other_factors`, `bridge_outcome`, `bridge_outcome_term_deposits`, `bridge_outcome_z1_flow_vs_level`, `bridge_outcome_unattributed`, `bridge_internal_transfers`, `bridge_cash`, `bridge_securities`, `rho`, `memo_s_h_inflation_compensation`, `n_rrp_others`, `gap`, `identity_rhs`, `identity_error`, `bridge_status`.
- `reserve_factor_ledger_v1_receipt.json`: receipt with closure bounds and era summaries.

### Weekly TRC (`tdc weekly-trc-export`)

Exports cash-corrected weekly TRC on the H.4.1 Wednesday clock, in USD millions.

- `trc_weekly_components_v1.csv`: weekly components and scenarios (`date`, `quarter`, `start_wednesday`, `c_h`, `bridge_all_securities_premium_discount`, `fed_leg_par`, `fed_leg_cash_corrected`, `settlement_clock_adjustment`, `primary_cash_adjustment`, `redemption_inflation`, `primary_cash_unavailable_par`, `redemption_cash_unavailable_par`, `cash_correction_status`, internal-transfer columns `j_*`, `soma_coupon_cash`, `cash_remittances`, `soma_inflation_compensation_change_excluded`, `secondary_purchases_par`, `secondary_sales_par`, `redemptions_par`, `primary_addons_par`, `unclassifiable_changes`, `unclassifiable_abs_par`, `unpriced_secondary_net_par`, `trc_core`, `trc_par_sensitivity`, `route_baseline`, `route_forward`, `route_reverse`, `net_bill_on_rrp_overlap`, `trc_forward_scenario`, `trc_reverse_scenario`, `rrp_others_vs_on_rrp_flow_bridge`, `core_status`, `coupon_status`, `remittance_status`, `soma_status`, `route_status`, `reserve_balances_start`, `reserve_balances_end`, `delta_reserve_balances`, `matched_rollover_par_memo`).
- `trc_weekly_quarterly_v1.csv`: full Wednesday-quarter sums of the weekly columns, `clock_status`, `quarter_status`, `unavailable_reasons`, `reserve_telescoping_error`, and term-by-term differences against `trc_quarterly_components_v1.csv`.
- `trc_weekly_identity_v1.csv`: exact decimal weekly reserve identity for `variant` in `core`, `forward_scenario`, `reverse_scenario` (`date`, `variant`, `delta_reserve_balances`, `trc`, `route`, `non_treasury_signed_factors`, `rrp_others_net_route`, `bridge_*`, `identity_rhs`, `identity_error`, `identity_status`).
- `trc_weekly_soma_changes_v1.csv`: CUSIP-level weekly SOMA par and cash event partition (`date`, `cusip`, `security_type`, `nominal_maturity_date`, `payment_date`, `issue_settlement_dates`, `opening_par`, `closing_par`, `delta_par`, `settlement_clock_adjustment`, `redemptions_par`, `redemptions_cash`, `redemption_inflation`, `primary_addons_par`, `primary_addons_cash`, `primary_cash_adjustment`, `primary_cash_unavailable_par`, `redemption_cash_unavailable_par`, `secondary_purchases_par`, `secondary_sales_par`, `unclassifiable_par`, `unclassifiable_abs_par`, `event_type`, `inflation_compensation_change_excluded`, `classification_status`, `primary_cash_status`, `redemption_status`, `gross_trade_status`).
- `trc_weekly_route_daily_v1.csv`: daily ON RRP and non-SOMA Treasury bill issuance/redemption capacity scenarios (`date`, `week`, `on_rrp_opening_principal`, `on_rrp_closing_principal`, `on_rrp_decline`, `gross_non_soma_bill_issue_cash`, `gross_non_soma_bill_redemption_cash`, `positive_net_bill_cash`, `net_bill_on_rrp_overlap`, `route_forward`, `route_reverse`, `route_baseline`, `route_status`).
- `trc_weekly_v1_receipt.json`: receipt with hashes and coverage summaries.

### Monthly TRC (`scripts/export_trc_monthly.py`)

Written to `<out-dir>/trc_monthly_v1.csv` and `<out-dir>/trc_monthly_v1_receipt.json` in USD millions. Sums weekly `trc_core`, `trc_par_sensitivity`, `c_h`, and `delta_reserve_balances` across each complete last-Wednesday-to-last-Wednesday month and adds calendar-month N-MFP money-fund terms (`mmf_route_{lb,prop,ub}`, `0.0` before `2013-09`). Columns: `month`, `start_wednesday`, `end_wednesday`, `weeks`, `weeks_with_core`, `reserve_balances_start`, `reserve_balances_end`, `trc_core`, `trc_par_sensitivity`, `c_h`, `delta_reserve_balances`, `mmf_route_lb`, `mmf_route_prop`, `mmf_route_ub`, `mmf_route_status`, `trc_preferred`, `trc_mmf_lower`, `trc_mmf_upper`.

## Descriptive and Interest-Decomposition Tables

### Bank Balance-Sheet Composition (`tdc bank-composition-export`)

USD billions; Z.1 Table S.122.1 sample `2002Q1`–`2026Q2`, H.8 Table 4 months `2025-09` and `2026-09`.

- `bank_composition_z1_quarterly_v1.csv` and `bank_composition_z1_annual_v1.csv`: quarterly and annual US-chartered depository institution asset transactions and liability flows (`period`, plus `n_quarters` in annual, asset categories from `catalog.BANK_Z1_COLUMNS`, `total_financial_assets`, `asset_closure_gap`, `deposits_level_change`, `deposits_transactions`, `deposits_flow_level_gap`, `checkable_deposits`, `time_savings_deposits`, `interbank_liabilities`, `nondeposit_liabilities`).
- `bank_composition_z1_holdings_v1.csv`: end-quarter asset and liability levels (`quarter`, `category`, `label`, `role`, `z1_level_codes`, `level_usd_bn`, `share_of_total_financial_assets`).
- `bank_composition_h8_v1.csv`: domestically chartered commercial bank levels and 12-month changes (`key`, `h8_table4_line`, `label`, `parent`, `fred_id`, `level_2025-09_usd_bn`, `level_2026-09_usd_bn`, `change_12m_usd_bn`, `pct_change_12m`).
- `bank_composition_v1_receipt.json`: receipt with Z.1 and H.8 closure bounds and column metadata.

### TDC and Federal Budget Deficit Comparison (`tdc deficit-comparison-export`)

USD millions; compares measured TDC (`tdc_regression_legs_v1.csv` column `C`) with the quarterly MTS federal deficit (`-MTSDS133FMS` summed over the three months) and decomposes TDC into five funding legs (`banks`, `foreign`, `fed`, `treasury_cash_drawdown`, `mmf_on_rrp`).

- `tdc_deficit_comparison_quarterly_v1.csv`: `quarter`, `tdc`, `deficit`, `banks`, `foreign`, `fed`, `treasury_cash_drawdown`, `mmf_on_rrp`, `leg_reconciliation_gap`.
- `tdc_deficit_comparison_periods_v1.csv`: cumulative sums over configured multi-quarter periods (`period`, `first_quarter`, `last_quarter`, `n_quarters`, `tdc_cumulative`, `deficit_cumulative`, `tdc_to_deficit_ratio`, `banks_cumulative`, `foreign_cumulative`, `fed_cumulative`, `treasury_cash_drawdown_cumulative`, `mmf_on_rrp_cumulative`).
- `tdc_deficit_comparison_v1_receipt.json`: receipt with leg definitions and reconciliation checks.

### Marketable Treasury Interest Rate-and-Debt Split (`tdc interest-rate-debt-export`)

USD billions; sample `2015Q1`–`2026Q2`, debt-trend fit window `2016Q1`–`2019Q4`, base quarter `2019Q4`.

- `interest_rate_debt_q_v1.csv`: quarterly official pool interest $I_q$, quarter-average marketable debt $D_q$ (MSPD Total Marketable less Federal Financing Bank), effective annualized rate $r_q$, counterfactual debt and rate effects (blank before `2019Q4`), and FiscalData reconciliation. Columns: `quarter`, `days`, `interest`, `avg_marketable_debt`, `effective_rate_pct`, `trend_debt`, `trend_interest`, `debt_only_interest`, `debt_effect`, `rate_effect`, `debt_effect_even`, `rate_effect_even`, `fiscaldata_interest_ex_tips_ic`, `pool_minus_fiscaldata`.
- `interest_rate_debt_holders_q_v1.csv`: quarterly interest split across `deposit_users`, `fed`, `foreign`, and `banks_credit_unions`, with base-share and shift decomposition from `2019Q4` onward. Columns: `quarter`, `holder`, `interest`, `interest_low`, `interest_high`, `share`, `trend_interest`, `base_share_part`, `shift`.
- `interest_rate_debt_q_v1_receipt.json`: receipt with counterfactual parameters, holder rules, and identity checks.

## Money-Fund and Interest Verification Tables

- `tdc_mmf_rrp_fund_month_adjustments.csv` (`tdc mmf-rrp-build`): fund-month SEC Form N-MFP money-fund inputs (`date`, `fund_id`, `fed_rrp`, `treasury_total`, `treasury_bills`, `non_treasury_non_fed_rrp_assets`, `nav`) and computed monthly terms (`rrp_runoff`, `treasury_increase`, `treasury_bills_increase`, `other_asset_increase`, `nav_decline`, `other_uses`, `mmf_rrp_adjustment_{lb,prop,ub}`, `mmf_rrp_bills_adjustment_{lb,prop,ub}`).
- `tdc_mmf_rrp_quarterly_adjustments.csv`: quarterly sums of `rrp_runoff`, `treasury_increase`, `treasury_bills_increase`, `other_uses`, `mmf_rrp_adjustment_{lb,prop,ub}`, and `mmf_rrp_bills_adjustment_{lb,prop,ub}`.
- `tdc_mmf_rrp_scale_audit.csv`: diagnostic checks on the money-fund support file (`check`, `status`, `value`, `detail`).
- `tdc_mmf_rrp_source_comparison.csv` (and `.md`): quarterly comparison of fund-level SEC Form N-MFP terms (`preferred_*`) against an aggregate fallback (`fallback_*`), with `preferred_minus_fallback_prop`, `abs_preferred_minus_fallback_prop`, `preferred_to_fallback_prop_ratio`, and `material_difference`.
- `tdc_gse_rrp_boundary_check.csv` (and `.md`, written by `tdc gse-rrp-check` and `tdc estimate`): upper-bound GSE ON RRP check (`date`, `status`, `gse_tsy_tx`, `gse_on_rrp`, `gse_on_rrp_runoff`, `gse_treasury_increase`, `gse_rrp_boundary_adjustment`, `detail`).
- `bill_discount_validation.csv` (and `.md`, written by `tdc bill-discount-validate` and `tdc estimate`): compares sector Treasury-bill discount estimates against aggregate Treasury bill amortized discount (`date`, `treasury_bill_amortized_discount_mil`, `bank_tsy_bill_discount_interest_proxy`, `row_tsy_bill_discount_interest_proxy`, `credit_union_tsy_bill_discount_interest_proxy`, `bank_row_proxy_mil`, `bank_row_cu_proxy_mil`, `bank_row_share_of_aggregate`, `bank_row_cu_share_of_aggregate`, `has_treasury_bill_benchmark`, `has_all_sector_proxies`).

## Summary Bundles and Auxiliary Pipeline Outputs

### `tdc_downstream_handoff_bundle.json` (and `.md`)

Written by `tdc estimate` to `data/processed/`. JSON summary with `bundle_format: "tdc_downstream_handoff_v1"` and top-level keys `bundle_format`, `generated_at_utc`, `distribution_scope`, `summary`, `goal_status`, `receipt_unblock_status`, `estimator_contract`, `use_cases`, `receipt_boundaries`, `backend_closeout_review`, `backend_release_check`, `problem_variables`, `series_panel`, and `comparison_panel`.

### `site/bundle.json` and `site/data/bundle.json`

Written by `tdc site-export` (and `tdc build`) for the static site. Top-level keys: `generated_at_utc`, `dates`, `estimates`, `components`, `corrections`, `quarterly_inputs`, `method_meta`, `series_meta`, `summary`, and `research`.

- `summary`: `latest_date`, `preferred_method`, `canonical_tier2_method`, `canonical_tier2_status`, `latest_preferred_value`, `latest_canonical_tier2_value`, `latest_4q_sum`, `latest_cum_sum`, `latest_values`.
- `research`: selected pipeline check tables mapped under keys `theory_map`, `goal_status`, `fiscal_comparison`, `receipt_status`, `bank_receipt_status`, `foreign_pilot_status`, `foreign_pilot_evidence`, `fiscal_residuals`, `fiscal_quality`, `fiscal_receipt_boundaries`, `monetary_review`, and `next_steps`.

### Auxiliary pipeline check files

`tdc estimate` also writes auxiliary CSV and Markdown checking tables to `data/processed/` covering input coverage, deposit-definition bridges (NCUA, FDIC, and Z.1), fiscal-reconciliation residuals, and downstream consistency checks. These files are standalone diagnostic outputs separate from the inputs to the main TDC series.
