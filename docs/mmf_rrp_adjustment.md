# MMF/ON RRP adjustment

This note defines the money-market-fund (MMF) adjustment for Federal Reserve overnight reverse repo (ON RRP) funding in the Tier 2 ladder. The adjustment uses SEC Form N-MFP fund-month filings; Office of Financial Research (OFR) aggregate data serve as a source comparison.

## Motivation

MMF Treasury purchases funded by running down Federal Reserve reverse-repo positions are not the same deposit-incidence event as MMF Treasury purchases funded by new domestic nonbank deposits. The aggregate quarterly diagnostic

```text
min(max(0, change in MMF Treasury bills), max(0, -change in ON RRP))
```

captures the basic direction, but it is too coarse for a preferred estimator because total ON RRP is not MMF-only and quarterly netting can miss within-quarter rotations.

## Fund-month adjustment

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
prop  = min(upper, rrp_runoff * treasury_increase / (treasury_increase + other_uses))
lower = min(treasury_increase, max(0, rrp_runoff - other_uses))
```

Fed RRP positions are set to zero before the ON RRP facility began (September 2013). A missing Fed RRP position is also read as zero before the change is taken, so a missing observation that follows a positive position would appear as runoff. The SEC fund-month file behind the published estimates has no missing Fed RRP positions.

Changes are measured against a fund's previous filing. When a fund files only a notice of late filing (Form NT N-MFP) for a month and no holdings report for that month follows, the next change spans two months. Net holdings changes still add up across the gap, but the adjustment applies positive parts, minima and a proportional split to each change, so a missing month can change both the timing and the size of the estimated adjustment, and its allocation cannot be recovered from the neighbouring filings. In the SEC data through 2025 this affects 231 of about 56,000 fund-month steps, concentrated in September 2018 (37 funds) and March 2021 (29 funds), when groups of funds filed notices only.

The same lower/proportional/upper family is also emitted for bills-only Treasury increases as a robustness check.

## Estimator rows

When `data/raw/support__mmf_fund_month.csv` is present, the pipeline writes:

- `tdc_mmf_rrp_fund_month_adjustments.csv`
- `tdc_mmf_rrp_quarterly_adjustments.csv`
- `tdc_mmf_rrp_adjustment.md`
- `tdc_mmf_rrp_source_comparison.csv` and `.md`, when `data/raw/support__mmf_fund_month_ofr_aggregate.csv` is also present

The quarterly adjustment columns are merged into `quarterly_inputs.csv`, and the estimator adds each of them to the Tier 2 rows:

- `tdc_tier2_mmf_rrp_{lb,prop,ub}_bank_only_ru_flow`
- `tdc_tier2_mmf_rrp_{lb,prop,ub}_broad_depository_np_cu_ru_flow`
- `tdc_tier2_mmf_rrp_{lb,prop,ub}_depository_institution_np_cu_ru_flow`, when credit-union interest support is present

These rows build on the component-anchored Tier 2 rows when component support is present, and on the H.15 rows otherwise; explicitly named `tdc_tier2_component_anchored_mmf_rrp_*` and `tdc_tier2_h15_mmf_rrp_*` rows are also written. The canonical Tier 2 row uses the proportional adjustment. The lower and upper rows are bounds.

## Input contract

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

## OFR aggregate bridge

The command below writes the OFR aggregate MMF dataset into the support-file shape, at `data/raw/support__mmf_fund_month_ofr_aggregate.csv`:

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

The aggregate cannot allocate purchases fund by fund, so the estimator does not read it. To run the adjustment on the aggregate anyway, pass `--out data/raw/support__mmf_fund_month.csv` explicitly.

## SEC Form N-MFP fund-level bridge

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

For each fund and report date, the filing with the latest filing date is kept. Two different filings on that same latest date stop the build rather than being resolved arbitrarily, so the result does not depend on archive order. Feeder funds are excluded to avoid double counting with their master portfolios, which are kept; with this rule, totals closely match the OFR aggregate scale. Treasury totals are summed from `U.S. Treasury Debt` holdings. Treasury bills are identified by bill CUSIP prefixes (`912796`, `912797`) or bill security titles. Fed RRP is identified from repurchase-agreement rows whose issuer or title names the Federal Reserve or FRBNY.

When both the SEC fund-level file and the OFR aggregate file are present, the pipeline writes a source-comparison artifact. That comparison is not an alternate estimator; it documents why the SEC fund-level proportional allocation is preferred and shows where aggregate netting materially changes the MMF/RRP adjustment.

## Boundary rule

This adjustment is specific to MMF Treasury acquisition funded by MMF Fed RRP runoff. GSE RRP runoff and broker/dealer Treasury inventory should remain separate diagnostics unless their funding source is identified tightly enough to support estimator inclusion.
