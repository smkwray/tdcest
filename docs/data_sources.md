# Data sources

## Core FRED series used by the estimator family

| Repo key | FRED series ID | Description | Use |
|---|---|---|---|
| `fed_tsy_tx` | `BOGZ1FU713061103Q` | Monetary Authority; Total Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `us_chartered_tsy_tx` | `BOGZ1FU763061100Q` | U.S.-Chartered Depository Institutions; Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `foreign_offices_tsy_tx` | `BOGZ1FU753061103Q` | Foreign Banking Offices in the U.S.; Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `affiliated_areas_tsy_tx` | `BOGZ1FU743061103Q` | Banks in U.S.-Affiliated Areas; Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `np_credit_unions_tsy_tx` | `BOGZ1FU473061103Q` | Credit Unions; Treasury Securities, Excluding Corporate Credit Unions; Asset, Transactions | broad-depository headline |
| `corp_credit_unions_tsy_tx` | `BOGZ1FU473061153Q` | Credit Unions; Treasury Securities Held by Corporate Credit Unions; Asset, Transactions | sensitivity |
| `ncua_capitalization_deposit_tx` | `BOGZ1FU473061203Q` | Credit Unions; NCUA Share Insurance Capitalization Deposit; Asset, Transactions | aggregate-CU sensitivity |
| `credit_unions_total_tsy_tx` | `BOGZ1FU473061105Q` | Credit Unions; Treasury Securities; Asset, Transactions | optional cross-check |
| `row_tsy_tx` | `BOGZ1FU263061105Q` | Rest of the World; Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `treasury_operating_cash_tx` | `BOGZ1FU313024000Q` | Federal Government; Treasury Operating Cash; Asset, Transactions | bank-only and broad headlines |
| `fed_remit_or_deferred` | MTS Table 4 support when present; otherwise `RESPPLLOPNWW` fallback | Federal Reserve earnings deposits / remittances | bank-only and broad headlines |
| `gse_tsy_tx` | `BOGZ1FA403061105Q` | Government-Sponsored Enterprises; Treasury Securities; Asset, Transactions | GSE/RRP boundary diagnostic only |

## Holdings-level sensitivity series

The repo can also download holdings-level analogs for the Treasury transaction series and Treasury operating cash.

These are used only for:

- level-change sensitivities
- diagnostics
- visual cross-checks

## Local Treasury support series

- `support__fed_remit_mts.csv` is the preferred Federal Reserve remittance cash-flow input. It is built from Monthly Treasury Statement Table 4 net receipts for `Deposits of earnings by Federal Reserve Banks`, using cached official MTS PDFs before the machine-readable MTS receipts window and `treasury__mts_receipts.csv` where available. When this file is present, the pipeline uses it to override the weekly H.4.1/FRED `RESPPLLOPNWW` balance-sheet stock series.
- `treasury__mts_receipts.csv` is the machine-readable FiscalData / MTS receipts extract used by several receipt-side bridges. For Fed remittances, it is used as the production source from its first available month onward, with PDF extraction retained for archival months.
- `support__mmf_fund_month.csv` is the normalized MMF/RRP support file. It can be built from the OFR aggregate MMF API via `mmf-rrp-support` or from SEC Form N-MFP ZIP files via `sec-nmfp-mmf-support`; the latter is the fund-level preferred source for final MMF/RRP source-of-funds allocation.
- `support__gse_on_rrp.csv` is the NY Fed reverse-repo propositions support file for GSE ON RRP accepted amounts. It is built by `gse-on-rrp-support` and used only in `tdc_gse_rrp_boundary_check.csv`; it is not an input to the canonical estimator.

## Optional macro support series

