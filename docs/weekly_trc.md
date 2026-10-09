# Weekly Treasury component of reserves

`weekly-trc-export` builds a cash-corrected Wednesday core **proxy**, a separate
uncorrected par sensitivity, and signed ON RRP route scenarios. It preserves
all admitted quarterly TRC and reserve-factor ledger artifacts. There is no
weekly preferred series, estimator, or allocation of monthly fund positions.

## Measurement and cash conventions

Weeks run Thursday through Wednesday. Exact Wednesday SOMA snapshots are
preferred. A source as-of date is mapped to a target Wednesday only when every
day in `(min(source, target), max(source, target)]` is closed for Federal Reserve
settlement. This admits the Tuesday before a Wednesday holiday and the
Thanksgiving Thursday after a Wednesday, without crossing an open settlement
day. Fridays before Saturday fixed holidays remain open. Original dates,
individual payload hashes, effective Wednesdays and substitution reasons are
retained in the manifest and receipt. The same mapped positions supply
classification, the Fed leg, coupon entitlement and route redemption holdings.
A missing eligible snapshot stays unavailable.

The admitted ledger supplies
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
remaining $10bn stock change stays candidate-only. Dated cash is examined even
when the facility factor has zero change. Unmatched nonzero postings retain
their cash dates, signed amounts and cash-candidate status separately from
stock candidates; matched cash is excluded from that list once. A possibly
delayed adjacent-week stock counterpart is not matched. Other cash/stock
mismatches remain candidates. Cash-candidate coverage is limited to the pinned
ESF query, 2020-01-01–2025-12-31; outside that window the cash input is
unavailable, not zero. This is candidate reporting within that source and
account perimeter, not a comprehensive Treasury–Fed cash crosswalk. SDR and gold entries lack a dated TGA/special-account cash
crosswalk and are candidate-only. Neither a reclassification nor an unmatched
certificate account entry is mechanically added to core. Coin, Treasury currency,
Treasury cash holdings, IORB and FIMA lending stay outside core.

Coupons are **payment-date proxies on prior-week positions**, plus known primary
allotments settling strictly before payment. Acquisition accrued interest enters
primary cash once; the subsequent full coupon enters once. Unknown primary
entitlement on a payment date makes that coupon unavailable, including an
auction-only non-bill CUSIP absent from both snapshots. Such CUSIPs remain in
the event universe even when their allotment is unknown. Secondary trades
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

Producer `1f19cc15a34d78f2627e3c274e4ca9f2a447fffe`; receipt SHA-256
`6bcf0fc4cbb4b419fccd3d7b391b3e22d0a3df6501dd9fbfa49cc2d1f4e56fb4`.

The default full suite reports **556 passed, 0 failed, 8 skipped, 3 deselected**.
The live weekly-export integration check reports **1 passed, 0 failed,
0 skipped, 17 deselected**. All five output hashes match the receipt. Admitted
artifacts retain their pre-build hashes. Weekly Decimal identity errors and
quarterly reserve telescoping errors are zero; the largest admitted-component
reconciliation residue is 8.7E-11 USD million from printed float inputs.
These are accounting checks, not validation of unobserved prices or entitlement.

Core coverage is **1,056 weeks, 2005-10-12–2025-12-31**. The first complete
available quarter is **2006Q1**. Quarterly reconciliation covers **80 complete
common quarters**, all quarters from 2006Q1 through 2025Q4.

All monetary tables below are signed sums in **USD billion**. The four eras
cover 1,044 available core weeks; twelve available 2005Q4 weeks remain in the
full-history receipt. Core and par use the same available weeks.

| Era | Core weeks | Cash-corrected core | Par sensitivity | Primary cash adjustment | TIPS redemption inflation |
| --- | --- | --- | --- | --- | --- |
| 2006Q1–2008Q3 | 143 | -408.394 | -407.074 | -0.286 | 1.034 |
| 2008Q4 | 14 | -196.312 | -196.229 | -0.083 | 0.000 |
| 2009–2015 | 365 | 2,210.238 | 2,213.173 | -0.488 | 2.447 |
| 2016–2025 | 522 | 673.027 | 796.041 | -49.743 | 41.763 |
| Total | 1044 | 2,278.558 | 2,405.911 | -50.600 | 45.244 |

