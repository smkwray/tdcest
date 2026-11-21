# Equations

All quarterly and monthly flows are in USD millions unless noted otherwise. Each symbol is defined at first use.

## Theoretical definition and accounting identity

Let deposit users ($\text{DU}$) be households, firms, and other nonbanks holding and paying from US bank deposits. Their bank deposits change over quarter $t$ by the Treasury Deposit Component ($\text{TDC}_t$) plus all other deposit changes ($N_t$):

```math
\Delta D_t = \text{TDC}_t + N_t
```

Seen from deposit users' accounts, TDC equals Treasury non-debt spending paid to them ($G^{\text{DU}}_t$), minus taxes and other payments to the Treasury ($T^{\text{DU}}_t$), plus Treasury interest ($I^{\text{DU}}_t$) and principal ($M^{\text{DU}}_t$) paid to them, plus proceeds from selling Treasury securities to other sectors ($S^{\text{DU}}_t$), minus payments for Treasury securities bought, including at auction ($P^{\text{DU}}_t$):

```math
\text{TDC}_t = G^{\text{DU}}_t - T^{\text{DU}}_t + I^{\text{DU}}_t + M^{\text{DU}}_t + S^{\text{DU}}_t - P^{\text{DU}}_t
```

The Treasury's cash balance changes by total receipts ($T_t$), minus non-interest outlays ($G_t$) and debt interest ($I_t$), plus net Treasury issuance ($\Delta B^{\text{net}}_t$) and Federal Reserve remittances to the Treasury ($\text{Remit}^{+}_{\text{Fed},t}$):

```math
\Delta \text{Cash}^{T}_t = T_t - G_t - I_t + \Delta B^{\text{net}}_t + \text{Remit}^{+}_{\text{Fed},t}
```

Positive Federal Reserve earnings ($E^{\text{Fed}}_t$) pay down any deferred asset ($DA^{\text{Fed}}_{t-1}$) before generating remittances; negative earnings raise the deferred asset:

```math
\text{Remit}^{+}_{\text{Fed},t} = \max\left(0,\; E^{\text{Fed}}_t - DA^{\text{Fed}}_{t-1}\right),
\qquad
DA^{\text{Fed}}_t = \max\left(0,\; DA^{\text{Fed}}_{t-1} - E^{\text{Fed}}_t\right)
```

With market clearing ($\Delta B^{\text{net}}_t = P^{\text{DU}}_t - S^{\text{DU}}_t - M^{\text{DU}}_t + \Delta \text{TS}^{\text{non-DU}}_t$) and non-interest fiscal flows settling with deposit users ($G_t - T_t = G^{\text{DU}}_t - T^{\text{DU}}_t$), substituting the Treasury cash constraint yields the Treasury-side expression below.

## Quarterly TDC measure

The series `tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow` in `data/processed/tdc_tier2_regression_series.csv` (2002Q1 onward) implements:

```math
\widehat{\text{TDC}}_t
= \Delta \text{TS}^{\text{tx}}_{\text{Fed},t}
+ \Delta \text{TS}^{\text{tx}}_{\text{Banks},t}
+ \Delta \text{TS}^{\text{tx}}_{\text{ROW},t}
+ \text{Remit}^{+}_{\text{Fed},t}
- \left(\Delta \text{Cash}^{\text{op}}_t - I^{\text{TF}}_t\right)
- \hat{I}^{\text{SOMA}}_{\text{Fed},t}
- \hat{I}_{\text{Banks}+\text{ROW},t}
+ A^{\text{prop}}_{\text{MMF},t}
```

### Sector purchases, remittances, and operating cash

Net purchases come from Z.1 quarterly transaction flows: Federal Reserve (`BOGZ1FU713061103Q`), foreign holders (`BOGZ1FU263061105Q`), and banks:

```math
\Delta \text{TS}^{\text{tx}}_{\text{Banks},t}
= \Delta \text{TS}^{\text{tx}}_{\text{USChar},t}
+ \Delta \text{TS}^{\text{tx}}_{\text{ForOff},t}
+ \Delta \text{TS}^{\text{tx}}_{\text{Affil},t}
```

summing US-chartered depository institutions (`BOGZ1FU763061100Q`), foreign banking offices in the US (`BOGZ1FU753061103Q`), and banks in US territories (`BOGZ1FU743061103Q`). The depository-institution comparison (`tdc_tier2_regression_mmf_rrp_prop_depository_institution_np_cu_ru_flow`) adds natural-person credit-union transactions (`BOGZ1FU473061103Q`) and subtracts credit-union interest $\hat{I}_{\text{CU},t}$.

