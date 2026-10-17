# Treasury Deposit Component

[Methodology](docs/methodology.md) · [Output schema](docs/output_schema.md)

TDCest constructs public-data proxies for the **Treasury Deposit Component (TDC)**: deposit-settlement flows attributable to Treasury cash operations and Treasury-security transactions. It combines the Federal Reserve's Financial Accounts, Treasury cash and interest data, and sector holdings information in a quarterly measurement pipeline. It also provides separate Treasury component of reserves (TRC) diagnostics.

## What the estimates mean

The accounting object and the measured proxy are different. For an exact flow measured on the same clock and deposit perimeter, the accounting identity is deposit change = Treasury-attributed flow + all other deposit flows. Public data do not observe every settlement route, so TDCest's proxy can differ from that exact flow. A regression coefficient on the proxy is a conditional association; it is not the accounting coefficient, a causal effect, or a deposit-retention share.

The headline deposit perimeter is bank-only. A wider comparison includes natural-person credit unions. Sector labels describe the data inputs; settlement incidence follows the deposit claim credited or debited, rather than the holder's legal-sector label alone. Treasury transactions are marketable-security focused, so the proxy does not cover every Treasury liability or settlement channel.

## Measurement ladder

| Output | Construction and role |
|---|---|
| Uncorrected baseline | Treasury transaction flows, operating cash and positive Federal Reserve remittances |
| Federal Reserve coupon correction | Removes the estimated coupon-interest distortion from the baseline |
| Tier 2 component-anchored proxy | Allocates separate Treasury interest components and applies the preferred proportional money-market-fund / overnight reverse-repurchase adjustment |
| Long-history regression series | Extends the quarterly proxy using explicitly graded source and method support |
| Receipt and perimeter comparisons | Historical bank-receipt overlays, incomplete foreign-receipt sensitivities, and the wider credit-union perimeter |
| Tier 3 fiscal and monetary diagnostics | Reconciliation and sensitivity checks with unresolved components explicitly labeled |

Money-market funds (MMFs) and the Federal Reserve's overnight reverse-repurchase facility (ON RRP) require a source-of-funds adjustment. Its proportional allocation is a measurement assumption, with alternative routes retained as sensitivities. Receipt-side gaps remain visible and do not become zero corrections by default.

Interest allocation consumes [WAMEST](https://github.com/smkwray/wamest) maturity and instrument-composition estimates. These weights divide aggregate Treasury interest pools; they do not observe individual holders' receipts. Coupon accrual, bill discount, floating-rate interest, inflation-protected coupon interest, and inflation compensation remain separate components. Matching date, sector, component eligibility, and gross-holder evidence are required. Broad-debt maturity bounds and signed dealer or household residuals do not establish eligible gross Treasury holdings.

Interest allocation is therefore a substantive sensitivity of the deposit proxy. Source observability and denominator evidence remain separate from backcast method grades. Legacy yield-based allocation requires an explicit coupon-maturity proxy; duration and zero-coupon-equivalent maturity are not substitutes. See the [interest contract](docs/wamest_interest_output_contract.md).

## Install and validate

Requires Python 3.11 or later. From the repository root:

```bash
make bootstrap
make test
make demo
```

The bootstrap creates an external environment at `$HOME/venvs/tdcest`. Override it with `TDC_VENV=/path/to/environment`, or run targets with `PYTHON=/path/to/python`. The offline demo uses synthetic inputs and writes only to ignored `examples/demo_build/`; it needs no API key or network access.

The default test suite excludes the separately marked integration tests. Integration tests require the corresponding retained input artifacts and fail when those inputs are absent; they do not establish fresh upstream data.

## Build with public data

```bash
make build
```

This runs `scripts/build_all.py --required-only`. The public FRED graph endpoint is used without a key; an exported `FRED_API_KEY` selects the API path. Source acquisition needs network access. Additional Treasury support can be requested with:

```bash
"$HOME/venvs/tdcest/bin/python" scripts/build_all.py --include-treasury-support
```

A build creates local measurement outputs with their own coverage and provenance.

## Outputs

| Path | Use |
|---|---|
| `data/processed/tdc_downstream_handoff_bundle.json` | Entry point for local downstream analysis: estimator roles, boundaries, series and comparison snapshots |
| `data/processed/tdc_tier2_regression_series.csv` | Long-history quarterly proxy with source and method labels |
| `examples/demo_build/` | Synthetic demonstration outputs |

Raw downloads, processed tables, reports, caches, environments and demo outputs are local and ignored.

For a hash-bound treatment-leg decomposition, `tdc regression-leg-export --quarterly-sha256 HASH --regression-sha256 HASH` reads existing inputs from a clean committed checkout and writes a CSV plus receipt. It rejects changed inputs and reconciliation failures. The resulting accounting legs do not identify settlement routes or causal responses.

## Reserve diagnostics and measurement vintages

`tdc trc-export`, `tdc reserve-factor-ledger-export`, and `tdc weekly-trc-export` construct separate reserve-side accounting diagnostics. The weekly construction is a cash-corrected Wednesday proxy with explicit missing-data and unpriced-secondary-trade boundaries, plus route sensitivities. There is no preferred weekly series. See [weekly TRC conventions](docs/weekly_trc.md).

A measurement vintage changes sample endpoints without selecting a new method. The configured default `v1` ends at 2025Q4 for quarterly exports and 2025-12-31 for weekly exports. Later vintages use a separate ignored root, such as `data/refresh_<name>/`, and an explicit `--vintage`; they do not overwrite the default inputs.

## Documentation

- [Methodology](docs/methodology.md) and [equations](docs/equations.md)
- [Data sources](docs/data_sources.md)
- [Output schema](docs/output_schema.md)
- [Interest-allocation contract](docs/wamest_interest_output_contract.md)
- [Local development](docs/local_development.md)

Source code is under `src/tdc_estimator/` and command entry points under `scripts/`. See [LICENSE](LICENSE) for reuse terms.
