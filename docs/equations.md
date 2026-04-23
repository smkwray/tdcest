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

This is the current bank-only headline.

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
- the Fed coupon term is still the exact SOMA-based proxy
- the bank and ROW coupon terms are built from `wamest` sector coupon-intensity weights
- the default live support files use those raw quarter-end weights directly
- a research-only cash-anchored variant can rescale the non-Fed weights to the observed non-Fed Treasury interest pool after subtracting the exact Fed coupon term
- otherwise the repo falls back to the raw quarter-end maturity/curve approximation

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

This is the main live corrected estimate in the repo.

Important caveat:
- current bank receipt corrections are still nondefault for current quarters
- current ROW receipt corrections remain nondefault
- so this is still a **partial** fiscal-flow implementation

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
- [tdc_theory_measurement_map.md](../data/processed/tdc_theory_measurement_map.md)
