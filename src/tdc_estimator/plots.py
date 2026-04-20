from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd


LABELS = {
    "tdc_base_bank_only_ru_flow": "Base bank-only RU-flow",
    "tdc_base_broad_depository_np_cu_ru_flow": "Broad depository (NP credit unions)",
    "tdc_broad_depository_np_corp_cu_ru_flow": "Broad depository (+ corporate CUs)",
    "tdc_credit_union_aggregate_sensitivity": "Aggregate-CU sensitivity (+ NCUA cap deposit)",
    "tdc_domestic_bank_only_ru_flow": "Domestic bank-only RU-flow",
    "tdc_no_remit_bank_only": "Bank-only, no remittances",
    "tdc_tier1_fed_corrected_bank_only_ru_flow": "Tier 1 bank-only (- Fed coupon proxy)",
    "tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow": "Tier 1 broad depository (- Fed coupon proxy)",
    "tdc_tier1_fed_corrected_domestic_bank_only_ru_flow": "Tier 1 domestic bank-only (- Fed coupon proxy)",
    "tdc_tier2_interest_corrected_bank_only_ru_flow": "Tier 2 bank-only (- Fed, bank, ROW coupon proxies)",
    "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow": "Tier 2 broad depository (- Fed, bank, ROW coupon proxies)",
    "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow": "Tier 2 domestic bank-only (- Fed, bank coupon proxies)",
    "tdc_level_bank_only_sensitivity": "Level-change bank-only",
    "tdc_level_broad_depository_np_cu_sensitivity": "Level-change broad depository",
    "tdc_decomposition_proxy_bank_centric": "Decomposition proxy (bank-centric)",
    "tdc_base_bank_only_ru_flow_4q": "Base bank-only, 4-quarter sum",
    "tdc_base_bank_only_ru_flow_cum": "Base bank-only, cumulative",
    "fed_tsy_tx": "Fed Treasury transactions",
    "bank_depository_tsy_tx": "Bank-sector Treasury transactions",
    "np_credit_unions_tsy_tx": "Natural-person CU Treasury transactions",
    "corp_credit_unions_tsy_tx": "Corporate CU Treasury transactions",
    "ncua_capitalization_deposit_tx": "NCUA capitalization deposit term",
    "row_tsy_tx": "Rest-of-world Treasury transactions",
    "minus_treasury_operating_cash_tx": "- Treasury operating cash transactions",
    "fed_remit_positive": "Fed remittances, positive only",
    "fed_tsy_coupon_interest_proxy": "Fed Treasury coupon-interest proxy",
    "bank_tsy_coupon_interest_proxy": "Bank-sector Treasury coupon-interest proxy",
    "row_tsy_coupon_interest_proxy": "Rest-of-world Treasury coupon-interest proxy",
}


def _label(name: str) -> str:
    return LABELS.get(name, name)


