"""Nonmarketable interest sidecars (owner ruling 1 + freeze-bless MUST 6).

Quarterly expense-basis sidecars from the FiscalData interest-expense ledger,
outside every DS^T_DU core object:

- savings bonds: household-facing, ACCRUAL-basis (EE/I interest pays at
  redemption) — labeled expense/accrual until a redemption bridge exists;
- SLGS: owned by state/local bond issuers — domestic public, NEVER household DU;
- GAS: intragovernmental (excluded core context; reported for the defense stat).

Labels here are locked by tests; none of these series may enter DS math.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SAVINGS_BOND_GROUP = "SAVINGS BONDS"
SLGS_TYPE = "State & Local Government-C/I's, Notes & Bonds"
GAS_CASH_GROUP = "CASH BASIS GAS PAYMENTS"

SAVINGS_BOND_LABEL = "household_facing_expense_accrual_no_redemption_bridge"
SLGS_LABEL = "domestic_public_state_local_not_household_du"
GAS_LABEL = "intragovernmental_excluded_from_public_holder_core"
CORE_EXCLUSION_LABEL = "never_in_dst_du_core_or_tier2_math"


def build_nonmarketable_sidecar(interest_expense: pd.DataFrame) -> pd.DataFrame:
    frame = interest_expense.copy()
    frame["record_date"] = pd.to_datetime(frame["record_date"], errors="coerce")
    frame["amount_mil"] = pd.to_numeric(frame["month_expense_amt"], errors="coerce") / 1e6
    frame = frame.dropna(subset=["record_date", "amount_mil"])
    quarter = frame["record_date"].dt.to_period("Q").dt.to_timestamp("Q")

    def leg(mask: pd.Series) -> pd.Series:
        return frame.loc[mask, "amount_mil"].groupby(quarter[mask]).sum()

    savings = leg(frame["expense_group_desc"].eq(SAVINGS_BOND_GROUP))
    slgs = leg(frame["expense_type_desc"].eq(SLGS_TYPE))
    gas = leg(frame["expense_group_desc"].eq(GAS_CASH_GROUP))

    out = pd.DataFrame(
        {
            "nonmarketable_savings_bond_expense_sidecar_mil": savings,
            "nonmarketable_slgs_expense_sidecar_mil": slgs,
            "nonmarketable_gas_cash_context_mil": gas,
        }
    ).sort_index()
    out.index.name = "date"
    out["savings_bond_label"] = SAVINGS_BOND_LABEL
    out["slgs_label"] = SLGS_LABEL
    out["gas_label"] = GAS_LABEL
    out["core_exclusion_label"] = CORE_EXCLUSION_LABEL
    return out.reset_index()


def write_nonmarketable_sidecar(
    *,
    interest_expense_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    ledger = pd.read_csv(interest_expense_path)
    panel = build_nonmarketable_sidecar(ledger)
    out_csv = Path(out_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write = panel.copy()
    write["date"] = pd.to_datetime(write["date"], errors="coerce").dt.date.astype(str)
    write.to_csv(out_csv, index=False)
    latest = panel.iloc[-1]
    lines = [
        "# Nonmarketable interest sidecars (expense basis)",
        "",
        "Outside every DS^T_DU core object; labels are locked (MUST 6):",
        f"- savings bonds: {SAVINGS_BOND_LABEL}",
        f"- SLGS: {SLGS_LABEL}",
        f"- GAS: {GAS_LABEL}",
        "",
        f"Latest quarter ({pd.Timestamp(latest['date']).date()}): savings bonds "
        f"${latest['nonmarketable_savings_bond_expense_sidecar_mil']:,.1f}M, SLGS "
        f"${latest['nonmarketable_slgs_expense_sidecar_mil']:,.1f}M, GAS (context) "
        f"${latest['nonmarketable_gas_cash_context_mil']:,.1f}M.",
        "",
        "Defense stat: nonmarketable intragovernmental share note (2026-07-13).",
        "",
    ]
    out_md = Path(out_markdown_path)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    return out_csv, out_md, panel
