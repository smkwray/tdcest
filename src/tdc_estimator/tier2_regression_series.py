from __future__ import annotations

from pathlib import Path
import hashlib
import io
import json
import subprocess

import numpy as np
import pandas as pd

from .catalog import BANK_DEPOSITORY_TX_KEYS


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

MODERN_SPLICE_SUPPORT_FILES = {
    "bank": (
        "support__bank_tier2_component_interest_proxy.csv",
        "bank_tier2_regression_interest_proxy",
    ),
    "credit_union": (
        "support__credit_union_tier2_component_interest_proxy.csv",
        "credit_union_tier2_regression_interest_proxy",
    ),
    "row": (
        "support__row_tier2_component_interest_proxy.csv",
        "row_tier2_regression_interest_proxy",
    ),
}
MODERN_SPLICE_TOLERANCE_MILLIONS = 1e-6

LEG_CANONICAL_COLUMN = "tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow"
LEG_QUARTERLY_COLUMNS = [
    "fed_tsy_tx", *BANK_DEPOSITORY_TX_KEYS, "row_tsy_tx",
    "treasury_operating_cash_tx", "fed_remit_or_deferred",
]
LEG_REGRESSION_COLUMNS = [
    LEG_CANONICAL_COLUMN, "tdc_tier2_regression_bank_only_ru_flow",
    "tdc_tier2_regression_domestic_bank_only_ru_flow",
    "row_tier2_regression_interest_proxy", "bank_tier2_regression_interest_proxy",
    "fed_tsy_coupon_interest_proxy", "mmf_rrp_adjustment_prop",
]
LEG_TIER_COLUMNS = ["row_method_tier", "tier2_regression_bank_row_method_tier"]


def build_regression_leg_table(
    quarterly: pd.DataFrame, regression: pd.DataFrame,
) -> pd.DataFrame:
    """Decompose the fixed 2002Q1–2025Q4 proxy without changing its inputs."""
    expected = pd.period_range("2002Q1", "2025Q4", freq="Q")
    frames = []
    for label, source, columns in [
        ("quarterly", quarterly, LEG_QUARTERLY_COLUMNS),
        ("regression", regression, [*LEG_REGRESSION_COLUMNS, *LEG_TIER_COLUMNS]),
    ]:
        missing = set(["date", *columns]) - set(source.columns)
        if missing:
            raise ValueError(f"{label}: missing columns {sorted(missing)}")
        frame = source[["date", *columns]].copy()
        dates = pd.to_datetime(frame.pop("date"), errors="raise")
        if dates.isna().any() or not dates.eq(dates.dt.to_period("Q").dt.end_time.dt.normalize()).all():
            raise ValueError(f"{label}: invalid quarter-end dates")
        frame.index = pd.PeriodIndex(dates, freq="Q")
        if frame.index.has_duplicates:
            raise ValueError(f"{label}: duplicate quarters")
        frame = frame.loc[(frame.index >= expected[0]) & (frame.index <= expected[-1])].sort_index()
        if not frame.index.equals(expected):
            raise ValueError(f"{label}: expected exactly 96 complete quarters")
        for column in columns:
            if column in LEG_TIER_COLUMNS:
                if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
                    raise ValueError(f"{label}: missing method tier {column}")
            else:
                frame[column] = pd.to_numeric(frame[column], errors="raise")
                structural_absence = (
                    frame[column].isna() & (frame.index < ON_RRP_FULL_MECHANISM_START.to_period("Q"))
                    if column == "mmf_rrp_adjustment_prop" else False
                )
                if not (np.isfinite(frame[column]) | structural_absence).all():
                    raise ValueError(f"{label}: nonfinite required values in {column}")
        frames.append(frame)
    out = frames[0].join(frames[1], validate="one_to_one")
    out["quarter"] = out.index.astype(str)
    out["C"] = out[LEG_CANONICAL_COLUMN]
    out["R"] = out["row_tsy_tx"] - out["row_tier2_regression_interest_proxy"]
    out["O"] = -out["treasury_operating_cash_tx"]
    out["J"] = out["C"] - out["R"] - out["O"]
    out["fed_remit_positive"] = out["fed_remit_or_deferred"]
    out["effective_mmf_rrp_adjustment_prop"] = out["mmf_rrp_adjustment_prop"].where(
        out.index >= ON_RRP_FULL_MECHANISM_START.to_period("Q"), 0.0,
    )
    out["J_expanded"] = (
        out[["fed_tsy_tx", *BANK_DEPOSITORY_TX_KEYS]].sum(axis=1)
        + out["fed_remit_positive"] - out["fed_tsy_coupon_interest_proxy"]
        - out["bank_tier2_regression_interest_proxy"]
        + out["effective_mmf_rrp_adjustment_prop"]
    )
    out["R_reconstruction_gap"] = out["R"] - (
        out["tdc_tier2_regression_bank_only_ru_flow"]
        - out["tdc_tier2_regression_domestic_bank_only_ru_flow"]
    )
    out["J_reconstruction_gap"] = out["J"] - out["J_expanded"]
    out["C_adding_up_gap"] = out["C"] - out[["R", "J", "O"]].sum(axis=1)
    for column in ["R_reconstruction_gap", "J_reconstruction_gap", "C_adding_up_gap"]:
        worst = float(out[column].abs().max())
        if worst > MODERN_SPLICE_TOLERANCE_MILLIONS:
            raise ValueError(f"{column}: {worst} exceeds {MODERN_SPLICE_TOLERANCE_MILLIONS} million")
    out["quarterly_missing_count"] = 0
    out["mmf_adjustment_raw_missing"] = out["mmf_rrp_adjustment_prop"].isna()
    out["regression_missing_count"] = out["mmf_adjustment_raw_missing"].astype(int)
    first = ["quarter", "C", "R", "J", "O"]
    return out[first + [column for column in out if column not in first]].reset_index(drop=True)


