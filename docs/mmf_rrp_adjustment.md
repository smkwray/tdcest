# MMF/RRP Adjustment

This note defines the money-market-fund reverse-repo adjustment for the Tier 2 TDC ladder.

## Status

The preferred MMF/RRP adjustment now uses the SEC Form N-MFP fund-month support file. The OFR aggregate bridge remains a fallback and source-comparison check.

## Motivation

MMF Treasury purchases funded by running down Federal Reserve reverse-repo positions are not the same deposit-incidence event as MMF Treasury purchases funded by new domestic nonbank deposits. The aggregate quarterly diagnostic

```text
min(max(0, change in MMF Treasury bills), max(0, -change in ON RRP))
```

captures the basic direction, but it is too coarse for a preferred estimator because total ON RRP is not MMF-only and quarterly netting can miss within-quarter rotations.

## Fund-Month Adjustment

For fund `i` in month `m`, the normalized support file supplies:

- Federal Reserve RRP or repo-with-Fed position.
- Treasury bills.
- Other Treasury securities.
- Non-Treasury, non-Fed-RRP assets.
- NAV or total net assets.

The builder computes:

```text
rrp_runoff = max(0, -change in Fed RRP)
treasury_increase = max(0, change in total Treasury securities)
other_uses = max(0, change in non-Treasury/non-Fed-RRP assets) + max(0, -change in NAV)
```

Then it emits:

```text
upper = min(treasury_increase, rrp_runoff)
prop  = rrp_runoff * treasury_increase / (treasury_increase + other_uses)
lower = min(treasury_increase, max(0, rrp_runoff - other_uses))
```

The same lower/proportional/upper family is also emitted for bills-only Treasury increases as a robustness check.

## Estimator Rows

When `data/raw/support__mmf_fund_month.csv` is present, the pipeline writes:

- `tdc_mmf_rrp_fund_month_adjustments.csv`
- `tdc_mmf_rrp_quarterly_adjustments.csv`
- `tdc_mmf_rrp_adjustment.md`
- `tdc_mmf_rrp_source_comparison.csv`, when the OFR aggregate fallback file is present
- `tdc_mmf_rrp_source_comparison.md`, when the OFR aggregate fallback file is present

The quarterly adjustment columns are merged into `quarterly_inputs.csv`, and `compute_estimates` emits candidate Tier 2 rows:

- `tdc_tier2_mmf_rrp_prop_bank_only_ru_flow`
- `tdc_tier2_mmf_rrp_lb_bank_only_ru_flow`
- `tdc_tier2_mmf_rrp_ub_bank_only_ru_flow`
- `tdc_tier2_mmf_rrp_prop_broad_depository_np_cu_ru_flow`
- `tdc_tier2_mmf_rrp_prop_depository_institution_np_cu_ru_flow`, when the credit-union interest proxy is present.

The preferred candidate is the proportional adjustment. The lower and upper rows are bounds.

## Input Contract

The raw fund-month support file should be normalized before use. Accepted column names are intentionally flexible, but the clean preferred names are:

```text
date
fund_id
fed_rrp
treasury_bills
treasury_other
non_treasury_non_fed_rrp_assets
nav
```

If `treasury_total` is present, it is used directly. Otherwise total Treasury securities are `treasury_bills + treasury_other`.

## OFR Aggregate Bridge

The command below writes the current aggregate OFR MMF dataset into the support-file shape:

```bash
tdc mmf-rrp-support
```

It uses the OFR Short-term Funding Monitor API dataset endpoint:

```text
https://data.financialresearch.gov/v1/series/dataset?dataset=mmf
```

The aggregate bridge maps:

- `MMF-MMF_RP_wFR-M` to `fed_rrp`
- `MMF-MMF_T_TOT-M` to `treasury_total`
- `MMF-MMF_OA_TOT-M` to `non_treasury_non_fed_rrp_assets`
- `MMF-MMF_TOT-M` to `nav`

This aggregate bridge is enough to run a candidate monthly MMF/RRP correction. It is not a substitute for a final fund-level N-MFP allocation, but it is materially better than quarterly total ON RRP netting.

## SEC Form N-MFP Fund-Level Bridge

The fund-level command normalizes official SEC Form N-MFP ZIP files into the same support-file shape:

```bash
tdc sec-nmfp-mmf-support --download --start 2024-01-31 --end 2024-03-31
```

or, for already-downloaded ZIP files:

```bash
tdc sec-nmfp-mmf-support --zip data/raw/sec_nmfp_cache/2024-03_nmfp.zip
```

The parser uses:

- `NMFP_SUBMISSION.tsv` for report date, filing date, fund series id, and amendments
- `NMFP_SERIESLEVELINFO.tsv` for NAV, cash, portfolio securities, other assets, and feeder/master flags
- `NMFP_SCHPORTFOLIOSECURITIES.tsv` for Treasury securities and Federal Reserve repo holdings

For duplicate fund-month filings, the latest filing or amendment is retained. Feeder funds are excluded to avoid feeder/master double counting, while master portfolios are retained; this matches the OFR aggregate scale closely in current files. Treasury totals are summed from `U.S. Treasury Debt` holdings, Treasury bills are identified from Treasury-bill security titles, and Fed RRP is identified from repurchase-agreement rows whose issuer/title names the Federal Reserve or FRBNY.

When both the SEC fund-level file and OFR aggregate fallback are present, the pipeline writes a source-comparison artifact. That comparison is not an alternate estimator; it documents why the SEC fund-level proportional allocation is preferred and shows where aggregate netting materially changes the MMF/RRP adjustment.

## Boundary Rule

This adjustment is specific to MMF Treasury acquisition funded by MMF Fed RRP runoff. GSE RRP runoff and broker/dealer Treasury inventory should remain separate diagnostics unless their funding source is identified tightly enough to support estimator inclusion.
