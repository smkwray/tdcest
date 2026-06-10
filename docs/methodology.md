# Methodology

## Concept

This repo is built around a practical empirical estimate of the **Treasury Deposit Component (TDC)**.

The Tier 0 starting point is a **marketable-Treasury, transaction-based, bank-only** estimate:

```math
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
\Delta TOC^{tx}_{Treasury,t}
+
Remit^{+}_{Fed,t}
```

The repo also publishes a **broad-depository** alternative:

```math
\widehat{\Delta D}^{mkt,broad}_{TDC,t}
=
\widehat{\Delta D}^{mkt,bank}_{TDC,t}
+
\Delta TS^{tx}_{CU^{NP},t}
```

Where `CU^{NP}` denotes natural-person credit unions.

## Interpretation

- When reserve users absorb Treasury securities from deposit users, deposits can rise.
- When Treasury operating cash rises, deposits are drained.
- Historically that operating-cash term should be read as Treasury operating cash, not just the TGA, so Treasury Tax and Loan balances belong inside the same cash concept when they were material.
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

The Tier 0 cash leg is intentionally an operating-cash concept rather than a TGA-only concept. High-frequency TGA series can still be useful for diagnostics, but they should not be treated as the full historical Tier 0 cash term when TT&L balances were material.

### Broad-depository alternative

`tdc_base_broad_depository_np_cu_ru_flow`

Adds natural-person credit unions to the bank-sector block.

### Domestic bank-only sensitivity

`tdc_domestic_bank_only_ru_flow`

Excludes the rest-of-world Treasury term.

### No-remittance sensitivity

`tdc_no_remit_bank_only`

Excludes Fed remittances.

### Tier 1 Fed-corrected variants

- `tdc_tier1_fed_corrected_bank_only_ru_flow`
- `tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow`
- `tdc_tier1_fed_corrected_domestic_bank_only_ru_flow`

These are optional local-support variants. They subtract a quarterly Fed Treasury coupon-interest proxy, built from SOMA holdings snapshots, from the corresponding Tier 0 methods.

### Tier 2 interest-corrected variants

- `tdc_tier2_interest_corrected_bank_only_ru_flow`
- `tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow`
- `tdc_tier2_interest_corrected_domestic_bank_only_ru_flow`

These are optional local-support variants on top of the same Tier 0 bank block. The domestic-only Tier 2 method subtracts Fed and bank-sector Treasury coupon-interest proxies. The ROW-inclusive Tier 2 methods also subtract a rest-of-world Treasury coupon-interest proxy.

The default bank perimeter for these corrected tiers is unchanged:

- U.S.-chartered depositories
- foreign banking offices in the U.S.
- banks in U.S.-affiliated areas

The bank and ROW coupon proxies are still approximations rather than security-level cash-flow reconstructions. The default published proxies use the raw quarter-end coupon-intensity approximation. A cash-anchored rescaling path remains available for research-only checks, but it is not the default publication method.

First, the builder forms sector coupon-intensity weights:

```math
\widetilde I^{TS}_{s,t}
\approx
\frac{Level_{s,t} \times CouponShare_{s,t} \times CurveRate_{s,t}}{4}
```

where the curve rate is read from a nominal Treasury curve at the sector's coupon-only maturity estimate, using linear interpolation when the estimate falls between standard tenors.

The research-only cash-anchored variant rescales those non-Fed sector weights to the observed non-Fed Treasury interest pool:

```math
\widehat I^{TS}_{s,t}
\approx
\left(I^{TS,gross}_{t} - Coupon^F_t\right)
\times
\frac{\widetilde I^{TS}_{s,t}}{\sum_{j \neq F}\widetilde I^{TS}_{j,t}}
```

The promoted Tier 2 support files use component-anchored bank, ROW, and credit-union Treasury interest allocations when those files are present. The raw quarter-end WAMEST/H.15 approximation $\widetilde I^{TS}_{s,t}$ is retained as an explicit H15 sensitivity path, and the old all-in cash-anchored variant remains diagnostic rather than default.

For day-to-day work, the Tier 2 builder can resolve those inputs directly from a `wamest` checkout via `--wamest-root`, using the repo's conventional full-history artifact locations.

### Level-change sensitivities

- `tdc_level_bank_only_sensitivity`
- `tdc_level_broad_depository_np_cu_sensitivity`

These use holdings-level differences instead of transactions. They are comparison methods rather than recommended headline estimates.

### Decomposition proxy

`tdc_decomposition_proxy_bank_centric`

A rough proxy based on:

