# Data sources

## Core FRED series used by the estimator family

| Repo key | FRED series ID | Description | Use |
|---|---|---|---|
| `fed_tsy_tx` | `BOGZ1FU713061103Q` | Monetary Authority; Total Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `us_chartered_tsy_tx` | `BOGZ1FU763061100Q` | U.S.-Chartered Depository Institutions; Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `foreign_offices_tsy_tx` | `BOGZ1FU753061103Q` | Foreign Banking Offices in the U.S.; Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `affiliated_areas_tsy_tx` | `BOGZ1FU743061103Q` | Banks in U.S.-Affiliated Areas; Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `np_credit_unions_tsy_tx` | `BOGZ1FU473061103Q` | Credit Unions; Treasury Securities, Excluding Corporate Credit Unions; Asset, Transactions | broad-depository headline |
| `corp_credit_unions_tsy_tx` | `BOGZ1FU473061153Q` | Credit Unions; Treasury Securities Held by Corporate Credit Unions; Asset, Transactions | sensitivity |
| `ncua_capitalization_deposit_tx` | `BOGZ1FU473061203Q` | Credit Unions; NCUA Share Insurance Capitalization Deposit; Asset, Transactions | aggregate-CU sensitivity |
| `credit_unions_total_tsy_tx` | `BOGZ1FU473061105Q` | Credit Unions; Treasury Securities; Asset, Transactions | optional cross-check |
| `row_tsy_tx` | `BOGZ1FU263061105Q` | Rest of the World; Treasury Securities; Asset, Transactions | bank-only and broad headlines |
| `treasury_operating_cash_tx` | `BOGZ1FU313024000Q` | Federal Government; Treasury Operating Cash; Asset, Transactions | bank-only and broad headlines |
| `fed_remit_or_deferred` | `RESPPLLOPNWW` | Earnings Remittances Due to the U.S. Treasury | bank-only and broad headlines |

## Holdings-level sensitivity series

The repo can also download holdings-level analogs for the Treasury transaction series and Treasury operating cash.

These are used only for:

- level-change sensitivities
- diagnostics
- visual cross-checks

## Optional macro support series

- `M2SL`
- `CURRCIR`
- `TOTBKCR`
- `WDTGAL`

These are used for rough decomposition proxies and high-frequency diagnostic checks.

## Optional Treasury Fiscal Data datasets

- Daily Treasury Statement operating cash balance
- Monthly Treasury Statement receipts
- MSPD marketable detail
- MSPD full detail
- SLGS securities

## Download philosophy

This repo prefers:

- official public sources
- URLs that can be called from scripts
- raw-file preservation in `data/raw/`
- transparent transformations into `data/processed/`

## Credit-union mapping note

The repo intentionally separates:

- natural-person credit-union Treasury transactions
- corporate credit-union Treasury transactions
- the NCUA capitalization deposit term

That makes it possible to publish:

- a bank-only headline
- a broad-depository natural-person-CU alternative
- a corporate-CU sensitivity
- an aggregate-CU sensitivity