Remittances sum monthly MTS Table 4 net receipts (`support__fed_remit_mts.csv`) over months $m \in t$, falling back to positive weekly H.4.1 remittances due (`RESPPLLOPNWW`, from 2002Q4) when that file is absent:

```math
\text{Remit}^{+}_{\text{Fed},t} = \sum_{m \in t} \text{MTSFedReceipts}_m
\qquad
\text{(fallback: } \sum_{w \in t} \max(0, \text{RESPPLLOPNWW}_w)\text{)}
```

Treasury operating cash uses Z.1 `BOGZ1FU313024000Q` ($\Delta \text{Cash}^{\text{op}}_t$) minus Treasury–Federal Reserve internal transfers $I^{\text{TF}}_t$ (`treasury_fed_internal_cash_tx` in `support__treasury_fed_internal_cash_tx.csv`): credit-facility equity matched to H.4.1 `H41RESH4ENWW` (plus documented Federal Reserve-account settlement exceptions) and facility LLC purchases and redemptions of nonmarketable Domestic Series securities ($I^{\text{TF}}_t = 0$ before 2020Q1).

### Treasury interest terms

Federal Reserve coupon interest sums scheduled payments across SOMA holdings $s \in \mathcal{S}_t$ paying in quarter $t$:

```math
\hat{I}^{\text{SOMA}}_{\text{Fed},t}
= \sum_{s \in \mathcal{S}_t} \text{Par}_{s,t} \cdot \frac{c_s}{100 \cdot k_s} \cdot \mathbf{1}\{\text{payment date of } s \in t\}
```

with par value $\text{Par}_{s,t}$, annual coupon rate $c_s$ in percent, and $k_s = 2$ for nominal notes, bonds, and TIPS coupons ($k_s = 4$ for FRNs). Earlier quarters before full public SOMA coverage use a Z.1 holdings, coupon-share, and H.15 yield backcast.

Marketable public Treasury interest from Fiscal Data (`interest_expense`, converted to quarterly USD millions) defines three pools: coupon accrual $P^{\text{cpn}}_t$ (notes, bonds, and TIPS accrued coupons), bill amortized discount $P^{\text{bill}}_t$, and FRN accrued interest $P^{\text{FRN}}_t$. TIPS inflation compensation and nonmarketable debt interest stay outside these pools.

From 2010Q2 onward, each pool $p \in \{\text{cpn}, \text{bill}, \text{FRN}\}$ removes exact SOMA Federal Reserve interest $I^{\text{Fed}}_{p,t}$ when present and divides the remainder across eligible sectors $j \in \mathcal{J}_p$ by weights $w_{j,p,t}$ (retaining the Federal Reserve in $\mathcal{J}_p$ on the full pool $P_{p,t}$ if $I^{\text{Fed}}_{p,t}$ is absent):

```math
P^{\text{ex-Fed}}_{p,t} = \max\left(P_{p,t} - \max(I^{\text{Fed}}_{p,t}, 0),\; 0\right),
\qquad
\hat{I}_{j,p,t} = P^{\text{ex-Fed}}_{p,t} \cdot \frac{w_{j,p,t}}{\sum_{k \in \mathcal{J}_p} w_{k,p,t}}
```

Sector interest sums the three pools ($\hat{I}_{j,t} = \hat{I}_{j,\text{cpn},t} + \hat{I}_{j,\text{bill},t} + \hat{I}_{j,\text{FRN},t}$), with $\hat{I}_{\text{Banks}+\text{ROW},t} = \hat{I}_{\text{Banks},t} + \hat{I}_{\text{ROW},t}$. From 2022Q1 onward (`constrained_component`), $w_{j,p,t}$ holds `wamest` maturity-bucket holdings to Call Report, TIC, and NCUA reports; for 2010Q2–2021Q4 (`component_pool_wamest_bucket_backcast`), $w_{j,p,t}$ uses `wamest` maturity buckets alone.