def write_regression_leg_table(
    *, root: Path, quarterly_path: Path, regression_path: Path,
    quarterly_sha256: str, regression_sha256: str,
    out_path: Path, receipt_path: Path,
) -> dict:
    """Bind the additive diagnostic to committed code and explicit input hashes."""
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Export requires a clean committed producer checkout")
    producer_commit = git("rev-parse", "HEAD")
    inputs = {}
    frames = []
    for role, path, expected_hash in [
        ("quarterly", quarterly_path, quarterly_sha256),
        ("regression", regression_path, regression_sha256),
    ]:
        raw = path.read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"{role}: source hash mismatch")
        inputs[role] = {"path": str(path.resolve().relative_to(root.resolve())), "sha256": actual_hash}
        frames.append(pd.read_csv(io.BytesIO(raw)))
    output_paths = [out_path.resolve(), receipt_path.resolve()]
    if len(set(output_paths)) != 2 or set(output_paths) & {quarterly_path.resolve(), regression_path.resolve()}:
        raise ValueError("Output paths must be distinct and cannot overwrite inputs")
    frame = build_regression_leg_table(*frames)
    for role, source in inputs.items():
        frame[f"{role}_source_sha256"] = source["sha256"]
    table_bytes = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    receipt = {
        "schema_version": "regression_legs_v1", "producer_commit": producer_commit,
        "units": "USD million", "sample": {"start": "2002Q1", "end": "2025Q4", "n": len(frame)},
        "inputs": inputs, "output": {"path": str(out_path.resolve().relative_to(root.resolve())),
        "sha256": hashlib.sha256(table_bytes).hexdigest()},
        "full_precision_reconciliation_tolerance": MODERN_SPLICE_TOLERANCE_MILLIONS,
        "max_absolute_gaps": {column: float(frame[column].abs().max()) for column in
            ["R_reconstruction_gap", "J_reconstruction_gap", "C_adding_up_gap"]},
        "negative_R_quarters": int((frame.R < 0).sum()),
        "negative_R_with_nonnegative_raw_purchases": int(((frame.R < 0) & (frame.row_tsy_tx >= 0)).sum()),
        "method_tier_counts": frame.row_method_tier.value_counts().sort_index().to_dict(),
        "structural_pre_mechanism_mmf_missing_quarters": int(frame.mmf_adjustment_raw_missing.sum()),
        "labels": {"R": "ROW net Treasury purchases net of allocated debt service",
                   "J": "remainder treatment leg", "O": "minus Treasury operating cash transactions"},
        "source_resolution": {leg: {"delta_usd_million": None, "status": "unestablished",
            "reason": "Derived CSV precision and arithmetic reconciliation do not establish source quantization bounds"}
            for leg in ["R", "J", "O"]},
        "boundaries": [
            "Descriptive treatment decomposition; no treatment promotion or counterpart settlement attribution",
            "Pre-component interest uses a scaled-H.15 backcast through 2010Q1",
            "J includes Fed and US-chartered, foreign-office and affiliated-area-bank purchases; it is not domestic-bank purchases",
            "Reference deposit outcome BOGZ1FL764100005Q covers US-chartered institutions and all holders; treatment-bank perimeter also includes foreign offices and affiliated-area banks",
            "Reference factor controls were selected and scored on the full panel including 2020–21; quarterly lag001 features anchor at t-2",
            "Both cached input objects are hash-pinned; no source-vintage refresh is performed",
            "Missing raw MMF adjustments before 2013Q3 are flagged; the effective term is definitionally zero there, and active-period missingness fails",
        ],
    }
    for path in [out_path, receipt_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(table_bytes)
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


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


def validate_regression_backcast_modern_splice(
    regression_backcast_wide: pd.DataFrame,
    component_support_dir: Path | str,
    *,
    tolerance: float = MODERN_SPLICE_TOLERANCE_MILLIONS,
) -> None:
    """Fail closed if the wide backcast's modern splice drifted from the certified
    component supports.

    A support file that is absent is skipped (support export is a separate stage);
    a support file that is present must overlap the backcast and match exactly to
    release rounding on every overlapping quarter.
    """
    support_dir = Path(component_support_dir)
    backcast = regression_backcast_wide.copy()
    backcast["date"] = pd.to_datetime(backcast["date"], errors="coerce").dt.normalize()
    failures: list[str] = []
    for sector, (filename, column) in MODERN_SPLICE_SUPPORT_FILES.items():
        path = support_dir / filename
        if not path.exists():
            continue
        if column not in backcast.columns:
            failures.append(f"{sector}: backcast is missing column {column}")
            continue
        support = pd.read_csv(path)
        support.columns = ["date", "support_value"]
        support["date"] = pd.to_datetime(support["date"], errors="coerce").dt.normalize()
        merged = backcast[["date", column]].merge(support, on="date", how="inner")
        if merged.empty:
            failures.append(
                f"{sector}: certified support {filename} has no date overlap with the backcast"
            )
            continue
        gaps = (
            pd.to_numeric(merged[column], errors="coerce")
            - pd.to_numeric(merged["support_value"], errors="coerce")
        ).abs()
        worst = gaps.max()
        if pd.isna(worst) or worst > tolerance:
            worst_date = merged.loc[gaps.idxmax(), "date"].date()
            failures.append(
                f"{sector}: stale modern splice — max |backcast - certified support| "
                f"= {worst:.6f} million at {worst_date} (tolerance {tolerance})"
            )
    if failures:
        raise ValueError(
            "Regression backcast modern splice does not match the certified component "
            "supports; regenerate tier2-regression-backcast before building the series. "
            + " | ".join(failures)
        )


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
    component_support_dir: Path | str | None = None,
) -> tuple[Path, Path, pd.DataFrame]:
    backcast_wide = _read_date_csv(regression_backcast_wide_path)
    if component_support_dir is not None:
        validate_regression_backcast_modern_splice(backcast_wide, component_support_dir)
    series = build_tier2_regression_series(
        estimates=_read_date_csv(estimates_path),
        components=_read_date_csv(components_path),
        regression_backcast_wide=backcast_wide,
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
