# Equations

This document separates:

- **theoretical TDC accounting identities**
- **implemented repo estimators**
- **bounded or diagnostic measurement surfaces**

The theoretical equations describe what TDC **is**. The repo estimates are narrower public-data approximations that map parts of that theory into measurement.

## Theoretical Identities

These are informational and conceptual. They should not be read as claims that every term is directly measured in the live repo.

### 1. DU-Facing Definition

```math
\Delta D^{TDC}_{DU}
=
\left(G^{ND}_{DU} - R^{T}_{DU}\right)
+ DS^{T}_{DU}
+ \left(Q^{T}_{DU \to RU} - Q^{T}_{RU \to DU}\right)
```

Plain English:
- TDC is the Treasury-driven part of deposit change seen from the domestic nonbank deposit-user side.
- It rises when Treasury makes net payments into DU deposits, pays Treasury-security debt service into DU deposits, or when DUs are net sellers of Treasury securities to reserve-side counterparties.

### 2. Treasury-Cash Constraint Version

```math
\Delta D^{TDC}_{DU}
=
\left(Q^{T}_{DU \to RU} - Q^{T}_{RU \to DU}\right)
+ \left(I^{T} + R^{T}_{RU} + \Pi^{F}_{T} - G^{ND}_{RU} - DS^{T}_{RU}\right)
- \Delta TOC
```

Plain English:
- This is the main Treasury-cash identity behind the measurement program.
- The key change relative to older shorthand is that the cash term is **TOC**:
  Treasury operating cash,
  not a narrow TGA-only concept.

### 3. Fed Remittance and Deferred-Asset Treatment

```math
\Pi^{F}_{T,t} = \max(0, E^{F}_{t} - DA^{F}_{t-1})
```

```math
DA^{F}_{t} = \max(0, DA^{F}_{t-1} - E^{F}_{t})
```

Plain English:
- Negative Fed earnings do not imply Treasury pays the Fed.
- They build a deferred asset and suppress future remittances until that deferred asset has been worked off.
- In the live estimator, Fed remittances are measured from MTS Table 4 Treasury cash receipts when that support file is present; H.4.1/FRED remittances-due levels are retained only as a fallback/comparison source.

### 4. Residual Deposit-Decomposition Version

```math
\Delta D^{TDC}_{DU}
=
\left(\Delta M - \Delta C - \Delta X\right)
- \left(\Delta L^{B}_{DU} + \Delta A^{B,NT}_{DU}\right)
- \Delta A^{CB,NT}_{DU}
- \Delta F^{NT}_{DU}
- \varepsilon
```

Plain English:
- This is the residual or monetary-disaggregated framing.
- Start from deposit change, subtract major non-Treasury drivers, and treat the remainder as the Treasury contribution.

## Implemented Repo Equations

These are the live measurement approximations currently used by `tdcest`.

### Bank-Only Baseline

```math
\Delta D^{mkt,bank}_{TDC,t}
=
\Delta TS^{tx}_{Fed,t}
+ \Delta TS^{tx}_{Banks,t}
+ \Delta TS^{tx}_{ROW,t}
- \Delta TOC^{tx}_{Treasury,t}
+ Remit^{+}_{Fed,t}
```

This is the Tier 0 bank-only baseline, not the final corrected measurement row.

Current construction note:
- `Remit^{+}_{Fed,t}` is the quarter-sum of MTS Table 4 net receipts for Federal Reserve earnings deposits when `support__fed_remit_mts.csv` exists
- without that support file, the repo falls back to positive-only H.4.1/FRED weekly remittances-due levels

### Broad-Depository Natural-Person Credit-Union Alternative

```math
\Delta D^{mkt,broad}_{TDC,t}
=
\Delta D^{mkt,bank}_{TDC,t}
+ \Delta TS^{tx}_{CU^{NP},t}
```

This is the main broader-perimeter comparison, not the preferred headline.

### Tier 2 Interest-Corrected Approximation

```math
\Delta D^{Tier2,bank}_{TDC,t}
=
\Delta D^{mkt,bank}_{TDC,t}
- Coupon^{F}_{t}
- Coupon^{Banks}_{t}
- Coupon^{ROW}_{t}
```

This removes coupon-interest distortions from the base transaction ladder.

Current construction note:
- the Fed coupon term is exact SOMA-based from the first full public SOMA quarter onward; when the support file is built with `--wamest-root`, earlier quarters use a WAMEST/H.15 Fed coupon-intensity backcast
- the bank and ROW coupon terms are built from `wamest` sector coupon-intensity weights
- the default live support files use those raw quarter-end weights directly
- a research-only cash-anchored variant can rescale the non-Fed weights to the observed non-Fed Treasury interest pool after subtracting the exact Fed coupon term
- otherwise the repo falls back to the raw quarter-end maturity/curve approximation

