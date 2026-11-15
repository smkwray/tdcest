"""Measured TDC against the federal budget deficit: a descriptive comparison of two totals.

Measured TDC is leg ``C`` of the vintage's regression legs. The deficit is minus the
calendar-quarter sum of the Monthly Treasury Statement total surplus or deficit, so a
positive value is a deficit and a surplus month reduces it. The five funding-source legs
and the comparison periods come from ``catalog.DEFICIT_FUNDING_LEGS`` and
``catalog.DEFICIT_COMPARISON_PERIODS``. Period ratios are ratios of cumulative sums; no
per-quarter ratio is formed because a single quarter's deficit can be near zero or negative.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import (
    DEFAULT_VINTAGE,
    DEFICIT_FUNDING_LEGS,
    MeasurementVintage,
    deficit_comparison_periods,
    fiscus_registries,
)
from .config import project_paths
from .reserve_factor_ledger import _sha256
from .tier2_regression_series import (
    LEG_CANONICAL_COLUMN,
    MODERN_SPLICE_TOLERANCE_MILLIONS,
    read_pinned_input,
    require_clean_commit,
)
from .trc_export import LEGS_FILE, load_fiscus_inputs
from .trc_reserve_component import _numeric

SCHEMA_VERSION = "tdc_deficit_comparison_v1"
DEFICIT_KEY = "mts_surplus_deficit"
LEG_KEYS = [leg.key for leg in DEFICIT_FUNDING_LEGS]
OUTPUT_FILES = {
    "quarterly": "tdc_deficit_comparison_quarterly_v1.csv",
    "periods": "tdc_deficit_comparison_periods_v1.csv",
    "receipt": "tdc_deficit_comparison_v1_receipt.json",
}
DEFICIT_SOURCE = {
    "series_id": "MTSDS133FMS",
    "title": "Federal Surplus or Deficit [-]",
    "publisher": "US Department of the Treasury, Monthly Treasury Statement, as distributed by FRED",
    "units": "USD million, monthly, not seasonally adjusted; negative values are deficits",
    "choice": "Treasury's own MTS Table 1 through fiscus (fiscaldata.mts_table_1) starts in 2015-03, after the "
              "start of the comparison window; its FRED mirror covers every month of the window",
}
INTERPRETATION = (
    "The ratio compares two differently scoped totals. Measured TDC includes secondary-market Treasury-security "
    "settlements, Treasury cash changes, and interest and remittance terms; the MTS surplus or deficit is a budget "
    "measure on a modified cash basis. The ratio is not the share of deficit dollars that stayed in deposits, and it "
    "is not a retention or reversal rate."
)
BOUNDARIES = [
    "Descriptive comparison; no estimation, identification, attribution, or causal interpretation",
    "Both series are calendar-quarter flows in USD million; the deficit is minus the sum of three MTS months",
    "Period ratios are cumulative TDC over cumulative deficit; no per-quarter ratio is reported",
    "The funding-source legs reconcile to measured TDC within the regression-leg tolerance; they are accounting "
    "terms and do not identify settlement routes",
]


def quarterly_deficit(frame: pd.DataFrame, quarters: pd.PeriodIndex) -> pd.Series:
    """Minus the summed monthly surplus of each quarter; every month must be present and numeric."""
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if not dates.dt.day.eq(1).all() or dates.duplicated().any():
        raise ValueError(f"{DEFICIT_KEY}: monthly observations must be unique first-of-month dates")
    surplus = pd.Series(_numeric(frame["value"], DEFICIT_KEY).to_numpy(), index=dates.dt.to_period("M"))
    months = pd.period_range(quarters[0].asfreq("M", "start"), quarters[-1].asfreq("M", "end"), freq="M")
    missing = months.difference(surplus.index)
    if len(missing):
        raise ValueError(f"{DEFICIT_KEY}: missing months {[str(m) for m in missing[:5]]}; refusing to truncate")
    window = surplus.loc[months]
    return -window.groupby(window.index.asfreq("Q")).sum()


def funding_legs(legs: pd.DataFrame, quarters: pd.PeriodIndex) -> pd.DataFrame:
    """Measured TDC, the registry funding-source legs, and their reconciliation gap, USD million."""
    columns = {"C", LEG_CANONICAL_COLUMN} | {column for leg in DEFICIT_FUNDING_LEGS for column, _ in leg.terms}
    missing = sorted(columns - set(legs.columns) - {"quarter"})
    if missing or "quarter" not in legs.columns:
        raise ValueError(f"regression legs: missing columns {missing or ['quarter']}")
    index = pd.PeriodIndex(legs["quarter"], freq="Q")
    if index.has_duplicates:
        raise ValueError("regression legs: duplicate quarters")
    missing_quarters = quarters.difference(index)
    if len(missing_quarters):
        raise ValueError(f"regression legs: missing quarters {[str(q) for q in missing_quarters[:5]]}; "
                         "refusing to truncate")
    values = legs[sorted(columns)].apply(pd.to_numeric, errors="raise").set_axis(index).loc[quarters]
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("regression legs: missing or nonfinite values")
    if not values["C"].equals(values[LEG_CANONICAL_COLUMN]):
        raise ValueError(f"regression legs: C differs from {LEG_CANONICAL_COLUMN}")
    out = pd.DataFrame({"tdc": values["C"]})
    for leg in DEFICIT_FUNDING_LEGS:
        out[leg.key] = sum(sign * values[column] for column, sign in leg.terms)
    out["leg_reconciliation_gap"] = out["tdc"] - out[LEG_KEYS].sum(axis=1)
    worst = float(out["leg_reconciliation_gap"].abs().max())
    if worst > MODERN_SPLICE_TOLERANCE_MILLIONS:
        raise ValueError(f"funding-source legs differ from C by {worst} USD million "
                         f"(tolerance {MODERN_SPLICE_TOLERANCE_MILLIONS})")
    return out


def build_comparison(
    legs: pd.DataFrame, surplus: pd.DataFrame, vintage: MeasurementVintage = DEFAULT_VINTAGE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Quarterly and period tables over the configured comparison periods."""
    periods = [(pd.Period(first, "Q"), pd.Period(last, "Q")) for first, last in deficit_comparison_periods(vintage)]
    end = pd.Period(vintage.quarter_end, "Q")
    if any(first > last or last > end for first, last in periods):
        raise ValueError(f"comparison periods must be ordered and end by {vintage.quarter_end}")
    quarters = pd.period_range(min(first for first, _ in periods), end, freq="Q")
    flows = funding_legs(legs, quarters)
    flows.insert(1, "deficit", quarterly_deficit(surplus, quarters))
    rows = []
    for first, last in periods:
        block = flows.loc[first:last]
        tdc, deficit = float(block["tdc"].sum()), float(block["deficit"].sum())
        if deficit <= 0:
            raise ValueError(f"{first}-{last}: cumulative deficit {deficit} is not positive; a ratio is undefined")
        rows.append({
            "period": f"{first}-{last}", "first_quarter": str(first), "last_quarter": str(last),
            "n_quarters": len(block), "tdc_cumulative": tdc, "deficit_cumulative": deficit,
            "tdc_to_deficit_ratio": tdc / deficit,
            **{f"{key}_cumulative": float(block[key].sum()) for key in LEG_KEYS},
        })
    quarterly = flows.reset_index(names="quarter")
    quarterly["quarter"] = quarterly["quarter"].astype(str)
    return quarterly, pd.DataFrame(rows)