For 2002Q1–2010Q1 (`pre_component_h15_scaled_backcast`), unscaled H.15 interest combines Z.1 holdings level $\text{TS}^{\text{lvl}}_{j,t}$, coupon and bill shares ($\theta^{\text{cpn}}_{j,t}$, $\theta^{\text{bill}}_{j,t}$), and H.15 curve yields $y^{\text{H15}}(\cdot)$ at coupon maturity $\text{WAM}^{\text{cpn}}_{j,t}$ and bill maturity $\text{WAM}^{\text{bill}}_{j,t}$ (default $0.25$ years), scaled by the median overlap ratio across the first five years of component quarters $\mathcal{Q}^{\text{ov}}_j$:

```math
\tilde{I}^{\text{H15}}_{j,t}
= \text{TS}^{\text{lvl}}_{j,t} \cdot \theta^{\text{cpn}}_{j,t} \cdot \frac{y^{\text{H15}}(\text{WAM}^{\text{cpn}}_{j,t})}{4}
+ \text{TS}^{\text{lvl}}_{j,t} \cdot \theta^{\text{bill}}_{j,t} \cdot \frac{y^{\text{H15}}(\text{WAM}^{\text{bill}}_{j,t})}{4}
```

```math
\hat{I}_{j,t} = s_j \cdot \tilde{I}^{\text{H15}}_{j,t},
\qquad
s_j = \operatorname{median}_{q \in \mathcal{Q}^{\text{ov}}_j}\left(\frac{\hat{I}^{\text{comp}}_{j,q}}{\tilde{I}^{\text{H15}}_{j,q}}\right)
```

### Money market fund ON RRP term

From SEC Form N-MFP fund-month filings (`support__mmf_fund_month.csv`), for fund $i$ in month $m$, define ON RRP runoff $R^{-}_{i,m}$, Treasury purchases $T^{+}_{i,m}$, and other uses $U^{\text{other}}_{i,m}$ (increases in non-Treasury, non-Fed-RRP assets plus NAV outflows):

```math
R^{-}_{i,m} = \max\left(0,\; -\Delta \text{FedRRP}_{i,m}\right),
\qquad
T^{+}_{i,m} = \max\left(0,\; \Delta \text{TS}^{\text{MMF}}_{i,m}\right)
```

```math
U^{\text{other}}_{i,m} = \max\left(0,\; \Delta A^{\text{nonTS,nonRRP}}_{i,m}\right) + \max\left(0,\; -\Delta \text{NAV}_{i,m}\right)
```

The upper bound, lower bound, and proportional allocation ($0/0 \equiv 0$) sum to quarters as:

```math
A^{\text{UB}}_{i,m} = \min\left(T^{+}_{i,m},\; R^{-}_{i,m}\right),
\qquad
A^{\text{LB}}_{i,m} = \min\left(T^{+}_{i,m},\; \max\left(0,\; R^{-}_{i,m} - U^{\text{other}}_{i,m}\right)\right)
```

```math
A^{\text{prop}}_{i,m} = \min\left(R^{-}_{i,m} \cdot \frac{T^{+}_{i,m}}{T^{+}_{i,m} + U^{\text{other}}_{i,m}},\; A^{\text{UB}}_{i,m}\right),
\qquad
A^{k}_{\text{MMF},t} = \sum_{m \in t} \sum_i A^{k}_{i,m}
```

for $k \in \{\text{LB}, \text{prop}, \text{UB}\}$, with $A^{k}_{\text{MMF},t} = 0$ before 2013Q3 (ON RRP start September 23, 2013). A bills-only comparison replaces $T^{+}_{i,m}$ with $\max(0, \Delta \text{Bills}^{\text{MMF}}_{i,m})$.

## Partial sums, legs, and comparison formulas

The leg export (`tdc regression-leg-export` -> `tdc_regression_legs_v1.csv`) partitions $\widehat{\text{TDC}}_t$ ($C_t$) into foreign ($R_t$), operating-cash ($O_t$), and domestic Fed, bank, and money-fund ($J_t$) legs:

```math
C_t = R_t + J_t + O_t,
\qquad
R_t = \Delta \text{TS}^{\text{tx}}_{\text{ROW},t} - \hat{I}_{\text{ROW},t},
\qquad
O_t = -\left(\Delta \text{Cash}^{\text{op}}_t - I^{\text{TF}}_t\right)
```

with $J_t = C_t - R_t - O_t$. Additional columns in `data/processed/tdc_estimates.csv` compute:

