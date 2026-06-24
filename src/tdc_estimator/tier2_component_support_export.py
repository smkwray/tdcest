from __future__ import annotations

from pathlib import Path
import shutil
import uuid

import pandas as pd

from .interest_source_window_validation import ALLOWED_USABLE_CONSTRAINT_STATUSES, build_interest_source_window_validation
from .tier2_interest_release_manifest import (
    COMPONENT_SUPPORT_COLUMNS,
    MANIFEST_FILENAME,
    default_component_release_dates,
    validate_support_frame_dates_and_values,
    write_tier2_component_release_manifest,
)


SUPPORT_EXPORT_COLUMNS = COMPONENT_SUPPORT_COLUMNS

DEFAULT_CONSTRAINED_COMPONENT_START = "2022-03-31"


def assert_component_support_source_window_ready(
    *,
    candidate: pd.DataFrame,
    constraints: pd.DataFrame,
    min_date: str | pd.Timestamp | None = DEFAULT_CONSTRAINED_COMPONENT_START,
    expected_dates: list[str] | None = None,
) -> pd.DataFrame:
    expected = expected_dates or default_component_release_dates()
    if "constraint_status" not in constraints.columns:
        raise ValueError("Tier 2 component support export blocked: source constraints missing constraint_status.")
    statuses = set(constraints["constraint_status"].dropna().astype(str))
    unexpected_statuses = sorted(
        status for status in statuses if status.startswith("usable") and status not in ALLOWED_USABLE_CONSTRAINT_STATUSES
    )
    if unexpected_statuses:
        raise ValueError(
            "Tier 2 component support export blocked: unexpected usable source statuses: "
            + ", ".join(unexpected_statuses)
        )
    required_candidate_columns = {"date", "sector_group", "component_anchored_interest_mil"}
    missing_candidate_columns = sorted(required_candidate_columns - set(candidate.columns))
    if missing_candidate_columns:
        raise ValueError(
            "Tier 2 component support export blocked: candidate missing required columns: "
            + ", ".join(missing_candidate_columns)
        )
    candidate_window = candidate.copy()
    candidate_window["date"] = pd.to_datetime(candidate_window["date"], errors="coerce").dt.normalize()
    if min_date is not None:
        candidate_window = candidate_window.loc[candidate_window["date"].ge(pd.Timestamp(min_date).normalize())].copy()
    actual_dates = sorted(candidate_window["date"].dropna().dt.date.astype(str).unique().tolist())
    if actual_dates != expected:
        raise ValueError(
            "Tier 2 component support export blocked: candidate date window mismatch: "
            f"expected {expected}, got {actual_dates}"
        )
    for sector in SUPPORT_EXPORT_COLUMNS:
        sector_rows = candidate_window.loc[candidate_window["sector_group"].astype(str).eq(sector)]
        if sector_rows.empty:
            raise ValueError(f"Tier 2 component support export blocked: candidate missing sector_group={sector}.")
        sector_dates = sorted(sector_rows["date"].dropna().dt.date.astype(str).unique().tolist())
        if sector_dates != expected:
            raise ValueError(
                f"Tier 2 component support export blocked: candidate sector {sector} date window mismatch: {sector_dates}"
            )
        values = pd.to_numeric(sector_rows["component_anchored_interest_mil"], errors="coerce")
        if values.isna().any():
            raise ValueError(f"Tier 2 component support export blocked: candidate sector {sector} has non-finite values.")

    validation = build_interest_source_window_validation(candidate=candidate, constraints=constraints)
    if validation.empty:
        raise ValueError("Tier 2 component support export blocked: source-window validation produced no rows.")
    work = validation.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    if min_date is not None:
        work = work.loc[work["date"].ge(pd.Timestamp(min_date).normalize())].copy()
    if work.empty:
        raise ValueError("Tier 2 component support export blocked: no source-window rows overlap the export window.")
    validation_dates = sorted(work["date"].dropna().dt.date.astype(str).unique().tolist())
    if validation_dates != expected:
        raise ValueError(
            "Tier 2 component support export blocked: source-window date mismatch: "
            f"expected {expected}, got {validation_dates}"
        )
    bad = work.loc[~work["promotion_ready_constraint_window"].astype(bool)].copy()
    if bad.empty:
        return work
    missing_by_date: list[str] = []
    for _, row in bad.head(8).iterrows():
        missing = [
            label
            for label, column in [
                ("bank", "bank_has_constraint"),
                ("credit_union", "credit_union_has_constraint"),
                ("money_market_funds", "money_market_funds_has_constraint"),
                ("row", "row_has_constraint"),
            ]
            if not bool(row.get(column, False))
        ]
        missing_by_date.append(f"{row['date'].date().isoformat()} missing {','.join(missing)}")
    raise ValueError(
        "Tier 2 component support export blocked: source-window validation is not promotion-ready "
        f"for {len(bad)} export-window quarter(s): {'; '.join(missing_by_date)}"
    )


