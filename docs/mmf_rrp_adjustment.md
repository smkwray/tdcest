# Money-Market-Fund ON RRP Term

Money market funds (MMFs) sit inside the deposit-user sector, so an ordinary MMF Treasury purchase paid from a commercial-bank deposit leaves aggregate deposits unchanged. When an MMF instead pays for Treasury securities by running down overnight reverse repurchase agreements (ON RRP) at the Federal Reserve, the transaction shifts Federal Reserve liabilities from ON RRP into the Treasury General Account (TGA), bypassing deposit accounts. Without a term for that funding path, the increase in TGA makes the Treasury-side calculation understate TDC.

From 2013Q3 onward, `tdcest` adds back the estimated share of MMF Treasury purchases funded out of ON RRP runoffs using fund-month SEC Form N-MFP filings. Because ON RRP began on September 23, 2013 (`2013-09-23`), the term is zero before 2013Q3.

## Fund-month accounting formulas

For each fund $i$ and consecutive reporting month $m$, define balance-sheet levels in USD millions:

- $R_{i,m}$: ON RRP holdings at the Federal Reserve (`fed_rrp`), forced to $0$ before `2013-09-23`
- $T_{i,m}$: total Treasury holdings (`treasury_total`)
- $O_{i,m}$: non-Treasury, non-ON RRP assets (`non_treasury_non_fed_rrp_assets`)
- $A_{i,m}$: net asset value (`nav`)

Month-to-month changes are taken only between consecutive calendar months (a one-month step within each fund). Define positive ON RRP runoff, Treasury purchases, and other funding uses as:

$$
\Delta R_{i,m}^{-} = \max(0,\, -(R_{i,m} - R_{i,m-1})),
$$

$$
\Delta T_{i,m}^{+} = \max(0,\, T_{i,m} - T_{i,m-1}),
$$

$$
U_{i,m} = \max(0,\, O_{i,m} - O_{i,m-1}) + \max(0,\, -(A_{i,m} - A_{i,m-1})).
$$

Because Form N-MFP reports month-end holdings without payment links between individual trades, `tdcest` computes a proportional allocation together with lower and upper bounds:

$$
\mathrm{UB}_{i,m} = \min(\Delta T_{i,m}^{+},\, \Delta R_{i,m}^{-}),
$$

$$
\mathrm{PROP}_{i,m} = \min\!\left(\mathrm{UB}_{i,m},\; \Delta R_{i,m}^{-} \cdot \frac{\Delta T_{i,m}^{+}}{\Delta T_{i,m}^{+} + U_{i,m}}\right),
$$

$$
\mathrm{LB}_{i,m} = \min\!\left(\Delta T_{i,m}^{+},\; \max(0,\, \Delta R_{i,m}^{-} - U_{i,m})\right).
$$

When $\Delta T_{i,m}^{+} + U_{i,m} = 0$, $\mathrm{PROP}_{i,m} = 0$. By construction, $0 \le \mathrm{LB}_{i,m} \le \mathrm{PROP}_{i,m} \le \mathrm{UB}_{i,m}$.

Quarterly totals sum the three monthly values across all funds in each calendar quarter:

$$
\Gamma_t^{k} = \sum_{m \in q(t)} \sum_i k_{i,m}, \qquad k \in \{\mathrm{LB},\, \mathrm{PROP},\, \mathrm{UB}\}.
$$

The main TDC series uses $\Gamma_t^{\mathrm{PROP}}$, with $\Gamma_t^{\mathrm{LB}}$ and $\Gamma_t^{\mathrm{UB}}$ reported alongside it. The same three formulas are also evaluated on Treasury bills (`treasury_bills`) when that column is populated, producing a bills-only check.

## Input file schema

Place the fund-month file at `data/raw/support__mmf_fund_month.csv` (USD millions):

| Column | Required | Description |
|---|---|---|
| `date` | Yes | Month-end reporting date (`YYYY-MM-DD`) |
| `fund_id` | Yes | Unique fund or series identifier |
| `fed_rrp` | Yes | ON RRP at the Federal Reserve (missing values filled with `0`) |
| `treasury_total` | Yes | Total Treasury security holdings |
| `non_treasury_non_fed_rrp_assets` | Yes | All other portfolio assets |
| `nav` | Yes | Fund net asset value |
| `treasury_bills` | No | Treasury bill holdings for the bills-only check |
| `source_mode` | No | Provenance label (for example `sec_nmfp_fund_month`) |