def column_metadata() -> dict:
    legs = {leg.key: {"label": leg.label, "terms": [{"column": column, "sign": sign} for column, sign in leg.terms]}
            for leg in DEFICIT_FUNDING_LEGS}
    quarterly = {
        "quarter": {"definition": "Calendar quarter"},
        "tdc": {"definition": f"Measured TDC: regression-leg column C, equal to {LEG_CANONICAL_COLUMN}"},
        "deficit": {"definition": "Minus the sum of the three monthly MTS surpluses (MTSDS133FMS); positive is a "
                                  "deficit and a surplus month reduces it"},
        **legs,
        "leg_reconciliation_gap": {"definition": "tdc less the sum of the five funding-source legs"},
    }
    periods = {
        "period": {"definition": "First and last calendar quarter of the period"},
        "first_quarter": {"definition": "First calendar quarter summed"},
        "last_quarter": {"definition": "Last calendar quarter summed"},
        "n_quarters": {"definition": "Quarters summed"},
        "tdc_cumulative": {"definition": "Sum of quarterly tdc"},
        "deficit_cumulative": {"definition": "Sum of quarterly deficit"},
        "tdc_to_deficit_ratio": {"definition": "tdc_cumulative / deficit_cumulative: a ratio of sums, never an "
                                               "average of quarterly ratios"},
        **{f"{key}_cumulative": {"definition": f"Sum of quarterly {key}"} for key in LEG_KEYS},
    }
    return {"quarterly": quarterly, "periods": periods}


