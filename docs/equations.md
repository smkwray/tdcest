# Equations

## Bank-only baseline

\[
\widehat{\Delta D}^{mkt,bank}_{TDC,t}
=
\left(
\Delta TS^{tx}_{Fed,t}
+
\Delta TS^{tx}_{Banks,t}
+
\Delta TS^{tx}_{ROW,t}
\right)
-
\Delta Cash^{tx}_{Treasury,t}
+
Remit^{+}_{Fed,t}
\]

## Broad-depository natural-person credit-union alternative

\[
\widehat{\Delta D}^{mkt,broad}_{TDC,t}
=
\widehat{\Delta D}^{mkt,bank}_{TDC,t}
+
\Delta TS^{tx}_{CU^{NP},t}
\]

## Broad-depository plus corporate credit unions

\[
\widehat{\Delta D}^{mkt,broad+corp}_{TDC,t}
=
\widehat{\Delta D}^{mkt,broad}_{TDC,t}
+
\Delta TS^{tx}_{CU^{Corp},t}
\]

## Aggregate credit-union sensitivity

\[
\widehat{\Delta D}^{mkt,aggCU}_{TDC,t}
=
\widehat{\Delta D}^{mkt,broad+corp}_{TDC,t}
+
\Delta CapDeposit^{tx}_{NCUA,t}
\]

## Domestic-only bank sensitivity

\[
\widehat{\Delta D}^{dom,bank}_{TDC,t}
=
\left(
\Delta TS^{tx}_{Fed,t}
+
\Delta TS^{tx}_{Banks,t}
\right)
-
\Delta Cash^{tx}_{Treasury,t}
+
Remit^{+}_{Fed,t}
\]

## No-remittance bank sensitivity

\[
\widehat{\Delta D}^{noremit,bank}_{TDC,t}
=
\left(
\Delta TS^{tx}_{Fed,t}
+
\Delta TS^{tx}_{Banks,t}
+
\Delta TS^{tx}_{ROW,t}
\right)
-
\Delta Cash^{tx}_{Treasury,t}
\]

## Level-change sensitivities

### Bank-only

\[
\widehat{\Delta D}^{level,bank}_{TDC,t}
=
\Delta TS^{lvl}_{Fed,t}
+
\Delta TS^{lvl}_{Banks,t}
+
\Delta TS^{lvl}_{ROW,t}
-
\Delta Cash^{lvl}_{Treasury,t}
+
Remit^{+}_{Fed,t}
\]

### Broad-depository natural-person credit-union variant

\[
\widehat{\Delta D}^{level,broad}_{TDC,t}
=
\widehat{\Delta D}^{level,bank}_{TDC,t}
+
\Delta TS^{lvl}_{CU^{NP},t}
\]

## Rough decomposition proxy

\[
\widehat{\Delta D}^{decomp}_{TDC,t}
=
\Delta M2_t
-
\Delta Currency_t
-
\Delta BankCredit^{nonTS}_t
\]

where:

\[
BankCredit^{nonTS}_t = BankCredit_t - TreasuryHoldings^{Banks}_{t}
\]

This proxy is intentionally rough and should not be treated as the preferred headline method.
