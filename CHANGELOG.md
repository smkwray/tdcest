# Changelog

## Unreleased

### Estimation

- Component-anchored Tier 2 rows: official Treasury coupon-accrual, bill-discount and FRN interest pools are allocated to bank, rest-of-world and credit-union holders with source-constrained WAMEST weights. They replace the H.15 coupon-intensity rows as the default; the H.15 rows remain as `tdc_tier2_h15_*` sensitivities.
- Canonical Tier 2 row `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow`: the depository-institution perimeter with the proportional MMF/ON RRP adjustment.
- MMF/ON RRP source-of-funds adjustment built from SEC Form N-MFP fund-month filings, with lower and upper bounds. N-MFP amendment selection no longer depends on archive order, and bills are classified by CUSIP.
- Long-history regression series from 2002Q1, with a method tier and source-observability labels for every quarter.
- WAMEST interest weights are checked for units, gross-holder eligibility and matching date, sector and component before allocation; missing or malformed eligibility stops the build.
- Hash-pinned export of the regression series as reconciled accounting legs (`tdc regression-leg-export`).
- The Treasury operating-cash term excludes Treasury–Federal Reserve internal transfers: equity paid into and returned from the Federal Reserve credit-facility LLCs and the LLCs' purchases and redemptions of nonmarketable Treasury securities. A dated ledger (`tdc treasury-fed-transfer-export`) builds them from the Daily Treasury Statement, matched to the H.4.1 Treasury-contributions liability, split by documented settlement account and reconciled to the Z.1 LLC holdings level, and writes the required support series `treasury_fed_internal_cash_tx`. Incomplete Domestic Series input fails. The correction applies to quarterly TDC and its level-change sensitivities, the regression legs, quarterly and weekly TRC, the reserve-factor bridges and the deficit comparison.
- Route-scope context outputs: monetary route bridge, MMF route split, route admissibility registry and Z.1 domestic nonbank sector context.

### Treasury component of reserves

- Quarterly TRC export (`tdc trc-export`) with a claim-based settlement-route registry and inputs acquired through fiscus.
- H.4.1 Wednesday reserve-factor ledger with bridges to quarterly TRC (`tdc reserve-factor-ledger-export`).
- Weekly cash-corrected TRC proxy with signed route scenarios (`tdc weekly-trc-export`).
- Monthly TRC on a last-Wednesday clock (`scripts/export_trc_monthly.py`).
- Descriptive U.S.-chartered bank balance-sheet composition tables (`tdc bank-composition-export`).

### Infrastructure

- Measurement vintages (`--vintage`) set sample endpoints without changing methods.
- Repository hygiene checks for tracked files.
- `make bootstrap` installs into the new environment instead of the system interpreter.

## v0.2.0

- Changed the default headline from an all-depository baseline to a bank-only baseline.
- Added a broad-depository alternative that includes natural-person credit unions.
- Added credit-union sensitivities: corporate credit unions, and an aggregate credit-union measure that includes the NCUA capitalization deposit.
- Added the [credit-union treatment](docs/credit_union_treatment.md) note.
- Updated the README, methodology and output schema for the new estimator family.
- Regenerated the offline demo outputs and figures.
- Removed machine-specific absolute paths from exported metadata.