- Partial sums before interest and money funds (`tdc_base_bank_only_ru_flow`): $\text{TDC}^{\text{base}}_t = \Delta \text{TS}^{\text{tx}}_{\text{Fed},t} + \Delta \text{TS}^{\text{tx}}_{\text{Banks},t} + \Delta \text{TS}^{\text{tx}}_{\text{ROW},t} + \text{Remit}^{+}_{\text{Fed},t} - (\Delta \text{Cash}^{\text{op}}_t - I^{\text{TF}}_t)$, and after Federal Reserve coupons only (`tdc_tier1_fed_corrected_bank_only_ru_flow`): $\text{TDC}^{\text{base}}_t - \hat{I}^{\text{SOMA}}_{\text{Fed},t}$.
- Short-window component calculations (2022Q1 onward): `tdc_tier2_component_anchored_*` and `tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow` (from `support__{bank,row,credit_union}_tier2_component_interest_proxy.csv`); `_fed_extension_` variants also subtract SOMA bill discount and FRN interest (`support__fed_tier1_component_extension_proxy.csv`).
- Holdings-level comparisons (`tdc_level_bank_only_sensitivity`, `tdc_bank_only_extended_1990`): replace $\Delta \text{TS}^{\text{tx}}_{j,t}$ with $\Delta \text{TS}^{\text{lvl}}_{j,t}$.
- Residual bank-balance-sheet check (`tdc_decomposition_proxy_bank_centric`, scaling M2SL, CURRCIR, and TOTBKCR by 1000 to USD millions):

```math
\text{TDC}^{\text{decomp}}_t = \Delta \text{M2}_t - \Delta \text{Currency}_t - \Delta\left(\text{BankCredit}_t - \text{BankTS}_t\right)
```

- Fiscal-flow diagnostic (`tdc_tier3_fiscal_corrected_*`): adds $-G^{\text{nonint}}_{\text{Banks},t} - G^{\text{nonint}}_{\text{ROW},t} + T^{\text{nonborr}}_{\text{Banks},t} + T^{\text{nonborr}}_{\text{ROW},t} + \text{MintCash}_t$. A separate historical bank-receipt overlay adds IRS SOI Publication 16 Table 5.1 corporate-tax shares carried forward at most two calendar years.

## Treasury component of reserves (TRC)

Quarterly TRC (`tdc trc-export` -> `trc_quarterly_components_v1.csv`, `trc_quarterly_series_v1.csv`, 2003Q1 onward) and its money-fund companion are:

```math
\widehat{\text{TRC}}^{\text{core}}_q
= -\Delta \text{TGA}_q - \Delta \text{SFP}_q + I^{\text{TF}}_q + \Delta \text{TS}^{\text{tx}}_{\text{Fed},q} + \text{Remit}^{+}_{\text{Fed},q} - \hat{I}^{\text{SOMA}}_{\text{Fed},q}
```

```math
\widehat{\text{TRC}}_q = \widehat{\text{TRC}}^{\text{core}}_q + A^{\text{prop}}_{\text{MMF},q}
```

Lower and upper bounds substitute $A^{\text{LB}}_{\text{MMF},q}$ and $A^{\text{UB}}_{\text{MMF},q}$. The reserve outcome is Z.1 `FU713113003.Q` ($y^{Z}_q = \Delta RB^{\text{Z1}}_q$), with definitional residual $\widehat{N}^{\text{res}}_q = y^{Z}_q - \widehat{\text{TRC}}_q$. Here $\Delta \text{TGA}_q$ uses last-Wednesday H.4.1 `WDTGAL` through 2005Q4 and DTS Table I final-business-day close from 2006Q1; $\Delta \text{SFP}_q$ is the DTS Supplementary Financing Account change; 2002 quarters are unavailable because H.4.1 TGA begins December 18, 2002.

The measured TDC–TRC wedge reconciles both tables ($\Delta \text{TT\&L}_q$ and source/clock residual $u_q$ available from 2006Q1):

```math
\widehat{\text{TDC}}_q - \widehat{\text{TRC}}_q
= \left(\Delta \text{TS}^{\text{tx}}_{\text{Banks},q} - \hat{I}_{\text{Banks},q}\right) + R_q - \Delta \text{TT\&L}_q + u_q
```

Separate bounds in `trc-export` bracket GSE ON RRP financing and foreign-official direct-account trades (from mid-2007, using H.4.1 foreign-official Treasury custody holdings $C^{\text{FO}}_q$ and foreign-official deposits plus RRP $F^{\text{FO}}_q = D^{\text{FO}}_q + \text{RRP}^{\text{FO}}_q$):