- `M2SL`
- `CURRCIR`
- `TOTBKCR`
- `LOANS`
- `INVEST`
- `TNMACBM027SBOG`
- `RMFSL`
- `STDSL`
- `DPSACBM027NBOG`
- `ODSACBM027SBOG`
- `LTDACBM027SBOG`
- `TERMT`
- `WLODLL`
- `H41RESPPALDNNWW`
- `H8B3094NCBDM`
- `CASACBM027SBOG`
- `WRESBAL`
- `RRPTSYD`
- `WDTGAL` — TGA-only weekly diagnostic, useful for cross-checks but not the full Tier 0 operating-cash concept when historical TT&L balances mattered
- `B093RC1Q027SBEA` — BEA/FRED federal interest payments to the rest of the world, used as a quarterly SAAR benchmark in the input-audit step for the ROW coupon proxy
- `W008RC1Q027SBEA` — BEA/FRED federal government current tax receipts: taxes from the rest of the world, used in the processed ROW receipt benchmark
- `W781RC1Q027SBEA` — BEA/FRED federal government current receipts: contributions for government social insurance from the rest of the world, used in the processed ROW receipt benchmark
- `LA0000281Q027SBEA` — BEA/FRED federal government current receipts: current transfer receipts from the rest of the world, used in the processed ROW receipt benchmark

These are used for rough decomposition proxies and high-frequency diagnostic checks.

The repo now uses the currently loaded H.6/H.8-style support series to emit a Stage 0 monetary diagnostic:

- `M2SL` and `CURRCIR` support a quarter-over-quarter `M2 - currency` partial target
- `RMFSL` adds the retail money-market-fund subtraction for a depository-style target
- `STDSL` adds the small-time-deposit subtraction for a more liquid-deposit target
- `DPSACBM027NBOG` adds a bank-only commercial-bank-deposit target
- `ODSACBM027SBOG` now adds a broad all-commercial-bank other-deposits context series
- `LTDACBM027SBOG` now adds a large-time bank-deposit context series
- `TOTBKCR` provides a commercial-bank-credit context series
- `LOANS`, `INVEST`, and `TNMACBM027SBOG` now support a first refined H.8 bank-credit block
- `WRESBAL` and `RRPTSYD` support first-pass reserve and RRP controls
- `TERMT`, `WLODLL`, and `H41RESPPALDNNWW` now support a deeper H.4.1 central-bank block
- `H8B3094NCBDM` and `CASACBM027SBOG` add bank funding/liquidity context
- `WMTSEC1` and `TNMFRIM027SBOG` now add foreign / portfolio-shift context, but remain outside the signed subtotals because they sit too close to the ladder's own Treasury channels

The repo now also emits a Stage 1 control-block diagnostic:

- `Simple subtotal` keeps total bank credit as the bank-side term
- `Refined subtotal` replaces total bank credit with loans and leases plus other securities excluding Treasury/agency non-MBS securities
- `Expanded subtotal` adds Fed liquidity-credit loans, Fed term deposits, other deposits at the Fed, and bank borrowings
- bank cash assets remain a context term rather than a signed subtotal input
- foreign-official custody holdings and foreign-related Treasury/agency securities are also context terms rather than signed subtotal inputs

The repo now also emits a monetary overlap-audit artifact:

- it grades each Stage 1 term as signed vs context-only
- it records overlap risk explicitly
- it keeps Treasury-adjacent foreign terms and TGA as context-only unless an overlap-safe mapping exists

The repo now also emits a residual-interpretation artifact:

- it turns the Stage 1 subtotals into a per-quarter waterfall
- it shows how much of each target gap is removed by the simple, refined, and expanded blocks
- it labels the remaining residual as `mostly_unresolved`, `partly_explained`, or `largely_explained`

The repo now also emits a target-wedge artifact:

- it isolates the commercial-bank-deposit target wedge relative to the depository target
- it shows how much of the unresolved bank residual is bank-target-specific rather than shared
- it makes the current bank-vs-depository target-definition problem explicit instead of leaving it buried inside the residual

The repo now also emits a target-preference review artifact:

- it turns the wedge and residual results into a repo-level recommendation
- it currently prefers the depository target as the main monetary cross-check
- it currently treats the commercial-bank-deposit target as a stress-test surface rather than the main monetary benchmark

The repo now also emits a target-definition bridge:

