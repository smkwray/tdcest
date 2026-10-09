# Weekly Treasury component of reserves

`weekly-trc-export` builds a cash-corrected Wednesday core **proxy**, a separate
uncorrected par sensitivity, and signed ON RRP route scenarios. It preserves
all admitted quarterly TRC and reserve-factor ledger artifacts. There is no
weekly preferred series, estimator, or allocation of monthly fund positions.

## Measurement and cash conventions

Weeks run Thursday through Wednesday. The admitted ledger supplies
`C = c_h = -delta TGA - delta SFP` unchanged. The measured securities leg is

```
B_hat = delta SOMA par + maturity-payment-clock adjustment
        + supported primary cash adjustment - supported redemption inflation
X0_hat = C + B_hat - coupon proxy + cash remittances + J_applied
```

Primary allotments use auction issue settlement dates and cash prices. Bills
use discounted price; nominal notes, bonds and FRNs add acquisition accrued
interest. TIPS use inflation-adjusted price and adjusted accrued interest when
reported; unadjusted fields multiply the issue-date index ratio once. Accrual
is definitionally zero for a new issue whose dated date equals settlement;
missing accrued interest on a reopening stays unavailable. Per-event corrections
are null when unsupported. Weekly sums apply supported corrections only and
carry the excluded events' par magnitudes and statuses. A zero supported sum
does not mean an unobserved correction is zero.

TIPS redemption principal is `max(par, par * nominal-maturity index ratio)`.
Inflation-compensation stock changes are excluded; inflation paid at maturity
is included. Published auction reference CPI is preferred on the nominal index
date, using original dated-date bases and independently dated issue references.
A reopening's later coupon dated date must not be paired with its original base
CPI. All 45 observed TIPS redemptions have published nominal-date reference CPI.
Current CPI-U NSA, with contractual interpolation and rounding, remains a proxy
where a published payment-date reference is absent. The receipt separately
compares reconstructed issue ratios with published auction ratios and lists
mismatches. Unrevised or contingency CPI and unobserved payment references
remain uncertainty for that reconstruction.

The event universe includes both snapshots and auction CUSIPs, including a
primary allotment sold before the closing snapshot. This is a **net partition**:
residual increases and decreases are net secondary par, never gross purchases
or sales. A missing expected auction record cannot establish secondary activity.
The table reports signed and absolute unclassifiable dollars by event category.
Redemption quantity equals opening holdings under an explicit no-intervening-
trade assumption. Gross churn and secondary entitlement remain unobserved.
Secondary trades remain par-valued because settlement prices are absent; the
absolute classified net secondary par reports the unpriced magnitude.

The rollover memo sums matched par on each maturity payment/issue settlement
date. Partial runoff retires the entire matured CUSIP and reinvests only part;
coincident weekly totals on different dates do not match. The memo is neither
gross transaction identification nor a cash rollover amount. Nominal maturity
dates/months remain separate from holiday-shifted payment dates. A snapshot
removal on a holiday maturity is deferred to the payment week under the same
entitlement assumption, with its own reversing clock bridge.

`J` corrects identifiable Treasury–Fed cash that has no direct reserve incidence.
Dated DTS ESF cash must match a facility factor in sign and magnitude (weekly
net or a single identifiable dated posting), or match an independently documented
facility transfer in the event crosswalk. The May 11, 2020 corporate-credit
transfer has independent Treasury confirmation: $37.5bn is applied while the
remaining $10bn stock change stays candidate-only. Other cash/stock mismatches
remain candidates. SDR and gold entries lack a dated TGA/special-account cash
crosswalk and are candidate-only. Neither a reclassification nor an unmatched
certificate account entry is mechanically added to core. Coin, Treasury currency,
Treasury cash holdings, IORB and FIMA lending stay outside core.

Coupons are **payment-date proxies on prior-week positions**, plus known primary
allotments settling strictly before payment. Acquisition accrued interest enters
primary cash once; the subsequent full coupon enters once. Unknown primary
entitlement on a payment date makes that coupon unavailable. Secondary trades
before payment cannot be recovered from weekly endpoints. Nominal and TIPS
coupons use maturity-anchored semiannual schedules; the TIPS index date in code
is the nominal coupon date, while the next-business-day payment date assigns
the cash week. A vanished holiday-maturity holding is carried only to its
deferred principal-date coupon.

FRNs reconstruct daily interest from the 13-week auction index and lifetime
spread, including the two-business-day settlement/payment lockout. A complete
auction query documents no new auction within its coverage window; the previous
index then carries beyond fourteen days. Missing feed coverage or missing rates
are distinct unavailable states. Actual published FRN rows are one-calendar-day
intervals, start inclusive/end exclusive; `record_date` is publication, not the
accrual date. The receipt verifies this contract and complete observed periods
cross-check reconstructed daily amounts. The acquired daily history starts
**2024-10-31**, not 2014. It does not cover the historical FRN lane.

DTS Table II Federal Reserve Earnings deposits supply dated cash remittances.
Reported positive payments and reported zeros are retained, including during an
aggregate deferred-asset period. Missing daily coverage stays unavailable.
History starts **2005-10-03**: the earliest complete input week is **2005-10-12**
and the earliest potentially complete Wednesday quarter is **2006Q1**. Other
missing inputs can narrow that coverage further. Earlier rows are diagnostics,
not a claim of complete core coverage.