def build_tier2_component_support_exports(
    candidate: pd.DataFrame,
    *,
    min_date: str | pd.Timestamp | None = DEFAULT_CONSTRAINED_COMPONENT_START,
) -> dict[str, pd.DataFrame]:
    if candidate.empty:
        return {key: pd.DataFrame(columns=["date", column]) for key, column in SUPPORT_EXPORT_COLUMNS.items()}
    df = candidate.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    if min_date is not None:
        df = df.loc[df["date"].ge(pd.Timestamp(min_date).normalize())].copy()
    df["component_anchored_interest_mil"] = pd.to_numeric(df["component_anchored_interest_mil"], errors="coerce")
    grouped = (
        df.dropna(subset=["date", "sector_group"])
        .groupby(["date", "sector_group"], as_index=False)["component_anchored_interest_mil"]
        .sum(min_count=1)
    )
    out: dict[str, pd.DataFrame] = {}
    for sector_group, value_column in SUPPORT_EXPORT_COLUMNS.items():
        rows = grouped.loc[grouped["sector_group"].astype(str).eq(sector_group), ["date", "component_anchored_interest_mil"]]
        support = rows.rename(columns={"component_anchored_interest_mil": value_column}).sort_values("date")
        support["date"] = pd.to_datetime(support["date"]).dt.date.astype(str)
        out[sector_group] = support.reset_index(drop=True)
    return out


def render_tier2_component_support_export_summary(exports: dict[str, pd.DataFrame]) -> str:
    lines = [
        "# Tier 2 Component-Anchored Support Exports",
        "",
        "These support files contain the constrained component-anchored default window. Earlier component-pool backcast quarters are available in `tier2_regression_interest_backcast.csv` instead of these canonical support files.",
        "",
        "| Sector | Rows | First date | Latest date | Latest value (mil) |",
        "|---|---:|---:|---:|---:|",
    ]
    for sector, frame in exports.items():
        if frame.empty:
            lines.append(f"| {sector} | 0 |  |  | NA |")
            continue
        date = pd.to_datetime(frame["date"], errors="coerce")
        value_col = [col for col in frame.columns if col != "date"][0]
        latest_idx = date.idxmax()
        latest_value = pd.to_numeric(frame.loc[latest_idx, value_col], errors="coerce")
        lines.append(
            f"| {sector} | {len(frame):,} | {date.min().date().isoformat()} | "
            f"{date.max().date().isoformat()} | ${float(latest_value):,.0f} |"
        )
    lines.extend(
        [
            "",
            "Promotion rule: consume these only through explicit component-anchored estimator wiring. Do not alias them to old coupon proxy names, because they already include coupon accrual, bill discount, and FRN interest.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tier2_component_support_exports(
    *,
    candidate_path: Path | str,
    out_dir: Path | str,
    markdown_path: Path | str,
    source_constraints_path: Path | str | None = None,
    require_source_window_ready: bool = True,
    expected_dates: list[str] | None = None,
) -> tuple[dict[str, Path], Path, dict[str, pd.DataFrame]]:
    expected = expected_dates or default_component_release_dates()
    candidate = pd.read_csv(candidate_path)
    if require_source_window_ready:
        if source_constraints_path is None:
            raise ValueError(
                "Tier 2 component support export blocked: --source-constraints-file is required for fail-closed export."
            )
        constraints = pd.read_csv(source_constraints_path)
        assert_component_support_source_window_ready(candidate=candidate, constraints=constraints, expected_dates=expected)
    exports = build_tier2_component_support_exports(candidate)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stage = out / f".tier2_component_support_stage_{uuid.uuid4().hex}"
    stage.mkdir(parents=True, exist_ok=False)
    paths: dict[str, Path] = {}
    try:
        staged_paths: dict[str, Path] = {}
        for sector, frame in exports.items():
            filename = f"support__{SUPPORT_EXPORT_COLUMNS[sector]}.csv"
            staged = stage / filename
            validate_support_frame_dates_and_values(
                frame,
                date_column="date",
                value_column=SUPPORT_EXPORT_COLUMNS[sector],
                expected_dates=expected,
                label=filename,
            )
            frame.to_csv(staged, index=False)
            staged_paths[sector] = staged
        staged_manifest = stage / MANIFEST_FILENAME
        if source_constraints_path is not None:
            write_tier2_component_release_manifest(
                manifest_path=staged_manifest,
                support_paths=staged_paths,
                candidate_path=candidate_path,
                source_constraints_path=source_constraints_path,
                expected_dates=expected,
            )
        for sector, staged in staged_paths.items():
            final = out / staged.name
            staged.replace(final)
            paths[sector] = final
        if staged_manifest.exists():
            staged_manifest.replace(out / MANIFEST_FILENAME)
        md_out = Path(markdown_path)
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_tier2_component_support_export_summary(exports), encoding="utf-8")
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return paths, md_out, exports