- it checks whether the unresolved commercial-bank-deposit residual is simply the raw bank-minus-depository target wedge
- it uses the loaded retail-MMF and small-time target components to keep the target-definition differences explicit
- when the alignment gap is zero, the unresolved bank residual is behaving like a target-definition wedge rather than a missing control

The repo now also emits a target-definition decomposition:

- it splits the bank-minus-depository wedge into the small-time component and the residual bank-minus-liquid/perimeter component
- it uses both signed shares and absolute component shares so opposite-signed small-time moves do not hide the dominant structural component
- it makes the current bank stress-test divergence easier to interpret without promoting the commercial-bank target back into the main monetary role

The repo now also emits a bank-target stress review:

- it combines the target-preference and target-definition decomposition artifacts
- it checks whether the commercial-bank target is now best interpreted as a perimeter stress test
- it turns that interpretation into an explicit review status instead of leaving it implicit

The repo now also emits a bank-target gap attribution:

- it reconstructs the commercial-bank target gap as shared depository gap plus small-time plus bank-minus-liquid/perimeter wedge
- it reconstructs the commercial-bank residual after expanded controls as shared depository residual plus the bank-specific wedge
- it quantifies whether the unresolved bank residual is mostly shared, small-time, or perimeter-style
- in the current live output, the perimeter-style component is the largest additive piece of the bank residual

The repo now also emits a bank-perimeter-gap review:

- it checks whether the currently loaded monetary inputs include the source families needed to decompose the bank-minus-liquid/perimeter wedge further
- it currently flags that genuinely new source families would be required, rather than more transformations of the current inputs
- it turns that stop condition into an explicit review artifact

The repo now also emits a bank-perimeter source map:

- it translates the missing source families into concrete official candidate sources
- it currently points to Federal Reserve / FRED H.8 and H.6 series for bank-liability pieces, while the NCUA quarterly Call Report ZIP bridge and FDIC quarterly savings-institution bridge are now both loaded on the nonbank-depository side
- it gives the repo a concrete next-source roadmap rather than only a stop condition
- the current live stance is now narrower:
  `LTDACBM027SBOG` is loaded as the first large-time bucket,
  `ODSACBM027SBOG` is loaded as the best broad bank-deposit context candidate but remains too broad for a bank-only liquid-deposit subcomponent,
  `ODSACBM027NBOG + WDDNS` is rejected for now as a liquid bridge because of likely demand-deposit overlap,
  and the NCUA plus FDIC bridge sides are both now loaded on the nonbank-depository side

The repo now also emits a bank-liquid source review:

- it collapses the current bank-only-liquid boundary into one publication-ready review artifact
- it names the best loaded broad bank-deposit context series, the loaded large-time series, the loaded additive liability context, and the explicitly rejected `ODSACBM027NBOG + WDDNS` construction
- in the latest live quarter, it says the repo still has `no_clean_bank_only_liquid_subcomponent_loaded`
- so the remaining blocker is not another transformation of the current public data; it is the lack of a cleaner public bank-only liquid-deposit family

The repo now also emits a bank-liquid stop gate:

- it converts that source review into explicit pass/fail and guardrail checks
- in the latest live quarter, the nonbank bridge side and large-time bucket pass
- the clean bank-only liquid subcomponent check fails
- `ODSACBM027SBOG` stays context-only as an active guardrail
- the explicit overall decision is now `stop_at_perimeter_stress_test`

The repo’s ROW receipt pilot is now MRV-first:

- the annual `Receipts by Department` intake still provides the account-title pilot surface
- but the primary recurring ROW bridge is now narrowed to the `Consular and Border Security Programs, Machine Readable Visa Fee, State` line
- secondary State visa lines such as the immigrant-visa security surcharge and diversity-visa fee remain visible only as nondefault sensitivities
- monthly State NIV issuance statistics are used only as a timing bridge for the MRV / CBSP line, while IV issuance counts are used only for the separate secondary visa sensitivity
- the default ROW nonborrow receipt correction remains zero because the public sources still do not prove the legal payer or debited account