```math
\Delta M - \Delta C - \Delta BankCredit_{nonTS}
```

This is not the preferred empirical estimate. It is included because it can be useful in exploratory work and diagnostics.

## Marketable vs nonmarketable

This starter repo keeps the baseline focused on **marketable Treasury securities** because that is the cleanest place to start with Z.1 transactions.

A later extension can add nonmarketables using:

- MSPD detail tables
- SLGS data
- savings securities / TreasuryDirect support
- sector-specific nonmarketable mappings

## Remittance treatment

The preferred remittance input is the Monthly Treasury Statement Table 4 net receipt line for Federal Reserve earnings deposits, quarter-summed from monthly cash receipts:

```math
Remit^{+}_{Fed,t} = \sum_{m \in t} MTSFedReceipts_m
```

This is the Treasury cash-flow concept used when `data/raw/support__fed_remit_mts.csv` is present.

The H.4.1 remittance series remains a fallback/comparison series. It is a weekly level series with two regimes:

- positive values = estimated remittances due to Treasury
- negative values = cumulative deferred asset position

For fallback TDC estimation, the repo applies:

```math
Remit^{+}_{Fed,t} = \sum_{w \in t} \max(0, H41_w)
```

## Recommended research workflow

1. Use `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow` as the current canonical Tier 2 measurement row when the component support files are present.
2. Use `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` as the preferred long-history regression row, with method-tier and sample-split caveats.
3. Report the matched-perimeter depository-institution regression companion when a downstream comparison needs credit-union consistency.
4. Keep the bank-only base RU-flow and broad-depository base rows visible as ladder inputs, not as the final corrected measure.
5. Keep corporate-credit-union, aggregate-CU, no-remit, domestic-only, level-change, and decomposition rows as sensitivity or diagnostic checks.
6. Treat Tier 3 fiscal rows as partial-shell diagnostics until current bank and ROW receipt cells clear the documented gates.

The canonical Tier 2 policy target is `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow`: the depository-institution row with coupon corrections, holder-specific bill-discount corrections, and the preferred proportional MMF/RRP source-of-funds adjustment. The GSE/RRP diagnostic checks the same Fed-liability-to-Treasury-security boundary for government-sponsored enterprises, but it is not a canonical estimator input. It is reported separately as `tdc_gse_rrp_boundary_check.csv` / `.md` because GSE Treasury absorption cannot be treated as a bank-deposit-scope correction without a stronger funding-source claim.

`tdc_domestic_nonbank_monetary_route_bridge.csv` is the downstream scope
contract for domestic nonbank and MMF routes. It labels retail MMFs as inside
M2 but outside bank-deposit pass-through, MMF/ON-RRP runoff as non-M2 plumbing,
aggregate Z.1 domestic nonbank absorption as mixed/unknown scope, and dealer,
other-financial, and institutional-MMF routes as non-M2 or context-only. This
bridge does not change canonical TDC math; it prevents downstream users from
treating non-M2 Treasury absorption as deposit-pass-through or current-demand
evidence.

`tdc_mmf_route_split_context.csv` is the SEC N-MFP companion context split. It
uses the fund retail flag and portfolio holdings to separate retail MMF and
institutional/nonretail MMF Treasury and Fed ON-RRP positions at quarter-end.
This is still context-only: fund type and portfolio holdings do not identify
final investor current-demand conversion, deposit pass-through, incidence,
pricing, or welfare effects.

`tdc_route_admissibility_registry.csv` is the quarterless source-owned route
guardrail built from the monetary route bridge and SEC N-MFP route split. It
deduplicates route rules by `route_id`, records the observed holder, funding,
and payment-route facts, and assigns fail-closed current-demand gates. It is
not an amount table and does not change canonical TDC math. Downstream users
should use it to prevent accidental promotion of retail MMFs,
institutional/nonretail MMFs, broad Z.1 domestic nonbanks, dealer/repo routes,
or MMF/ON-RRP plumbing into current-demand or canonical runtime math. The
ON-RRP boundary columns distinguish NY Fed/Fed-liability counterparty-type
context from SEC N-MFP fund-scope portfolio context; neither clears the final
investor or deposit-recipient route gate.

`tdc_z1_domestic_nonbank_sector_context.csv` is the Z.1 sector companion for
the broad domestic-nonbank route blocker. It decomposes domestic nonbank
Treasury-security transactions into MMFs, dealers, GSEs, mutual funds,
insurance/pension funds, households/nonprofits residual, nonfinancial business,
state/local government, structured-finance, holding-company, and clearing
counterparty sector rows. This is still sector/instrument context only: it does
not identify debited claims, settlement accounts, payment routes, final
investors, or current-demand conversion.