## Signed route scenarios

The same-day **net-bill/ON RRP overlap statistic** is
`min(positive aggregate ON RRP decline, positive net bill cash)`. It is diagnostic
only: unrelated redemptions or offsetting participant flows can conceal an
actual forward route while leaving this statistic zero.

The primary-bill channel scenarios instead use gross cash:

```
U_fwd,d = min(opening ON RRP principal, gross non-SOMA bill settlement cash)
U_rev,d = min(closing ON RRP principal, gross non-SOMA bill redemption cash)
Gamma_forward,w = sum U_fwd,d
Gamma_reverse,w = -sum U_rev,d
Gamma_baseline,w = 0
```

Thus declared same-day channel paths lie between the negative reverse and
positive forward capacities, subject to shared daily constraints. These are
route scenarios, **not bounds on TRC or regression coefficients**. Zero is a
no-route baseline. No participant financing or Treasury destination is identified.
MMF/GSE/other allocations must share one facility capacity; they cannot each
consume its full amount. Separate directional endpoints are alternative paths,
not simultaneously realized routes. Lagged funding and secondary-market routes
are outside this channel.

Auction totals are normalized using `soma_included` and `fima_included`. Excluded
add-ons are added to the all-allotment total, then SOMA is removed once. FIMA is
included in the broad non-SOMA total and is not classified as MMF financing.
Redemptions sum all original allotments/reopenings and remove prior-snapshot
SOMA once per CUSIP, retaining the entitlement assumption. Missing inclusion
fields or holdings produce unavailable capacities. Facility-scope zeros before
September 2013 do not establish absence of other historical repo routes.
Daily ON RRP and H.4.1 RRP-others have an explicit signed flow bridge.

## Reconciliation and coverage reporting

For every declared route, the identity is

```
delta R = (X0_hat + Gamma) + (F_RRP - Gamma) + F_other + V
          + (S - delta SOMA par)
          - primary cash adjustment + redemption inflation
          - maturity-payment-clock adjustment
          + (coupon proxy - remittances) - J_applied + rho
```

This is the disaggregated form of `S - B_hat` and `coupon - remittances - J`.
`V` covers all securities' premiums/discounts, including agency and MBS books,
amortization and derecognition. It is never a Treasury cash-price correction.
Closure in decimal arithmetic checks accounting, not event measurement. The
independent coupon mutation fixture changes core while preserving closure.

Complete Wednesday quarters telescope reserves and sum all required weeks;
missing weeks never become partial-quarter point values. The receipt lists every
unavailable quarter and its reasons. Summaries include 2008Q4 and 2015Q4, using
2006Q1–2008Q3, 2008Q4, 2009–2015, and 2016–2025, plus declared-era totals and
separate full diagnostic-history totals. Every sum carries its observed count.
Quarterly reconciliation uses common available core quarters and names:
Treasury-deposit clock; Fed snapshot par versus Z.1 source/valuation; primary
price; redemption inflation; maturity payment clock; coupon measurement/clock;
remittance source/clock; and applied internal postings. Only a comparison of the
same economic quantity on two clocks can be called pure timing.

## Reproduction

External acquisition uses the existing fiscus registry/exporter, with discovery
before fetch. The caller-owned overlay supplies DTS Table II and FRN entries.
The consolidated manifest pins every source file's hash, coverage, vintage and
cache key, including dated ESF cash. From this worktree:

```
uv run python scripts/acquire_trc_inputs.py --registry weekly-trc --fiscus-project ../../../fiscus
```

From a clean committed producer, run:

```
uv run tdc weekly-trc-export --inputs-manifest-sha256 MANIFEST_SHA256 --ledger-sha256 LEDGER_SHA256 --trc-components-sha256 COMPONENTS_SHA256
uv run pytest
uv run pytest -m integration tests/test_weekly_trc.py
```

The branch-only files are `trc_weekly_components_v1.csv`,
`trc_weekly_quarterly_v1.csv`, `trc_weekly_identity_v1.csv`,
`trc_weekly_soma_changes_v1.csv`, `trc_weekly_route_daily_v1.csv`, and
`trc_weekly_v1_receipt.json`. The receipt binds the committed producer, exact
input/output hashes, column sources/clocks/units, unavailable quarters, era
summaries, uncertainty statuses and unchanged admitted-artifact hashes.

Source conventions: [Treasury settlement regulations, Appendix B](https://www.treasurydirect.gov/files/laws-and-regulations/auction-regulations-uoc/31-cfr-part-356.pdf),
[Treasury rollovers](https://www.newyorkfed.org/markets/treasury-rollover-faq),
[SOMA holdings](https://www.newyorkfed.org/markets/soma-holdings),
[FRN daily indexes](https://www.treasurydirect.gov/auctions/announcements-data-results/frn-daily/),
[DTS](https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/), and
[Treasury's dated corporate-credit contribution](https://home.treasury.gov/news/press-releases/sm1007).

## Build readout

The generated receipt carries era sums, observed counts, unavailable quarters,
internal-posting statuses, classification dollars, route scenarios and the named
quarterly differences. All 45 observed TIPS redemptions use published nominal-date
reference CPI; reconstructed issue-ratio comparisons still report six mismatches.