### Tier 2 MMF/RRP Candidate

```math
\Delta D^{Tier2+MMF,bank}_{TDC,t}
=
\Delta D^{Tier2,bank}_{TDC,t}
+ A^{MMF,RRP}_{t}
```

The preferred candidate uses the fund-month proportional adjustment:

```math
A^{MMF,RRP}_{t}
=
\sum_{m \in t}\sum_i
R^{-}_{i,m}
\cdot
\frac{T^{+}_{i,m}}{T^{+}_{i,m}+U^{other}_{i,m}}
```

where:

```math
R^{-}_{i,m}=\max(0,-\Delta FedRRP_{i,m})
```

```math
T^{+}_{i,m}=\max(0,\Delta Treasury^{MMF}_{i,m})
```

```math
U^{other}_{i,m}
=
\max(0,\Delta A^{nonTreasury,nonFedRRP}_{i,m})
+
\max(0,-\Delta NAV_{i,m})
```

The repo also emits lower and upper bounds:

```math
A^{UB}_{i,m}=\min(T^{+}_{i,m},R^{-}_{i,m})
```

```math
A^{LB}_{i,m}=\min(T^{+}_{i,m},\max(0,R^{-}_{i,m}-U^{other}_{i,m}))
```

Current construction note:
- the proportional adjustment feeds the canonical Tier 2 row when paired with the component-anchored depository-institution estimator
- the raw input is `data/raw/support__mmf_fund_month.csv`
- the preferred Treasury definition is total Treasury securities, with bills-only rows kept as robustness checks

### Depository-Institution Credit-Union Candidate

```math
\Delta D^{Tier2,DI}_{TDC,t}
=
\Delta D^{Tier2,broadNP}_{TDC,t}
-
Coupon^{CU}_{t}
```

This candidate includes natural-person credit-union Treasury transactions and subtracts a separate credit-union Treasury coupon-interest proxy when `support__credit_union_tsy_coupon_interest_proxy.csv` is present. The default proxy is built from `wamest` sector maturity estimates and the `credit_unions_marketable_proxy` level series, reconstructing computed full-history sectors from WAMEST inventory dependencies when the prebuilt full sector panel is absent.

### Tier 2 Component-Anchored Candidate

```math
\Delta D^{Tier2,component}_{TDC,t}
=
\Delta D^{Tier0}_{TDC,t}
-
Coupon^{Fed}_{t}
-
I^{component,Banks}_{t}
-
I^{component,ROW}_{t}
```

For the depository-institution row:

```math
\Delta D^{Tier2,component,DI}_{TDC,t}
=
\Delta D^{Tier2,component,broadNP}_{TDC,t}
-
I^{component,CU}_{t}
```

The component inputs are `support__bank_tier2_component_interest_proxy.csv`, `support__row_tier2_component_interest_proxy.csv`, and `support__credit_union_tier2_component_interest_proxy.csv`. They are exported from `tier2_interest_component_candidate.csv` and allocate official Treasury coupon-accrual, bill-discount, and FRN interest pools using source-constrained sector weights. When these support files are present, they feed the canonical Tier 2 interest-corrected rows; the legacy WAMEST/H.15 coupon-intensity rows remain available under explicit `tdc_tier2_h15_*` sensitivity names.

The nondefault Fed-extension variants additionally subtract:

```math
FedExt_t = BillDisc^{Fed}_t + FRN^{Fed}_t
```

from `support__fed_tier1_component_extension_proxy.csv`. This extension excludes TIPS inflation compensation and does not add the separate Fed TIPS coupon diagnostic, to avoid double-counting coupon-like SOMA payments already handled by the existing Fed coupon schedule.

### Tier 2 Bill-Discount Robustness

```math
\Delta D^{Tier2+BillDisc,bank}_{TDC,t}
=
\Delta D^{Tier2,bank}_{TDC,t}
-
BillDisc^{Banks}_{t}
-
BillDisc^{ROW}_{t}
```

The bill-discount proxies are built from WAMEST sector bill shares and levels, Treasury bill WAM support, and the Treasury curve. They test whether using broader "Treasury-security interest correction" language changes the Tier 2 read materially beyond the implemented coupon correction.

The validation benchmark is Treasury FiscalData `interest_expense`, filtered to public-issue `Treasury Bills` / `AMORTIZED DISCOUNT` and summed from monthly dollars to calendar-quarter millions. That aggregate benchmark does not allocate bill discount by holder; it is used to check whether the WAMEST-backed bank, ROW, and credit-union sector proxies are plausible fractions of total Treasury bill discount before promoting the robust row to a headline canonical estimator.

### Canonical Tier 2 Policy Target

```math
\Delta D^{Tier2,canonical}_{TDC,t}
=
\Delta D^{Tier2+BillDisc,DI}_{TDC,t}
+
MMF^{RRP,prop}_{t}
```

