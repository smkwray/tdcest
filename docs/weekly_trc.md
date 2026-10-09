# Weekly Treasury component of reserves

The opt-in `weekly-trc-export` producer builds a par-valued weekly core TRC,
with zero and conditional upper ON RRP route bounds. It does not change the
admitted quarterly TRC, the reserve-factor ledger, or any default estimator.
There is no weekly preferred row and no interpolation of monthly fund holdings.

## Construction and scope

The week runs Thursday through Wednesday. Cash is the admitted ledger's exact
`c_h = -delta TGA - delta SFP`. The net Fed leg is the change in CUSIP-level
SOMA Treasury par, excluding the separate inflation-compensation stock field.
For every security between consecutive snapshots, scheduled maturity removes
opening par, and auction `soma_accepted` on issue dates supplies primary add-ons.
The remaining positive or negative par change is classified as a net secondary
purchase or sale. Missing allotments and inconsistent metadata are explicitly
unclassifiable. No unknown change is silently converted to a secondary purchase.
The classification table retains the signed unresolved amount. Net snapshot
changes cannot recover gross purchases and sales within a week.

Both primary add-ons and redemptions enter net Fed par: they offset the cash
leg when Treasury pays the Fed or receives payment from it. A par rollover
has zero net Fed par and moves no cash. The aggregate matched-rollover memo
is not a security-level matching claim and is not added to core.

Coupons are subtracted on actual payment dates, moved to the next Federal
Reserve business day when required. Nominal and TIPS coupons follow the
security's maturity-anchored semiannual schedule, preserving month ends. TIPS
coupons use payment-date reference CPI interpolation, the auction's dated-date
reference CPI, and the prescribed truncation/rounding. FRN coupons sum daily
interest from historical 13-week bill auction high discount rates and lifetime
spreads, with the two-business-day settlement/payment lockout. Complete observed FRN daily
rate periods independently cross-check the reconstructed amount. The published
FRN daily endpoint retains outstanding securities, so it cannot supply the
whole historical lane by itself.

Payment-date holdings are approximated by the latest prior Wednesday position.
A matured position that disappears on a holiday Wednesday is carried from the
preceding snapshot only for its postponed principal-date coupon. Intraweek
trades, ex-coupon eligibility and securities bought just before a payment cannot
be identified from weekly positions alone. This is a disclosed measurement
limitation, not an exact daily cash ledger.

DTS Table II Federal Reserve Earnings deposits supply cash remittances by date
through the existing Table II loader. Positive reported deposits are retained,
including payments from profitable Reserve Banks during an aggregate deferred-
asset period. Negative earnings accruals are not cash remittances. The DTS
history begins in October 2005; earlier cash-remittance inputs are unavailable.
Required missing snapshots, business-day observations and payment inputs carry
recorded unavailable statuses, never zero fills. Missing CPI months are recorded
and prevent a payment requiring that month from being calculated.

Core is `c_h + Fed par change - SOMA cash coupons + cash remittances`. Par is
not cash price. Realized TIPS principal inflation at maturity, bill discounts,
primary auction price differences and purchase accrued interest are outside this
par-valued core. The named securities-source bridge retains them together with
other source/settlement differences. The H.4.1 unamortized-premium and discount
changes are shown as a separate **all-securities** valuation bridge, covering
Treasuries, agency securities and MBS. They mix price effects, amortization and
derecognition; they are not an identified Treasury cash-price correction.

## Route bound and reconciliation

The lower route is zero. The daily upper is the minimum of the positive daily
ON RRP take-up decline and positive net bill cash settling that day. Issue cash
is total accepted bill par less SOMA allotments, times auction price. Redemption
cash is the sum of maturing bill allotments less SOMA par at the prior snapshot.
These daily envelopes are summed over the week. The bound is conditional on
same-day net funding without intraday recycling or lagged funding. It is not a
measurement of MMF purchases or an unconditional gross-purchase bound; take-up
includes all ON RRP counterparties. Days before the declared ON RRP facility
start have an explicit structural-zero status. Missing required bill cash or
ON RRP inputs make the upper unavailable. The lower remains definitionally zero.

For core, lower and upper separately, the identity table reports

```
reserve change = TRC
               + other signed factors
               + (RRP-others signed factor - route)
               + all-securities premium/discount bridge
               + (H.4.1 Treasury-securities change - Fed par change)
               + (SOMA coupons - cash remittances)
               + published ledger rounding
```

Every available row closes exactly in decimal arithmetic. Named source and
payment bridges do not independently validate the proxy's economics. Quarterly
flows sum complete weeks between the last Wednesdays of adjacent quarters.
Reserve changes independently telescope to endpoint levels. Incomplete quarters
and quarters with missing core weeks are unavailable, not partial point values.
The admitted calendar-quarter core is reconciled with Treasury-deposit clock,
Fed par versus Z.1 source/valuation, coupon schedule/timing, and cash remittance
versus admitted remittance differences. Printed admitted float arithmetic
residue is retained separately; era summaries report common observed coverage.

## Reproduction and artifacts

Run from the producer checkout, with its source package importable:

```
python scripts/acquire_trc_inputs.py --registry weekly-trc --fiscus-project ../../../fiscus
```

Discovery precedes fetching. All new external acquisition goes through fiscus.
`config/fiscus_weekly_trc.yml` supplies caller-owned entries for DTS Table II and
FRN daily rates to the maintained FiscalData executor. SOMA snapshots are
consolidated into one input file; each original fiscus cache key, hash, coverage,
vintage and empty-snapshot status remains in the manifest. CPI-U NSA is fetched
through fiscus's declared uncatalogued FRED passthrough.

From a clean committed producer, run:

```
tdc weekly-trc-export --inputs-manifest-sha256 MANIFEST_SHA256 --ledger-sha256 LEDGER_SHA256 --trc-components-sha256 COMPONENTS_SHA256
```

The three hashes pin the weekly input manifest, admitted weekly ledger, and
admitted quarterly components. `data/processed/trc_weekly_v1_receipt.json` names
the exact committed producer, all input/output hashes, each column's source,
clock and units, availability/classification counts, era descriptions, and
before/after hashes of all eight admitted TRC/ledger outputs. Output CSVs are
`trc_weekly_components_v1`, `trc_weekly_quarterly_v1`, `trc_weekly_identity_v1`,
`trc_weekly_soma_changes_v1`, and `trc_weekly_route_daily_v1`.

Economic fixture courts exercise the production builder and command. Live
receipt/hash checks run only in the explicit integration lane.

Source conventions: [Treasury auction regulations, Appendix B](https://www.treasurydirect.gov/files/laws-and-regulations/auction-regulations-uoc/31-cfr-part-356.pdf),
[Treasury rollovers](https://www.newyorkfed.org/markets/treasury-rollover-faq),
[SOMA holdings](https://www.newyorkfed.org/markets/soma-holdings), and
[DTS](https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/).
