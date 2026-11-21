# tdcest

tdcest estimates the Treasury Deposit Component (TDC): the change in bank deposits that comes from the Treasury's own
payments and from purchases and sales of Treasury securities. When the Treasury spends, deposits rise; when people pay
taxes or buy Treasury securities from their deposits, deposits fall. When a bank, the Federal Reserve or a foreign
account buys the securities instead, no household or business deposit is drawn down. tdcest measures that flow from public
data, quarterly from 2002, together with its counterpart for bank reserves, the Treasury component of reserves (TRC),
at quarterly, monthly and weekly frequency. It writes CSV tables, figures and JSON summaries.

Methodology: [method](docs/methodology.md), [equations](docs/equations.md), [data sources](docs/data_sources.md),
[output columns](docs/output_schema.md).

## How TDC is measured

The basic quarterly estimate, in USD millions, is

```text
TDC = net purchases of Treasury securities by the Federal Reserve, banks and the rest of the world
      - the change in the Treasury's operating cash (excluding transfers between Treasury and Federal Reserve accounts)
      + Federal Reserve remittances to the Treasury
```

Two adjustments refine it when their input files are present:

- **Interest.** Treasury interest paid to the Federal Reserve, banks, credit unions and foreign holders goes to holders
  outside the deposit-using public, so it is taken out. Coupon interest, bill discount, floating-rate note interest and
  TIPS payments are estimated separately; the Federal Reserve's share comes from its System Open Market Account (SOMA)
  holdings.
- **Money funds.** When money market funds pay for Treasury securities by drawing down their balances at the Federal
  Reserve's overnight reverse repurchase (ON RRP) facility, no bank deposit is involved. Using fund filings (SEC Form
  N-MFP), tdcest estimates how much of their purchases were paid that way and adds it back, with lower and upper bounds.

"Banks" means US-chartered depository institutions, US offices of foreign banks and banks in US territories. A second
version also counts credit unions as banks. Further versions, such as one without Federal Reserve remittances, are
written alongside for comparison.

Separate commands export TRC, the weekly H.4.1 ledger of factors affecting reserve balances, bank balance-sheet
composition, a comparison of TDC with the federal deficit, and a breakdown of Treasury interest by holder.

## Data

All inputs are public:

- Financial Accounts of the United States (Z.1) and the H.4.1 release, from FRED. The public download endpoint works
  without a key; set `FRED_API_KEY` to use the FRED API instead.
- Treasury Fiscal Data (`api.fiscaldata.treasury.gov`): the Daily Treasury Statement, the Monthly Treasury Statement,
  the Monthly Statement of the Public Debt, interest expense and floating-rate note indexes.
- SOMA holdings, SEC Form N-MFP filings, and holder maturity weights from [wamest](https://github.com/smkwray/wamest)
  for the two adjustments.
- Reserve-side inputs, downloaded through [fiscus](https://github.com/smkwray/fiscus) by
  `scripts/acquire_trc_inputs.py` (requires [uv](https://docs.astral.sh/uv/)).

## Install

Python 3.11 or later. From the repository root:

```bash
make bootstrap
```

This creates a virtual environment at `$HOME/venvs/tdcest` and installs the package with its test dependencies. Set
`TDC_VENV=/path/to/env` to put it elsewhere.

## Usage

An offline demo on synthetic data (no network, no key) writes to `examples/demo_build/`:

```bash
make demo
```

Download the required FRED series and build the estimates, figures and summary bundle:

```bash
make build
```

The build stops if a required series fails to download; failed optional series are listed in
`data/raw/manifest_fred.json`. To include the Treasury Fiscal Data downloads as well:

```bash
"$HOME/venvs/tdcest/bin/python" scripts/build_all.py --include-treasury-support
```

The interest and money-fund adjustments need their input files, which `tdc` subcommands build; `tdc --help` lists them.
The reserve-side and comparison exports pin every input by SHA-256, run only from a clean committed checkout, and write
a JSON receipt beside each table:

| Command | Output |
|---|---|
| `tdc trc-export` | Quarterly TRC and its components |
| `tdc reserve-factor-ledger-export` | Weekly H.4.1 reserve factors, bridged to quarterly TRC |
| `tdc weekly-trc-export` | Weekly TRC (see [docs/weekly_trc.md](docs/weekly_trc.md)) |
| `scripts/export_trc_monthly.py` | Monthly TRC on a last-Wednesday clock |
| `tdc treasury-fed-transfer-export` | Dated transfers between Treasury and Federal Reserve accounts |
| `tdc regression-leg-export` | The long-history TDC series split into its accounting parts |
| `tdc bank-composition-export` | Bank balance-sheet composition |
| `tdc deficit-comparison-export` | TDC beside the federal deficit |
| `tdc interest-rate-debt-export` | Quarterly Treasury interest split into debt and rate effects and by holder |

Download their inputs with `scripts/acquire_trc_inputs.py --registry <name>`. `--vintage v1` ends in 2025Q4 and
`--vintage 2026q2` in 2026Q2; `--root <dir>` builds a vintage in its own directory.

## Output

Generated files go to `data/processed/` and are not tracked:

- `tdc_estimates.csv`: quarterly TDC in USD millions, in every version and with each adjustment.
- `tdc_tier2_regression_series.csv`: the longest consistent quarterly series, from 2002Q1, in USD millions.
- `tdc_downstream_handoff_bundle.json`: a summary of the series and their latest values.
- `trc_*_v1.csv` and `reserve_factor_*_v1.csv`: reserve-side tables, each with a `*_receipt.json`.

Column definitions are in [docs/output_schema.md](docs/output_schema.md).

## Limits

Public data report Treasury holdings and purchases by sector, not which account each payment came from, so every series
here is an estimate of the deposit flow rather than a direct measure. The interest adjustment depends on estimated
holder maturity and instrument mix. The money-fund adjustment assumes funds pay for Treasury purchases in proportion to
their funding sources; the lower and upper bounds show how much that matters.

## Tests

```bash
make test
```

Tests marked `integration` read locally built data and fail if it is absent. Run them with
`"$HOME/venvs/tdcest/bin/pytest" -m integration`.

## License

MIT. See [LICENSE](LICENSE).