def write_deficit_comparison_export(
    *, root: Path | str, legs_sha256: str, inputs_manifest_sha256: str, vintage: MeasurementVintage = DEFAULT_VINTAGE,
) -> dict:
    """Bind the comparison to a clean commit, the pinned regression legs, and the pinned fiscus manifest."""
    registry = fiscus_registries(vintage)["deficit"]
    paths = project_paths(root)
    root = paths.root
    producer_commit = require_clean_commit(root)
    legs_path, manifest_path = paths.processed / LEGS_FILE, root / registry.manifest
    legs_raw, legs_record = read_pinned_input(root, legs_path, legs_sha256, "regression_legs")
    manifest_raw, manifest_record = read_pinned_input(root, manifest_path, inputs_manifest_sha256, "inputs_manifest")
    manifest = json.loads(manifest_raw)
    frames, input_records = load_fiscus_inputs(root, manifest, registry)

    quarterly, periods = build_comparison(pd.read_csv(io.BytesIO(legs_raw)), frames[DEFICIT_KEY], vintage)
    payloads = {role: frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
                for role, frame in [("quarterly", quarterly), ("periods", periods)]}
    output_paths = {role: paths.processed / name for role, name in OUTPUT_FILES.items()}
    protected = {legs_path.resolve(), manifest_path.resolve()} | {
        (root / record["file"]).resolve() for record in input_records.values()}
    if {path.resolve() for path in output_paths.values()} & protected:
        raise ValueError("Output paths cannot overwrite inputs")
    deficit_input = input_records[DEFICIT_KEY]
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "producer_commit": producer_commit,
        "vintage": vintage.name,
        "units": "USD million",
        "sample": {"first": quarterly["quarter"].iloc[0], "last": quarterly["quarter"].iloc[-1],
                   "n": int(len(quarterly))},
        "interpretation": INTERPRETATION,
        "boundaries": BOUNDARIES,
        "deficit_source": {**DEFICIT_SOURCE, "dataset_id": deficit_input["dataset_id"],
                           "source_url": deficit_input["source_url"], "source_vintage": deficit_input["vintage"],
                           "sha256": deficit_input["sha256"], "cache_key": deficit_input["cache_key"],
                           "retrieved_at_utc": deficit_input["retrieved_at_utc"]},
        "inputs": {"regression_legs": legs_record,
                   "inputs_manifest": {**manifest_record, "fiscus": manifest.get("fiscus", {}),
                                       "acquired_at_utc": manifest.get("acquired_at_utc")},
                   "fiscus_inputs": input_records},
        "outputs": {role: {"path": str(output_paths[role].relative_to(root)), "sha256": _sha256(data),
                           "byte_count": len(data)} for role, data in payloads.items()},
        "periods": periods[["period", "first_quarter", "last_quarter", "n_quarters"]].to_dict("records"),
        "reconciliation": {"tolerance_usd_million": MODERN_SPLICE_TOLERANCE_MILLIONS,
                           "max_abs_gap_usd_million": float(quarterly["leg_reconciliation_gap"].abs().max())},
        "columns": column_metadata(),
    }
    text = json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    for role, data in payloads.items():
        output_paths[role].parent.mkdir(parents=True, exist_ok=True)
        output_paths[role].write_bytes(data)
    output_paths["receipt"].write_text(text, encoding="utf-8")
    return receipt
