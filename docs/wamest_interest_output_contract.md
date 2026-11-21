# WAMEST Interest Output Contract

Treasury interest paid to banks, credit unions, and foreign holders is a term of TDC. To split quarterly Fiscal Data interest-expense pools by type (coupons on notes, bonds, and TIPS; amortized bill discount; floating-rate note interest) after removing exact Federal Reserve SOMA interest, `tdcest` reads sector weights exported by `wamest`.

## Files and lookup order

`src/tdc_estimator/wamest_interest_contract.py` resolves each file under `wamest` in `outputs/full_coverage_release/` first, then `data/processed/` (ignoring fixtures):

1. `sector_interest_allocation_weights.csv`
2. `sector_component_bucket_weights.csv`
3. `sector_interest_observability_tier.csv`

Pass explicit paths to `tdc tier2-interest-component-candidate` via `--wamest-interest-weights-file` and `--wamest-bucket-weights-file` (or `--wamest-root`). When `sector_interest_allocation_weights.csv` is absent, `tdcest` builds fallback weights from `wamest` sector maturity (`canonical_sector_maturity.csv` / `sector_effective_maturity_full.csv`), Z.1 sector holdings (`z1_series_auto_full.csv` / `z1_sector_panel_full.csv`), and H.15 Treasury yield curves (`h15_curves_auto_nominal_treasury_constant_maturity.csv` / `h15_curves_fed.csv` / `h15_curves_fred.csv`).

## Schemas and validation

All tables require valid quarter-end `date` values, non-empty string keys, and unique primary keys.

`sector_interest_allocation_weights.csv` — key `(date, sector_key, component_key)`:
- Required columns: `date`, `sector_key`, `component_key`, `gross_interest_weight` (finite nonnegative USD million when eligible; null when ineligible), `weight_unit` (must equal `usd_millions`), `eligible_for_gross_interest` (`true`/`false` or `1`/`0`), `basis_method`, `source_basis`, `observability_tier`, `caveat_code` (blank or null when absent). Ineligible rows are excluded from the allocation denominator.

`sector_component_bucket_weights.csv` — key `(date, sector_key, component_key, bucket_key)`:
- Required columns: `date`, `sector_key`, `component_key`, `bucket_key`, `bucket_weight` (finite in `[0, 1]`), `bucket_weight_unit` (must equal `fraction`), `source_basis`, `observability_tier`.

`sector_interest_observability_tier.csv` — key `(date, sector_key, component_key)`:
- Required columns: `date`, `sector_key`, `component_key`, `observability_tier`, `supports_gross_interest_allocation` (boolean), `source_basis`, `notes`. Validated by the contract reader when loaded directly.

## Component keys, sectors, and allocation

Allowed `component_key` values (unknown keys raise an error):

- Active: `coupon_accrual`, `bill_amortized_discount`, `frn_accrued_interest` (falls back to `coupon_accrual` weights if absent).
- Reserved: `notes_accrued_interest`, `bonds_accrued_interest`, `tips_accrued_interest`, `tips_inflation_compensation` (kept separate from cash interest).

Default sector groups: banks (`bank_us_chartered`, `bank_foreign_banking_offices_us`, `bank_us_affiliated_areas`), credit unions (`credit_unions_marketable_proxy`), foreign holders (`foreigners_total`), and Federal Reserve (`fed`, excluded from the non-Fed pool).

For quarter $t$ and active interest family $c$, `tdcest` subtracts exact SOMA Federal Reserve interest $I_{c,t}^{\mathrm{Fed}}$ from the Fiscal Data pool $P_{c,t}$ and allocates $P_{c,t}^{\mathrm{nonFed}} = P_{c,t} - I_{c,t}^{\mathrm{Fed}}$ across eligible non-Fed sectors $\mathcal{E}_{c,t}$ in proportion to `gross_interest_weight` $W_{s,c,t}$:

$$
I_{s,c,t} = P_{c,t}^{\mathrm{nonFed}} \cdot \frac{W_{s,c,t}}{\sum_{j \in \mathcal{E}_{c,t}} W_{j,c,t}},
$$

holding totals within reported Call Report or NCUA constraints where available. Through 2010Q1, `tdcest` estimates bank, credit-union, and foreign interest from sector holdings and H.15 yields.

```bash
tdc tier2-interest-component-candidate \
  --wamest-root ../wamest \
  --treasury-interest-file data/raw/treasury__interest_expense.csv
```
