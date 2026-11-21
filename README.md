# tdcest

tdcest measures the Treasury Deposit Component (TDC): the part of the change in US bank deposits that comes from the
Treasury's payments and from trades in Treasury securities. It builds a quarterly series from 2002 using public data,
together with its counterpart for bank reserves, the Treasury component of reserves (TRC), at quarterly, monthly and
weekly frequency.

## What TDC is

Households, firms and other nonbanks hold bank deposits and pay from them. Call them deposit users. Their deposits
rise when the Treasury pays them and fall when they pay taxes or buy Treasury securities. Banks, the Federal Reserve
and foreign official accounts pay from other balances (reserves, or accounts outside US banks), so their payments
leave deposit users' deposits unchanged. TDC is the net effect on deposit users' deposits:

```text
TDC = Treasury spending paid to deposit users - taxes and other payments they make to the Treasury
    + interest and principal the Treasury pays them
    + what they receive for Treasury securities they sell to others
    - what they pay for Treasury securities they buy, including at auction
```

Over any period, the change in deposits equals TDC plus every other source of deposit change, such as bank lending.

## How tdcest measures it

Public data do not record who received each Treasury payment, so tdcest measures TDC from the Treasury's side of the
same transactions. The Treasury's cash changes by what it receives less what it pays, so the definition above equals

```text
TDC = net purchases of Treasury securities by the Federal Reserve, banks and foreign holders
    - Treasury interest paid to those holders
    + Federal Reserve remittances to the Treasury
    - the increase in the Treasury's operating cash
    + Treasury securities that money market funds pay for out of the Federal Reserve's ON RRP facility
```

Every term is a quarterly flow in USD millions:

- **Purchases.** Treasury-security transactions by sector from the Financial Accounts of the United States (Z.1). Banks
  are US-chartered depository institutions, US offices of foreign banks and banks in US territories.
- **Interest.** Interest on marketable Treasury debt is split by type (bills, coupon securities, floating-rate notes,
  TIPS) and allocated across holders. The Federal Reserve's share comes from its System Open Market Account holdings,
  security by security. Banks' and foreign holders' shares come from estimates of their holdings by type and maturity
  ([wamest](https://github.com/smkwray/wamest)), held to reported holdings where those exist (bank Call Reports and
  Treasury International Capital data). Before 2010, when those estimates are unavailable, their interest is
  estimated from sector holdings and H.15 Treasury yields (through 2010Q1).
- **Remittances.** The Federal Reserve's payments of its earnings to the Treasury.
- **Treasury cash.** The change in the Treasury's operating cash, excluding transfers between Treasury and Federal
  Reserve accounts that never reach a bank deposit, such as the Treasury's equity in the 2020 lending facilities.
- **Money funds.** Money market funds are deposit users, but when they pay for Treasury securities by drawing down
  their balances at the Federal Reserve's overnight reverse repurchase (ON RRP) facility, no bank deposit moves. Fund
  filings (SEC Form N-MFP) show how each fund financed its purchases; tdcest allocates purchases across funding
  sources in proportion and reports lower and upper bounds. This term starts in 2013Q3, when the facility began
  operating at scale.

The series is the column `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` in
`data/processed/tdc_tier2_regression_series.csv`, 2002Q1 onward.

TRC applies the same accounting to bank reserves: the change in reserves caused by the Treasury's cash operations, by
the Federal Reserve's Treasury transactions and remittances, and by money-fund ON RRP financing.

## Data

All inputs are public:

- Financial Accounts of the United States (Z.1) and the Federal Reserve's H.4.1 release, from FRED. The public download
  works without a key; set `FRED_API_KEY` to use the FRED API instead.
- Treasury Fiscal Data (`api.fiscaldata.treasury.gov`): the Daily Treasury Statement, the Monthly Treasury Statement,
  the Monthly Statement of the Public Debt, interest expense and floating-rate note indexes.
- System Open Market Account holdings, SEC Form N-MFP filings, and holder estimates from
  [wamest](https://github.com/smkwray/wamest).
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
`data/raw/manifest_fred.json`. To include the Treasury Fiscal Data downloads:

```bash
"$HOME/venvs/tdcest/bin/python" scripts/build_all.py --include-treasury-support
```

The interest and money-fund inputs are built by `tdc` subcommands; `tdc --help` lists them. The reserve-side and
comparison exports pin every input by SHA-256, run only from a clean committed checkout, and write a JSON receipt
beside each table:

| Command | Output |
|---|---|
| `tdc trc-export` | Quarterly TRC and its components |
| `tdc reserve-factor-ledger-export` | Weekly H.4.1 factors affecting reserve balances, bridged to quarterly TRC |
| `tdc weekly-trc-export` | Weekly TRC |
| `scripts/export_trc_monthly.py` | Monthly TRC on a last-Wednesday clock |
| `tdc treasury-fed-transfer-export` | Dated transfers between Treasury and Federal Reserve accounts |
| `tdc regression-leg-export` | TDC split into its terms |
| `tdc bank-composition-export` | Bank balance-sheet composition |
| `tdc deficit-comparison-export` | TDC beside the federal deficit |
| `tdc interest-rate-debt-export` | Quarterly Treasury interest split into debt and rate effects and by holder |

Download their inputs with `scripts/acquire_trc_inputs.py --registry <name>`. `--vintage v1` ends in 2025Q4 and
`--vintage 2026q2` in 2026Q2; `--root <dir>` builds a vintage in its own directory.

## Output

Generated files go to `data/processed/` and are not tracked. The main ones are the TDC series above, the reserve-side
tables (`trc_*_v1.csv` and `reserve_factor_*_v1.csv`, each with a `*_receipt.json`), and
`tdc_downstream_handoff_bundle.json`, a summary of the series and their latest values.

## Limits

TDC is estimated, not observed: public data report Treasury holdings and transactions by sector, not the account each
payment came from. The measure assumes the Treasury's spending and tax receipts, apart from debt service, are paid to
and from deposit users, and that foreign holders pay for Treasury securities from outside US bank deposits. Interest allocated to banks and foreign holders depends on estimated holdings by type and
maturity. The money-fund term assumes each fund financed its purchases in proportion to its funding sources; the lower
and upper bounds show how much that matters.

## Tests

```bash
make test
```

Tests marked `integration` read locally built data and fail if it is absent. Run them with
`"$HOME/venvs/tdcest/bin/pytest" -m integration`.

## License

MIT. See [LICENSE](LICENSE).