| Era | J applied | Stock-candidate-only | Cash-candidate-only | Statuses |
| --- | --- | --- | --- | --- |
| 2006Q1–2008Q3 | 0.000 | 0.000 | unavailable | Certificate special-account cash link unobserved; dated cash unavailable |
| 2008Q4 | 0.000 | 0.000 | unavailable | No stock candidate; dated cash unavailable |
| 2009–2015 | 0.000 | 3.000 | unavailable | Certificate special-account cash link unobserved; dated cash unavailable |
| 2016–2025 | -31.509 | 40.688 | 26.072 | Dated full/partial matches; stock mismatches; unmatched dated cash |

Stock and cash candidate totals are separate descriptions and are not additive:
a delayed counterpart can appear in both candidate classes. Signed net candidates
are not uncertainty limits. Cash-candidate coverage is 313 complete weeks in the
2020–2025 query; it is unavailable for 209 earlier/partial weeks of the 2016–2025
era, and throughout the three earlier eras.

The modern facility posting statuses comprise eleven
`applied_dated_dts_facility_cash_match` weeks (+$5.991bn), one
`applied_dated_cash_partial_stock_remainder_candidate` week (−$37.500bn applied,
−$10.000bn stock remainder), and eight
`candidate_only_dts_cash_stock_mismatch` weeks (+$40.688bn stock candidates).
SDR candidates are +$3.000bn in 2009–2015 and +$10.000bn in 2016–2025 under
`candidate_only_certificate_special_account_tga_link_unobserved`. Gold has zero
signed net and $0.006bn absolute candidates in 2006Q1–2008Q3 under the same status.

There are 219 weeks with `cash_candidate_only_no_same_week_stock_crosswalk`:
+$26.072bn signed and $60.334bn absolute unmatched cash postings. Seven weeks
have applied cash with no unmatched postings, and 87 have no nonzero cash
candidate. Among the 219 candidate weeks, all **203 zero-stock-change weeks**
identified in the review retain their nonzero dated cash (signed net **−$15.107bn**).
The 2020-04-13 withdrawal remains a **−$10.000bn cash candidate** in the week
ending 2020-04-15 and is not applied. The 2020-05-11 **−$37.500bn** application
is retained; its **−$10.000bn stock remainder** stays a candidate.

| Reconciliation component | 2006Q1–2008Q3 | 2008Q4 | 2009–2015 | 2016–2025 | Total |
| --- | --- | --- | --- | --- | --- |
| Complete common quarters | 11 | 1 | 28 | 40 | 80 |
| Treasury deposit clock | 167.168 | -167.498 | 8.601 | -8.601 | -0.330 |
| Fed source/par vs Z.1 | -3.275 | 0.706 | -42.737 | -142.231 | -187.537 |
| Primary cash price | -0.286 | -0.083 | -0.488 | -49.743 | -50.600 |
| Redemption inflation | -1.034 | 0.000 | -2.447 | -41.763 | -45.244 |
| Coupon measurement/clock | -0.163 | -0.668 | -6.959 | -23.018 | -30.809 |
| Remittance source/clock | 0.002 | 0.003 | 0.003 | 0.004 | 0.013 |
| Internal postings | 0.000 | 0.000 | 0.000 | -31.509 | -31.509 |
| Maturity payment clock | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Core difference | 162.412 | -167.541 | -44.027 | -296.860 | -346.016 |

The differences compare Wednesday-bounded weekly sums with the admitted
calendar-quarter components. Their sum reconciles the core difference up to
the retained printed-input arithmetic residue. No residual is assigned to an
unobserved cash correction.

Unavailable quarters are **2003Q3, 2003Q4, 2004Q1, 2004Q2, 2004Q3, 2004Q4,
2005Q1, 2005Q2, 2005Q3 and 2005Q4**, all with
`unavailable_dts_daily_coverage`. The opening SOMA coverage is also unavailable
in 2003Q3: **2003-07-02 has no eligible snapshot**, and 2003-07-09 cannot cross
open settlement days to replace it. The pinned DTS history begins 2005-10-03;
the week ending 2005-10-05 needs earlier days and remains unavailable.

