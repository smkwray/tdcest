# TDCest

TDCest estimates the **Treasury Deposit Component (TDC)**: the part of quarterly U.S. deposit change linked to Treasury cash operations and Treasury-security transactions. It also builds a reserve-side counterpart, the **Treasury component of reserves (TRC)**, at quarterly, monthly and weekly frequency.

Every input is public. The main sources are the Federal Reserve's Financial Accounts of the United States (Z.1) and H.4.1 release, Treasury cash and debt data, System Open Market Account (SOMA) holdings, SEC Form N-MFP money-market-fund filings, and Treasury holder-maturity estimates from [WAMEST](https://github.com/smkwray/wamest).

[Methodology](docs/methodology.md) · [Equations](docs/equations.md) · [Data sources](docs/data_sources.md) · [Output schema](docs/output_schema.md)

## What the estimates measure

Deposit change equals the Treasury-attributed flow plus all other deposit flows, provided both are measured on the same clock and the same deposit perimeter. Public data do not show every settlement route, so TDCest publishes a **proxy** for the Treasury-attributed flow. Three limits apply:

- The proxy can differ from the exact flow. A regression coefficient on the proxy is a conditional association. It is not the accounting coefficient, a causal effect, or a deposit-retention share.
- Sector labels describe the data inputs. Settlement incidence follows the deposit account that is credited or debited, not the holder's legal sector alone.
- The proxy covers marketable Treasury securities. It does not cover every Treasury liability or settlement channel.

## Measurement ladder

The baseline, in USD millions per quarter, is

```
TDC = Treasury-security transactions by the Fed, banks and the rest of the world
      − change in Treasury operating cash
      + positive Federal Reserve remittances to Treasury
```

Each tier refines the one before it:

| Tier | Construction | Role |
|---|---|---|
| 0. Baseline | Z.1 Treasury transactions, Treasury operating cash, Fed remittances | Ladder input |
| 1. Fed coupon correction | Removes coupon interest paid on SOMA holdings | Ladder input |
| 2. Interest and money-fund correction | Removes Treasury interest paid to banks, credit unions and the rest of the world, by component, and applies the money-market-fund / ON RRP source-of-funds adjustment | Canonical quarterly measure |
| Long-history regression series | Extends Tier 2 back to 2002Q1 with graded backcasts | Preferred series for regressions |
| 3. Fiscal and monetary diagnostics | Receipt-side, perimeter and monetary-aggregate cross-checks | Diagnostic only |

**Deposit perimeter.** The baseline headline is bank-only: U.S.-chartered depository institutions, foreign banking offices in the U.S., and banks in U.S.-affiliated areas. The canonical Tier 2 row widens this to depository institutions by adding natural-person credit unions. Corporate credit unions, the NCUA capitalization deposit, domestic-only, no-remittance and holdings-level variants are sensitivities.

**Interest allocation.** WAMEST maturity and instrument-composition weights divide aggregate Treasury interest pools across holder sectors. The weights do not observe what any holder actually received. Coupon accrual, bill discount, floating-rate note (FRN) interest, inflation-protected (TIPS) coupon interest and TIPS inflation compensation stay separate, and an allocation needs matching date, sector, component eligibility and gross-holder evidence. The choice of allocation materially affects the proxy. See the [interest-allocation contract](docs/wamest_interest_output_contract.md).

**Money-market funds.** A money-market fund (MMF) that buys Treasury securities by running down its overnight reverse repo (ON RRP) at the Federal Reserve does not draw on bank deposits, but the baseline counts the resulting rise in Treasury cash as a deposit drain. The adjustment adds those purchases back. The preferred version allocates each fund's purchases proportionally between ON RRP runoff and other funding, using SEC Form N-MFP filings; lower and upper bounds are published alongside it. See [MMF/ON RRP adjustment](docs/mmf_rrp_adjustment.md).

Receipt-side corrections that public sources cannot support stay out of the default rows and are reported separately as sensitivities.

## Which series to use

| Purpose | Series | File |
|---|---|---|
| Canonical quarterly measure | `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow` | `tdc_estimates.csv` |
| Regressions over a long sample | `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow`, with its method-tier columns | `tdc_tier2_regression_series.csv` |
| Credit-union-consistent comparison | `tdc_tier2_regression_mmf_rrp_prop_depository_institution_np_cu_ru_flow` | `tdc_tier2_regression_series.csv` |
| Ladder inputs | `tdc_base_bank_only_ru_flow`, `tdc_base_broad_depository_np_cu_ru_flow` | `tdc_estimates.csv` |

