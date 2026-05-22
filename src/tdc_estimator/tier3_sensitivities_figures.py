from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd


def _read_indexed(path: Path | str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        raise ValueError(f"{path} is missing required column: date")
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date").sort_index()


def _num(frame: pd.DataFrame, column: str, index: pd.DatetimeIndex, fill: float = 0.0) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(fill, index=index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").reindex(index).fillna(fill)


def build_tier3_extension_sensitivity_matrix(
    vintages: pd.DataFrame,
    bank_receipts_bridge: pd.DataFrame,
) -> pd.DataFrame:
    vintage = vintages.copy()
    bank = bank_receipts_bridge.copy()
    if "date" in vintage.columns:
        vintage["date"] = pd.to_datetime(vintage["date"])
        vintage = vintage.set_index("date")
    if "date" in bank.columns:
        bank["date"] = pd.to_datetime(bank["date"])
        bank = bank.set_index("date")

    index = pd.DatetimeIndex(vintage.index).sort_values()
    out = pd.DataFrame(index=index)
    out["bank_receipt_strict_gross_mil"] = _num(vintage, "receipt_banks_strict_lower_mil", index)
    out["bank_receipt_central_gross_mil"] = _num(vintage, "receipt_banks_depository_bhc_central_mil", index)
    out["bank_receipt_finance_upper_gross_mil"] = _num(vintage, "receipt_banks_finance_upper_mil", index)
    out["bank_receipt_strict_net_mil"] = _num(bank, "bank_corp_tax_receipts_net_strict_depository_mil", index)
    out["bank_receipt_central_net_mil"] = _num(bank, "bank_corp_tax_receipts_net_depository_plus_bhc_mil", index)
    out["bank_receipt_finance_net_mil"] = _num(bank, "bank_corp_tax_receipts_net_finance_share_mil", index)
    out["row_receipt_bea_only_mil"] = _num(vintage, "receipt_row_bea_anchor_mil", index, fill=float("nan"))
    out["row_mrv_timing_overlay_mil"] = _num(vintage, "receipt_row_mrv_nonadditive_overlay_mil", index)
    out["row_receipt_bea_plus_mrv_additive_mil"] = pd.NA
    out["row_receipt_additive_rule"] = "do_not_add_mrv_to_bea_anchor"
    out["row_outlay_narrow_mil"] = _num(vintage, "outlay_row_narrow_mil", index)
    out["row_outlay_broad_mil"] = _num(vintage, "outlay_row_broad_sensitivity_mil", index)
    out["bank_outlay_direct_mil"] = _num(vintage, "outlay_banks_mil", index)
    out["bank_outlay_parent_share_mil"] = pd.NA
    out["bank_outlay_family_share_mil"] = pd.NA
    out["bank_outlay_bea_fallback_mil"] = pd.NA
    out["cashfactor_mil"] = _num(vintage, "cashfactor_mil", index)

    bea_available = out["row_receipt_bea_only_mil"].notna()
    out["scenario_gross_strict_narrow_bea_mil"] = (
        -out["bank_outlay_direct_mil"]
        - out["row_outlay_narrow_mil"]
        + out["bank_receipt_strict_gross_mil"]
        + out["row_receipt_bea_only_mil"]
        + out["cashfactor_mil"]
    ).where(bea_available)
    out["scenario_gross_central_narrow_bea_mil"] = _num(vintage, "tier3_extended_research_correction_mil", index, fill=float("nan"))
    out["scenario_gross_finance_narrow_bea_mil"] = (
        -out["bank_outlay_direct_mil"]
        - out["row_outlay_narrow_mil"]
        + out["bank_receipt_finance_upper_gross_mil"]
        + out["row_receipt_bea_only_mil"]
        + out["cashfactor_mil"]
    ).where(bea_available)
    out["scenario_net_central_narrow_bea_mil"] = (
        -out["bank_outlay_direct_mil"]
        - out["row_outlay_narrow_mil"]
        + out["bank_receipt_central_net_mil"]
        + out["row_receipt_bea_only_mil"]
        + out["cashfactor_mil"]
    ).where(bea_available)
    out["scenario_gross_strict_broad_bea_mil"] = _num(vintage, "tier3_bea_anchored_research_correction_mil", index, fill=float("nan"))
    out["scenario_gross_central_broad_bea_mil"] = (
        -out["bank_outlay_direct_mil"]
        - out["row_outlay_broad_mil"]
        + out["bank_receipt_central_gross_mil"]
        + out["row_receipt_bea_only_mil"]
        + out["cashfactor_mil"]
    ).where(bea_available)
    out["scenario_mrv_overlay_nonadditive_mil"] = out["row_mrv_timing_overlay_mil"]
    out["quality_worst_component_key"] = vintage.get("worst_component_key", pd.Series(index=index, dtype="object")).reindex(index)
    out["structural_break_flags"] = vintage.get("structural_break_flags", pd.Series(index=index, dtype="object")).reindex(index)
    return out


def render_tier3_extension_sensitivity_matrix_markdown(matrix: pd.DataFrame) -> str:
    title = "# Tier 3 Extension Sensitivity Matrix"
    intro = (
        "Historical Tier 3 research-extension sensitivity matrix. Amounts are correction deltas relative to Tier 2, "
        "not live-default estimator outputs."
    )
    if matrix.empty:
        return "\n".join([title, "", intro, "", "No sensitivity rows are available."])

    complete = matrix.loc[matrix["scenario_gross_central_narrow_bea_mil"].notna()]
    latest_date = complete.index.max() if not complete.empty else matrix.index.max()
    latest = matrix.loc[latest_date]
    summary = (
        f"Rows: {len(matrix)}. Latest complete quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Central gross/narrow/BEA {float(latest['scenario_gross_central_narrow_bea_mil']):,.3f}; "
        f"strict broad/BEA {float(latest['scenario_gross_strict_broad_bea_mil']):,.3f}; "
        f"MRV overlay {float(latest['scenario_mrv_overlay_nonadditive_mil']):,.3f}."
    )
    notes = [
        "Notes:",
        "- MRV is carried as a non-additive timing overlay; additive BEA plus MRV cells are intentionally blank.",
        "- Bank-outlay parent/family/BEA fallback cells are reserved placeholders until 2003-2004 FAS manual QA and fallback calibration are complete.",
        "- Figure-ready central research series is `scenario_gross_central_narrow_bea_mil`.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *notes, ""])


def write_tier3_extension_sensitivity_matrix_from_paths(
    *,
    vintages_path: Path | str,
    bank_receipts_bridge_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    matrix = build_tier3_extension_sensitivity_matrix(
        _read_indexed(vintages_path),
        _read_indexed(bank_receipts_bridge_path),
    )
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = matrix.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_tier3_extension_sensitivity_matrix_markdown(matrix), encoding="utf-8")
    return csv_path, markdown_path, matrix


def _savefig(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    return path.with_suffix(".png")


def plot_tier3_research_extension_same_sample(estimates: pd.DataFrame, matrix: pd.DataFrame, out_dir: Path | str) -> Path:
    est = estimates.copy()
    if "date" in est.columns:
        est["date"] = pd.to_datetime(est["date"])
        est = est.set_index("date")
    mat = matrix.copy()
    if "date" in mat.columns:
        mat["date"] = pd.to_datetime(mat["date"])
        mat = mat.set_index("date")
    index = est.index.intersection(mat.index)
    required = ["tdc_tier1_fed_corrected_bank_only_ru_flow", "tdc_tier2_interest_corrected_bank_only_ru_flow"]
    frame = pd.DataFrame(index=index)
    frame["tier1"] = pd.to_numeric(est.loc[index, required[0]], errors="coerce")
    frame["tier2"] = pd.to_numeric(est.loc[index, required[1]], errors="coerce")
    frame["tier3_research_extension"] = frame["tier2"] + pd.to_numeric(mat.loc[index, "scenario_gross_central_narrow_bea_mil"], errors="coerce")
    frame = frame.dropna()

    fig, ax = plt.subplots(figsize=(12, 6.8))
    ax.plot(frame.index, frame["tier1"], label="Tier 1 bank-only", color="#777777", linewidth=1.9)
    ax.plot(frame.index, frame["tier2"], label="Tier 2 bank-only", color="#222222", linewidth=2.1)
    ax.plot(frame.index, frame["tier3_research_extension"], label="Tier 3 research extension", color="#1f77b4", linewidth=2.4)
    ax.axhline(0, color="0.35", linewidth=1)
    ax.set_title("Same-sample Tier 1 / Tier 2 / Tier 3 research extension")
    ax.set_ylabel("Millions of dollars")
    ax.legend(loc="best", fontsize=8.8)
    return _savefig(fig, Path(out_dir) / "tier3_research_extension_same_sample")


def plot_tier3_minus_tier2_component_decomposition(matrix: pd.DataFrame, out_dir: Path | str) -> Path:
    mat = matrix.copy()
    if "date" in mat.columns:
        mat["date"] = pd.to_datetime(mat["date"])
        mat = mat.set_index("date")
    complete = mat.loc[mat["scenario_gross_central_narrow_bea_mil"].notna()].copy()
    components = pd.DataFrame(
        {
            "Bank receipt central": complete["bank_receipt_central_gross_mil"],
            "ROW BEA anchor": complete["row_receipt_bea_only_mil"],
            "CashFactor": complete["cashfactor_mil"],
            "Bank outlay": -complete["bank_outlay_direct_mil"],
            "ROW outlay narrow": -complete["row_outlay_narrow_mil"],
        },
        index=complete.index,
    )

    fig, ax = plt.subplots(figsize=(12, 7.0))
    pos_bottom = pd.Series(0.0, index=components.index)
    neg_bottom = pd.Series(0.0, index=components.index)
    colors = ["#2b6cb0", "#38a169", "#805ad5", "#d69e2e", "#c53030"]
    for (column, values), color in zip(components.items(), colors):
        values = values.fillna(0.0)
        pos = values.clip(lower=0)
        neg = values.clip(upper=0)
        ax.bar(components.index, pos, bottom=pos_bottom, width=65, label=column, color=color, alpha=0.88)
        ax.bar(components.index, neg, bottom=neg_bottom, width=65, color=color, alpha=0.88)
        pos_bottom += pos
        neg_bottom += neg
    ax.plot(
        complete.index,
        complete["scenario_gross_central_narrow_bea_mil"],
        color="#111111",
        linewidth=1.8,
        label="Tier 3 - Tier 2 research delta",
    )
    ax.axhline(0, color="0.35", linewidth=1)
    ax.set_title("Tier 3 minus Tier 2 component decomposition (research extension)")
    ax.set_ylabel("Millions of dollars")
    ax.legend(loc="best", fontsize=8.2, ncol=2)
    return _savefig(fig, Path(out_dir) / "tier3_minus_tier2_component_decomposition")


def write_tier3_thesis_figures_from_paths(
    *,
    estimates_path: Path | str,
    sensitivity_matrix_path: Path | str,
    out_dir: Path | str,
) -> list[str]:
    estimates = _read_indexed(estimates_path)
    matrix = _read_indexed(sensitivity_matrix_path)
    outputs = [
        str(plot_tier3_research_extension_same_sample(estimates, matrix, out_dir)),
        str(plot_tier3_minus_tier2_component_decomposition(matrix, out_dir)),
    ]
    return outputs