The repo now also emits a dedicated MRV default-readiness gate. That gate confirms the current blocker is not absence of an MRV line or annual account mapping. With the current `Combined Statement` support file loaded, the repo now confirms the broader CBSP main-account family around MRV. The binding blocker remains lack of public debited-account / legal-remitter evidence, with quarterly cash timing still proxy-based.

The repo now also emits a direct recurring-pilot review for the State / visa branch. That artifact keeps the primary MRV / CBSP bridge separate from the secondary visa branch and makes the policy stance explicit:

- MRV / CBSP is the only recurring ROW branch under default review
- the secondary visa branch remains a separate recurring sensitivity
- both branches still rely on activity-based timing proxies rather than observed Treasury cash timing

The repo now also emits a narrower MRV payment-chain review. That evidence artifact uses official State/FAM/Treasury sources to separate:

- what is now source-backed:
  MRV fee/applicant link,
  retained-fee authority to `19X5713.5`,
  broader CBSP account-family confirmation,
  and stronger exclusion evidence for IV/AOS-style lines because NVC fee guidance requires U.S.-bank payments that anyone with the case login can make
- what is still not source-backed:
  the actual legal remitter or debited account for the Treasury MRV cash receipt,
  and observed quarterly cash timing

The repo now also emits a single MRV promotion checklist. That checklist collapses the readiness gate, payment-chain review, and recurring-pilot split into the exact evidence classes that matter for promotion. In the current live output, required MRV checks are:

- `3` complete:
  Treasury receipt-account identification,
  payer-scope and exclusion control,
  annual reconciliation
- `1` partial:
  cash-treatment and retained-account evidence
- `2` missing:
  legal-remitter / debited-account proof,
  observed quarterly cash timing

So the repo no longer just says “MRV is not yet promotable.” It now says exactly what evidence classes are complete, partial, and still missing.

The repo now also emits an MRV source map. That source map translates the remaining checklist gaps into concrete official source families:

- Treasury / State account-family mapping: already loaded strongly enough for the current pilot
- stronger cash-treatment evidence: still partial
- public legal-remitter or debited-account proof: still missing
- public quarterly cash timing or remittance schedule: still missing

The repo now also emits an MRV stop gate. That gate turns the checklist and source map into an explicit repo-level decision:

- keep MRV as the leading recurring ROW pilot
- but stop at `stop_at_mrv_nondefault_pilot`
- and target only the remaining missing source families rather than broadening the ROW branch further

The repo now also emits a consolidated receipt unblock-status surface. That artifact keeps the main remaining receipt branches together:

- bank historical age-eligible window:
  usable as a historical default view under the current stale-share rule
- bank current window:
  still blocked by stale-share freshness
- MRV primary recurring ROW branch:
  still blocked by the MRV stop gate
- secondary State visa branch:
  explicitly visible but not on the main promotion path

That gives the repo one canonical place to absorb future external research answers instead of scattering them across multiple gates.

The repo now also emits a ROW receipt-family review on top of the same annual bridge plus `Combined Statement` crosswalk. That review makes a distinction the earlier artifacts did not:

- some ROW families are now blocked mainly by contamination or concept,
  not by missing annual account-family confirmation
- MRV remains the primary recurring pilot
- confirmed DHS immigration and traveler families strengthen exclusion logic and contaminated-family accounting
- confirmed FMS advance families strengthen deposit/trust classification rather than any move toward default current-receipt treatment

## Optional normalized NCUA bridge input

- `ncua__credit_union_deposit_bridge.csv` — normalized quarterly bridge built locally by `scripts/build_ncua_credit_union_deposits.py`
- `support__credit_union_deposits.csv` — support-series projection of federally insured credit-union `Acct_018` totals into the quarterly frame
- `fdic__savings_institution_deposit_bridge.csv` — normalized quarterly bridge built locally by `scripts/build_fdic_savings_institution_deposits.py`
- `support__thrift_deposits.csv` — support-series projection of FDIC savings-institution `DEP` totals for BKCLASS `SB`, `SI`, and `SL` into the quarterly frame

This bridge is built from final NCUA quarterly Call Report ZIP files, specifically:

