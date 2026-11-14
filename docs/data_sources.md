# Data sources

All inputs are public. Downloads are written to `data/raw/` unchanged, and every transformation into `data/processed/` is done in code. Acquisition prefers official sources with scriptable URLs.

## Core Z.1 series

These Financial Accounts (Z.1) series, downloaded from FRED, drive the baseline estimator family.

| Key | FRED series | Description | Use |
|---|---|---|---|
| `fed_tsy_tx` | `BOGZ1FU713061103Q` | Monetary authority; Treasury securities; transactions | Baseline |
| `us_chartered_tsy_tx` | `BOGZ1FU763061100Q` | U.S.-chartered depository institutions; Treasury securities; transactions | Baseline |
| `foreign_offices_tsy_tx` | `BOGZ1FU753061103Q` | Foreign banking offices in the U.S.; Treasury securities; transactions | Baseline |
| `affiliated_areas_tsy_tx` | `BOGZ1FU743061103Q` | Banks in U.S.-affiliated areas; Treasury securities; transactions | Baseline |
| `row_tsy_tx` | `BOGZ1FU263061105Q` | Rest of the world; Treasury securities; transactions | Baseline |
| `treasury_operating_cash_tx` | `BOGZ1FU313024000Q` | Federal government; Treasury operating cash; transactions | Baseline |
| `np_credit_unions_tsy_tx` | `BOGZ1FU473061103Q` | Credit unions excluding corporate credit unions; Treasury securities; transactions | Broad-depository row |
| `corp_credit_unions_tsy_tx` | `BOGZ1FU473061153Q` | Corporate credit unions; Treasury securities; transactions | Sensitivity |
| `ncua_capitalization_deposit_tx` | `BOGZ1FU473061203Q` | Credit unions; NCUA share-insurance capitalization deposit; transactions | Aggregate credit-union sensitivity |
| `credit_unions_total_tsy_tx` | `BOGZ1FU473061105Q` | Credit unions; Treasury securities; transactions | Cross-check |
| `gse_tsy_tx` | `BOGZ1FA403061105Q` | Government-sponsored enterprises; Treasury securities; transactions | GSE/ON RRP boundary diagnostic only |

Holdings-level counterparts of the Treasury and operating-cash series are also downloaded. They feed only the holdings-level sensitivities and diagnostics.

The cash term is the Z.1 Treasury operating cash concept. Daily Treasury Statement (DTS) operating cash and the H.4.1 TGA series (`WDTGAL`) are diagnostics; neither replaces operating cash in years when Treasury Tax and Loan balances were material.

## Federal Reserve remittances

| File | Source | Role |
|---|---|---|
| `support__fed_remit_mts.csv` | MTS Table 4 receipts, "Deposits of earnings by Federal Reserve Banks". Archived MTS PDFs before the machine-readable window; FiscalData `treasury__mts_receipts.csv` after it. | Preferred remittance input |
| `RESPPLLOPNWW` | H.4.1 earnings remittances due to Treasury, weekly level (FRED) | Fallback and comparison |

## Interest-allocation inputs

| File | Contents |
|---|---|
| `support__fed_tsy_coupon_interest_proxy.csv` | Quarterly Fed coupon interest from SOMA holdings snapshots and inferred coupon schedules, in USD millions. With `--wamest-root`, quarters before the first full SOMA quarter use a WAMEST/H.15 coupon-intensity backcast. |
| `support__fed_treasury_interest_components.csv`, `support__fed_tier1_component_extension_proxy.csv` | SOMA bill-discount and FRN interest from SOMA holdings, Treasury auction results and FRN daily indexes. Used only by the Fed-extension rows. |
| `support__{bank,row,credit_union}_tier2_component_interest_proxy.csv` | Component-anchored sector interest, exported from `tier2_interest_component_candidate.csv`. Official coupon-accrual, bill-discount and FRN interest pools are allocated with source-constrained WAMEST weights. These feed the default Tier 2 rows. |
| `support__{bank,row,credit_union}_tsy_coupon_interest_proxy.csv` | H.15 coupon-intensity proxies from WAMEST sector maturity, level and curve data. They feed the `tdc_tier2_h15_*` sensitivities. |
| `support__{bank,row,credit_union}_tsy_bill_discount_interest_proxy.csv` | WAMEST-based sector bill-discount proxies for the H.15 robustness rows. Together with the coupon proxies, they form the H.15 interest proxy used in the earliest regression backcast tier. |

Interest pools and benchmarks:

- FiscalData `interest_expense` (interest expense on the public debt). The `Treasury Bills` / `AMORTIZED DISCOUNT` line, summed from monthly dollars to calendar-quarter millions, validates the sector bill-discount proxies (`tdc bill-discount-validation --download-treasury-interest`).
- Treasury auction results and FRN daily index values, for SOMA bill-discount and FRN interest.

Source constraints on the sector allocation come from FFIEC Call Reports (Schedule RC-B), NCUA Call Reports and Treasury International Capital (TIC) securities holdings.

The FRED/BEA series `B093RC1Q027SBEA` (federal interest payments to the rest of the world, SAAR) is a sanity benchmark for the rest-of-world interest proxy after conversion to quarterly levels. It is not the same concept.

### WAMEST inputs

With `--wamest-root`, the builders read a [WAMEST](https://github.com/smkwray/wamest) checkout from its standard locations:

- `data/external/normalized/soma_holdings_fed.csv`
- `outputs/full_coverage_release/canonical_sector_maturity.csv`
- `data/external/normalized/z1_series_fred.csv` (computed sectors are rebuilt from the full-coverage inventory when needed)
- `data/external/normalized/h15_curves_auto_nominal_treasury_constant_maturity.csv`
- `data/processed/treasury_bill_wam_support.csv`, with `--include-bill-discount`

WAMEST sector levels in billions are converted to USD millions. The interest-allocation files TDCest reads, and the checks it applies to them, are specified in the [interest-allocation contract](wamest_interest_output_contract.md).

## Money-market fund and ON RRP inputs

| File | Source | Role |
|---|---|---|
| `support__mmf_fund_month.csv` | SEC Form N-MFP filings (`tdc sec-nmfp-mmf-support`) | MMF/ON RRP adjustment |
| `support__mmf_fund_month_ofr_aggregate.csv` | Office of Financial Research aggregate MMF data (`tdc mmf-rrp-support`, or `--include-mmf-support` on `download` and `build`) | Source comparison only |
| `support__gse_on_rrp.csv` | New York Fed reverse repo operation results, GSE accepted amounts (`tdc gse-on-rrp-support`) | GSE/ON RRP boundary diagnostic only |

See [MMF/ON RRP adjustment](mmf_rrp_adjustment.md) for the input contract.

## Treasury component of reserves (TRC)

`tdc trc-export` reads two hash-pinned processed inputs, `data/processed/tdc_regression_legs_v1.csv` and `data/processed/quarterly_inputs.csv`, plus the files below. `scripts/acquire_trc_inputs.py` fetches each file through [fiscus](https://github.com/smkwray/fiscus), writes it to `data/raw/fiscus/`, and records in `data/raw/fiscus/trc_inputs_manifest.json` the dataset ID, request, cache key, payload SHA-256, byte count, retrieval time and source vintage. The registry is `TRC_FISCUS_INPUTS` in `catalog.py`.

| Key | Dataset | Use | Status |
|---|---|---|---|
| `dts_operating_cash_balance_table_i` | `fiscaldata.dts_operating_cash_balance` (Table I, from 2005-10-03) | TGA from 2006Q1, SFP, TT&L | Default |
| `h41_tga_wednesday` | `fred.wdtgal` | TGA for changes through 2005Q4; all-H.4.1 diagnostic | Default bridge |
| `z1_reserves_transactions` | Z.1 `FU713113003.Q` | Reserve outcome | Default |
| `z1_sfp_transactions` | Z.1 `FU713123043.Q` | SFP cross-check | Check |
| `h41_reserve_balances_wednesday` | `fred.wrbwfrbl` | H.4.1 clock diagnostic | Nondefault |
| `h41_rrp_others_wednesday` | `fred.wlrraol` | Reserves plus ON RRP memo; ON RRP remainder cell | Nondefault |
| `h41_rrp_foreign_official_wednesday`, `h41_foreign_official_deposits_wednesday` | `fred.wlrrafoial`, `fred.wdfol` | Foreign official cash at the Fed | Nondefault |
| `h41_custody_marketable_treasury_wednesday` | `fred.wmtsecl1` | Foreign-official route bound | Nondefault |
| `h3_total_reserves_monthly` | `fred.totresns` (billions) | H.3 memo | Memo only |
| `z1_us_chartered_reserves_transactions` | Z.1 `FU763013005.Q` | U.S.-chartered reserves memo | Memo only |

Source notes:

- The `dts_operating_cash_balance` key used elsewhere names the Table II deposits-and-withdrawals endpoint. The TRC key is separate.
- DTS Table I changes its account labels over time: `Federal Reserve Account` through 2021-09-30, `Treasury General Account (TGA)` until 2022-04-15, then the `Closing Balance` row, whose value is in `open_today_bal`. SFP and TT&L spellings vary, and TT&L includes its Short-Term Cash Investments successor. An unrecognized or duplicate account on a business day stops the export.
- The SFP and TT&L lines end on 2022-04-15 at zero balances and are structural zeros afterwards. The unclassified `Financial Institution Account` (2008–2010) must be zero on every quarter-end business day.
- From 2006, DTS TGA + SFP + TT&L reproduces Z.1 Treasury operating cash transactions within published rounding, and DTS SFP changes match Z.1 `FU713123043`.
- `WMTSECL1` reports zero before July 2007. Those zeros are treated as non-reporting, so the foreign-official bound starts in 2007Q4.
- H.3 total reserves include vault cash used to meet reserve requirements before April 2020. They are a memo, not a TRC perimeter.

## H.4.1 reserve-factor ledger

`scripts/acquire_trc_inputs.py --registry h41-ledger` fetches every H.4.1 Table 1 row in the ledger into `data/raw/fiscus/h41_ledger/` and records each file's series ID, units (USD millions) and fiscus identity in `inputs_manifest.json`. The row taxonomy is `H41_TABLE1_ROWS` in `catalog.py`; each row names its FRED series, its Table 1 parent and its role. Factor rows enter the signed ledger. Check rows are published parents and totals that only verify their factor descendants. A memo row is displayed and never summed. No factor sits under another factor, so a parent and its child never both enter.

| Role | Rows (FRED series) |
|---|---|
| Outcome | Reserve balances (`WRBWFRBL`, Wednesday level; never the `WRESBAL` week average) |
| Supplying factors | Treasury securities `WSHOTSL`; agency debt `WSHOFADSL`; MBS `WSHOMCB`; unamortized premiums `WUPSHO` and discounts `WUDSHO` (published negative); repurchase agreements `WORAL`; term auction credit `RESPPALTNWW`; loans `WLCFLL`; CPFF LLC `H0RESPPAACHNWW`; MMIFF LLCs `H0RESPPAAMMIHNWW`; Maiden Lane I–III `WAML1L`, `WAML2L`, `WAML3L`; TALF LLC `H0RESPPAATALHNWW`; AIA/ALICO preferred interests `H0RESPPAAAAAINWW`; CPFF II LLC `H41RESPPAAC2HNWW`; Corporate Credit Facilities LLC `H41RESPPAABNWW`; Municipal Liquidity Facility LLC `H41RESPPAADHNWW`; MS Facilities LLC `H41RESPPAAENWW`; TALF II LLC `H41RESPPAATAL2HNWW`; float `WOFSRBFL`; central bank liquidity swaps `SWPT`; other Federal Reserve assets `WOFRAL`; foreign-currency-denominated assets `WFCDA`; gold stock `WOFSRBGSL`; SDR certificate account `WOSDRL`; Treasury currency outstanding `WTCOL` |
| Absorbing factors | Currency in circulation `WCICL`; reverse repos with foreign official accounts `WLRRAFOIAL` and others `WLRRAOL`; Treasury cash holdings `WOFDRBTHL`; term deposits `TERMT`; TGA `WDTGAL`; SFP `WDSFAL`; foreign official deposits `WDFOL`; service-related deposits `H0RESPPLLDDSNWW`; other deposits `WLODL`; AIG disposition funds held as agent `H0RESPPLLANWW`; Treasury contributions to credit facilities `H41RESH4ENWW`; other liabilities and capital `WOLCL` |
| Checks | Total supplying `WTFSRFL`; total absorbing other than reserve balances `WTFORBAFL`; Reserve Bank credit `WOFSRBRBC`; securities held outright `WSHOSHO`; reverse repos `WLRRAL`; deposits other than reserve balances `WOFDRBORBL` |
| Memo | Treasury inflation compensation `WSHOICL` (included in `WSHOTSL`) |
| Outcome bridge | Z.1 `FL713113003.Q` level and `FU713113003.Q` transactions |

Source notes:

- Every series is the H.4.1 Wednesday level in USD millions, from 2002-12-18 to the latest published Wednesday.
- `WLODL` is the "other deposits" row that closes against `WOFDRBORBL`. `RESPPMLLDONWW` does not close and is not used.
- `WDSFAL` begins 2008-09-24. Earlier Wednesdays are structural zeros because the program began on 2008-09-17.
- A discontinued row is a structural zero after its last observation. A row discontinued at a nonzero balance (TALF LLC, AIA/ALICO preferred interests, AIG disposition funds, service-related deposits) carries a declared reason, and published totals must still close.
- A row that ends early without a declared reason, a gap inside a row's reporting span, or a missing input stops the export.

The weekly TRC adds SOMA holdings snapshots, Treasury auction results, DTS Table II and FRN indexes; see [weekly TRC conventions](weekly_trc.md).

## Monetary cross-check series

Optional FRED series used by the monetary diagnostics. Targets are read as quarter-end (last-observation) values.

| Role | Series |
|---|---|
| Targets | `M2SL`, `CURRCIR`, `RMFSL` (retail MMFs), `STDSL` (small time deposits), `DPSACBM027NBOG` (commercial bank deposits) |
| Bank-deposit context | `ODSACBM027SBOG` (other deposits), `LTDACBM027SBOG` (large time deposits) |
| Bank credit and funding | `TOTBKCR`, `LOANS`, `INVEST`, `TNMACBM027SBOG`, `H8B3094NCBDM`, `CASACBM027SBOG` |
| Federal Reserve balance sheet | `WRESBAL`, `RRPTSYD`, `TERMT`, `WLODLL`, `H41RESPPALDNNWW` |
| Foreign and portfolio context | `WMTSEC1`, `TNMFRIM027SBOG` |

The diagnostics form a deposit target, subtract signed non-Treasury control blocks and report the remaining residual. Foreign-related series and the TGA are context only, because they overlap the ladder's own Treasury terms.

### Depository perimeter bridges

| File | Source |
|---|---|
| `ncua__credit_union_deposit_bridge.csv`, `support__credit_union_deposits.csv` | NCUA quarterly Call Report ZIP files: `FS220.txt` (`Acct_018` total shares and deposits, `Acct_013` member shares) and `FOICU.txt` (`CU_TYPE`, to separate federally insured credit unions). Built by `scripts/build_ncua_credit_union_deposits.py`. |
| `fdic__savings_institution_deposit_bridge.csv`, `support__thrift_deposits.csv` | FDIC quarterly financials, total deposits (`DEP`) for charter classes `SB`, `SI` and `SL`. Built by `scripts/build_fdic_savings_institution_deposits.py`. |

These bridges measure how much of the gap between the commercial-bank and depository targets comes from institutions outside the commercial-bank perimeter.

## Receipt-side research inputs

These inputs support the Tier 3 diagnostics. None enters a default correction.

| File | Source | Use |
|---|---|---|
| `irs__soi_bank_tax_shares.csv` | IRS Statistics of Income Publication 16, Table 5.1 | Annual bank-minor-industry shares of corporate income tax after credits: commercial banking, savings institutions and other depository credit intermediation, and offices of bank holding companies, with derived `strict_depository` and `depository_plus_bhc` shares |
| `irs__soi_bank_minor_industry_availability.csv` | IRS Publication 16, Table 5.3 | Records whether the bank-like rows are published or suppressed; not a share input |
| `treasury__receipts_by_department.csv` | FiscalData `receipts_by_department` | Annual account-symbol receipts, scanned for bank-related and rest-of-world receipt candidates with Federal Account Symbols and Titles (FAST Book) classification |
| Combined Statement support file | Treasury Combined Statement of Receipts, Outlays, and Balances | Confirms main-account families for candidate receipt lines |
| `state__visa_issuances_monthly.csv` | State Department monthly visa statistics | Monthly nonimmigrant and immigrant visa issuances; timing bridge for the visa-fee sensitivity |
| `W008RC1Q027SBEA`, `W781RC1Q027SBEA`, `LA0000281Q027SBEA` | BEA via FRED | Federal current receipts from the rest of the world (taxes, social insurance contributions, transfers); receipt benchmark |
| FiscalData MTS receipts and outlays, DTS, Revenue Collections | Treasury FiscalData | Receipt and outlay timing, bank-channel bounds and the broad rest-of-world outlay profile |

Source notes:

- Publication 16 shares are annual and published with a lag of several years. Quarters beyond the age limit of the latest published tax year are excluded rather than extrapolated. When last checked (April 2026), no complete Publication 16 report later than tax year 2022 had been published.
- The Table 5.3 bank minor-industry rows are suppressed, so the stricter Table 5.3 route is unavailable.
- Annual account titles identify receipt lines but not the paying account or the quarterly cash timing, so every candidate stays outside the default. The OCC timing sensitivity applies OCC semiannual assessment due dates to annual OCC lines.

## Other Treasury datasets

`tdc download --include-treasury-support` also fetches Monthly Statement of the Public Debt (MSPD) marketable and full detail and State and Local Government Series (SLGS) data for supporting analysis.
