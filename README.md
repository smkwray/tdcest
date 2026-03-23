# Treasury-Attributed Component of Deposits (TDC)

[Live site](https://smkwray.github.io/tdcest/)

A public, self-contained repo for estimating the **treasury-attributed component of deposits (TDC)** with transparent data downloads, reproducible pipelines, and static-site-ready outputs.

This repo is opinionated on purpose:

- It treats the **transaction-based RU-flow estimator** as the main baseline.
- It separates a **bank-only headline** from a **broad-depository alternative**.
- It handles **credit unions explicitly**, instead of silently folding the aggregate credit-union Treasury series into the baseline.
- It keeps **level-change** and **monetary-decomposition** approaches as sensitivity checks.
- It keeps the baseline **marketable-Treasury focused** and leaves nonmarketables for a future extension.
- It can run **fully offline** in demo mode with synthetic fixtures.

## Recommended baseline

The preferred quarterly marketable-Treasury estimator in this repo is:

```math
\widehat{\Delta D}^{mkt,bank}_{TDC,t}
=
\underbrace{\Delta TS^{tx}_{Fed,t} + \Delta TS^{tx}_{Banks,t} + \Delta TS^{tx}_{ROW,t}}_{\text{RU net acquisition of marketable Treasuries}}
-
\underbrace{\Delta Cash^{tx}_{Treasury,t}}_{\text{Treasury operating cash drain}}
+
\underbrace{Remit^{+}_{Fed,t}}_{\text{positive Fed remittances only}}
```

Where:

- `Fed` = monetary authority / Federal Reserve
- `Banks` = the bank-sector depository block used in the default headline:
  - U.S.-chartered depositories
  - foreign banking offices in the U.S.
  - banks in U.S.-affiliated areas
- `ROW` = rest of world
- `Remit^{+}` clips the Fed remittance series at zero because negative H.4.1 values represent the **deferred asset**, not negative cash remittances.

## Credit-union treatment

The repo now makes the deposit concept explicit.

### Bank-only headline

`tdc_base_bank_only_ru_flow`

This is the recommended default. It **excludes all credit-union Treasury transactions** from the headline RU term.

### Broad-depository alternative

`tdc_base_broad_depository_np_cu_ru_flow`

This adds **natural-person credit-union Treasury transactions** to the bank-sector block.

### Credit-union sensitivity ladder

The repo also publishes:

- `tdc_broad_depository_np_corp_cu_ru_flow` — adds corporate credit unions
- `tdc_credit_union_aggregate_sensitivity` — adds natural-person and corporate credit unions plus the NCUA capitalization deposit term, matching the broad published aggregate credit-union Treasury concept

This split is intentional. The published aggregate credit-union Treasury series in Z.1 is not a clean pure marketable-Treasury series for the broad-depository headline because it also folds in the NCUA capitalization deposit term.

## Why this baseline

1. **Transactions beat level changes** for the main estimate. Z.1 transaction series are closer to the flow concept than holdings-level changes, which can mix transactions, revaluations, and other volume changes.
2. **Treasury operating cash** is the better quarterly drain term for baseline estimation.
3. **Fed remittances should be positive-only** because negative H.4.1 values are deferred-asset accounting, not a reverse cash transfer to Treasury.
4. **Credit unions should be configurable by deposit concept** rather than hard-coded into the headline.

## What this repo includes

- Python package with CLI: `tdc`
- FRED download helpers
- Treasury Fiscal Data download helpers
- quarterly estimation pipeline
- chart generation
- static-site export bundle
- offline synthetic demo
- offline tests
- a minimal GitHub Pages site shell backed by the exported site bundle
- documentation for local private files and live-data setup

## Public repo conventions

- Keep all private material under `do/`. That directory is gitignored.
- The public repo and default CI do **not** require a FRED API key.
- Local environments and caches should live outside the repo under `$HOME/venvs`.
- Generated demo outputs are reproducible, but they are not checked into git.

## Quick start

### 1) Bootstrap the external environment

```bash
make bootstrap
```

This creates and uses `$HOME/venvs/tdcest` instead of an in-repo virtual environment.

You can also bootstrap directly with:

```bash
./scripts/bootstrap_env.sh
```

### 2) Run tests

```bash
make test
```

### 3) Run the offline demo

```bash
make demo
```

This writes:

- `examples/demo_build/data/processed/tdc_estimates.csv`
- `examples/demo_build/figures/*.png`
- `examples/demo_build/site/bundle.json`

These demo outputs are generated locally and are not tracked in git.

### 4) Download live data and build

```bash
$HOME/venvs/tdcest/bin/python scripts/build_all.py --required-only
```

Or, if you also want supporting Treasury datasets:

```bash
$HOME/venvs/tdcest/bin/python scripts/build_all.py --include-treasury-support
```

If you want to use the FRED API instead of the public graph CSV endpoint, load `FRED_API_KEY` from `do/.env` or your shell before running the live-data build.

### 5) Use the site bundle

The pipeline exports a single `data/site/bundle.json` file designed to be consumed by the static front end. Processed CSVs remain under `data/processed/`.

For setup details, local-private-file conventions, and cache locations, see `docs/local_development.md`.

## CLI overview

```bash
$HOME/venvs/tdcest/bin/tdc download --required-only
$HOME/venvs/tdcest/bin/tdc estimate
$HOME/venvs/tdcest/bin/tdc plot
$HOME/venvs/tdcest/bin/tdc site-export
$HOME/venvs/tdcest/bin/tdc build --required-only
$HOME/venvs/tdcest/bin/tdc demo
```

## Methods included

### 1) `tdc_base_bank_only_ru_flow`
Preferred headline.

Uses:
- Z.1/FRED marketable Treasury **transactions**
- Z.1/FRED Treasury operating cash **transactions**
- H.4.1/FRED Fed remittance/deferred-asset series, clipped at zero and aggregated to quarter sum

### 2) `tdc_base_broad_depository_np_cu_ru_flow`
Recommended broad-depository alternative.

Adds natural-person credit-union Treasury transactions to the bank-only block.

### 3) `tdc_broad_depository_np_corp_cu_ru_flow`
Sensitivity that also adds corporate credit-union Treasury transactions.

### 4) `tdc_credit_union_aggregate_sensitivity`
Sensitivity that matches the broad aggregate credit-union Treasury concept by adding the NCUA capitalization deposit term.

### 5) `tdc_domestic_bank_only_ru_flow`
Sensitivity method that excludes the rest-of-world term.

### 6) `tdc_no_remit_bank_only`
Sensitivity method that excludes Fed remittances.

### 7) `tdc_level_bank_only_sensitivity`
Optional method based on **level changes**. Included for comparison, not recommended as the headline estimator.

### 8) `tdc_level_broad_depository_np_cu_sensitivity`
Level-change broad-depository sensitivity with natural-person credit unions.

### 9) `tdc_decomposition_proxy_bank_centric`
Optional rough proxy based on money and bank-balance-sheet decomposition. It is intentionally labeled as a rough proxy.

## Default data mapping

### Core FRED series

- `BOGZ1FU713061103Q` — Monetary Authority; Total Treasury Securities; Asset, Transactions
- `BOGZ1FU763061100Q` — U.S.-Chartered Depository Institutions; Treasury Securities; Asset, Transactions
- `BOGZ1FU753061103Q` — Foreign Banking Offices in the U.S.; Treasury Securities; Asset, Transactions
- `BOGZ1FU743061103Q` — Banks in U.S.-Affiliated Areas; Treasury Securities; Asset, Transactions
- `BOGZ1FU473061103Q` — Credit Unions; Treasury Securities, Excluding Corporate Credit Unions; Asset, Transactions
- `BOGZ1FU473061153Q` — Credit Unions; Treasury Securities Held by Corporate Credit Unions; Asset, Transactions
- `BOGZ1FU473061203Q` — Credit Unions; NCUA Share Insurance Capitalization Deposit; Asset, Transactions
- `BOGZ1FU263061105Q` — Rest of the World; Treasury Securities; Asset, Transactions
- `BOGZ1FU313024000Q` — Federal Government; Treasury Operating Cash; Asset, Transactions
- `RESPPLLOPNWW` — Earnings Remittances Due to the U.S. Treasury (H.4.1 weekly level; positive-only flow proxy)

### Optional FRED series

- holdings-level analogs for the above RU Treasury series
- `BOGZ1FL313024000Q` — Treasury operating cash level
- `M2SL`
- `CURRCIR`
- `TOTBKCR`
- `WDTGAL`

### Optional Treasury support datasets

- Daily Treasury Statement operating cash balance
- Monthly Treasury Statement receipts
- MSPD marketable detail
- MSPD total detail
- SLGS securities

## Repo structure

```text
.
├── .github/workflows/pages.yml
├── docs/
├── site/
├── scripts/
├── src/tdc_estimator/
├── tests/
├── data/
└── pyproject.toml
```

## Static site and Pages

The repo includes a minimal static site shell for GitHub Pages. It reads the generated `bundle.json` site contract documented in:

- `docs/output_schema.md`
- `docs/methodology.md`

The public Pages URL is intended to be:

- `https://smkwray.github.io/tdcest/`

The public site is published from the committed `site/` directory, including the single-file bundle at `site/data/bundle.json`.

Refreshing the public site means updating that bundle and pushing `main`.

## Caveats

- The baseline is a **marketable-Treasury** estimator, not an all-liabilities Treasury estimator.
- The H.4.1 remittance series is a **weekly level** that becomes a usable cash-flow proxy only after clipping negatives and aggregating.
- The broad aggregate credit-union Treasury concept is kept as a **sensitivity**, not the headline, because it includes the NCUA capitalization deposit term.
- Treasury datasets can help for diagnostics and future extensions, but the base estimator is intentionally centered on Z.1 + H.4.1.
- This repo is a starter public repo, not a finished research monograph.

## Roadmap

1. Add nonmarketable-Treasury extension with MSPD + SLGS mapping
2. Add foreign-official vs private-foreign split
3. Add vintage tracking via ALFRED
4. Expand the GitHub Pages site
5. Add sibling holder-maturity project scaffolding
