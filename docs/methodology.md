# Methodology

This document explains what `tdcest` measures, how it constructs the quarterly Treasury Deposit Component (TDC) and its reserve-side counterpart, and what the comparison calculations and checks compute. Formulas are collected in [equations](equations.md), input series in [data sources](data_sources.md), and output columns in the [output schema](output_schema.md).

## What TDC is

Households, firms, and other nonbanks hold US bank deposits and make payments from them. Call this group deposit users. Their deposits rise when the Treasury pays them and fall when they pay taxes or buy Treasury securities. Banks, the Federal Reserve, and foreign holders settle through reserves or accounts outside US banks, so payments between those sectors and the Treasury leave deposit users' deposits unchanged.

TDC is the net change in deposit users' bank deposits from Treasury payments and Treasury-security trades:

- Treasury non-debt spending paid to deposit users
- minus taxes and other payments deposit users make to the Treasury
- plus interest and principal the Treasury pays to deposit users
- plus proceeds deposit users receive from selling Treasury securities to other sectors
- minus payments deposit users make to buy Treasury securities, including at auction

Over any period, the total change in deposit users' deposits equals TDC plus all other deposit changes, such as bank lending.

## Measuring TDC from the Treasury's side

Public data report sector-level Treasury transactions and balances, whereas the payee or payer behind individual Treasury disbursements is unobserved. Because the Treasury's cash balance changes by receipts minus outlays, the deposit-user definition equals the Treasury's side of the same transactions:

```math
\widehat{\mathrm{TDC}}_t
=
\Delta \mathrm{TS}^{\mathrm{tx}}_{\mathrm{Fed},t}
+ \Delta \mathrm{TS}^{\mathrm{tx}}_{\mathrm{Banks},t}
+ \Delta \mathrm{TS}^{\mathrm{tx}}_{\mathrm{ROW},t}
- \hat{I}_{\mathrm{Fed},t}
- \hat{I}_{\mathrm{Banks},t}
- \hat{I}_{\mathrm{ROW},t}
+ \mathrm{Remit}^{+}_{\mathrm{Fed},t}
- \Delta \mathrm{Cash}^{\mathrm{op,adj}}_t
+ A^{\mathrm{prop}}_{\mathrm{MMF},t}
```

Every term is a quarterly flow in USD millions. The series is `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` in `data/processed/tdc_tier2_regression_series.csv`, covering 2002Q1 onward.

### Sector purchases

Net Treasury purchases come from quarterly Financial Accounts of the United States (Z.1) flow series, which exclude market-price revaluations and other volume changes. The bank group covers US-chartered depository institutions (`BOGZ1FU763061100Q`), US offices of foreign banks (`BOGZ1FU753061103Q`), and banks in US territories (`BOGZ1FU743061103Q`). Federal Reserve purchases use `BOGZ1FU713061103Q`, and foreign purchases use rest-of-world transactions (`BOGZ1FU263061105Q`). Credit unions are excluded from the main bank group and carried in comparison calculations; see [credit-union treatment](credit_union_treatment.md). The estimator covers marketable Treasury securities; interest on nonmarketable debt (savings bonds, State and Local Government Series, and intragovernmental holdings) is reported separately.

### Treasury interest

Interest paid by the Treasury to the Federal Reserve, banks, and foreign holders lowers Treasury cash without crediting a bank deposit, so subtracting it removes that offset from the operating-cash term.

Federal Reserve interest comes from System Open Market Account (SOMA) security-level holdings snapshots (`support__fed_tsy_coupon_interest_proxy.csv`), assigning scheduled coupon payments to quarters from each security's maturity date and coupon rate. Before the first full public SOMA quarter, the build can backcast Federal Reserve coupon interest from Z.1 holdings, estimated coupon shares, and H.15 yields.

Marketable public Treasury interest from Treasury Fiscal Data (`interest_expense`) is split into three quarterly pools: coupon accrual (notes, bonds, and TIPS nominal coupons), bill amortized discount, and floating-rate note (FRN) interest. TIPS inflation compensation stays separate outside the TDC interest pools. In each pool where an exact SOMA Federal Reserve figure exists, that amount is subtracted first and the remainder is divided across non-Federal Reserve holders; when the SOMA figure is absent, the Federal Reserve stays in the denominator with its estimated weight.

Bank and foreign interest is estimated in three consecutive periods, depending on the data available:

- 2022Q1 onward: official component pools allocated using [wamest](https://github.com/smkwray/wamest) holdings by instrument type and maturity bucket, held to reported bank Call Report and Treasury International Capital (TIC) holdings (and NCUA Call Reports in the credit-union comparison).
- 2010Q2 through 2021Q4: the same official component pools allocated with `wamest` maturity-bucket weights before Call Report and TIC constraints begin.
- 2002Q1 through 2010Q1: sector holdings combined with `wamest` instrument shares and H.15 Treasury yields, scaled by each sector's median ratio of component-allocated interest to H.15 interest over the first five years of overlap.

The [WAMEST interest output contract](wamest_interest_output_contract.md) documents the required sector-weight inputs.

### Federal Reserve remittances

Federal Reserve remittances to the Treasury fund outlays without draining bank deposits. Only positive remittances enter because negative Federal Reserve earnings accumulate as a deferred asset. The build sums monthly Monthly Treasury Statement (MTS) Table 4 net receipts for deposits of earnings by Federal Reserve Banks (`support__fed_remit_mts.csv`). When that local support file is absent, it falls back to summing positive weekly H.4.1 earnings remittances due to the Treasury (`RESPPLLOPNWW`), starting in 2002Q4.

### Treasury operating cash and internal transfers

Treasury operating cash uses Z.1 `BOGZ1FU313024000Q`, which includes both the Treasury General Account (TGA) and historical Treasury Tax and Loan (TT&L) balances at commercial banks. Transfers between Treasury and Federal Reserve accounts move operating cash without touching a bank deposit, so the build subtracts `treasury_fed_internal_cash_tx` (`support__treasury_fed_internal_cash_tx.csv`, exported by `tdc treasury-fed-transfer-export`) from Z.1 operating cash.

The internal-transfer ledger covers two 2020 onward families:

- Treasury equity contributions to and returns from Federal Reserve emergency credit facilities: Daily Treasury Statement (DTS) Table II entries under `ESF - Economic Recovery Programs` matched to the H.4.1 Treasury-contributions liability (`H41RESH4ENWW`), plus documented Federal Reserve-account settlement exceptions. Facility earnings paid through commercial-bank operating accounts and undocumented amounts stay in operating cash.
- Credit-facility LLC purchases and redemptions of nonmarketable Domestic Series securities: DTS Table III-A postings reconciled to Monthly Statement of the Public Debt (MSPD) holder class `SPV Demand` and Z.1 LLC holdings (`FL503069203.Q`).

Pre-2020 quarters are zero because both H.4.1 Treasury contributions (from December 2002) and Z.1 LLC holdings are zero.

### Money market funds and ON RRP

Money market funds are deposit users, yet purchases of Treasury securities financed by drawing down balances at the Federal Reserve's overnight reverse repurchase (ON RRP) facility shift Federal Reserve liabilities into Treasury cash without changing bank deposits. Using SEC Form N-MFP fund-month filings (`support__mmf_fund_month.csv`), `tdcest` allocates each fund's monthly Treasury purchases across ON RRP runoff and other funding uses in proportion (`mmf_rrp_adjustment_prop`), alongside exact lower (`_lb`) and upper (`_ub`) balance-sheet bounds, and sums them to quarters. Office of Financial Research aggregate MMF data serve as a fallback check. The term is zero before 2013Q3, when the ON RRP facility began (September 23, 2013). It is one-sided: it measures ON RRP runoff funding Treasury purchases and omits Treasury redemptions placed back into ON RRP. See [money market funds and ON RRP](mmf_rrp_adjustment.md).

## Partial sums, comparisons, and diagnostics

Alongside the main series, the pipeline writes partial sums, sector-boundary comparisons, and diagnostic tables for verification.

| Column or file | What it computes |
|---|---|
| `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` (`tdc_tier2_regression_series.csv`) | Main TDC series (2002Q1 onward); `_lb_` and `_ub_` replace proportional MMF/ON RRP with lower and upper bounds |
| `tdc_tier2_regression_mmf_rrp_prop_depository_institution_np_cu_ru_flow` (`tdc_tier2_regression_series.csv`) | Comparison treating natural-person credit unions with banks (adds their purchases, subtracts their interest) |
| `tdc_regression_legs_v1.csv` (`tdc regression-leg-export`) | Exact split of TDC into foreign (`R`), operating cash (`O`), and domestic Fed, bank, and money-fund (`J`) terms |
| `tdc_base_bank_only_ru_flow` (`tdc_estimates.csv`) | Partial sum before subtracting interest or adding the money-fund ON RRP term |
| `tdc_tier1_fed_corrected_bank_only_ru_flow` (`tdc_estimates.csv`) | Partial sum after subtracting Federal Reserve coupon interest only |
| `tdc_tier2_component_anchored_*`, `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow` (`tdc_estimates.csv`) | Short-window calculations restricted to quarters with constrained component interest support (2022Q1 onward); `_fed_extension_` variants also subtract SOMA bill discount and FRN interest |
| `tdc_tier2_h15_*` (`tdc_estimates.csv`) | Full-sample interest comparisons using H.15 yield intensity (and optional bill-discount proxies) without official component pools |
| `tdc_base_broad_depository_np_cu_ru_flow`, `tdc_broad_depository_np_corp_cu_ru_flow`, `tdc_credit_union_aggregate_sensitivity` (`tdc_estimates.csv`) | Partial-sum comparisons adding natural-person credit unions, corporate credit unions, and the NCUA capitalization deposit |
| `tdc_domestic_bank_only_ru_flow`, `tdc_no_remit_bank_only` (`tdc_estimates.csv`) | Partial-sum comparisons omitting foreign purchases or Federal Reserve remittances |
| `tdc_level_bank_only_sensitivity`, `tdc_bank_only_extended_1990` (`tdc_estimates.csv`) | Comparisons using first differences of Z.1 holdings levels (extending back to 1990 in the `_extended_1990` column) |
| `tdc_decomposition_proxy_bank_centric` (`tdc_estimates.csv`) | Residual bank-balance-sheet check: change in M2 minus currency and non-Treasury bank credit |
| `tdc_tier3_fiscal_corrected_*`, `tdc_du_fiscal_flow_*`, `tdc_du_residual_proxy_*` (`tdc_estimates.csv`) | Optional fiscal-flow diagnostics for bank corporate taxes (IRS SOI shares carried forward up to two years), visa fee candidates, and direct MTS budget checks (the six MTS deposit-user columns are unaudited for 2020 facility transfers) |

Other exports compare TDC with money-stock measures and record how money funds, other domestic nonbanks and government-sponsored enterprises settle; the [output schema](output_schema.md) lists them.

## Treasury component of reserves and H.4.1 ledger

The Treasury component of reserves (TRC) applies the same balance-sheet accounting to bank reserves at the Federal Reserve (`delta_rb_z1`, Z.1 `FU713113003.Q`). Exported by `tdc trc-export` (`trc_quarterly_components_v1.csv`, `trc_quarterly_series_v1.csv`), quarterly TRC sums the fall in Treasury deposits at the Federal Reserve (TGA and the Supplementary Financing Program, excluding Treasury–Federal Reserve internal transfers), Federal Reserve Treasury transactions, positive remittances, minus Federal Reserve SOMA coupon interest, plus the money-fund ON RRP term (with core, lower, and upper companions). TT&L balances sit at commercial banks and stay out of the reserve cash leg. The TGA change uses last-Wednesday H.4.1 `WDTGAL` through 2005Q4 and DTS Table I final-business-day close from 2006Q1; 2002 quarters are unavailable because H.4.1 TGA starts December 18, 2002. `trc-export` also reports the measured TDC–TRC wedge, separate GSE ON RRP and foreign-official direct-account bounds (the latter starting mid-2007 when H.4.1 custody reporting begins), and reserve-scope comparisons (reserves plus ON RRP, H.3 total reserves, US-chartered reserves, and an all-H.4.1 clock check).

An independent H.4.1 Table 1 reserve-factor ledger (`tdc reserve-factor-ledger-export`) tracks every supplying and absorbing factor on the Wednesday clock from December 18, 2002, verifies closure against reserve balances (`WRBWFRBL`), published totals, and parent subtotals within the 0.5 USD million per-component rounding bound, telescopes weekly flows into Wednesday-bounded quarters, and reconciles quarterly TRC term by term against Z.1 reserve changes.

Weekly TRC (`tdc weekly-trc-export`, Thursday–Wednesday clock from October 12, 2005, first complete quarter 2006Q1) and monthly TRC (`scripts/export_trc_monthly.py`, summing weekly components onto a last-Wednesday month clock with calendar-month Form N-MFP money-fund terms) provide higher-frequency reserve series; see [weekly TRC conventions](weekly_trc.md). All reserve-side and pinned comparison exports verify input SHA-256 hashes from a clean committed checkout and write a JSON receipt beside each output (`--vintage v1` ends in 2025Q4; `--vintage 2026q2` ends in 2026Q2).

## Limits

TDC is estimated from sector-level public accounts, where the specific deposit or reserve account debited on each transaction is unobserved. The measure assumes non-debt-service Treasury spending and tax receipts settle with deposit users and foreign holders settle outside US bank deposits. Bank and foreign interest relies on estimated holdings by type and maturity (and H.15 yields through 2010Q1). The money-fund ON RRP term is one-sided and assumes proportional allocation across each fund's uses, bracketed by the lower and upper bounds. Comparisons across Z.1, DTS, Form N-MFP, and H.4.1 combine calendar-quarter, month-end, and last-Wednesday clocks.
