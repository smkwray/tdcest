# Methodology

This page describes what TDCest measures, how each estimator row is built, and which rows to use for which purpose. Formulas are collected in [equations](equations.md); input series are listed in [data sources](data_sources.md); column definitions are in the [output schema](output_schema.md).

## Concept

The **Treasury Deposit Component (TDC)** is the part of deposit change caused by Treasury cash operations and by transactions in Treasury securities. Deposits rise when Treasury pays into deposit accounts, or when sectors outside the deposit-holding perimeter (the Federal Reserve, banks and the rest of the world) buy Treasury securities from deposit holders. Deposits fall when Treasury cash accumulates in its accounts.

Public data do not record the settlement account behind every Treasury payment, so TDCest builds a **proxy**: a transactions-based measure that follows the accounting identity as closely as public sources allow. The gap between the proxy and the exact flow is a measurement error, not a behavioral parameter.

## Baseline (Tier 0)

The baseline is a marketable-Treasury, transactions-based, bank-only estimate:

```math
\widehat{\Delta D}^{mkt,bank}_{TDC,t}
=
\Delta TS^{tx}_{Fed,t}
+ \Delta TS^{tx}_{Banks,t}
+ \Delta TS^{tx}_{ROW,t}
- \Delta TOC^{tx}_{Treasury,t}
+ Remit^{+}_{Fed,t}
```

- $\Delta TS^{tx}$ are Z.1 Treasury-security transactions by the Federal Reserve, banks and the rest of the world. When these sectors absorb Treasury securities from deposit holders, deposits rise.
- $\Delta TOC^{tx}$ is the Z.1 transaction in Treasury operating cash, net of Treasury–Federal Reserve internal transfers. A rise in Treasury cash drains deposits. The cash concept is operating cash, not the Treasury General Account (TGA) alone, because Treasury Tax and Loan (TT&L) balances held at commercial banks were material in earlier years. TGA series are useful diagnostics but are not substitutes for the historical cash term.
- Treasury–Federal Reserve internal transfers move operating cash without reaching a deposit: in 2020–2026, Treasury equity paid into and returned from the Federal Reserve credit-facility LLCs, and the LLCs' purchases and redemptions of nonmarketable Treasury securities. A dated ledger built from the Daily Treasury Statement identifies them (equity by its match to the H.4.1 Treasury-contributions liability, LLC securities by their Monthly Statement of the Public Debt holder class, reconciled to the Z.1 LLC holdings level), and the cash term removes their quarterly sum, `treasury_fed_internal_cash_tx`. Other payments in the same DTS category, such as direct loans to businesses, stay in the cash term.
- $Remit^{+}_{Fed}$ is Federal Reserve earnings remitted to Treasury. Remittances fund Treasury spending without a deposit drain. Only positive remittances enter, because negative Fed earnings create a deferred asset rather than a payment from Treasury.

Transactions are preferred to changes in holdings because holdings-level changes also contain price revaluations, other volume changes and statistical discrepancies. Holdings-level variants are kept as sensitivities.

### Fed remittances

The preferred remittance input is the Monthly Treasury Statement (MTS) Table 4 receipt line for deposits of earnings by Federal Reserve Banks, summed over the months of each quarter:

```math
Remit^{+}_{Fed,t} = \sum_{m \in t} MTSFedReceipts_m
```

When that support file is absent, the pipeline falls back to the weekly H.4.1 remittances-due series. That series is positive when remittances are due and negative when the Fed carries a deferred asset; the fallback sums its positive weekly values over the quarter.

## Deposit perimeter

The right treatment of credit unions depends on the deposit concept being estimated, so it is an explicit choice rather than a hidden sector mapping.

| Row | Perimeter | Role |
|---|---|---|
| `tdc_base_bank_only_ru_flow` | U.S.-chartered depository institutions, foreign banking offices in the U.S., banks in U.S.-affiliated areas | Bank-only baseline (ladder input) |
| `tdc_base_broad_depository_np_cu_ru_flow` | Bank-only plus natural-person credit unions | Broad-depository alternative |
| `tdc_broad_depository_np_corp_cu_ru_flow` | Also adds corporate credit unions | Sensitivity |
| `tdc_credit_union_aggregate_sensitivity` | Also adds the NCUA share-insurance capitalization deposit | Sensitivity |

The aggregate sensitivity lets users compare the clean broad-depository treatment with the published aggregate credit-union Treasury concept. See [credit-union treatment](credit_union_treatment.md).

Other baseline sensitivities:

| Row | Change from the baseline |
|---|---|
| `tdc_domestic_bank_only_ru_flow` | Drops the rest-of-world Treasury term |
| `tdc_no_remit_bank_only` | Drops Fed remittances |
| `tdc_level_bank_only_sensitivity`, `tdc_level_broad_depository_np_cu_sensitivity` | Use holdings-level changes instead of transactions |
| `tdc_decomposition_proxy_bank_centric` | Rough residual proxy, $\Delta M - \Delta C - \Delta BankCredit_{nonTS}$, for exploratory comparison only |