The explicit canonical Tier 2 series key is `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow`. It is an alias for the depository-institution Treasury-flow row with Fed, bank, ROW, and credit-union coupon corrections; bank, ROW, and credit-union bill-discount corrections; and the preferred proportional MMF/RRP source-of-funds adjustment. In `method_meta.json`, this appears as `canonical_tier2_method`.

### Tier 3 Fiscal-Corrected Approximation

```math
\Delta D^{Tier3,bank}_{TDC,t}
=
\Delta D^{Tier2,bank}_{TDC,t}
- Outlay^{Banks}_{t}
- Outlay^{ROW}_{t}
+ Receipt^{Banks}_{t}
+ Receipt^{ROW}_{t}
+ CashFactor_{t}
```

This is a partial fiscal-flow shell, not the main live corrected estimate.

Important caveat:
- current bank receipt corrections are still nondefault for current quarters
- current ROW receipt corrections remain nondefault
- so this remains a **partial** fiscal-flow implementation below the canonical Tier 2 row

## Bounded And Diagnostic Surfaces

### Historical Bank-Receipt Overlay

```math
\Delta D^{HistBank}_{TDC,t}
=
\Delta D^{Tier3,bank}_{TDC,t}
+ \Delta Receipt^{Bank,Table5.1}_{t}
```

This is the strongest bank-receipt result in the repo, but only inside the age-eligible historical window.

### MRV ROW Pilot

```math
\Delta Receipt^{ROW,MRV}_{t} \subset \Delta D^{Tier3,bank}_{TDC,t}
```

This is the only serious recurring ROW receipt candidate currently carried forward. It remains nondefault.

### Monetary Cross-Check

```math
\Delta D^{decomp}_{TDC,t}
\approx
\Delta M_t
- \Delta C_t
- \Delta X_t
- \text{non-Treasury deposit drivers}
```

This is diagnostic only. It is useful as a cross-check, not as the headline estimator.

## Treasury Component of Reserves (TRC)

TRC is an additive, opt-in companion to TDC. It reads the frozen TDC leg table and never rewrites it.

### Theory

```math
TDC^{DU}_q=\sum_{e\in\mathcal T_q}\lambda^{DU}_e f_e,
\qquad
TRC^{RB}_q=\sum_{e\in\mathcal T_q}\mu^{RB}_e f_e,
\qquad
\Delta RB_q = TRC^{RB}_q + N^{RB}_q
```

Plain English:
- TDC and TRC weight the same Treasury cash and Treasury-security settlement events; TDC records the effect on covered deposits, TRC the effect on aggregate reserve balances.
- `N^{RB}` is every reserve posting not classified to a Treasury event.
- Incidence follows the claim debited or credited at settlement, not the holder's legal sector. The typed route registry (`settlement_routes.py`) gives each claim a deposit and a reserve incidence; an event moving cash from claim A to claim B posts `(λ_B − λ_A, μ_B − μ_A)`. A foreign official paying from its Fed deposit and the same holder paying through a bank therefore post different reserve changes.

The exact wedge is the same event ledger weighted by the incidence difference:

```math
TDC^{DU}_q-TRC^{RB}_q=\sum_{e\in\mathcal T_q}\left(\lambda^{DU}_e-\mu^{RB}_e\right)f_e
```

### Implemented Default Rows

```math
\widehat{TRC}^{core}_q
=
-\Delta TGA_q
-\Delta SFP_q
+\Delta TS^{tx}_{Fed,q}
+Remit^{+}_{Fed,q}
-Coupon^{F}_q
```

```math
\widehat{TRC}^{pref}_q=\widehat{TRC}^{core}_q+A^{MMF,RRP,prop}_q
```

Current construction note:
- USD million on the Z.1 calendar quarter; the reserve outcome is Z.1 `FU713113003`
- `ΔTGA` uses the last H.4.1 `WDTGAL` Wednesday on or before quarter end for changes through 2005Q4 and the DTS Table I final-business-day close for changes from 2006Q1; both endpoints of every change sit on one clock, and each row records its clock
- `ΔSFP` is the DTS supplementary financing account, a structural zero before the program and after the line closes at a zero balance; Treasury Tax and Loan balances are commercial-bank claims and stay out of the cash leg, so Z.1 Treasury operating cash is not used here
- the Fed terms are the frozen leg-table `fed_tsy_tx`, actual MTS cash remittances, and the SOMA coupon proxy
- the MMF/ON RRP term carries lower, proportional, and upper companions; it is definitionally zero before the ON RRP mechanism and one-sided after it, so the preferred row is labeled `partial_one_sided_route_coverage`
- all four 2002 rows are unavailable because no H.4.1 TGA level precedes 2002-12-18

