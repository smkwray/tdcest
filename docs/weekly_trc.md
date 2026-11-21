# Weekly Treasury Component of Reserves (TRC)

`tdc weekly-trc-export` builds the weekly reserve-side counterpart to TDC on the Federal Reserve H.4.1 Thursday–Wednesday reporting clock, using exact decimal arithmetic (`Decimal`) throughout `src/tdc_estimator/weekly_trc.py`. All dollar columns are in USD millions.

## Weekly definition

For each H.4.1 reporting week $w$ ending on Wednesday $t$, the cash-corrected core weekly series is:

$$
\mathrm{TRC}_w^{\mathrm{core}} = C_w^{H} + F_w^{\mathrm{Fed,cash}} - I_w^{\mathrm{SOMA}} + R_w^{\mathrm{DTS}} + J_w,
$$

where:

- $C_w^{H} = -\Delta \mathrm{TGA}_w - \Delta \mathrm{SFP}_w$ (`c_h`): negative weekly change in the Treasury General Account (`WDTGAL`) and Supplementary Financing Account (`WDSFAL`) from `reserve_factor_ledger_weekly_v1.csv`. Treasury Tax and Loan balances at commercial banks do not appear on H.4.1.
- $F_w^{\mathrm{Fed,cash}} = F_w^{\mathrm{Fed,par}} + \Delta_w^{\mathrm{clock}} + A_w^{\mathrm{primary}} - A_w^{\mathrm{redemp}}$ (`fed_leg_cash_corrected`): weekly change in NY Fed SOMA Treasury par holdings (`fed_leg_par`, converted from USD by dividing by $10^6$ and excluding `inflationCompensation`), plus holiday maturity payment-clock shifts (`settlement_clock_adjustment`), plus supported primary-market SOMA auction cash minus par (`primary_cash_adjustment`), minus supported TIPS redemption inflation cash above par (`redemption_inflation`).
- $I_w^{\mathrm{SOMA}}$ (`soma_coupon_cash`): scheduled cash coupon payments on SOMA Treasury notes, bonds, TIPS, and floating-rate notes falling in week $w$, shifted to the next business day under the federal holiday calendar (including Juneteenth from 2021).
- $R_w^{\mathrm{DTS}}$ (`cash_remittances`): DTS Table II `Federal Reserve Earnings` cash deposits into TGA during week $w$.
- $J_w$ (`j_applied`): weekly sum from `treasury_fed_transfers_weekly_v1.csv` covering Treasury–Federal Reserve internal transfers on DTS dates—Treasury equity transfers with Federal Reserve credit-facility LLCs plus LLC purchases minus redemptions of nonmarketable Domestic Series Treasury securities.

A par-only comparison column, `trc_par_sensitivity = c_h + fed_leg_par - soma_coupon_cash + cash_remittances`, omits the primary cash price, holiday maturity shift, redemption inflation, and $J_w$ terms.

## SOMA classification, cash pricing, and coupon rules

Each CUSIP change between consecutive Wednesday SOMA snapshots is written to `trc_weekly_soma_changes_v1.csv`:

- Redemptions (`redemptions_par`) use the prior Wednesday snapshot par as entitlement at actual payment date (assuming no intervening trade between that snapshot and maturity). When a nominal maturity falls on a weekend or federal holiday and crosses a Wednesday boundary, `settlement_clock_adjustment` moves the par removal into the payment week.
- Primary add-ons (`primary_addons_par`) match `fiscaldata.auctions_query` `soma_accepted` on issue date. Net secondary purchases or sales are the residual $\Delta \mathrm{par} + \mathrm{redemptions\_par} - \mathrm{primary\_addons\_par}$. Unresolved classification residuals are tagged `unclassifiable_*` and summed into `unclassifiable_abs_par`.
- Primary cash (`primary_addons_cash`) multiplies SOMA auction par by dirty settlement price, indexing adjusted TIPS fields once. TIPS redemption cash (`redemptions_cash`) equals $\max(\mathrm{par},\; \mathrm{par} \times \text{index ratio at nominal maturity})$, preferring contractual reference CPI published in auction records and falling back to linear interpolation of CPI-U (`CPIAUCNS`).
- Floating-rate note (FRN) coupons use `fiscaldata.frn_daily_indexes` (verified one-calendar-day accrual intervals starting `2024-10-31`). Earlier weeks with an FRN coupon payment record an unavailable coupon status.
- Secondary-market trades lack transaction prices in SOMA snapshots; their net par volume is reported separately in `unpriced_secondary_net_par`.

## Signed ON RRP and bill route scenarios

Daily bill settlements, bill redemptions, and ON RRP balances (`RRPONTSYD`, converted from USD billions by multiplying by `1000`) are assembled in `trc_weekly_route_daily_v1.csv` to bound directional ON RRP–Treasury bill flows without forming a point estimate:

