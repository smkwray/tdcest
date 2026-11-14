# WAMEST Interest Output Contract

This contract defines the [WAMEST](https://github.com/smkwray/wamest) files that
TDCest reads to allocate Treasury interest components across holder sectors for
the component-anchored Tier 2 rows. TDCest, as the consumer, defines the contract.

## Contract Files

TDCest looks for these files under a WAMEST checkout:

- `outputs/full_coverage_release/sector_interest_allocation_weights.csv`
- `outputs/full_coverage_release/sector_component_bucket_weights.csv`
- `outputs/full_coverage_release/sector_interest_observability_tier.csv`

It also accepts the same filenames under `data/processed/` for local research
builds.

## `sector_interest_allocation_weights.csv`

Required columns:

- `date`
- `sector_key`
- `component_key`
- `central_weight`
- `low_weight`
- `high_weight`
- `gross_interest_weight`
- `gross_interest_low_weight`
- `gross_interest_high_weight`
- `weight_class`
- `eligible_for_gross_interest`
- `weight_unit` (`usd_millions`)
- `weight_basis`
- `source_family`
- `observability_tier`

Recommended columns:

- `uses_revaluation_inference`
- `uses_tic_anchor`
- `uses_regulatory_constraint`
- `uses_peer_fallback`
- `method_note`

Purpose: allocate official Treasury interest component pools to holder sectors.
`tdcest` consumes the nonnegative `gross_interest_*` fields. The central/low/high
fields retain signed Z.1 allocations for audit; dealer net exposure and the
household statistical residual are explicitly ineligible for gross-interest
allocation. Weights are not coupon cashflows by themselves.

Active `tdcest` candidate component keys:

- `coupon_accrual`: pooled notes, bonds, and TIPS accrued-interest expense.
  This is the current nondefault comparison key until WAMEST has reliable
  instrument-specific coupon weights.
- `bill_amortized_discount`: Treasury bill amortized-discount expense.
- `frn_accrued_interest`: Floating Rate Note accrued-interest expense,
  allocated from sector FRN-share weights when WAMEST exports them. If absent,
  `tdcest` keeps the FRN component nondefault and labels any coupon-weight
  fallback explicitly.

Reserved component keys:

- `notes_accrued_interest`
- `bonds_accrued_interest`
- `tips_accrued_interest`
- `tips_inflation_compensation`

Reserved keys should not feed a central `tdcest` publication until their
sector-weight evidence is explicitly available. Unknown component keys are
rejected by the `tdcest` contract reader.

## `sector_component_bucket_weights.csv`

Required columns:

- `date`
- `sector_key`
- `component_key`
- `bucket_key`
- `bucket_weight`
- `bucket_basis`
- `source_family`
- `observability_tier`

Purpose: expose the bucket evidence behind the allocation weights. Examples
include bill share, coupon-bearing share, TIPS share, FRN share, and maturity or
duration buckets where those buckets are the best available public evidence.

## `sector_interest_observability_tier.csv`

Required columns:

- `date`
- `sector_key`
- `component_key`
- `observability_tier`
- `source_family`
- `uses_revaluation_inference`
- `uses_tic_anchor`
- `uses_regulatory_constraint`
- `uses_peer_fallback`

Purpose: prevent weak sectors from silently feeding default Tier 2 corrections.
Tier D or peer-fallback rows must carry uncertainty and should remain
nondefault unless the estimator explicitly promotes them.

## `soma_interest_proxy_backtest.csv`

Required columns:

- `date`
- `component_key`
- `exact_soma_interest_mil`
- `proxy_soma_interest_mil`
- `proxy_error_mil`
- `proxy_error_pct`
- `proxy_method`

Purpose: benchmark WAMEST/H.15-style proxy methods against exact SOMA component
interest. This is the relevant backtest for `tdcest`; maturity error alone is
not enough.

## Fallback rule

If these contract files are absent, Tier 2 uses the WAMEST maturity,
coupon-share and H.15 path instead. Rows built that way are H.15 approximations,
not component-anchored estimates, and the absence of the contract files is not
evidence that the H.15 method is adequate.