- `FS220.txt` for `Acct_018` total shares and deposits
- `Acct_013` total member shares
- `FOICU.txt` for `CU_TYPE` counts used to split federally insured and nonfederally insured credit unions

The current repo uses the federally insured `Acct_018` total as the loaded support series for the credit-union side of the bank-versus-broad-depository bridge. The live processed bridge currently shows:

- `2025-12-31` federally insured credit-union shares and deposits `2,067,600.394` million
- implied federally insured nonmember deposits `25,107.064` million
- credit-union-to-commercial-bank-deposit ratio `11.041%`

The repo now loads both the credit-union and thrift sides of the nonbank depository bridge. In the latest live quarter, that loaded nonbank-depository bridge explains only about `17.9%` of the bank-minus-liquid wedge. Adding the loaded large-time bucket brings the currently admissible loaded liability context to about `44.6%` of the wedge, while `ODSACBM027SBOG` remains context-only because it is broader than a clean bank-only liquid-deposit subcomponent. The remaining perimeter gap is therefore no longer “missing FDIC thrift data”; it is the unresolved bank-only liquid or perimeter wedge on the commercial-bank side.

The current Stage 0 / Stage 1 monetary implementation is still not a full monetary-disaggregation system:

- it uses the loaded FRED/H.6/H.8-style series as quarter-end/last-observation targets
- it still lacks broader foreign / portfolio-shift controls
- it still lacks broader foreign / portfolio-shift controls
- it does not yet attempt a structural residual attribution model

So the monetary artifact is a sign/magnitude cross-check around the ladder, not a substitute estimator.

## Optional Treasury Fiscal Data datasets

- Daily Treasury Statement deposits and withdrawals of operating cash
- Monthly Treasury Statement receipts
- Monthly Treasury Statement outlays
- MSPD marketable detail
- MSPD full detail
- SLGS securities
- U.S. Government Revenue Collections
- Receipts by Department annual account-symbol detail
- Interest Expense on the Public Debt Outstanding, used to validate sector bill-discount proxies against aggregate Treasury bill amortized discount

The Tier 0 cash leg is sourced from the Z.1 Treasury operating cash concept. DTS operating-cash and `WDTGAL` TGA data are useful diagnostics, but neither should silently replace the broader operating-cash concept in historical periods where Treasury Tax and Loan balances were material.

## Optional local support series

- `support__fed_tsy_coupon_interest_proxy.csv` — quarterly Fed Treasury coupon-interest proxy built locally from SOMA holdings snapshots and inferred coupon schedules, normalized to millions of U.S. dollars; when built with `--wamest-root`, pre-full-SOMA quarters are bridged with a WAMEST/H.15 Fed coupon-intensity backcast
- `support__fed_tier1_component_extension_proxy.csv` — staged nondefault Fed Tier 1 component-extension proxy exported from `support__fed_treasury_interest_components.csv`; it sums exact SOMA bill-discount and FRN interest and feeds only Fed-extension component-anchored rows
- `support__bank_tsy_coupon_interest_proxy.csv` — quarterly bank-sector Treasury coupon-interest proxy for the default bank-only Tier 0 perimeter, built from `wamest` sector coupon-intensity weights
- `support__row_tsy_coupon_interest_proxy.csv` — quarterly rest-of-world Treasury coupon-interest proxy for ROW-inclusive Tier 2 variants, built from the same raw quarter-end sector coupon-intensity method
- `support__credit_union_tsy_coupon_interest_proxy.csv` — quarterly credit-union Treasury coupon-interest proxy for depository-institution Tier 2 candidates, built from the `wamest` `credit_unions_marketable_proxy` sector
- `support__bank_tsy_bill_discount_interest_proxy.csv`, `support__row_tsy_bill_discount_interest_proxy.csv`, and `support__credit_union_tsy_bill_discount_interest_proxy.csv` — optional WAMEST-backed bill-discount interest robustness proxies, built from sector bill shares, sector levels, Treasury bill WAM support, and the Treasury curve
- `support__bank_tier2_component_interest_proxy.csv`, `support__row_tier2_component_interest_proxy.csv`, and `support__credit_union_tier2_component_interest_proxy.csv` — component-anchored Tier 2 support series exported from `tier2_interest_component_candidate.csv`; they allocate official Treasury coupon-accrual, bill-discount, and FRN interest pools using source-constrained sector weights and feed the promoted canonical Tier 2 rows when present. Legacy WAMEST/H.15 coupon-intensity rows remain available under explicit `tdc_tier2_h15_*` sensitivity names.
- `support__gse_on_rrp.csv` — optional NY Fed GSE ON RRP support series, stored as daily levels in millions with `value` equal to GSE accepted amount; the quarterly pipeline uses quarter-end levels for the diagnostic `min(max(0, GSE Treasury acquisition), max(0, -Delta GSE ON RRP))`