```math
\Gamma^{\text{GSE}}_q \in \left[0,\; \min\left((\Delta \text{TS}^{\text{GSE}}_q)^{+},\; (-\Delta \text{RRP}^{\text{GSE}}_q)^{+}\right)\right]
```

```math
\Gamma^{\text{FO}}_q \in \left[-\min\left((-\Delta C^{\text{FO}}_q)^{+},\; (\Delta F^{\text{FO}}_q)^{+}\right),\; \min\left((\Delta C^{\text{FO}}_q)^{+},\; (-\Delta F^{\text{FO}}_q)^{+}\right)\right]
```

Remainder cells subtract the route allocation once: $N^{\text{RRP}}_q = -\Delta \text{RRP}^{\text{other}}_q - \Gamma^{\text{RRP}}_q$ and $N^{\text{FO}}_q = -\Delta F^{\text{FO}}_q - \Gamma^{\text{FO}}_q$.

### H.4.1 reserve-factor ledger and bridges

On the H.4.1 Wednesday clock from December 18, 2002 (`tdc reserve-factor-ledger-export`), Table 1 supplying factors enter with $\sigma_k = +1$ and absorbing factors other than reserve balances with $\sigma_k = -1$:

```math
\Delta RB^{H}_w = \sum_{k} f_{k,w} + \rho^{H}_w,
\qquad
f_{k,w} = \sigma_k \Delta L_{k,w}
```

Level and change closure against reserve balances (`WRBWFRBL`), published totals, and parent subtotals is verified within $0.5$ USD million per reported component. Weekly flows telescope into Wednesday-bounded quarterly flows $F^{H}_{k,q} = \sum_{w \in q} f_{k,w}$, with $y^{H}_q = \Delta RB^{H}_q$, $C^{H}_q = -\Delta \text{TGA}^{H}_q - \Delta \text{SFP}^{H}_q$, and $S^{H}_q = \Delta \text{TS}^{H}_q$ (`WSHOTSL`).

For each TRC calculation $x_q = C^{M}_q + B_q + \Gamma_q$ (where $C^{M}_q = -\Delta \text{TGA}_q - \Delta \text{SFP}_q + I^{\text{TF}}_q$, $B_q = \Delta \text{TS}^{\text{tx}}_{\text{Fed},q} + \text{Remit}^{+}_{\text{Fed},q} - \hat{I}^{\text{SOMA}}_{\text{Fed},q}$, and $\Gamma_q \in \{0, A^{\text{prop}}_{\text{MMF},q}, A^{\text{LB}}_{\text{MMF},q}, A^{\text{UB}}_{\text{MMF},q}\}$), the quarterly bridge identity is:

```math
y^{Z}_q - x_q
= \sum_{k \notin \{\text{TGA},\,\text{SFP},\,\text{TS},\,\text{RRP}^{o}\}} F^{H}_{k,q}
+ N^{\text{RRP},o}_q
+ \left(y^{Z}_q - y^{H}_q\right)
+ \left(C^{H}_q - C^{M}_q + I^{\text{TF}}_q\right)
- I^{\text{TF}}_q
+ \left(S^{H}_q - B_q\right)
+ \rho^{H}_q
```

with $N^{\text{RRP},o}_q = -\Delta \text{RRP}^{o}_q - \Gamma_q$. Using H.4.1 term deposits (`TERMT`, $\Delta \text{TermDep}^{H}_q = -F^{H}_{\text{term},q}$) and Z.1 reserve levels (`FL713113003.Q`, $\Delta \text{FL}^{Z}_q$), the outcome bridge splits as:

```math
y^{Z}_q - y^{H}_q
= \Delta \text{TermDep}^{H}_q
+ \left(y^{Z}_q - \Delta \text{FL}^{Z}_q\right)
+ \left(\Delta \text{FL}^{Z}_q - y^{H}_q - \Delta \text{TermDep}^{H}_q\right)
```

where the final term reflects quarter-end versus last-Wednesday timing and the 2007Q1–2017Q4 FHLB deposit exclusion from Z.1 reserves.

Monthly TRC (`scripts/export_trc_monthly.py` -> `trc_monthly_v1.csv`) sums consecutive weekly TRC components across each last-Wednesday month and adds calendar-month SEC Form N-MFP money-fund terms (zero before September 2013). Weekly TRC security formulas appear in [weekly TRC conventions](weekly_trc.md). After a local pipeline run, `data/processed/tdc_theory_measurement_map.md` lists the generated mapping from theoretical terms to output columns.
