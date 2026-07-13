"""Tier 3 DU-facing share diagnostic — TWO side-specific series with bands.

Per the 2026-07-13 freeze-bless ingest (Phase C): publish the DU-facing share of
noninterest OUTLAYS and of noninterest RECEIPTS as separate series under the
common "noninterest fiscal core" caption — never a single blended scalar, never
"share of the deficit," never a lower bound, never evidence that ROW receipt
incidence is literally zero.

Outlays: DU share = 1 - (Financial Agent Services + foreign/international lines
+ Mint cash factor) / total noninterest outlays.
Receipts: DU share = 1 - (Fed earnings deposits + banded bank corporate tax +
ROW treatment) / total receipts, where the bank band is the SOI Table 5.1
classification/perimeter band (strict depositories / +BHCs central /
finance-wide stress) applied to NET corporate receipts with step-held shares,
and ROW is a zero baseline plus the BEA macro stress ceiling. Diagnostic tier
only; Tier 3 canonical promotion stays rejected.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

WINDOW_START = pd.Timestamp("2022-09-30")
DIAGNOSTIC_LABEL = "tier3_modern_window_diagnostic_noninterest_fiscal_core"


def _support_series(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    frame.columns = ["date", "value"]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    return frame.set_index("date")["value"].astype(float).sort_index()


def _non_du_outlay_legs(mts_targets: pd.DataFrame) -> pd.Series:
    """Quarterly sum of the Tier 3 non-DU outlay target lines (Financial Agent
    Services + the foreign/international classification family from
    tier3_source + United States Mint) from the stitched MTS ledger, in $M."""
    from .tier3_source import BANK_OUTLAY_LABELS, MINT_LABELS, ROW_OUTLAY_COMPONENT_LABELS

    labels = set(BANK_OUTLAY_LABELS) | set(ROW_OUTLAY_COMPONENT_LABELS.values()) | set(MINT_LABELS)
    frame = mts_targets.copy()
    frame = frame[frame["classification_desc"].isin(labels)]
    frame["record_date"] = pd.to_datetime(frame["record_date"], errors="coerce")
    frame["amount_mil"] = (
        pd.to_numeric(frame["current_month_net_outly_amt"], errors="coerce") / 1e6
    )
    frame = frame.dropna(subset=["record_date", "amount_mil"])
    quarter = frame["record_date"].dt.to_period("Q").dt.to_timestamp("Q")
    return frame["amount_mil"].groupby(quarter).sum().sort_index()


def build_tier3_du_share_diagnostic(
    *,
    du_research: pd.DataFrame,
    bank_bridge: pd.DataFrame,
    bea_row: pd.DataFrame,
    mts_targets: pd.DataFrame,
) -> pd.DataFrame:
    research = du_research.copy()
    research["date"] = pd.to_datetime(research["date"], errors="coerce").dt.normalize()
    research = research.set_index("date").sort_index()

    outlays_total = pd.to_numeric(research["treasury_total_outlays_proxy"], errors="coerce")
    interest = pd.to_numeric(research["treasury_interest_gross_proxy"], errors="coerce")
    receipts_total = pd.to_numeric(research["treasury_total_receipts_proxy"], errors="coerce")
    fed_earnings = pd.to_numeric(research["fed_earnings_receipt_mts"], errors="coerce").fillna(0.0)
    noninterest_outlays = outlays_total - interest

    bridge = bank_bridge.copy()
    bridge["date"] = pd.to_datetime(bridge["date"], errors="coerce").dt.normalize()
    bridge = bridge.set_index("date").sort_index()
    bank_strict = pd.to_numeric(
        bridge["bank_corp_tax_receipts_net_strict_depository_mil"], errors="coerce"
    )
    bank_central = pd.to_numeric(
        bridge["bank_corp_tax_receipts_net_depository_plus_bhc_mil"], errors="coerce"
    )
    bank_stress = pd.to_numeric(
        bridge["bank_corp_tax_receipts_net_finance_share_mil"], errors="coerce"
    )

    row_receipts = bea_row.copy()
    row_receipts["date"] = pd.to_datetime(row_receipts["date"], errors="coerce").dt.normalize()
    row_stress = (
        row_receipts.set_index("date")["bea_row_current_receipts_total_q_mil"].astype(float).sort_index()
    )

    non_du_legs = _non_du_outlay_legs(mts_targets)
    index = noninterest_outlays.loc[WINDOW_START:].dropna().index
    rows: list[dict[str, object]] = []
    for date in index:
        leg_value = non_du_legs.reindex([date]).iloc[0]
        if pd.isna(leg_value):
            continue  # fail closed: no share without observed target legs
        non_du_outlays = float(leg_value)
        outlay_total = float(noninterest_outlays.loc[date])
        receipt_total = float(receipts_total.loc[date])
        if outlay_total <= 0 or receipt_total <= 0:
            continue
        fed_leg = float(fed_earnings.loc[date]) if date in fed_earnings.index else 0.0
        strict = float(bank_strict.reindex([date]).fillna(0.0).iloc[0])
        central = float(bank_central.reindex([date]).fillna(0.0).iloc[0])
        stress = float(bank_stress.reindex([date]).fillna(0.0).iloc[0])
        row_ceiling = float(row_stress.reindex([date]).fillna(0.0).iloc[0])

        rows.append(
            {
                "date": date,
                "outlay_du_share": 1.0 - non_du_outlays / outlay_total,
                "receipt_du_share_strict_row0": 1.0 - (fed_leg + strict) / receipt_total,
                "receipt_du_share_central_row0": 1.0 - (fed_leg + central) / receipt_total,
                "receipt_du_share_finance_stress_row0": 1.0 - (fed_leg + stress) / receipt_total,
                "receipt_du_share_central_row_stress": 1.0
                - (fed_leg + central + row_ceiling) / receipt_total,
                "receipt_du_share_finance_row_stress": 1.0
                - (fed_leg + stress + row_ceiling) / receipt_total,
                "diagnostic_label": DIAGNOSTIC_LABEL,
                "row_receipt_treatment": "zero_baseline_with_bea_macro_stress_ceiling",
                "bank_share_treatment": "soi_table_5_1_step_held_net_receipts_perimeter_band",
            }
        )
    panel = pd.DataFrame(rows)
    if panel.empty:
        raise ValueError("No Tier 3 diagnostic quarters could be built.")
    return panel


def render_tier3_du_share_summary(panel: pd.DataFrame) -> str:
    def band(column: str) -> str:
        return f"{panel[column].min():.1%}-{panel[column].max():.1%}"

    weighted_outlay = panel["outlay_du_share"].mean()
    weighted_receipt = panel["receipt_du_share_central_row0"].mean()
    lines = [
        "# DU-facing share of the noninterest fiscal core (Tier 3 diagnostic)",
        "",
        "TWO side-specific series — never a single blended scalar, never 'share of",
        "the deficit,' never a lower bound, and never evidence that foreign receipt",
        "incidence is literally zero. Diagnostic tier; Tier 3 canonical promotion",
        "remains rejected. The interest leg is the RU-heavy exception, which is the",
        "motivation for DS^T_DU.",
        "",
        f"Window: {panel['date'].min().date()} to {panel['date'].max().date()} ({len(panel)} quarters).",
        "",
        f"- Outlays: mean {weighted_outlay:.1%}; quarterly band {band('outlay_du_share')}",
        f"- Receipts, structural ROW=0 band: strict {band('receipt_du_share_strict_row0')}, "
        f"central (+BHC) {band('receipt_du_share_central_row0')}, "
        f"finance-wide stress {band('receipt_du_share_finance_stress_row0')}",
        f"- Receipts, BEA-macro ROW stress: central {band('receipt_du_share_central_row_stress')}, "
        f"finance-wide {band('receipt_du_share_finance_row_stress')}",
        "",
        f"Defensible wording: about {weighted_outlay:.1%} of noninterest outlays and a",
        f"central estimate of about {weighted_receipt:.1%} of noninterest receipts were",
        "DU-facing over the window, within the implemented bank-only, marketable,",
        "transaction-based approximation; the short '~99% of the noninterest fiscal",
        "core' phrase is a rounded central characterization and must appear with the",
        "separate outlay and receipt bands above.",
        "",
    ]
    return "\n".join(lines)


def write_tier3_du_share_diagnostic(
    *,
    du_research_path: Path | str,
    bank_bridge_path: Path | str,
    bea_row_path: Path | str,
    mts_targets_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    panel = build_tier3_du_share_diagnostic(
        du_research=pd.read_csv(du_research_path),
        bank_bridge=pd.read_csv(bank_bridge_path),
        bea_row=pd.read_csv(bea_row_path),
        mts_targets=pd.read_csv(mts_targets_path, low_memory=False),
    )
    out_csv = Path(out_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write = panel.copy()
    write["date"] = pd.to_datetime(write["date"], errors="coerce").dt.date.astype(str)
    write.to_csv(out_csv, index=False)
    out_md = Path(out_markdown_path)
    out_md.write_text(render_tier3_du_share_summary(panel), encoding="utf-8")
    return out_csv, out_md, panel