- `route_baseline`: $0$.
- `route_forward`: weekly sum of daily $\min(\text{opening ON RRP principal},\; \text{gross non-SOMA bill settlement cash})$; gives `trc_forward_scenario = trc_core + route_forward`.
- `route_reverse`: weekly sum of daily $-\min(\text{closing ON RRP principal},\; \text{gross non-SOMA bill redemption cash})$; gives `trc_reverse_scenario = trc_core + route_reverse`.
- `net_bill_on_rrp_overlap`: weekly sum of daily $\min(\max(0, -\Delta \text{ON RRP}),\; \text{positive net non-SOMA bill cash})$ (diagnostic only).

## Exact weekly H.4.1 identity and quarterly reconciliation

For every week with complete inputs, `trc_weekly_identity_v1.csv` verifies exact decimal closure against weekly H.4.1 reserve-balance changes $\Delta \mathrm{RB}_w$ (`identity_error == 0`) for the core series and both route scenarios:

$$
\Delta \mathrm{RB}_w = \mathrm{TRC}_w + \sum_{k \in \mathcal{O}} f_{k,w} + (f_{\mathrm{RRP,other},w} - \text{route}_w) + B_w^{\mathrm{prem/disc}} + B_w^{\mathrm{source}} + B_w^{\mathrm{clock}} + B_w^{\mathrm{primary}} + B_w^{\mathrm{redemp}} + B_w^{\mathrm{int}} + B_w^{\mathrm{coup/remit}} + \rho_w,
$$

where $\sum_{k \in \mathcal{O}} f_{k,w}$ (`non_treasury_signed_factors`) sums all H.4.1 factors outside TGA, SFP, Treasury securities, RRP others, and premiums/discounts; `rrp_others_net_route` subtracts the active route scenario from the RRP-others factor once; and the eight bridge columns are:

- `bridge_all_securities_premium_discount`: `f_unamortized_premiums + f_unamortized_discounts` (all securities held outright)
- `bridge_treasury_securities_source_inflation`: `s_h - fed_leg_par`
- `bridge_maturity_payment_clock`: `-settlement_clock_adjustment`
- `bridge_primary_cash_price`: `-primary_cash_adjustment`
- `bridge_redemption_inflation`: `+redemption_inflation`
- `bridge_internal_postings`: `-j_applied`
- `bridge_coupon_remittance_payments`: `soma_coupon_cash - cash_remittances`
- `bridge_published_rounding`: `rho`

`trc_weekly_quarterly_v1.csv` sums complete Wednesday-bounded quarters (all Wednesdays strictly after the prior quarter's last Wednesday through the current quarter's last Wednesday), checks exact telescoping of reserve changes (`reserve_telescoping_error == 0`), and reconciles summed weekly `trc_core` to `trc_quarterly_components_v1.csv` across eight named difference columns (clock, source/valuation, coupon, remittance, primary cash price, redemption inflation, internal transfers, and maturity payment clock) within $10^{-6}$ USD million.

## Sample dates, inputs, and commands

The H.4.1 ledger begins `2002-12-18`, DTS Table II begins `2005-10-03`, the earliest weekly `trc_core` observation is `2005-10-12`, and the earliest complete Wednesday-bounded quarter is `2006Q1`. Sample vintage `v1` runs through `2025-12-31` (`2025Q4`); `2026q2` runs through `2026-09-30` (`2026Q2`).

Acquire inputs and build the weekly internal-transfer ledger first:

```bash
PYTHONPATH=src python scripts/acquire_trc_inputs.py --registry weekly-trc
PYTHONPATH=src python scripts/acquire_trc_inputs.py --registry treasury-fed-transfers

tdc treasury-fed-transfer-export \
  --inputs-manifest-sha256 <TRANSFERS_MANIFEST_SHA256> \
  --weekly-trc-manifest-sha256 <WEEKLY_TRC_MANIFEST_SHA256> \
  --h41-ledger-manifest-sha256 <H41_LEDGER_MANIFEST_SHA256>
```

Then run the weekly export (requires a clean committed git checkout and SHA-256 pins; fails if any existing quarterly TRC or ledger file changes):

```bash
tdc weekly-trc-export \
  --inputs-manifest-sha256 <WEEKLY_TRC_MANIFEST_SHA256> \
  --ledger-sha256 <LEDGER_WEEKLY_SHA256> \
  --trc-components-sha256 <TRC_COMPONENTS_SHA256> \
  --transfers-weekly-sha256 <TRANSFERS_WEEKLY_SHA256>
```

Outputs written to `data/processed/`:

- `trc_weekly_components_v1.csv` — weekly core series, components, status flags, and route scenarios
- `trc_weekly_quarterly_v1.csv` — Wednesday-bounded quarterly sums and reconciliation to quarterly TRC
- `trc_weekly_identity_v1.csv` — exact H.4.1 weekly reserve identity checks
- `trc_weekly_soma_changes_v1.csv` — CUSIP-level SOMA weekly change classification and cash pricing
- `trc_weekly_route_daily_v1.csv` — daily ON RRP and non-SOMA bill cash inputs to the route scenarios
- `trc_weekly_v1_receipt.json` — SHA-256 input/output provenance, column contracts, and summary diagnostics
