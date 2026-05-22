# WAMEST Interest Output Contract

This contract defines the future `wamest` files that `tdcest` can use when
moving Tier 2 interest corrections from raw WAMEST/H.15 intensity proxies toward
component-anchored holder allocations.

The contract is intentionally owned here first because `tdcest` is the estimator
that consumes the outputs. `wamest` can implement the files after the component
keys and validation gates are stable.

## Contract Files

`tdcest` will look for these files under a `wamest` checkout:

- `outputs/full_coverage_release/sector_interest_allocation_weights.csv`
- `outputs/full_coverage_release/sector_component_bucket_weights.csv`
- `outputs/full_coverage_release/sector_interest_observability_tier.csv`
- `outputs/full_coverage_release/soma_interest_proxy_backtest.csv`

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
Weights are not coupon cashflows by themselves. They are allocation weights for
component pools.

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

## Fallback Rule

If these contract files are absent, `tdcest` may continue using the current
WAMEST maturity/coupon-share/H.15 path as a live stopgap. Absence of the contract
files must not be treated as evidence that the old method is final.