The non-Treasury residual `ΔRB − \widehat{TRC}^{pref}` closes by construction and is labeled definitional.

The measured wedge is a reconciliation of producer legs, not an identity:

```math
\widehat{TDC}_q-\widehat{TRC}^{pref}_q
=
\left(B^{net}_q-I_{B,q}\right)
+R_q
-\Delta TT\&L_q
+u_q
```

where `B^{net}` is bank Treasury transactions, `I_B` the bank interest proxy, `R` the ROW leg, and `u` the residual between Z.1 Treasury operating cash and DTS TGA plus SFP plus TT&L. `ΔTT&L` and `u` are unavailable before 2006.

### Nondefault Bounds And Diagnostics

- GSE ON RRP route: `[0, \min(GSE\ Treasury\ increase^{+}, GSE\ ON\ RRP\ runoff^{+})]`
- foreign-official direct-account route, a heuristic opposite-sign overlap of custody `C` and foreign official Fed cash `F` (deposits plus reverse repos); custody is never a point estimate:

```math
\Gamma^{FO}_q\in\left[-\min\left((-\Delta C_q)^{+},(\Delta F_q)^{+}\right),\ \min\left((\Delta C_q)^{+},(-\Delta F_q)^{+}\right)\right]
```

- remainder cells subtract the Treasury allocation exactly once:

```math
N^{RB}_{RRP,q}=-\Delta RRP_q-\Gamma^{T}_{RRP,q},
\qquad
N^{RB}_{FO,q}=-\Delta\left(D^{FO}_q+RRP^{FO}_q\right)-\Gamma^{T}_{FO,q}
```

- memo perimeters: reserves plus ON RRP, H.3 total reserves, US-chartered reserves; and an all-H.4.1 clock diagnostic

### H.4.1 Reserve-Factor Ledger And Bridges

The opt-in `tdc reserve-factor-ledger-export` command builds an independent H.4.1 Table 1 ledger on the Wednesday clock and reconciles it with the admitted TRC rows above, which it reads under a pinned hash and never rewrites.

```math
\Delta RB^{H}_w=\sum_{k\in S}\Delta A_{k,w}-\sum_{k\in A}\Delta L_{k,w}+\rho^{H}_w,
\qquad
C^{H}_w=-\Delta TGA_w-\Delta SFP_w,
\qquad
S^{H}_w=\Delta TS^{H.4.1}_w
```

Plain English:
- `S` are the supplying factors and `A` the absorbing factors other than reserve balances; each enters once as a signed change `f_k`
- `ρ^H` is the published rounding plus any unmapped row; level and change closure against reserve balances, the two published totals, and each published parent must hold within half a million per rounded component, or the export fails
- `C^H` uses the H.4.1 TGA and SFP rows only; Treasury Tax and Loan balances are not Federal Reserve liabilities
- `S^H` is the change in Table 1 "U.S. Treasury securities" held outright: bills, nominal notes and bonds, inflation-indexed notes and bonds, and inflation compensation; premiums and discounts cover all securities held outright and remain separate factors
- quarters telescope between the last Wednesdays of adjacent quarters, the same dating as the all-H.4.1 TRC diagnostic

For each admitted TRC row `x = C^M + B + Γ` (core, preferred, lower, upper) and the Z.1 outcome `y^Z`:

```math
y^{Z}_q-x_q=\sum_{k\notin\{TGA,SFP,TS,RRP^{o}\}}F^{H}_{k,q}+N^{RRP,o}_q+\left(y^{Z}_q-y^{H}_q\right)+\left(C^{H}_q-C^{M}_q\right)+\left(S^{H}_q-B_q\right)+\rho^{H}_q,
\qquad
N^{RRP,o}_q=-\Delta RRP^{o}_q-\Gamma_q
```

- the identity holds row by row; the MMF/ON RRP route already counted in TRC is removed from the RRP-others factor once
- `y^Z − y^H` is the outcome perimeter, clock, and source bridge; it splits into the H.4.1 term-deposit change (Z.1 `FL713113003` includes term deposits), Z.1 transactions less the Z.1 level change, and an explicit unattributed remainder that carries the quarter-end versus last-Wednesday clock and the 2007Q1–2017Q4 FHLB exclusion
- `C^H − C^M` is the Treasury-deposit clock and source bridge; `S^H − B` is the securities valuation, accrual, and Fed-payment bridge
- the bridges and `ρ^H` are measured accounting differences, not estimates; no covariance or causal decomposition is computed here

## Interpretation Rule

Use the equations in this order:

1. theoretical identities to explain what TDC is
2. implemented equations to explain what the repo actually measures
3. bounded and diagnostic surfaces to explain what is still historical-only, nondefault, or cross-check-only

For the machine-readable mapping between theory and measurement, see:
- generated `data/processed/tdc_theory_measurement_map.md` after a local pipeline run