## Monetary cross-check stance

The repo now treats the monetary side as a diagnostic system with a preferred cross-check target.

### Preferred monetary cross-check

`depository_target = M2 - currency - retail money market funds`

This is the preferred monetary comparison surface because, under the current Stage 1 control blocks, it is materially better explained than the commercial-bank-deposit target.

### Commercial-bank-deposit target

`commercial_bank_deposit_target = deposits at all commercial banks`

This remains useful, but it is currently treated as a **stress-test surface**, not the main monetary benchmark.

The reason is empirical rather than rhetorical:

- the commercial-bank-deposit target remains mostly unresolved after the expanded Stage 1 control block
- the unresolved bank-side residual is dominated by a bank-target-specific wedge
- the target-definition bridge shows that, in the latest live quarter, that bank-specific residual wedge matches the raw bank-minus-depository target wedge exactly
- the target-definition decomposition shows that this wedge is mostly the larger bank-minus-liquid/perimeter component rather than just the small-time-deposit subtraction
- the bank-target stress review therefore treats the commercial-bank target mainly as a perimeter stress surface, not as a parallel benchmark waiting for one more generic control block
- the NCUA quarterly Call Report ZIP bridge is now loaded for federally insured credit-union shares and deposits
- the FDIC quarterly savings-institution bridge is now also loaded, so the nonbank-depository side is no longer missing a thrift leg
- the additive bank-target gap attribution now shows the unresolved commercial-bank residual as shared depository residual plus a much larger perimeter-style wedge, with the small-time component relatively minor
- the nonbank-depository bridge attribution now shows that the loaded NCUA plus FDIC bridge explains only about `17.9%` of the latest bank-minus-liquid wedge
- `LTDACBM027SBOG` is now loaded as a large-time bank-deposit context series, and the liability-candidate audit shows that the currently admissible additive liability context of `nonbank bridge + large time` explains about `44.6%` of that latest wedge
- `ODSACBM027SBOG` is now also loaded as the best broad bank-deposit context series, but it remains context-only because it is still too broad for a clean bank-only liquid-deposit subcomponent
- the new bank-liquid source review collapses that boundary into one explicit methods verdict: `no_clean_bank_only_liquid_subcomponent_loaded`
- the new bank-liquid stop gate goes one step further and makes the repo-level decision explicit: `stop_at_perimeter_stress_test`
- so the remaining unresolved bank-side story is now much more about perimeter definition than about a missing generic monetary control
- the perimeter-gap source review now explicitly says the current loaded inputs are not enough to decompose the remaining roughly `55.4%` of the latest bank-minus-liquid wedge further, so progressing past this point requires genuinely new source families
- the perimeter source map now names those candidate families concretely rather than leaving them as abstract gaps
- under current public-source coverage, the remaining blocker is the bank-only liquid-deposit split, not the nonbank-depository bridge side

So the current repo-level interpretation is:

- use the depository target as the main monetary cross-check
- use the commercial-bank-deposit target to stress-test how sensitive the monetary side is to bank-target definition rather than as a peer headline diagnostic

## Receipt-side end state

The receipt side is now best read as three separate layers rather than one unresolved block.

### 1. Bank historical window

The live `Publication 16 Table 5.1` bank-minor bridge is now strong enough to support a **historical default view** in the age-eligible window. The repo therefore treats the historical bank window as usable and distinct from the current stale-share window.

### 2. Bank current window

The current-quarter bank bridge remains explicitly nondefault. The blocker is no longer perimeter ambiguity. The blocker is that the latest official public bank-minor share path still tops out at `TY2022`, so current quarters remain outside the stale-share rule.

### 3. ROW recurring pilot

The serious recurring ROW candidate is now the **MRV-first / CBSP** branch. Public FAH/FAM and State OIG evidence now materially improves the nondefault cash-route case by supporting:

- USDO collection accounts
- sweep and remittance mechanics
- deposit notifications and OF-158 support
- GFSC / USDO reconciliation mechanics

But the repo still stops below default because it does not yet have:

- public legal-remitter or debited-account proof
- public quarterly cash timing or remittance evidence

So the repo’s receipt-side stance is now:

- **bank historical window:** usable research default view
- **bank current window:** explicit nondefault bridge
- **MRV primary ROW branch:** explicit nondefault pilot
- **secondary ROW families and bank non-tax families:** explicit exclusions or sensitivity-only layers