## Building the input from SEC Form N-MFP

`tdc sec-nmfp-mmf-support` parses SEC Form N-MFP quarterly bulk ZIP archives (`NMFP_SUBMISSION.tsv`, `NMFP_SERIESLEVELINFO.tsv`, and `NMFP_SCHPORTFOLIOSECURITIES.tsv`) into `data/raw/support__mmf_fund_month.csv`:

```bash
tdc sec-nmfp-mmf-support --zip-dir path/to/sec_nmfp_zips
```

Parser rules in `src/tdc_estimator/mmf_rrp.py`:

- Multiple filings for the same `(fund_id, REPORTDATE)` keep the latest `FILING_DATE`; same-day duplicate accession numbers raise an error.
- Feeder funds (`FEEDERFUNDFLAG == "Y"`) are excluded to avoid double-counting master-feeder holdings.
- Dollar amounts are converted from USD to USD millions (`1e6`), using `EXCLUDINGVALUEOFANYSPONSORSUPP` with fallback to `INCLUDINGVALUEOFANYSPONSORSUPP`.
- Treasury holdings match `INVESTMENTCATEGORY` containing `U.S. Treasury Debt`; Treasury bills match CUSIP prefixes `912796` or `912797` or titles matching `Treasury Bill`, `T-Bill`, or `Bill`.
- Federal Reserve ON RRP matches `Repurchase Agreement` rows whose issuer or title matches `Federal Reserve`, `Federal Reserve Bank of New York`, or `FRBNY`.
- If a fund skips a monthly filing (for example, after a Form NT N-MFP filing), no difference is taken across the multi-month gap. In the 2013-09 through 2025-12 SEC N-MFP file (`56,434` fund-months across `666` funds), `231` of `55,768` inter-filing steps span more than one month (the largest clusters skip September 2018 with `37` funds and March 2021 with `29` funds).

## OFR aggregate comparison file

`tdc mmf-rrp-support` downloads the Office of Financial Research (OFR) aggregate MMF dataset (`https://data.financialresearch.gov/v1/series/dataset?dataset=mmf`) and writes `data/raw/support__mmf_fund_month_ofr_aggregate.csv` using `MMF-MMF_RP_wFR-M` (`fed_rrp`), `MMF-MMF_T_TOT-M` (`treasury_total`), `MMF-MMF_OA_TOT-M` (`non_treasury_non_fed_rrp_assets`), and `MMF-MMF_TOT-M` (`nav`), all scaled by `1e6`. When that file is present, `tdc estimate` writes a comparison against the fund-month SEC series so aggregation bias can be checked; the OFR file is never substituted into the main TDC series.

## Outputs and active-quarter rules

Before 2013Q3, `mmf_route_bounds` sets the MMF term to `0` (`structural_zero_pre_on_rrp_mechanism`). From 2013Q3 onward, unobserved quarters stay missing (`missing_active_period`), except when `lb` is missing while `prop` and `ub` are both zero.

Running `tdc estimate` with `data/raw/support__mmf_fund_month.csv` writes:

- `data/processed/tdc_mmf_rrp_fund_month_adjustments.csv`
- `data/processed/tdc_mmf_rrp_quarterly_adjustments.csv`
- `data/processed/tdc_mmf_rrp_adjustment.md`
- `data/processed/tdc_mmf_rrp_scale_audit.csv` and `.md`
- `data/processed/tdc_mmf_rrp_source_comparison.csv` and `.md` (when the OFR file exists)

The quarterly columns `mmf_rrp_adjustment_lb`, `mmf_rrp_adjustment_prop`, and `mmf_rrp_adjustment_ub` enter `data/processed/tdc_components.csv`, `data/processed/tdc_estimates.csv`, and `data/processed/tdc_tier2_regression_series.csv` (where `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` is the main series, alongside `lb` and `ub` columns).

## Limits

- Month-end snapshots cannot observe intra-month turnover or separate MMF purchases paid from bank deposits versus ON RRP runoffs directly; the `[LB, UB]` interval reflects that measurement ambiguity.
- Only the runoff-into-Treasury direction is modeled directly from fund-month snapshots; reverse flows (Treasury redemptions flowing into ON RRP) and GSE ON RRP activity are checked separately (`tdc gse-on-rrp-support` and the weekly reserve-side scenarios in `docs/weekly_trc.md`).
