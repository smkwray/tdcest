# Equations

This document separates:

- **theoretical TDC accounting identities**
- **implemented repo estimators**
- **bounded or diagnostic measurement surfaces**

The theoretical equations describe what TDC **is**. The repo estimates are narrower public-data approximations that map parts of that theory into measurement.

## Theoretical Identities

These are informational and conceptual. They should not be read as claims that every term is directly measured in the live repo.

### 1. DU-Facing Definition

```text
ΔD^TDC_DU
=
(G^ND_DU - R^T_DU)
+ DS^T_DU
+ (Q^T_DU→RU - Q^T_RU→DU)
```

Plain English:
- TDC is the Treasury-driven part of deposit change seen from the domestic nonbank deposit-user side.
- It rises when Treasury makes net payments into DU deposits, pays Treasury-security debt service into DU deposits, or when DUs are net sellers of Treasury securities to reserve-side counterparties.

### 2. Treasury-Cash Constraint Version

```text
ΔD^TDC_DU
=
(Q^T_DU→RU - Q^T_RU→DU)
+ (I^T + R^T_RU + Π^F_T - G^ND_RU - DS^T_RU)
- ΔTOC
```

Plain English:
- This is the main Treasury-cash identity behind the measurement program.
- The key change relative to older shorthand is that the cash term is **TOC**:
  Treasury operating cash,
  not a narrow TGA-only concept.

### 3. Fed Remittance and Deferred-Asset Treatment

```text
Π^F_T,t = max(0, E^F_t - DA^F_t-1)
DA^F_t = max(0, DA^F_t-1 - E^F_t)
```

Plain English:
- Negative Fed earnings do not imply Treasury pays the Fed.
- They build a deferred asset and suppress future remittances until that deferred asset has been worked off.

### 4. Residual Deposit-Decomposition Version

```text
ΔD^TDC_DU
=
(ΔM - ΔC - ΔX)
- (ΔL^B_DU + ΔA^B,NT_DU)
- ΔA^CB,NT_DU
- ΔF^NT_DU
- ε
```

Plain English:
- This is the residual or monetary-disaggregated framing.
- Start from deposit change, subtract major non-Treasury drivers, and treat the remainder as the Treasury contribution.

## Implemented Repo Equations

These are the live measurement approximations currently used by `tdcest`.

### Bank-Only Baseline

```text
ΔD^mkt,bank_TDC,t
=
ΔTS^tx_Fed,t
+ ΔTS^tx_Banks,t
+ ΔTS^tx_ROW,t
- ΔTOC^tx_Treasury,t
+ Remit^+_Fed,t
```

This is the current bank-only headline.

### Broad-Depository Natural-Person Credit-Union Alternative

```text
ΔD^mkt,broad_TDC,t
=
ΔD^mkt,bank_TDC,t
+ ΔTS^tx_CU^NP,t
```

This is the main broader-perimeter comparison, not the preferred headline.

### Tier 2 Interest-Corrected Approximation

```text
ΔD^Tier2,bank_TDC,t
=
ΔD^mkt,bank_TDC,t
- Coupon^F_t
- Coupon^Banks_t
- Coupon^ROW_t
```

This removes coupon-interest distortions from the base transaction ladder.

Current construction note:
- the Fed coupon term is still the exact SOMA-based proxy
- the bank and ROW coupon terms are built from `wamest` sector coupon-intensity weights
- the default live support files use those raw quarter-end weights directly
- a research-only cash-anchored variant can rescale the non-Fed weights to the observed non-Fed Treasury interest pool after subtracting the exact Fed coupon term
- otherwise the repo falls back to the raw quarter-end maturity/curve approximation

### Tier 3 Fiscal-Corrected Approximation

```text
ΔD^Tier3,bank_TDC,t
=
ΔD^Tier2,bank_TDC,t
- Outlay^Banks_t
- Outlay^ROW_t
+ Receipt^Banks_t
+ Receipt^ROW_t
+ CashFactor_t
```

This is the main live corrected estimate in the repo.

Important caveat:
- current bank receipt corrections are still nondefault for current quarters
- current ROW receipt corrections remain nondefault
- so this is still a **partial** fiscal-flow implementation

## Bounded And Diagnostic Surfaces

### Historical Bank-Receipt Overlay

```text
ΔD^HistBank_TDC,t
=
ΔD^Tier3,bank_TDC,t
+ ΔReceipt^Bank,Table5.1_t
```

This is the strongest bank-receipt result in the repo, but only inside the age-eligible historical window.

### MRV ROW Pilot

```text
ΔReceipt^ROW,MRV_t ⊂ ΔD^Tier3,bank_TDC,t
```

This is the only serious recurring ROW receipt candidate currently carried forward. It remains nondefault.

### Monetary Cross-Check

```text
ΔD^decomp_TDC,t
≈
ΔM_t
- ΔC_t
- ΔX_t
- non-Treasury deposit drivers
```

This is diagnostic only. It is useful as a cross-check, not as the headline estimator.

## Interpretation Rule

Use the equations in this order:

1. theoretical identities to explain what TDC is
2. implemented equations to explain what the repo actually measures
3. bounded and diagnostic surfaces to explain what is still historical-only, nondefault, or cross-check-only

For the machine-readable mapping between theory and measurement, see:
- [tdc_theory_measurement_map.md](../data/processed/tdc_theory_measurement_map.md)
