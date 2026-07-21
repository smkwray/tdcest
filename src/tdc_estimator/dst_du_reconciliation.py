"""DS^T_DU residual-versus-direct reconciliation and promotion-gate evaluation.

Compares the expense-layer complement (residual form: pool minus RU legs) with
an INDEPENDENT direct construction (DU-universe Treasury positions times curve
yields, the same machinery used for the certified RU proxies) per component
family over the certified window, then evaluates the canonical promotion gates
verbatim from the project's 2026-07 promotion-gate specification and emits the
automatic outcome:

- all gates pass                      -> promotable_modern_aggregate
- aggregate passes, allocation fails  -> canonical_aggregate_research_sector_split
- aggregate reconciliation fails      -> research_tier_canonical_tier2_unchanged

FRN has no sector-position source (Z.1 carries no per-sector FRN split), so the
direct side covers nominal coupon and bill discount; FRN is reported as a
directly-unmatched component and the aggregate comparison excludes it, stated
in the report. A failed gate never relaxes: the outcome label changes instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .dst_du_sector_allocation import DU_UNIVERSE, Z1_LEVEL_FILES, _mmf_quarterly_positions
from .io import load_quarterly_fred_series
from .sector_coupon import (
    estimate_quarterly_sector_bill_discount_interest_proxy,
    estimate_quarterly_sector_coupon_interest_proxy,
)

CERTIFIED_START = pd.Timestamp("2022-03-31")
CERTIFIED_END = pd.Timestamp("2025-12-31")
TOTAL_COMPONENT_KEY = "total_core"

GATES = {
    "signed_mean_pct_max": 2.0,
    "mae_pct_max": 5.0,
    "p95_pct_max": 10.0,
    "min_quarters_within_10pct": 14,
    "max_consecutive_same_sign_gt5pct": 3,
    "annual_component_pct_max": 10.0,
}


def _du_synthetic_panel(raw_dir: Path) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for sector, filename in Z1_LEVEL_FILES.items():
        path = raw_dir / filename
        if not path.exists():
            continue
        series = load_quarterly_fred_series(path, agg="last")
        frame = series.reset_index()
        frame.columns = ["date", "level"]
        frame["sector_key"] = sector
        rows.append(frame)
    mmf = _mmf_quarterly_positions(raw_dir)
    if not mmf.empty:
        frame = mmf.reset_index().rename(columns={"index": "date"})
        frame["level"] = frame["coupon_position_mil"] + frame["bill_position_mil"]
        frame["sector_key"] = "money_market_funds"
        rows.append(frame[["date", "level", "sector_key"]])
    panel = pd.concat(rows, ignore_index=True)
    panel["level_units"] = "millions"
    return panel


def build_direct_du_interest(
    *,
    raw_dir: Path | str,
    sector_maturity: pd.DataFrame,
    curves: pd.DataFrame,
) -> pd.DataFrame:
    panel = _du_synthetic_panel(Path(raw_dir))
    coupon = estimate_quarterly_sector_coupon_interest_proxy(
        sector_maturity=sector_maturity,
        sector_panel=panel,
        curves=curves,
        sector_keys=DU_UNIVERSE,
        series_name="direct_du_coupon_mil",
    )
    bills = estimate_quarterly_sector_bill_discount_interest_proxy(
        sector_maturity=sector_maturity,
        sector_panel=panel,
        curves=curves,
        sector_keys=DU_UNIVERSE,
        series_name="direct_du_bill_discount_mil",
    )
    return pd.DataFrame({"direct_du_coupon_mil": coupon, "direct_du_bill_discount_mil": bills})


def _metrics(residual: pd.Series, direct: pd.Series, pool: pd.Series) -> dict[str, float | int | bool]:
    gap = direct - residual
    gap_pct_pool = 100.0 * gap / pool
    within = (gap_pct_pool.abs() <= 10.0)
    big_same_sign = (gap_pct_pool > 5.0).astype(int) - (gap_pct_pool < -5.0).astype(int)
    max_run = 0
    run = 0
    prev = 0
    for sign in big_same_sign:
        if sign != 0 and sign == prev:
            run += 1
        elif sign != 0:
            run = 1
        else:
            run = 0
        prev = sign
        max_run = max(max_run, run)
    yearly_resid = residual.groupby(residual.index.year).sum()
    yearly_direct = direct.groupby(direct.index.year).sum()
    yearly_pool = pool.groupby(pool.index.year).sum()
    annual_pct = (100.0 * (yearly_direct - yearly_resid) / yearly_pool).abs()
    return {
        "signed_mean_pct": float(gap_pct_pool.mean()),
        "mae_pct": float(gap_pct_pool.abs().mean()),
        "p95_pct": float(gap_pct_pool.abs().quantile(0.95)),
        "quarters_within_10pct": int(within.sum()),
        "quarters_total": int(len(gap_pct_pool)),
        "max_consecutive_same_sign_gt5pct": int(max_run),
        "annual_abs_pct_max": float(annual_pct.max()),
    }


def _gate_pass(metrics: dict[str, float | int | bool]) -> dict[str, bool]:
    return {
        "signed_mean": abs(metrics["signed_mean_pct"]) <= GATES["signed_mean_pct_max"],
        "mae": metrics["mae_pct"] <= GATES["mae_pct_max"],
        "p95": metrics["p95_pct"] <= GATES["p95_pct_max"],
        "quarters_within_10pct": metrics["quarters_within_10pct"] >= GATES["min_quarters_within_10pct"],
        "no_persistent_same_sign": metrics["max_consecutive_same_sign_gt5pct"]
        <= GATES["max_consecutive_same_sign_gt5pct"],
        "annual_components": metrics["annual_abs_pct_max"] <= GATES["annual_component_pct_max"],
    }


def build_dst_du_reconciliation(
    *,
    expense_panel: pd.DataFrame,
    direct: pd.DataFrame,
    nmfp_mapping_share: float | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    expense = expense_panel.copy()
    expense["date"] = pd.to_datetime(expense["date"], errors="coerce").dt.normalize()
    window = expense[(expense["date"] >= CERTIFIED_START) & (expense["date"] <= CERTIFIED_END)]
    if window.empty:
        raise ValueError("Expense panel has no certified-window rows.")
    direct = direct.copy()
    direct.index = pd.to_datetime(direct.index).normalize()
    direct = direct.loc[(direct.index >= CERTIFIED_START) & (direct.index <= CERTIFIED_END)]

    def component_series(key: str, column: str) -> tuple[pd.Series, pd.Series]:
        rows = window[window["component_key"] == key].set_index("date").sort_index()
        return (
            pd.to_numeric(rows["dst_du_expense_complement_mil"], errors="coerce"),
            pd.to_numeric(rows["official_component_pool_mil"], errors="coerce"),
        )

    coupon_resid, coupon_pool = component_series("coupon_accrual", "")
    bill_resid, bill_pool = component_series("bill_amortized_discount", "")
    frn_resid, frn_pool = component_series("frn_accrued_interest", "")

    coupon_direct = pd.to_numeric(direct["direct_du_coupon_mil"], errors="coerce").reindex(coupon_resid.index)
    bill_direct = pd.to_numeric(direct["direct_du_bill_discount_mil"], errors="coerce").reindex(bill_resid.index)

    comparisons = {
        "coupon_accrual": _metrics(coupon_resid, coupon_direct, coupon_pool),
        "bill_amortized_discount": _metrics(bill_resid, bill_direct, bill_pool),
        "total_ex_frn": _metrics(
            coupon_resid.add(bill_resid, fill_value=0.0),
            coupon_direct.add(bill_direct, fill_value=0.0),
            coupon_pool.add(bill_pool, fill_value=0.0),
        ),
    }
    gate_results = {key: _gate_pass(metrics) for key, metrics in comparisons.items()}
    aggregate_pass = all(gate_results["total_ex_frn"].values())
    components_pass = all(all(g.values()) for k, g in gate_results.items() if k != "total_ex_frn")
    mapping_pass = nmfp_mapping_share is None or nmfp_mapping_share >= 0.98

    open_gates = ["ffiec_002_rcfd0260_pilot", "shl_a7_annual_validator", "row_ita_annual_anchor"]
    if aggregate_pass and components_pass and mapping_pass and not open_gates:
        outcome = "promotable_modern_aggregate"
    elif aggregate_pass:
        outcome = "canonical_aggregate_research_sector_split_conditional_on_open_gates"
    else:
        outcome = "research_tier_canonical_tier2_unchanged"

    report_rows = []
    for key, metrics in comparisons.items():
        row = {"comparison": key, **metrics}
        row.update({f"gate_{name}": passed for name, passed in gate_results[key].items()})
        report_rows.append(row)
    report = pd.DataFrame(report_rows)

    manifest = {
        "window": [str(CERTIFIED_START.date()), str(CERTIFIED_END.date())],
        "gates": GATES,
        "gate_results": gate_results,
        "frn_direct_side": "not_directly_estimable_no_sector_frn_positions",
        "nmfp_mapping_share": nmfp_mapping_share,
        "open_source_gates_not_evaluated_here": open_gates,
        "outcome": outcome,
        "outcome_rule": (
            "all pass -> promotable_modern_aggregate; aggregate passes but components/"
            "mapping/open gates fail -> canonical aggregate + research sector split "
            "conditional on the open gates; aggregate fails -> research tier, canonical "
            "Tier 2 unchanged. Gates are never relaxed."
        ),
    }
    return report, manifest


def write_dst_du_reconciliation(
    *,
    expense_panel_path: Path | str,
    raw_dir: Path | str,
    sector_maturity_path: Path | str,
    curves_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
    out_manifest_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame, dict[str, object]]:
    expense = pd.read_csv(expense_panel_path)
    maturity = pd.read_csv(sector_maturity_path)
    curves = pd.read_csv(curves_path)
    direct = build_direct_du_interest(raw_dir=raw_dir, sector_maturity=maturity, curves=curves)
    report, manifest = build_dst_du_reconciliation(expense_panel=expense, direct=direct)

    out_csv = Path(out_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_csv, index=False)
    lines = [
        "# DS^T_DU residual-vs-direct reconciliation (certified window)",
        "",
        f"Outcome: **{manifest['outcome']}**",
        "",
        "Residual form = official component pool - Fed exact - certified RU legs.",
        "Direct form = DU-universe Z.1/N-MFP positions x curve yields (independent",
        "construction; FRN not directly estimable, excluded and stated).",
        "",
        report.to_string(index=False),
        "",
        "Gate thresholds: " + json.dumps(GATES),
        "Open source gates (not evaluated here): "
        + ", ".join(manifest["open_source_gates_not_evaluated_here"]),
        "",
    ]
    out_md = Path(out_markdown_path)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    out_manifest = Path(out_manifest_path)
    out_manifest.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return out_csv, out_md, report, manifest
