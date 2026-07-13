"""Long-history DS^T_DU expense-equivalent row (plan B5, owner-required).

Era ladder (identity note / freeze-bless ingest section Q3):
- 2022Q1+            certified_modern_component_identity (exact overwrite from the
                     expense panel; equality asserted, never re-derived here)
- 2010Q2-2021Q4      analysis_component_identity (expense panel rows as built)
- 2002Q1-2010Q1      backcast_bounded_ratio_expense_equivalent - the blessed
                     RUNNER-UP design (bounded ratio), used with an explicit
                     method exception because the recommended dynamic-share
                     state-space model is not yet built. Construction:
                     pool_hat = long-history gross-interest proxy x step-held
                     pool/gross ratio calibrated on the earliest observed window;
                     complement_hat = pool_hat - Fed coupon proxy - RU legs from
                     the method-tiered regression backcast. Total-core row only:
                     a per-component split is REFUSED pre-2010 (no reconstructed
                     per-component pools).
- pre-2002           frame_only_not_estimated - numerical values REFUSED.

Drift guards implemented: ratio bounded to its calibration-window p10-p90 with
uncertainty bands carried into the backcast; a 2010Q2 splice-jump check; a
rolling-origin backtest (withhold 2018-2021, reconstruct from 2010-2017) whose
results publish with the row. Claim label: expense-equivalent holder-incidence
control; NEVER cash received; never additive to Tier 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CERTIFIED_TIER = "certified_modern_component_identity"
ANALYSIS_TIER = "analysis_component_identity"
BACKCAST_TIER = "backcast_bounded_ratio_expense_equivalent"
BACKCAST_START = pd.Timestamp("2002-03-31")
PANEL_START = pd.Timestamp("2010-06-30")
CERTIFIED_START = pd.Timestamp("2022-03-31")
RATIO_CALIBRATION_END = pd.Timestamp("2014-12-31")
SPLICE_JUMP_FLAG_SHARE = 0.25

TOTAL_COMPONENT_KEY = "total_core"


def _quarter_index(series: pd.Series) -> pd.Series:
    out = series.copy()
    out.index = pd.to_datetime(out.index).normalize()
    return out.sort_index()


def build_dst_du_long_history(
    *,
    expense_panel: pd.DataFrame,
    gross_interest_proxy: pd.Series,
    fed_coupon_proxy: pd.Series,
    ru_backcast_wide: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    expense = expense_panel.copy()
    expense["date"] = pd.to_datetime(expense["date"], errors="coerce").dt.normalize()
    totals = (
        expense[expense["component_key"] == TOTAL_COMPONENT_KEY]
        .set_index("date")
        .sort_index()
    )
    if totals.empty:
        raise ValueError("Expense panel has no total_core rows.")

    gross = _quarter_index(pd.to_numeric(gross_interest_proxy, errors="coerce")).dropna()
    fed = _quarter_index(pd.to_numeric(fed_coupon_proxy, errors="coerce"))
    wide = ru_backcast_wide.copy()
    wide["date"] = pd.to_datetime(wide["date"], errors="coerce").dt.normalize()
    wide = wide.set_index("date").sort_index()
    ru_total = (
        pd.to_numeric(wide["bank_tier2_regression_interest_proxy"], errors="coerce")
        + pd.to_numeric(wide["credit_union_tier2_regression_interest_proxy"], errors="coerce")
        + pd.to_numeric(wide["row_tier2_regression_interest_proxy"], errors="coerce")
    )
    ru_tier = wide["bank_method_tier"].astype(str)

    # Ratio calibration: earliest observed pool/gross overlap (2010Q2-2014Q4).
    pool_obs = pd.to_numeric(totals["official_component_pool_mil"], errors="coerce")
    overlap = pool_obs.loc[PANEL_START:RATIO_CALIBRATION_END]
    gross_overlap = gross.reindex(overlap.index)
    ratios = (overlap / gross_overlap).dropna()
    if len(ratios) < 8:
        raise ValueError("Insufficient pool/gross overlap to calibrate the backcast ratio.")
    ratio_center = float(ratios.median())
    ratio_low = float(ratios.quantile(0.10))
    ratio_high = float(ratios.quantile(0.90))

    rows: list[dict[str, object]] = []
    for date, row in totals.iterrows():
        rows.append(
            {
                "date": date,
                "dst_du_expense_complement_mil": float(row["dst_du_expense_complement_mil"]),
                "dst_du_expense_complement_low_mil": float(row["dst_du_expense_complement_mil"]),
                "dst_du_expense_complement_high_mil": float(row["dst_du_expense_complement_mil"]),
                "method_tier": str(row["method_tier"]),
                "pool_basis": "official_component_pool",
                "ru_leg_tier": "constrained_component"
                if date >= CERTIFIED_START
                else str(ru_tier.reindex([date]).iloc[0])
                if date in ru_tier.index
                else "component_pool_wamest_bucket_backcast",
            }
        )

    backcast_dates = [
        d for d in gross.index if BACKCAST_START <= d < PANEL_START and d in ru_total.index
    ]
    dropped: list[str] = []
    for date in backcast_dates:
        fed_value = fed.reindex([date]).iloc[0]
        ru_value = ru_total.reindex([date]).iloc[0]
        if pd.isna(fed_value) or pd.isna(ru_value):
            dropped.append(str(date.date()))
            continue
        gross_value = float(gross.loc[date])
        center = gross_value * ratio_center - float(fed_value) - float(ru_value)
        low = gross_value * ratio_low - float(fed_value) - float(ru_value)
        high = gross_value * ratio_high - float(fed_value) - float(ru_value)
        rows.append(
            {
                "date": date,
                "dst_du_expense_complement_mil": center,
                "dst_du_expense_complement_low_mil": min(low, high),
                "dst_du_expense_complement_high_mil": max(low, high),
                "method_tier": BACKCAST_TIER,
                "pool_basis": f"gross_proxy_x_ratio({ratio_center:.4f})",
                "ru_leg_tier": str(ru_tier.reindex([date]).iloc[0])
                if date in ru_tier.index
                else "unknown",
            }
        )

    frame = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    # Splice-jump guard at the 2010Q2 seam.
    seam_flag = False
    seam_detail = ""
    before = frame[frame["date"] < PANEL_START].tail(1)
    at = frame[frame["date"] == PANEL_START]
    if not before.empty and not at.empty:
        prev_value = float(before["dst_du_expense_complement_mil"].iloc[0])
        seam_value = float(at["dst_du_expense_complement_mil"].iloc[0])
        base = max(abs(prev_value), abs(seam_value), 1.0)
        jump_share = abs(seam_value - prev_value) / base
        seam_flag = jump_share > SPLICE_JUMP_FLAG_SHARE
        seam_detail = f"2010Q2 seam jump share {jump_share:.2%} (flag > {SPLICE_JUMP_FLAG_SHARE:.0%})"

    # Rolling-origin backtest: calibrate ratio on 2010Q2-2017Q4, reconstruct
    # 2018Q1-2021Q4 pools from the gross proxy, compare with observed pools.
    train = (pool_obs.loc[PANEL_START:"2017-12-31"] / gross.reindex(pool_obs.index)).dropna()
    train = train.loc[:"2017-12-31"]
    test_pool = pool_obs.loc["2018-01-01":"2021-12-31"].dropna()
    backtest: dict[str, object] = {"status": "insufficient_data"}
    if len(train) >= 8 and len(test_pool) >= 8:
        ratio_bt = float(train.median())
        predicted = gross.reindex(test_pool.index) * ratio_bt
        errors = 100.0 * (predicted - test_pool).abs() / test_pool
        backtest = {
            "status": "run",
            "design": "withhold_2018_2021_ratio_from_2010_2017",
            "ratio": ratio_bt,
            "pool_mape_pct": float(errors.mean()),
            "pool_max_abs_pct": float(errors.max()),
        }

    manifest = {
        "tier_ladder": {
            "certified": f"{CERTIFIED_START.date()}+",
            "analysis": f"{PANEL_START.date()}-2021Q4",
            "backcast": f"{BACKCAST_START.date()}-2010Q1 ({BACKCAST_TIER})",
            "pre_2002": "frame_only_not_estimated (numerical values refused)",
        },
        "method_exception": (
            "Bounded-ratio runner-up design used for the 2002-2010 leg per the "
            "freeze-bless ingest MUST 3 allowance; the recommended dynamic "
            "component-share state-space design remains open post-freeze work."
        ),
        "ratio_calibration": {
            "window": [str(PANEL_START.date()), str(RATIO_CALIBRATION_END.date())],
            "center_median": ratio_center,
            "p10": ratio_low,
            "p90": ratio_high,
            "observed_quarters": int(len(ratios)),
        },
        "component_split_pre_2010": "refused_no_reconstructed_component_pools",
        "estimand": "expense_equivalent_holder_incidence_control_not_cash",
        "backcast_quarters": int((frame["method_tier"] == BACKCAST_TIER).sum()),
        "dropped_backcast_quarters_missing_legs": dropped,
        "splice_seam_flag": seam_flag,
        "splice_seam_detail": seam_detail,
        "rolling_origin_backtest": backtest,
    }
    return frame, manifest


def write_dst_du_long_history(
    *,
    expense_panel_path: Path | str,
    du_research_path: Path | str,
    components_path: Path | str,
    ru_backcast_wide_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
    out_manifest_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame, dict[str, object]]:
    expense = pd.read_csv(expense_panel_path)
    research = pd.read_csv(du_research_path, parse_dates=["date"]).set_index("date")
    components = pd.read_csv(components_path, parse_dates=["date"]).set_index("date")
    wide = pd.read_csv(ru_backcast_wide_path)
    frame, manifest = build_dst_du_long_history(
        expense_panel=expense,
        gross_interest_proxy=research["treasury_interest_gross_proxy"],
        fed_coupon_proxy=components["fed_tsy_coupon_interest_proxy"],
        ru_backcast_wide=wide,
    )
    out_csv = Path(out_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write = frame.copy()
    write["date"] = pd.to_datetime(write["date"], errors="coerce").dt.date.astype(str)
    write.to_csv(out_csv, index=False)

    latest = frame.iloc[-1]
    earliest = frame.iloc[0]
    lines = [
        "# DS^T_DU long-history expense-equivalent row",
        "",
        f"Coverage: {earliest['date'].date()} to {latest['date'].date()} "
        f"({len(frame)} quarters; {manifest['backcast_quarters']} backcast).",
        "Estimand: expense-equivalent holder-incidence control (modified accrual);",
        "NOT cash received; never additive to Tier 2. Pre-2002 values are refused.",
        f"Method exception: {manifest['method_exception']}",
        f"Ratio calibration: {json.dumps(manifest['ratio_calibration'])}",
        f"Backtest: {json.dumps(manifest['rolling_origin_backtest'])}",
        f"Seam check: {manifest['splice_seam_detail'] or 'n/a'} -> flag={manifest['splice_seam_flag']}",
        "",
    ]
    out_md = Path(out_markdown_path)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    out_manifest = Path(out_manifest_path)
    out_manifest.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return out_csv, out_md, frame, manifest
