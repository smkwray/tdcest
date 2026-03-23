# Methodology

## Concept

This repo is built around a practical empirical estimate of the **treasury-attributed component of deposits (TDC)**.

The default headline is a **marketable-Treasury, transaction-based, bank-only** estimate:

\[
\widehat{\Delta D}^{mkt,bank}_{TDC,t}
=
\left(
\Delta TS^{tx}_{Fed,t}
+
\Delta TS^{tx}_{Banks,t}
+
\Delta TS^{tx}_{ROW,t}
\right)
-
\Delta Cash^{tx}_{Treasury,t}
+
Remit^{+}_{Fed,t}
\]

The repo also publishes a **broad-depository** alternative:

\[
\widehat{\Delta D}^{mkt,broad}_{TDC,t}
=
\widehat{\Delta D}^{mkt,bank}_{TDC,t}
+
\Delta TS^{tx}_{CU^{NP},t}
\]

Where `CU^{NP}` denotes natural-person credit unions.

## Interpretation

- When reserve users absorb Treasury securities from deposit users, deposits can rise.
- When Treasury operating cash rises, deposits are drained.
- When the Fed remits earnings to Treasury, those receipts can support Treasury-driven deposit creation, but only when remittances are positive.
- Whether credit unions belong in the headline depends on the **deposit concept** being estimated. The repo therefore separates bank-only and broad-depository versions.

## Why use transactions

A transactions-based estimator is preferred because holdings-level changes can combine:

- transactions
- price revaluations
- other volume changes
- residual discrepancies

That makes level changes better suited for sensitivity checks than for the headline estimate.

## Credit-union treatment

The repo now handles credit unions as an explicit policy choice.

### Default headline

`tdc_base_bank_only_ru_flow`

This excludes all credit-union Treasury transactions from the headline RU term.

### Recommended broad-depository alternative

`tdc_base_broad_depository_np_cu_ru_flow`

This adds **natural-person credit-union Treasury transactions**.

### Additional sensitivities

- `tdc_broad_depository_np_corp_cu_ru_flow`
- `tdc_credit_union_aggregate_sensitivity`

The second sensitivity adds the NCUA capitalization deposit term so users can compare the clean broad-depository treatment against the published aggregate credit-union Treasury concept.

## Methods in the codebase

### Base method

`tdc_base_bank_only_ru_flow`

Uses:

- Fed Treasury transactions
- bank-sector Treasury transactions
- rest-of-world Treasury transactions
- Treasury operating cash transactions
- positive-only Fed remittances, quarter-summed

### Broad-depository alternative

`tdc_base_broad_depository_np_cu_ru_flow`

Adds natural-person credit unions to the bank-sector block.

### Domestic bank-only sensitivity

`tdc_domestic_bank_only_ru_flow`

Excludes the rest-of-world Treasury term.

### No-remittance sensitivity

`tdc_no_remit_bank_only`

Excludes Fed remittances.

### Level-change sensitivities

- `tdc_level_bank_only_sensitivity`
- `tdc_level_broad_depository_np_cu_sensitivity`

These use holdings-level differences instead of transactions. They are comparison methods rather than recommended headline estimates.

### Decomposition proxy

`tdc_decomposition_proxy_bank_centric`

A rough proxy based on:

\[
\Delta M - \Delta C - \Delta BankCredit_{nonTS}
\]

This is not the preferred empirical estimate. It is included because it can be useful in exploratory work and diagnostics.

## Marketable vs nonmarketable

This starter repo keeps the baseline focused on **marketable Treasury securities** because that is the cleanest place to start with Z.1 transactions.

A later extension can add nonmarketables using:

- MSPD detail tables
- SLGS data
- savings securities / TreasuryDirect support
- sector-specific nonmarketable mappings

## Remittance treatment

The H.4.1 remittance series is a weekly level series with two regimes:

- positive values = estimated remittances due to Treasury
- negative values = cumulative deferred asset position

For TDC estimation, the repo applies:

\[
Remit^{+}_{Fed,t} = \sum_{w \in t} \max(0, H41_w)
\]

## Recommended research workflow

1. Use the bank-only base RU-flow method as the headline series.
2. Report the broad-depository natural-person credit-union variant alongside it.
3. Show corporate-credit-union and aggregate-CU treatments only as sensitivity checks.
4. Show no-remit and domestic-only variants as secondary sensitivities.
5. Show level-based and decomposition proxies only as supplemental comparisons.
6. Add Treasury support datasets for diagnostics and the future nonmarketable extension.