## Tier 1: Fed coupon correction

Coupon interest that Treasury pays on Fed-held securities lowers Treasury cash, which the baseline counts as a deposit inflow, but it is paid to the Federal Reserve rather than to a deposit holder. Tier 1 subtracts a quarterly Fed coupon-interest proxy built from SOMA holdings snapshots and inferred coupon schedules:

- `tdc_tier1_fed_corrected_bank_only_ru_flow`
- `tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow`
- `tdc_tier1_fed_corrected_domestic_bank_only_ru_flow`

From the first full public SOMA quarter onward the proxy follows security-level holdings. Earlier quarters can be filled with a coupon-intensity backcast from WAMEST maturity estimates and the H.15 Treasury curve.

## Tier 2: holder interest and money-fund corrections

### Interest components

Treasury interest paid to banks, credit unions and the rest of the world lowers Treasury cash without crediting a domestic nonbank deposit, yet the operating-cash term counts every fall in Treasury cash as a deposit inflow. Tier 2 subtracts that interest.

The default Tier 2 rows are **component-anchored**. Official Treasury interest pools are split by component (coupon accrual, bill discount and FRN interest) and allocated across holder sectors with source-constrained weights. The weights come from [WAMEST](https://github.com/smkwray/wamest) holder maturity and instrument-composition estimates, bounded by Call Report, NCUA and TIC evidence. An allocation is admitted only when date, sector, component eligibility and gross-holder evidence all match. TIPS inflation compensation is kept separate and is not subtracted by default. The Federal Reserve's own interest is taken out of each pool using its exact SOMA-based amount; in a quarter where that amount is unavailable, the Fed keeps its WAMEST-weighted share of the pool rather than having it spread over the other holders.

| Row | Construction |
|---|---|
| `tdc_tier2_component_anchored_bank_only_ru_flow` | Bank-only baseline − Fed coupon − bank and ROW component interest |
| `tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow` | Same corrections on the broad-depository baseline |
| `tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow` | Broad-depository row − credit-union component interest |
| `tdc_tier2_component_anchored_domestic_bank_only_ru_flow` | Domestic-only baseline − Fed coupon − bank component interest |

Two families are kept as sensitivities:

- `tdc_tier2_h15_*` rows use the earlier coupon-intensity approximation: each sector's Treasury level × coupon share × the H.15 curve rate at the sector's coupon maturity, divided by four. Bill-discount robustness rows (`tdc_tier2_h15_treasury_interest_robust_*`) add sector bill-discount proxies, validated against the aggregate bill amortized discount in Treasury's interest-expense data.
- `tdc_tier2_component_anchored_fed_extension_*` rows also subtract SOMA bill-discount and FRN interest.

The allocation is a modeling assumption: WAMEST weights divide aggregate pools and do not observe the interest any holder received. Broad-debt maturity ladders and signed dealer or household residual positions are not treated as evidence of gross Treasury holdings. The [interest-allocation contract](wamest_interest_output_contract.md) states the input requirements.

### Money-market fund / ON RRP adjustment

A money-market fund that buys Treasury securities by running down its overnight reverse repo (ON RRP) at the Federal Reserve moves reserves, not bank deposits. Counting those purchases as deposit-funded would overstate the deposit drain. The adjustment adds back the share of each fund's monthly Treasury purchases that ON RRP runoff can fund:

- **Proportional (preferred):** ON RRP runoff × the fund's Treasury purchases ÷ (Treasury purchases + other uses of funds).
- **Lower and upper bounds:** the minimum and maximum runoff-funded purchases consistent with the fund's balance sheet.

The fund-month inputs come from SEC Form N-MFP filings; the Office of Financial Research aggregate MMF data are a fallback and cross-check. The adjustment is zero before the ON RRP facility began in September 2013. See [MMF/ON RRP adjustment](mmf_rrp_adjustment.md).

### Canonical Tier 2 row

`tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow` is the canonical quarterly measure: the component-anchored depository-institution row plus the proportional MMF/ON RRP adjustment. It exists only for quarters that have component-level interest support.

## Long-history regression series

`tdc_tier2_regression_series.csv` extends Tier 2 back to 2002Q1 for regression use. Quarters with component support use the constrained component allocation; earlier quarters use backcasts, and every quarter carries a method-tier label:

| Method tier | Construction |
|---|---|
| `constrained_component` | Component-anchored allocation with source constraints (from 2022Q1) |
| `component_pool_wamest_bucket_backcast` | Official component pools allocated with WAMEST maturity-bucket weights, before source constraints are available |
| `pre_component_h15_scaled_backcast` | H.15 coupon-intensity and bill-discount proxies, rescaled by the median ratio of component to H.15 interest over the first five years in which both exist |

Source observability and denominator evidence are recorded separately from the method tier; a later date does not upgrade source evidence. The preferred regression row is `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow`. Its matched credit-union companion is `tdc_tier2_regression_mmf_rrp_prop_depository_institution_np_cu_ru_flow`. Analyses should report results by method tier or show that they are robust to it.

## Recommended use

1. Use `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow` as the canonical quarterly measure where it is available.
2. Use `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` for long-sample regressions, together with its method-tier columns.
3. Use the depository-institution regression companion when a comparison needs credit-union consistency.
4. Treat the baseline bank-only and broad-depository rows as ladder inputs, not as corrected measures.
5. Treat corporate-credit-union, aggregate-credit-union, no-remittance, domestic-only, holdings-level and decomposition rows as sensitivities.
6. Treat Tier 3 rows as diagnostics.

## Tier 3: fiscal-flow diagnostics

Tier 3 adds Treasury outlays to and receipts from banks and the rest of the world, which the Tier 2 baseline does not separate. Public sources identify these flows only partially, so Tier 3 is a partial reconciliation rather than a corrected estimate.

- **Bank receipts.** IRS Statistics of Income Publication 16 Table 5.1 supplies bank-minor-industry shares of corporate income tax. They support a historical bank-receipt overlay. A published share may be carried forward for up to two calendar years after its tax year; quarters older than that are excluded from the overlay rather than extrapolated.
- **Rest-of-world receipts.** The leading recurring candidate is the State Department machine-readable visa (MRV) fee line, timed with monthly visa issuance statistics. It stays outside the default because public sources do not identify the remitting account or the quarterly cash timing.
- **Other candidates.** Bank regulatory receipts, other visa and immigration lines, and foreign-military-sales deposits are kept as labeled sensitivities or exclusions.

Receipt corrections that public sources cannot support are not estimated inside the Tier 3 rows, which therefore carry essentially zero bank and rest-of-world receipt corrections. The candidate receipt series are published separately as sensitivities, so the gap stays visible instead of being silently closed.

## Route-scope context

Several outputs label which Treasury-absorption routes can or cannot be read as deposit flows. None changes the estimator arithmetic.

- `tdc_domestic_nonbank_monetary_route_bridge.csv` classifies retail MMFs as inside M2 but outside bank-deposit pass-through, MMF/ON RRP runoff as non-M2 plumbing, aggregate Z.1 domestic nonbank absorption as mixed scope, and dealer, other-financial and institutional-MMF routes as context only.
- `tdc_mmf_route_split_context.csv` uses N-MFP retail flags and holdings to split retail and institutional MMF Treasury and ON RRP positions at quarter end. Fund type does not identify final investors or deposit pass-through.
- `tdc_route_admissibility_registry.csv` lists each route once, with its holder, funding and payment-route facts and a fail-closed gate that prevents a context route from entering canonical arithmetic.
- `tdc_z1_domestic_nonbank_sector_context.csv` decomposes domestic nonbank Treasury transactions by Z.1 sector. It does not identify settlement accounts or final investors.
- `tdc_gse_rrp_boundary_check.csv` bounds Treasury purchases by government-sponsored enterprises funded from ON RRP runoff. It is reported separately because it is not a bank-deposit-scope correction.

## Monetary cross-check

The monetary diagnostics compare the TDC ladder with changes in monetary aggregates after subtracting identifiable non-Treasury drivers (bank credit, Federal Reserve lending and balance-sheet items). They are sign and magnitude checks, not an alternative estimator.

- The preferred comparison target is **M2 − currency − retail money-market funds**, which isolates deposits.
- **Deposits at all commercial banks** is a stress test. Its unexplained residual is dominated by a perimeter wedge between the bank and depository targets. Credit-union (NCUA Call Report) and savings-institution (FDIC) bridges, and H.8 large-time-deposit data, explain only part of that wedge. Public sources do not provide a clean bank-only liquid-deposit series that would close it.

## Scope: marketable securities

The estimator covers **marketable Treasury securities**, which Z.1 records as transactions by sector. Nonmarketable debt (savings bonds, State and Local Government Series, intragovernmental holdings) is outside the estimator. A separate sidecar reports interest on these securities from Treasury's interest-expense data; it never enters estimator arithmetic.

## Reserve-side counterpart

The Treasury component of reserves (TRC) applies reserve-balance incidence to the same Treasury events:

```math
TRC^{core}_q = -\Delta TGA_q - \Delta SFP_q + \Delta TS^{tx}_{Fed,q} + Remit^{+}_{Fed,q} - Coupon^{F}_q
```

The preferred quarterly TRC adds the proportional MMF/ON RRP term. TT&L balances are commercial-bank claims and stay out of the reserve cash leg. An H.4.1 Wednesday reserve-factor ledger reconciles TRC with all published supplying and absorbing factors, and a weekly construction provides a cash-corrected Wednesday proxy with route scenarios. See [equations](equations.md#treasury-component-of-reserves-trc) and [weekly TRC conventions](weekly_trc.md).