The command `tdc bill-discount-validation --download-treasury-interest` downloads FiscalData `interest_expense`, extracts `Treasury Bills` / `AMORTIZED DISCOUNT`, sums monthly dollar amounts to calendar quarters in millions, and compares that aggregate benchmark with the bank, ROW, and credit-union sector bill-discount proxies. The benchmark starts with FiscalData's available interest-expense history, while the sector proxies are still governed by WAMEST support coverage.

The sector-coupon builder now prefers the full `wamest` holder panel and normalizes `wamest` full-history sector panel levels to estimator-scale millions when the source panel is using the standard billions-style level convention. The repo also writes a processed unit-and-frequency audit that compares the live ROW coupon proxy against the BEA/FRED ROW federal-interest benchmark after SAAR-to-quarterly conversion. That benchmark is a sanity check, not a claim of exact concept identity.

If you pass `--wamest-root` to the Tier 2 builder, `tdcest` resolves these inputs from the conventional `wamest` locations:

- `data/external/normalized/soma_holdings_fed.csv` for the Fed coupon proxy builder; the same command also uses the WAMEST maturity, panel, and curve artifacts below to backcast Fed coupon support before the first full SOMA quarter
- `outputs/full_coverage_release/canonical_sector_maturity.csv`
- `data/external/normalized/z1_series_fred.csv`, with computed `wamest` sectors reconstructed from the full-coverage inventory when needed
- `data/external/normalized/h15_curves_auto_nominal_treasury_constant_maturity.csv`
- `data/processed/treasury_bill_wam_support.csv` when `--include-bill-discount` is used

## Download philosophy

This repo prefers:

- official public sources
- URLs that can be called from scripts
- raw-file preservation in `data/raw/`
- transparent transformations into `data/processed/`

## Optional normalized IRS bridge input

- `irs__soi_bank_tax_shares.csv` — normalized annual IRS Publication 16 Table 5.1 bank-minor tax-share table built locally by `scripts/build_irs_soi_bank_tax_shares.py`
- `irs__soi_bank_minor_industry_availability.csv` — normalized IRS Publication 16 Table 5.3 bank minor-industry availability table built locally by `scripts/build_irs_soi_bank_minor_industry_availability.py`

This file is not a quarterly Treasury cash series. It is a reproducible annual bridge input that currently exposes:

- `Commercial banking`
- `Savings institutions / other depository credit intermediation`
- `Offices of bank holding companies`
- derived `strict depository` and `depository plus BHC` shares of total income tax after credits
- retained finance-share values as an upper benchmark / QA check

The current repo now treats the Table 5.1 bank-minor bridge as the best public official bank receipt candidate. It materially improves the payer perimeter relative to the older finance-sector bridge, but it does not resolve the stale-share problem for current 2025 to 2026 quarters.

That split is now made explicit in the processed historical-promotion surface too: age-eligible historical quarters are separated from current stale-share quarters, with `depository_plus_bhc` treated as the main historical default candidate and `strict_depository` retained as the lower-bound sensitivity.

The repo now also carries a research-only historical Tier 3 surface built from that same age-eligible window. It applies the historical `depository_plus_bhc` candidate only in quarters still inside the stale-share rule and leaves current stale quarters out by construction.

The companion Table 5.3 availability file is not itself a share input. It is a reproducible source-evidence table that records whether the relevant public bank-like rows are actually observable. The current live file shows:

- `Commercial banking` — suppressed
- `Savings institutions and other depository credit intermediation` — suppressed
- `Offices of bank holding companies` — suppressed

That evidence now feeds the processed bank default-readiness gate directly, which keeps the stricter Table 5.3 path blocked and the current Table 5.1 bridge in explicit `not yet promotable` status for stale current quarters.

An April 18, 2026 official-source check against IRS public pages also found no newer public Publication 16 complete report than tax year 2022 and no better post-2022 official IRS public substitute for this bank-share use case. So the stale-share blocker is not just a local policy choice; it reflects the current public IRS source boundary.

The repo now also emits a bank source map. That source map translates the current bank blocker into concrete source families:

- loaded and usable:
  Publication 16 Table 5.1 bank-minor history for the historical window
- still missing for current default:
  fresher public IRS bank-minor shares
- blocked but visible:
  the stricter Table 5.3 C-corp path
- loaded as context:
  share-stability history

The repo now also emits a bank stop gate. That gate turns the current bank branch into an explicit split:

- historical age-eligible window:
  usable as a historical default view
- current quarter:
  stop at `historical_default_only_current_nondefault`
  until fresher public IRS bank-minor shares exist

## Optional Treasury account-candidate bridge input

- `treasury__receipts_by_department.csv` — public annual Treasury account-symbol receipt detail from the `receipts_by_department` Fiscal Data endpoint

This file is not a quarterly payer-identity source. It is useful for:

- bank non-tax account reconnaissance, especially OCC and OFR-related lines
- ROW account reconnaissance, especially visa/consular and foreign-military-sales-linked lines
- grading candidate receipt lines before any narrower pilot is promoted
- carrying a public FAST Book / CARS overlay on those candidates:
  availability type,
  general-fund major-class logic where applicable,
  fund-group proxy,
  and a first budget-treatment guess
- carrying compact structured grading fields on top of that title/account-treatment logic:
  `candidate_family`,
  `promotion_priority`,
  `payer_identity_subgrade`,
  and `default_blocker`

The current processed bridge keeps every public `Receipts by Department` match out of the default Tier 3 correction because annual account titles still do not identify the actual payer account or cash timing precisely enough.

The repo now also layers a small official `Combined Statement` annual support file on top of that same annual receipt-account bridge. This support now covers State, Treasury, Homeland Security, International Assistance Programs, and a narrow Independent Agencies probe. It gives the repo a second annual account-system surface that can confirm broader main-account families even when the exact sub-account line is not present at the same granularity. In the current live state that means:

- MRV / CBSP lines have broader State main-account `5713` confirmation
- OFR / Financial Research Fund lines have broader Treasury main-account `5590` confirmation
- Homeland Security immigration and traveler lines now have broader account-family confirmation:
  `5088` Immigration Examination Fees,
  `5087` Immigration User Fees,
  `5543` International Registered Traveler,
  and `5702` 9-11 Response / Biometric Exit
- International Assistance lines now confirm broader foreign-program account families including:
  `8242` Advances, Foreign Military Sales,
  `8502` U.S. dollars advanced from foreign governments,
  and `8246` Peace Corps advances from foreign governments
- the support file now also exposes the FDIC `4596` Deposit Insurance Fund family as context, but the current FDIC penalty line `51--1099-0` still does not reconcile to it
- current OCC fines lines still do not reconcile to the loaded OCC assessment-fund family, which sharpens the nondefault OCC treatment rather than promoting it

The repo now also uses this same annual source to emit two narrower pilot artifacts:

- a ROW visa/consular pilot that isolates strict State/visa lines from mixed immigration and passport contamination buckets
- a bank non-tax regulatory pilot that isolates OCC, OFR, and other bank-regulatory-style lines as explicit sensitivity intake

Within that annual bridge, the structured grading now explicitly distinguishes:

- `row_mrv_cbsp_primary` from `row_secondary_visa_sensitivity`
- `row_dhs_immigration_family_mixed` and `row_dhs_traveler_family` from generic foreign-title rows
- mixed sponsor-sensitive titles from passport or broad-consular contamination
- `bank_regulatory_specific_occ` from `bank_large_bhc_specific_ofr` and `bank_regulatory_mixed_fdic`
- `row_fms_deposit_trust_family` from general-fund-style foreign-title bridge concepts

Those pilot artifacts are still annual and diagnostic. They are not promoted default Tier 3 corrections.

The repo also now emits a quarterly OCC timing sensitivity from the OCC-linked annual pilot lines. That quarterly artifact is not a new raw source; it is a timing convention layered onto the annual public account surface using the current official OCC semiannual assessment due dates.

## Optional normalized State visa timing input

- `state__visa_issuances_monthly.csv` — normalized monthly State Department NIV and IV issuance totals built locally by `scripts/build_state_visa_monthly_issuances.py`

This file is not a Treasury receipts table. It is a timing bridge input used to allocate the strict annual State/visa pilot into quarterly sensitivities. The builder currently normalizes official monthly Travel.State.Gov visa-statistics workbooks into:

- `date`
- `fiscal_year`
- `niv_issuances_total`
- `iv_issuances_total`

The current repo uses this monthly timing input only for the quarterly ROW State/visa sensitivity layer. It does not by itself prove payer identity or cash settlement timing tightly enough to justify a default Tier 3 ROW receipt correction.

## Optional processed receipt-candidate stack

The repo now emits a consolidated quarterly receipt-candidate sensitivity artifact around the default Tier 3 bank-only series when at least one of the current non-default receipt modules is available:

- bank corporate-tax bridge
- OCC timing sensitivity
- ROW State/visa timing sensitivity

This artifact is intentionally downstream of other processed sources rather than a new raw source family. Its purpose is to show scale and sign effects from the strongest current non-default receipt candidates without silently promoting them into the default estimator.

The current version also distinguishes between:

- the raw bank corporate-tax bridge
- the policy-eligible bank bridge that still satisfies the current stale-share rule

This makes it visible when a candidate remains interesting as a bridge but no longer qualifies as a currently admissible default-side sensitivity.

## Optional processed fiscal reconciliation shell

The repo now also emits a structured fiscal-reconciliation shell around the default bank-only ladder:

- `tdc_fiscal_reconciliation_cells.csv`
- `tdc_fiscal_reconciliation_residuals.csv`
- `tdc_fiscal_source_quality.csv`

This shell does not introduce a new raw source family. It is a structured integration layer over existing raw and processed sources, currently combining:

- default ladder cells from Z.1, H.4.1, local coupon proxies, and source-backed Tier 3 support
- benchmark cells such as the BEA ROW receipt benchmark and bank corporate-tax bridge
- sensitivity cells such as Revenue Collections bank-channel bounds, the broad ROW outlay profile, OCC timing, and ROW State/visa timing

The residual table is a consistency check: it should stay near zero when the reconciliation shell faithfully reproduces the current default Tier 0 through Tier 3 bank-only path.

## Optional processed receipt-promotion review

The repo now also emits a promotion-review table for the current receipt-side candidates. This is not a new raw source family; it is a decision layer over the existing benchmark, bridge, pilot, and sensitivity artifacts.

Its purpose is to keep the next promotion decision explicit:

- which bank candidate is closest to becoming the first nonzero default bank receipt correction
- which ROW candidate is closest to a future default pilot
- which large visible candidates should remain permanently outside the default because they are routing-channel or deposit/trust concepts

The repo now also emits a bank default-readiness gate for the bank corporate-tax bridge. This is not a new raw source family either; it is a methods-control layer over the bridge, estimates, and receipt-side sensitivity outputs. Its purpose is to keep the “promote or not yet?” decision explicit and reproducible rather than narrative-only.

## Credit-union mapping note

The repo intentionally separates:

- natural-person credit-union Treasury transactions
- corporate credit-union Treasury transactions
- the NCUA capitalization deposit term

That makes it possible to publish:

- a bank-only headline
- a broad-depository natural-person-CU alternative
- a corporate-CU sensitivity
- an aggregate-CU sensitivity
