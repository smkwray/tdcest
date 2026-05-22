from __future__ import annotations

from pathlib import Path

import pandas as pd

from .tier3_source import build_tier3_source_diagnostics


def _read_indexed(path: Path | str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.set_index("date").sort_index()
    if "record_date" in frame.columns:
        frame["record_date"] = pd.to_datetime(frame["record_date"])
        return frame.set_index("record_date").sort_index()
    raise ValueError(f"{path} must contain date or record_date")


def build_tier3_pre2003_feasibility_panel(
    *,
    mts_outlays_path: Path | str,
    mts_receipts_path: Path | str,
    bea_row_anchor: pd.DataFrame,
    start: str = "1999-03-31",
    end: str = "2002-12-31",
) -> pd.DataFrame:
    diagnostics = build_tier3_source_diagnostics(mts_outlays_path=mts_outlays_path, start=start)
    receipts = pd.read_csv(mts_receipts_path)
    receipts["record_date"] = pd.to_datetime(receipts["record_date"])
    receipts["current_month_gross_rcpt_amt"] = pd.to_numeric(receipts["current_month_gross_rcpt_amt"], errors="coerce")
    receipts["current_month_refund_amt"] = pd.to_numeric(receipts["current_month_refund_amt"], errors="coerce")
    receipts["current_month_net_rcpt_amt"] = pd.to_numeric(receipts["current_month_net_rcpt_amt"], errors="coerce")
    quarterly_receipts = receipts.groupby(receipts["record_date"].dt.to_period("Q")).agg(
        {
            "current_month_gross_rcpt_amt": "sum",
            "current_month_refund_amt": "sum",
            "current_month_net_rcpt_amt": "sum",
        }
    )
    quarterly_receipts.index = quarterly_receipts.index.to_timestamp("Q")
    quarterly_receipts = quarterly_receipts / 1_000_000.0

    bea = bea_row_anchor.copy()
    if "date" in bea.columns:
        bea["date"] = pd.to_datetime(bea["date"])
        bea = bea.set_index("date")
    bea.index = pd.to_datetime(bea.index)

    index = diagnostics.index.union(quarterly_receipts.index).union(bea.index)
    index = pd.DatetimeIndex(index).sort_values()
    index = index[(index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))]
    out = pd.DataFrame(index=index)
    out["corp_tax_gross_cash_mil"] = quarterly_receipts["current_month_gross_rcpt_amt"].reindex(index)
    out["corp_tax_refunds_mil"] = quarterly_receipts["current_month_refund_amt"].reindex(index)
    out["corp_tax_net_cash_mil"] = quarterly_receipts["current_month_net_rcpt_amt"].reindex(index)
    out["row_outlay_narrow_mil"] = diagnostics["row_outlay_default_selected"].reindex(index).fillna(0.0)
    out["row_outlay_broad_sensitivity_mil"] = diagnostics["row_outlay_broad_selected"].reindex(index).fillna(0.0)
    out["mint_cashfactor_mil"] = diagnostics["mint_cb_cash_factor_source"].reindex(index).fillna(0.0)
    out["bank_outlay_direct_mil"] = pd.NA
    out["bank_receipt_bridge_mil"] = pd.NA
    out["bea_row_receipt_anchor_mil"] = pd.to_numeric(bea.get("bea_row_current_receipts_total_q_mil"), errors="coerce").reindex(index)
    out["partial_tier3_pre2003_correction_mil"] = (
        -out["row_outlay_narrow_mil"] + out["bea_row_receipt_anchor_mil"] + out["mint_cashfactor_mil"]
    )
    out["missing_bank_outlay_fas"] = True
    out["missing_bank_receipt_share"] = True
    out["research_status"] = "partial_pre2003_bridge_not_full_tier3"
    out["quality_note"] = (
        "MTS corp-tax, ROW outlay, Mint, and BEA ROW anchor are loaded; bank receipt shares and FAS bank outlays remain unresolved before 2003."
    )
    return out


def render_tier3_pre2003_feasibility_markdown(panel: pd.DataFrame) -> str:
    title = "# Tier 3 Pre-2003 Feasibility Panel"
    intro = (
        "Partial 1999-2002 research bridge for extending Tier 3 earlier than 2003. "
        "This is not a full Tier 3 vintage because bank receipt shares and direct FAS bank outlays are not yet resolved."
    )
    if panel.empty:
        return "\n".join([title, "", intro, "", "No pre-2003 panel rows are available."])
    summary = (
        f"Rows: {len(panel)} from {panel.index.min().date().isoformat()} through {panel.index.max().date().isoformat()}. "
        f"Average partial correction {float(panel['partial_tier3_pre2003_correction_mil'].mean()):,.3f} million per quarter."
    )
    notes = [
        "Notes:",
        "- Partial correction is `- ROW narrow outlays + BEA ROW receipt anchor + Mint CashFactor`.",
        "- Bank corporate-tax receipt bridge and direct FAS bank outlay bridge are intentionally blank before 2003.",
        "- This artifact answers feasibility; it does not promote 1999-2002 into the completed Tier 3 research vintage.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *notes, ""])


def write_tier3_pre2003_feasibility_panel_from_paths(
    *,
    mts_outlays_path: Path | str,
    mts_receipts_path: Path | str,
    bea_row_anchor_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "1999-03-31",
    end: str = "2002-12-31",
) -> tuple[Path, Path, pd.DataFrame]:
    panel = build_tier3_pre2003_feasibility_panel(
        mts_outlays_path=mts_outlays_path,
        mts_receipts_path=mts_receipts_path,
        bea_row_anchor=_read_indexed(bea_row_anchor_path),
        start=start,
        end=end,
    )
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = panel.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)
    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_tier3_pre2003_feasibility_markdown(panel), encoding="utf-8")
    return csv_path, markdown_path, panel
