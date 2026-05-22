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

## Interpretation Rule

Use the equations in this order:

1. theoretical identities to explain what TDC is
2. implemented equations to explain what the repo actually measures
3. bounded and diagnostic surfaces to explain what is still historical-only, nondefault, or cross-check-only

For the machine-readable mapping between theory and measurement, see:
- generated `data/processed/tdc_theory_measurement_map.md` after a local pipeline run
