# Treasury-Attributed Component of Deposits (TDC)

[Live site](https://smkwray.github.io/tdcest/)

A public, self-contained repo for estimating the **treasury-attributed component of deposits (TDC)** — the portion of deposits that can be traced to Treasury operations, Treasury security transactions, and related reserve-user channels.

The project provides transparent data downloads, reproducible estimation pipelines, and an interactive static site for exploring results.

### Design choices

- **Transaction-based primary estimate.** The preferred baseline uses quarterly transaction data from the Federal Reserve's Z.1 Financial Accounts, which directly measure Treasury security flows rather than inferring them from holdings changes.
- **Bank-only headline with a broad-depository alternative.** The default estimate covers banks only. A separate series adds natural-person credit unions for a broader view.
- **Explicit credit-union handling.** Credit unions are broken out into separate series rather than folded into the headline, because the published aggregate includes non-marketable items (like the NCUA capitalization deposit) that don't belong in a marketable-Treasury estimate.
- **Sensitivity checks included.** Alternative methods (holdings-level changes, monetary decomposition) are provided alongside the primary estimate for comparison.
- **Marketable-Treasury focused.** Nonmarketable Treasury instruments are left for a future extension.
- **Fully offline capable.** A demo mode runs with synthetic data — no API keys or network access required.

## Preferred estimate

The recommended quarterly estimate of the treasury-attributed component of deposits is:

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

Credit unions are handled separately from banks because the published aggregate credit-union data include items that don't belong in a clean marketable-Treasury estimate.

### Bank-only headline (recommended default)

`tdc_base_bank_only_ru_flow`

Covers commercial banks, foreign banking offices, and banks in U.S.-affiliated areas. **Excludes all credit unions.**

### Broad-depository alternative

`tdc_base_broad_depository_np_cu_ru_flow`

Adds **natural-person credit unions** (the standard retail credit unions) to the bank-only estimate.

### Credit-union sensitivity ladder

Additional series let you see the effect of progressively including more credit-union categories:

- `tdc_broad_depository_np_corp_cu_ru_flow` — adds corporate credit unions
- `tdc_credit_union_aggregate_sensitivity` — adds all credit-union categories including the NCUA capitalization deposit, matching the broadest published aggregate

The reason for this separation: the published Z.1 aggregate credit-union Treasury series folds in the NCUA capitalization deposit, which is not a marketable Treasury security. Including it would distort the estimate.

## Why these choices

1. **Transaction data are more accurate** than holdings-level changes for measuring flows. Holdings changes can mix actual transactions with revaluations and other accounting adjustments, while transaction series directly measure what was bought and sold.
2. **Treasury operating cash** is the appropriate quarterly drain term — it captures how much cash Treasury pulled from the banking system.
3. **Fed remittances are capped at zero** because negative values on the H.4.1 report represent deferred-asset bookkeeping, not actual reverse cash transfers to Treasury.
4. **Credit unions are separated out** so users can choose whether to include them, rather than having them baked into the headline with non-marketable items attached.

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
- `examples/demo_build/data/figures/*.png`
- `examples/demo_build/data/site/bundle.json`

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

See `docs/roadmap.md` for the full roadmap with shipped, near-term, medium-term, and long-term items.

Near term:

1. Foreign-official vs private-foreign split
2. Treasury support dataset parsing improvements
3. ALFRED vintage support
4. Nonmarketable-Treasury extension with MSPD + SLGS mapping
5. Sibling holder-maturity project scaffolding