The canonical row covers only the quarters that component-level interest support reaches; earlier quarters are left empty rather than backfilled. The regression series fills the longer sample with backcasts whose method tier is recorded for every quarter, so analyses can split or weight by it. All other columns are sensitivities or diagnostics; [the output schema](docs/output_schema.md) describes each one.

## Install and validate

Requires Python 3.11 or later. From the repository root:

```bash
make bootstrap   # create the environment and install the package
make test        # default test suite
make demo        # offline demonstration on synthetic data
```

`make bootstrap` creates a virtual environment at `$HOME/venvs/tdcest`. Set `TDC_VENV=/path/to/environment` to put it elsewhere, or pass `PYTHON=/path/to/python` to any target. The demo needs no network access or API key and writes only to `examples/demo_build/`.

The default suite excludes tests marked `integration`. Those tests reproduce retained local outputs, need the corresponding input files, and fail when the inputs are absent. Run them with `pytest -m integration`.

## Build from public data

```bash
make build
```

`make build` downloads the baseline Z.1 series and the H.4.1 remittance series from FRED, then writes the estimates, figures and JSON export bundles. If a required series fails to download, the build stops; failures of optional series are listed in `data/raw/manifest_fred.json`. Without an API key it uses FRED's public graph endpoint; export `FRED_API_KEY` to use the API instead. To also download supporting Treasury FiscalData datasets:

```bash
"$HOME/venvs/tdcest/bin/python" scripts/build_all.py --include-treasury-support
```

The baseline needs only the downloaded series. Tiers 1 and 2 also need support files built from SOMA holdings, Treasury auction and interest data, SEC N-MFP filings and a WAMEST checkout. Each support builder is a `tdc` subcommand (`tdc --help` lists them), and the [data sources](docs/data_sources.md) page describes their inputs. Tier 1 and Tier 2 rows are produced only when their support files are present.

## Reserve-side diagnostics

| Command | Output |
|---|---|
| `tdc trc-export` | Quarterly TRC components, series and settlement-route registry |
| `tdc reserve-factor-ledger-export` | H.4.1 Wednesday reserve-factor ledger and its bridges to quarterly TRC |
| `tdc weekly-trc-export` | Weekly cash-corrected core proxy with signed route scenarios |
| `scripts/export_trc_monthly.py` | Monthly TRC on a last-Wednesday clock |
| `tdc bank-composition-export` | Descriptive U.S.-chartered bank balance-sheet composition |

The `tdc` export commands take SHA-256 pins for their inputs, either directly or through an acquisition manifest, and stop if an input does not match. They must run from a clean committed checkout, so that each JSON receipt names the commit that produced it. The monthly script records input and output hashes in its receipt. Source files are acquired with `scripts/acquire_trc_inputs.py`, which runs [fiscus](https://github.com/smkwray/fiscus) through [uv](https://docs.astral.sh/uv/) and records every retrieval in a manifest. The weekly series has no preferred variant; see [weekly TRC conventions](docs/weekly_trc.md).

`tdc regression-leg-export` writes a hash-bound decomposition of the regression series into accounting legs. The legs do not identify settlement routes or causal responses.

## Measurement vintages

A measurement vintage fixes the sample endpoint without changing the method. The default vintage `v1` ends at 2025Q4 for the quarterly TDC and TRC exports and at 2025-12-31 for the weekly export. A later vintage is built in its own directory tree, such as `data/refresh_<name>/`, with an explicit `--vintage` argument, and never overwrites the default inputs. The certified Tier 2 component support (`tdc tier2-component-support-export --vintage <name>`) covers 2022Q1 through the vintage endpoint, and the estimator loads it only when its window matches a registered vintage.

## Outputs

Raw downloads, processed tables, figures, caches and demo outputs are generated locally and are not tracked. The main processed outputs, all under `data/processed/`, are:

| File | Contents |
|---|---|
| `tdc_estimates.csv` | Quarterly estimator ladder: every tier, perimeter and sensitivity |
| `tdc_tier2_regression_series.csv` | Long-history regression series with source and method labels |
| `tdc_downstream_handoff_bundle.json` | Machine-readable summary of estimator roles, boundaries and latest values |
| `trc_*_v1.csv`, `reserve_factor_*_v1.csv` | Reserve-side diagnostics, each with a JSON receipt of its inputs and outputs |

## Repository layout

| Path | Contents |
|---|---|
| `src/tdc_estimator/` | Package and the `tdc` command-line interface |
| `scripts/` | Build, acquisition and export entry points |
| `config/` | Source catalog overlays |
| `docs/` | Methodology, equations, data sources and output schema |
| `tests/` | Test suite with synthetic fixtures |

## License

MIT. See [LICENSE](LICENSE).
