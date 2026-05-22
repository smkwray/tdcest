# Treasury Deposit Component (TDC)

[Live site](https://smkwray.github.io/tdcest/)

`tdcest` is a public research repo about a practical macro question: **how much of deposit change is linked to Treasury operations?**

More specifically, it estimates the **Treasury Deposit Component**: the part of deposit change associated with Treasury cash movements, Treasury security settlement, and related channels in the banking system.

The project combines:
- reproducible public-data downloads
- a quarterly estimation pipeline
- a static site for reading the results in plain English

It is meant for researchers, macro analysts, policy readers, and technically curious users who want a transparent public estimate rather than a black-box series.

## What this repo is for

This repo is meant to answer a simple question:

**How much of deposit change can reasonably be attributed to Treasury-related flows?**

It does that with a step-by-step estimate rather than a single black-box series. The site and exported outputs show:
- the main current estimate
- the correction steps that move it
- historical receipt overlays that are usable only in earlier periods where the evidence is fresh enough
- sensitivity views and diagnostic cross-checks that should not be mistaken for the main public estimate

## Current estimate structure

The main public sequence is:

1. **Uncorrected baseline**
   Built from marketable Treasury transaction flows, Treasury operating cash, and positive Fed remittances.
2. **After Fed coupon correction**
   Removes the Fed coupon-flow distortion from the raw baseline.
3. **Canonical Tier 2 deposit component**
   Adds the current component-anchored interest corrections and the preferred proportional MMF/RRP source-of-funds adjustment.
4. **Long-history regression row**
   Keeps a longer 2002Q1-forward regression/MMF-RRP row for downstream empirical work where the modern component-anchored row is too short.

The repo also keeps several related surfaces visible:
- **Broad-depository alternative**
  Adds natural-person credit unions for a wider perimeter comparison.
- **Historical bank-receipt overlay**
  A historical-only overlay for periods where bank receipt evidence is strong enough to use directly.
- **Foreign-receipt sensitivity**
  A small recurring foreign-receipt comparison kept separate from the main estimate because the public evidence is still incomplete.
- **Partial fiscal shell**
  A diagnostic Tier 3 surface that keeps unresolved current bank and foreign receipt cells below headline status.
- **Monetary cross-check**
  A diagnostic surface used for interpretation and stress testing, not as the main estimate.

## Theory and measurement

The project distinguishes between:
- **theoretical accounting identities**
- **measured approximations built from public data**

The site shows both layers explicitly. The theoretical identities explain what TDC is conceptually; the live estimators are narrower practical measurements with documented boundaries.

For details:
- [Methodology](docs/methodology.md)
- [Equations](docs/equations.md)
- [Output schema](docs/output_schema.md)

## Main public outputs

The most important machine-readable outputs are:
- [`site/data/bundle.json`](site/data/bundle.json) for the static site
- `data/processed/tdc_downstream_handoff_bundle.json` for downstream analytical use after a local pipeline run

`data/processed/` is generated and intentionally not committed. The handoff bundle is the best single entrypoint for downstream work after regeneration because it gathers:
- estimator roles
- receipt boundaries
- use-case routing
- problem-variable summaries
- latest series and comparison snapshots

## Quick start

### 1. Bootstrap the environment

```bash
make bootstrap
```

This uses an external virtual environment under `$HOME/venvs/tdcest` rather than creating one inside the repo.

### 2. Run tests

```bash
make test
```

### 3. Run the offline demo

```bash
make demo
```

The demo build writes synthetic outputs under `examples/demo_build/` and does not require network access or API keys.

### 4. Build from live data

```bash
$HOME/venvs/tdcest/bin/python scripts/build_all.py --required-only
```

To include supporting Treasury datasets too:

```bash
$HOME/venvs/tdcest/bin/python scripts/build_all.py --include-treasury-support
```

If you want to use the FRED API instead of the public graph CSV endpoint, set `FRED_API_KEY` in your shell before running the live-data build.

### 5. Export the site bundle directly

```bash
$HOME/venvs/tdcest/bin/tdc site-export
```

## Static site

The public site lives under `site/` and is published from that directory.

Core files:
- `site/index.html`
- `site/styles.css`
- `site/app.js`
- `site/theme.js`
- `site/data/bundle.json`

The live Pages URL is:
- [https://smkwray.github.io/tdcest/](https://smkwray.github.io/tdcest/)

## Repo layout

```text
.
├── docs/
├── scripts/
├── site/
├── src/tdc_estimator/
├── tests/
├── data/
└── pyproject.toml
```

## Important boundaries

- The main estimator is **marketable-Treasury focused**, not an all-liabilities Treasury measure.
- The broadest credit-union treatment is kept as a comparison view, not the main estimate.
- Receipt-side evidence is still limited: some historical overlays are usable, while some current-quarter receipt paths remain outside the main estimate.
- The monetary branch is a diagnostic cross-check, not a replacement for the main estimate.

## Documentation

- [Methodology](docs/methodology.md)
- [Equations](docs/equations.md)
- [Data sources](docs/data_sources.md)
- [Local development](docs/local_development.md)
- [Output schema](docs/output_schema.md)

## Contributing

Issues and pull requests are welcome, especially for:
- data-quality fixes
- documentation improvements
- public-site improvements
- methodological clarifications that improve transparency without overstating the evidence

## License

This project is released under the license in [LICENSE](LICENSE).