Fourteen substitutions share the manifest reason
`unchanged_position_across_non_settlement_days`. “Wednesday holiday” means a
Tuesday source carried across the closed Wednesday; “Thanksgiving” means the
closed Thursday source mapped to the preceding Wednesday. Hashes identify the
individual original fiscus snapshot payloads, not the consolidated file.

| Target Wednesday | Source as-of | Reason | SHA-256 |
| --- | --- | --- | --- |
| 2007-07-04 | 2007-07-03 | Wednesday holiday | `8377f314d6f5c3072589b5987bf9749b01d3e91ae22efa1d0363c2e7aa7cc48b` |
| 2009-11-11 | 2009-11-10 | Wednesday holiday | `a7a2d70d4ca553f1cecc5dbdf8cf7bfd20ad02412d2d687a021508a0889d0da0` |
| 2012-07-04 | 2012-07-03 | Wednesday holiday | `177226a98fa8b8aaf172ef824216cae079b9d1b2ca1cf5fac7cf8ffc7e01f91d` |
| 2013-12-25 | 2013-12-24 | Wednesday holiday | `4b6b557d8c250a7f14d7f4887cfe4bcbebde5b47c4e32eee120206a7fdde25bd` |
| 2014-01-01 | 2013-12-31 | Wednesday holiday | `8c6c1e42b81bd26afaae5e586ba0c812c241faa53cf0391db9dc094a89153aa2` |
| 2015-11-11 | 2015-11-10 | Wednesday holiday | `862133e46afaba33d4ef6c55e99c35424caad51b2a5c15bc783e82f046e7155e` |
| 2018-11-21 | 2018-11-22 | Thanksgiving | `a26afaab6e5030d4e987f344b09d3b150f00ae7e1f84508f0f6991e243de6ea3` |
| 2019-11-27 | 2019-11-28 | Thanksgiving | `73eca0afb51f2778c8b2b67aa37572e24bedc1b72d04578459e4337d88e1bdac` |
| 2019-12-25 | 2019-12-24 | Wednesday holiday | `a649343739f50afd8fc98578f21a2ce1c71b97b8925a232666c904cc972dfe5b` |
| 2020-01-01 | 2019-12-31 | Wednesday holiday | `3ded1c724fdb1ea0cb612f87b5a8692ea7537b36e648c560139012d4fc02d40e` |
| 2020-11-11 | 2020-11-10 | Wednesday holiday | `ecc32bfa59b342cb2816a7223dbc093c1be1801ff4dd7bbd9dc0ca43f4c166bf` |
| 2024-06-19 | 2024-06-18 | Wednesday holiday | `186fc872be687214056854888558f7cf964b3404f44f5cd8bfbdcbf88a1263f2` |
| 2024-12-25 | 2024-12-24 | Wednesday holiday | `5e4fd156f5af1f1d83fd0d4c5633f48f2e2e7ceffbd581d3a5fa3a0f39cb5fa3` |
| 2025-01-01 | 2024-12-31 | Wednesday holiday | `32f1e5b31e46a476c1d5c46b3dee81d7ccf474be83c4046f25290fd38d0e8c5a` |

| Era | Forward scenario (observed weeks) | Reverse scenario (observed weeks) |
| --- | --- | --- |
| 2006Q1–2008Q3 | 0.000 (143) | 0.000 (143) |
| 2008Q4 | 0.000 (14) | 0.000 (14) |
| 2009–2015 | 8,990.325 (361) | -8,786.144 (362) |
| 2016–2025 | 86,570.446 (508) | -83,647.568 (509) |

Missing capacities are not zero. These are observed-week sums rather than
full-era route totals; early zeros declare facility scope. The TIPS reconstruction
check compares 259 rows with one unavailable row and six mismatches. All 45 TIPS
redemptions use published nominal-date reference CPI; their quantities retain
the no-intervening-trade assumption. Secondary cash prices and coupon entitlement
remain unobserved where stated. The coupon regression propagates an unknown
auction-only pre-payment allotment to an unavailable payment with its reason.