def _savefig(fig: plt.Figure, out_base: Path) -> None:
    out_base.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_base.with_suffix(".png"), dpi=180, bbox_inches="tight")
    fig.savefig(out_base.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def _zero_line(ax: plt.Axes) -> None:
    ax.axhline(0, linewidth=1, color="0.35", alpha=0.9)


BASELINE_COL = "tdc_base_bank_only_ru_flow"
SECONDARY_HIGHLIGHT_COL = "tdc_base_broad_depository_np_cu_ru_flow"


def plot_method_comparison(estimates: pd.DataFrame, out_dir: Path | str) -> Path:
    out_dir = Path(out_dir)
    columns = [c for c in estimates.columns if not c.endswith("_4q") and not c.endswith("_cum")]
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for col in columns:
        if col == BASELINE_COL:
            lw = 3.0
            alpha = 1.0
            z = 4
        elif col == SECONDARY_HIGHLIGHT_COL:
            lw = 2.4
            alpha = 0.95
            z = 3
        else:
            lw = 1.35
            alpha = 0.82
            z = 2
        ax.plot(estimates.index, estimates[col], linewidth=lw, alpha=alpha, label=_label(col), zorder=z)
    _zero_line(ax)
    ax.set_title("Treasury-Attributed Component of Deposits: method comparison")
    ax.set_ylabel("Millions of dollars")
    ax.set_xlabel("")
    ax.legend(loc="best", fontsize=8.8)
    path = out_dir / "tdc_method_comparison"
    _savefig(fig, path)
    return path.with_suffix(".png")


def plot_base_components(components: pd.DataFrame, out_dir: Path | str) -> Path:
    out_dir = Path(out_dir)
    cols = [
        "fed_tsy_tx",
        "bank_depository_tsy_tx",
        "row_tsy_tx",
        "minus_treasury_operating_cash_tx",
        "fed_remit_positive",
    ]
    data = components[cols].copy()

    fig, ax = plt.subplots(figsize=(12, 6.5))
    pos_bottom = pd.Series(0.0, index=data.index)
    neg_bottom = pd.Series(0.0, index=data.index)

    for col in cols:
        values = data[col].fillna(0.0)
        pos = values.clip(lower=0)
        neg = values.clip(upper=0)
        ax.bar(data.index, pos, bottom=pos_bottom, width=70, label=_label(col))
        ax.bar(data.index, neg, bottom=neg_bottom, width=70)
        pos_bottom = pos_bottom + pos
        neg_bottom = neg_bottom + neg

    ax.plot(
        components.index,
        components[BASELINE_COL],
        linewidth=2.6,
        label=_label(BASELINE_COL),
    )
    _zero_line(ax)
    ax.set_title("Base bank-only estimator: quarterly component contributions")
    ax.set_ylabel("Millions of dollars")
    ax.legend(loc="best", fontsize=8.8)
    path = out_dir / "tdc_base_components"
    _savefig(fig, path)
    return path.with_suffix(".png")


def plot_credit_union_increments(components: pd.DataFrame, out_dir: Path | str) -> Path:
    out_dir = Path(out_dir)
    cols = [
        "np_credit_unions_tsy_tx",
        "corp_credit_unions_tsy_tx",
        "ncua_capitalization_deposit_tx",
    ]
    fig, ax = plt.subplots(figsize=(12, 6.0))
    for col in cols:
        ax.plot(components.index, components[col], linewidth=2.0, label=_label(col))
    _zero_line(ax)
    ax.set_title("Credit-union treatment: incremental quarterly contribution")
    ax.set_ylabel("Millions of dollars")
    ax.set_xlabel("")
    ax.legend(loc="best", fontsize=8.8)
    path = out_dir / "tdc_credit_union_increments"
    _savefig(fig, path)
    return path.with_suffix(".png")


def plot_base_rolling_4q(estimates: pd.DataFrame, out_dir: Path | str) -> Path:
    out_dir = Path(out_dir)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(estimates.index, estimates["tdc_base_bank_only_ru_flow_4q"], linewidth=2.5, label=_label("tdc_base_bank_only_ru_flow_4q"))
    if SECONDARY_HIGHLIGHT_COL in estimates:
        broad_4q = estimates[SECONDARY_HIGHLIGHT_COL].rolling(4).sum()
        ax.plot(estimates.index, broad_4q, linewidth=2.0, alpha=0.9, label="Broad depository (NP credit unions), 4-quarter sum")
    _zero_line(ax)
    ax.set_title("Base estimator family: rolling 4-quarter sum")
    ax.set_ylabel("Millions of dollars")
    ax.legend(loc="best", fontsize=8.8)
    path = out_dir / "tdc_base_rolling_4q"
    _savefig(fig, path)
    return path.with_suffix(".png")


def plot_base_cumulative(estimates: pd.DataFrame, out_dir: Path | str) -> Path:
    out_dir = Path(out_dir)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(estimates.index, estimates["tdc_base_bank_only_ru_flow_cum"], linewidth=2.5, label=_label("tdc_base_bank_only_ru_flow_cum"))
    if SECONDARY_HIGHLIGHT_COL in estimates:
        broad_cum = estimates[SECONDARY_HIGHLIGHT_COL].cumsum()
        ax.plot(estimates.index, broad_cum, linewidth=2.0, alpha=0.9, label="Broad depository (NP credit unions), cumulative")
    _zero_line(ax)
    ax.set_title("Base estimator family: cumulative sum")
    ax.set_ylabel("Millions of dollars")
    ax.legend(loc="best", fontsize=8.8)
    path = out_dir / "tdc_base_cumulative"
    _savefig(fig, path)
    return path.with_suffix(".png")


def plot_monetary_target_preference(
    monetary_stage0: pd.DataFrame,
    monetary_stage1: pd.DataFrame,
    monetary_target_wedge: pd.DataFrame,
    monetary_target_preference_review: pd.DataFrame,
    out_dir: Path | str,
) -> Path:
    out_dir = Path(out_dir)
    stage0 = monetary_stage0.copy()
    if "date" in stage0.columns:
        stage0["date"] = pd.to_datetime(stage0["date"])
        stage0 = stage0.set_index("date")
    else:
        stage0.index = pd.to_datetime(stage0.index)

    stage1 = monetary_stage1.copy()
    if "date" in stage1.columns:
        stage1["date"] = pd.to_datetime(stage1["date"])
        stage1 = stage1.set_index("date")
    else:
        stage1.index = pd.to_datetime(stage1.index)

    wedge = monetary_target_wedge.copy()
    wedge["date"] = pd.to_datetime(wedge["date"])
    wedge = wedge.set_index("date")

    latest = monetary_target_preference_review.iloc[0] if not monetary_target_preference_review.empty else None

    fig, ax = plt.subplots(figsize=(12, 7.2))
    ax.plot(
        stage0.index,
        stage0["delta_depository_target_level_mil"],
        linewidth=2.5,
        label="Depository target change",
        color="#1f77b4",
    )
    ax.plot(
        stage0.index,
        stage0["delta_commercial_bank_deposits_level_mil"],
        linewidth=2.2,
        label="Commercial-bank-deposit target change",
        color="#d62728",
        alpha=0.9,
    )
    ax.plot(
        stage0.index,
        stage0["tier3_bank_only_flow_mil"],
        linewidth=2.0,
        label="Tier 3 bank-only",
        color="#222222",
        alpha=0.95,
    )
    ax.plot(
        wedge.index,
        wedge["bank_specific_residual_wedge_mil"],
        linewidth=2.0,
        linestyle="--",
        label="Bank-specific residual wedge",
        color="#ff7f0e",
        alpha=0.95,
    )
    _zero_line(ax)
    preferred_label = "Depository target preferred" if latest is not None else "Target preference review"
    ax.set_title(
        "Monetary cross-check preference: depository target versus bank-deposit stress test"
        f" ({preferred_label})"
    )
    ax.set_ylabel("Millions of dollars")
    ax.legend(loc="best", fontsize=8.6)
    ax.plot(
        wedge.index,
        wedge["depository_residual_after_expanded_mil"],
        linewidth=1.8,
        linestyle=":",
        label="Depository residual after expanded controls",
        color="#1f77b4",
        alpha=0.9,
    )
    path = out_dir / "tdc_monetary_target_preference"
    _savefig(fig, path)
    return path.with_suffix(".png")


def plot_historical_bank_receipt_research(
    research: pd.DataFrame,
    out_dir: Path | str,
) -> Path:
    out_dir = Path(out_dir)
    frame = research.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date")
    else:
        frame.index = pd.to_datetime(frame.index)

    fig, ax = plt.subplots(figsize=(12, 6.8))
    ax.plot(
        frame.index,
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"],
        linewidth=2.3,
        label="Default Tier 3 bank-only",
        color="#222222",
        alpha=0.95,
    )
    ax.plot(
        frame.index,
        frame["tdc_tier3_bank_only_plus_historical_bank_receipt_candidate"],
        linewidth=2.5,
        label="Historical Tier 3 + dep+BHC bank receipt candidate",
        color="#1f77b4",
        alpha=0.95,
    )
    ax.plot(
        frame.index,
        frame["tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound"],
        linewidth=2.0,
        linestyle="--",
        label="Historical Tier 3 + strict-depository lower bound",
        color="#ff7f0e",
        alpha=0.9,
    )
    _zero_line(ax)
    ax.set_title("Historical Tier 3 bank-receipt research window")
    ax.set_ylabel("Millions of dollars")
    ax.set_xlabel("")
    ax.legend(loc="best", fontsize=8.8)
    path = out_dir / "tdc_historical_bank_receipt_research"
    _savefig(fig, path)
    return path.with_suffix(".png")


def plot_tier2_tier3_research_comparison(
    estimates: pd.DataFrame,
    research: pd.DataFrame,
    out_dir: Path | str,
) -> Path:
    out_dir = Path(out_dir)
    est = estimates.copy()
    est.index = pd.to_datetime(est.index)
    frame = research.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date")
    else:
        frame.index = pd.to_datetime(frame.index)

    overlap = est.loc[est.index.isin(frame.index)].copy()
    frame = frame.loc[frame.index.isin(overlap.index)].copy()

    fig, ax = plt.subplots(figsize=(12, 6.8))
    ax.plot(
        overlap.index,
        overlap["tdc_tier2_interest_corrected_bank_only_ru_flow"],
        linewidth=2.2,
        label="Tier 2 bank-only",
        color="#6c757d",
        alpha=0.95,
    )
    ax.plot(
        frame.index,
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"],
        linewidth=2.4,
        label="Default Tier 3 bank-only",
        color="#222222",
        alpha=0.95,
    )
    ax.plot(
        frame.index,
        frame["tdc_tier3_bank_only_plus_historical_bank_receipt_candidate"],
        linewidth=2.5,
        label="Historical Tier 3 + dep+BHC bank receipt view",
        color="#1f77b4",
        alpha=0.95,
    )
    _zero_line(ax)
    ax.set_title("Tier 2 versus Tier 3 research comparison in the historical bank-receipt window")
    ax.set_ylabel("Millions of dollars")
    ax.set_xlabel("")
    ax.legend(loc="best", fontsize=8.6)
    path = out_dir / "tdc_tier2_tier3_research_comparison"
    _savefig(fig, path)
    return path.with_suffix(".png")


def build_all_figures(
    estimates: pd.DataFrame,
    components: pd.DataFrame,
    out_dir: Path | str,
    *,
    tier3_historical_bank_receipt_research: pd.DataFrame | None = None,
    tier3_research_comparison: pd.DataFrame | None = None,
    monetary_stage0: pd.DataFrame | None = None,
    monetary_stage1: pd.DataFrame | None = None,
    monetary_target_wedge: pd.DataFrame | None = None,
    monetary_target_preference_review: pd.DataFrame | None = None,
) -> list[str]:
    outputs = [
        str(plot_method_comparison(estimates, out_dir)),
        str(plot_base_components(components, out_dir)),
        str(plot_credit_union_increments(components, out_dir)),
        str(plot_base_rolling_4q(estimates, out_dir)),
        str(plot_base_cumulative(estimates, out_dir)),
    ]
    if tier3_historical_bank_receipt_research is not None and not tier3_historical_bank_receipt_research.empty:
        outputs.append(str(plot_historical_bank_receipt_research(tier3_historical_bank_receipt_research, out_dir)))
        outputs.append(str(plot_tier2_tier3_research_comparison(estimates, tier3_historical_bank_receipt_research, out_dir)))
    if (
        monetary_stage0 is not None
        and not monetary_stage0.empty
        and monetary_stage1 is not None
        and not monetary_stage1.empty
        and monetary_target_wedge is not None
        and not monetary_target_wedge.empty
        and monetary_target_preference_review is not None
        and not monetary_target_preference_review.empty
    ):
        outputs.append(
            str(
                plot_monetary_target_preference(
                    monetary_stage0,
                    monetary_stage1,
                    monetary_target_wedge,
                    monetary_target_preference_review,
                    out_dir,
                )
            )
        )
    return outputs
