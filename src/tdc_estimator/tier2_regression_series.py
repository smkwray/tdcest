from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_COLUMNS = [
    "tdc_base_bank_only_ru_flow",
    "tdc_base_broad_depository_np_cu_ru_flow",
    "tdc_domestic_bank_only_ru_flow",
]

BACKCAST_COLUMNS = [
    "bank_tier2_regression_interest_proxy",
    "row_tier2_regression_interest_proxy",
    "credit_union_tier2_regression_interest_proxy",
    "bank_row_tier2_regression_interest_proxy",
    "di_tier2_regression_interest_proxy",
]

MMF_RRP_ADJUSTMENT_COLUMNS = {
    "lb": "mmf_rrp_adjustment_lb",
    "prop": "mmf_rrp_adjustment_prop",
    "ub": "mmf_rrp_adjustment_ub",
}
ON_RRP_FULL_MECHANISM_START = pd.Timestamp("2013-09-30")

REGRESSION_TDC_COLUMNS = [
    "tdc_tier2_regression_domestic_bank_only_ru_flow",
    "tdc_tier2_regression_bank_only_ru_flow",
    "tdc_tier2_regression_broad_depository_np_cu_ru_flow",
    "tdc_tier2_regression_depository_institution_np_cu_ru_flow",
]


def _read_date_csv(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError(f"{path} must include a date column.")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _required_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        raise ValueError(f"Missing required column: {column}")
    return pd.to_numeric(df[column], errors="coerce")


def _combine_tiers(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    values = frame[columns].astype("string")

    def combine(row: pd.Series) -> str | pd.NA:
        observed = [str(value) for value in row.dropna().tolist() if str(value) != "<NA>"]
        unique = list(dict.fromkeys(observed))
        if not unique:
            return pd.NA
        if len(unique) == 1:
            return unique[0]
        return "mixed:" + "|".join(unique)

    return values.apply(combine, axis=1)


def build_tier2_regression_series(
    *,
    estimates: pd.DataFrame,
    components: pd.DataFrame,
    regression_backcast_wide: pd.DataFrame,
) -> pd.DataFrame:
    est = estimates.copy()
    comp = components.copy()
    backcast = regression_backcast_wide.copy()
    for frame in [est, comp, backcast]:
        if "date" not in frame.columns:
            raise ValueError("All input frames must include a date column.")
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()

    keep_est = ["date", *BASE_COLUMNS]
    keep_comp = ["date", "fed_tsy_coupon_interest_proxy"]
    keep_comp.extend([col for col in MMF_RRP_ADJUSTMENT_COLUMNS.values() if col in comp.columns])
    missing_est = [col for col in keep_est if col not in est.columns]
    missing_comp = [col for col in ["date", "fed_tsy_coupon_interest_proxy"] if col not in comp.columns]
    missing_backcast = [col for col in ["date", *BACKCAST_COLUMNS] if col not in backcast.columns]
    if missing_est:
        raise ValueError(f"Missing estimates columns: {missing_est}")
    if missing_comp:
        raise ValueError(f"Missing components columns: {missing_comp}")
    if missing_backcast:
        raise ValueError(f"Missing regression backcast columns: {missing_backcast}")

    out = est[keep_est].merge(comp[keep_comp], on="date", how="inner").merge(backcast, on="date", how="inner")
    out = out.sort_values("date").reset_index(drop=True)

    fed = _required_numeric(out, "fed_tsy_coupon_interest_proxy")
    bank = _required_numeric(out, "bank_tier2_regression_interest_proxy")
    bank_row = _required_numeric(out, "bank_row_tier2_regression_interest_proxy")
    di = _required_numeric(out, "di_tier2_regression_interest_proxy")

    out["tdc_tier2_regression_domestic_bank_only_ru_flow"] = (
        _required_numeric(out, "tdc_domestic_bank_only_ru_flow") - fed - bank
    )
    out["tdc_tier2_regression_bank_only_ru_flow"] = (
        _required_numeric(out, "tdc_base_bank_only_ru_flow") - fed - bank_row
    )
    out["tdc_tier2_regression_broad_depository_np_cu_ru_flow"] = (
        _required_numeric(out, "tdc_base_broad_depository_np_cu_ru_flow") - fed - bank_row
    )
    out["tdc_tier2_regression_depository_institution_np_cu_ru_flow"] = (
        _required_numeric(out, "tdc_base_broad_depository_np_cu_ru_flow") - fed - di
    )

    for suffix, column in MMF_RRP_ADJUSTMENT_COLUMNS.items():
        if column not in out.columns:
            continue
        adjustment = pd.to_numeric(out[column], errors="coerce")
        adjustment = adjustment.where(
            out["date"].ge(ON_RRP_FULL_MECHANISM_START),
            0.0,
        )
        out[f"tdc_tier2_regression_mmf_rrp_{suffix}_bank_only_ru_flow"] = (
            out["tdc_tier2_regression_bank_only_ru_flow"] + adjustment
        )
        out[f"tdc_tier2_regression_mmf_rrp_{suffix}_broad_depository_np_cu_ru_flow"] = (
            out["tdc_tier2_regression_broad_depository_np_cu_ru_flow"] + adjustment
        )
        out[f"tdc_tier2_regression_mmf_rrp_{suffix}_depository_institution_np_cu_ru_flow"] = (
            out["tdc_tier2_regression_depository_institution_np_cu_ru_flow"] + adjustment
        )

    tier_columns = [
        col
        for col in ["bank_method_tier", "row_method_tier", "credit_union_method_tier"]
        if col in out.columns
    ]
    if {"bank_method_tier", "row_method_tier"}.issubset(out.columns):
        out["tier2_regression_bank_row_method_tier"] = _combine_tiers(
            out, ["bank_method_tier", "row_method_tier"]
        )
    if set(tier_columns) == {"bank_method_tier", "row_method_tier", "credit_union_method_tier"}:
        out["tier2_regression_di_method_tier"] = _combine_tiers(out, tier_columns)

    required_output = REGRESSION_TDC_COLUMNS
    out = out.dropna(subset=required_output, how="all")
    return out


def render_tier2_regression_series_summary(series: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 Regression Series",
        "",
        "Transaction-based TDC series corrected with the regression-grade Tier 2 interest backcast.",
        "",
    ]
    if series.empty:
        return "\n".join(lines + ["No regression-corrected rows were available."]) + "\n"

    df = series.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    lines.extend(
        [
            f"Coverage runs from {df['date'].min().date().isoformat()} through {df['date'].max().date().isoformat()}.",
            "",
            "| Series | Nonmissing quarters | First date | Latest date | Latest value (mil) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    mmf_rrp_columns = [
        f"tdc_tier2_regression_mmf_rrp_{suffix}_{perimeter}_ru_flow"
        for suffix in ["lb", "prop", "ub"]
        for perimeter in [
            "bank_only",
            "broad_depository_np_cu",
            "depository_institution_np_cu",
        ]
    ]
    for column in [*REGRESSION_TDC_COLUMNS, *mmf_rrp_columns]:
        if column not in df.columns:
            continue
        value = pd.to_numeric(df[column], errors="coerce")
        observed = df.loc[value.notna(), ["date", column]]
        if observed.empty:
            continue
        latest = observed.iloc[-1]
        lines.append(
            f"| `{column}` | {len(observed):,} | {observed['date'].min().date().isoformat()} | "
            f"{observed['date'].max().date().isoformat()} | ${float(latest[column]):,.0f} |"
        )

    if "tier2_regression_bank_row_method_tier" in df.columns:
        lines.extend(["", "Method-tier counts:", "", "| Method tier | Quarters |", "|---|---:|"])
        for tier, count in df["tier2_regression_bank_row_method_tier"].value_counts(dropna=True).sort_index().items():
            lines.append(f"| {tier} | {int(count):,} |")
    lines.extend(
        [
            "",
            "Use these rows for regression windows that need history before the 2022 constrained-component window. The 2002-2010 segment remains a scaled-H15 interest backcast; it is not equivalent to the current constrained component default.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tier2_regression_series(
    *,
    estimates_path: Path | str,
    components_path: Path | str,
    regression_backcast_wide_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    series = build_tier2_regression_series(
        estimates=_read_date_csv(estimates_path),
        components=_read_date_csv(components_path),
        regression_backcast_wide=_read_date_csv(regression_backcast_wide_path),
    )
    out_csv = Path(out_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write = series.copy()
    write["date"] = pd.to_datetime(write["date"], errors="coerce").dt.date.astype(str)
    write.to_csv(out_csv, index=False)

    out_md = Path(out_markdown_path)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_tier2_regression_series_summary(series), encoding="utf-8")
    return out_csv, out_md, series
