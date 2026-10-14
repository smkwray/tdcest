"""U.S.-chartered bank balance-sheet composition: descriptive examples of non-Treasury deposit postings.

Z.1 table S.122.1 (formerly F.111 transactions and L.111 levels) supplies
quarterly transactions and quarter-end levels for U.S.-chartered depository
institutions. H.8 Table 4 supplies monthly loan and securities detail for
domestically chartered commercial banks. Every line comes from the typed
registries ``catalog.BANK_Z1_LINES`` and ``catalog.BANK_H8_LINES``.

The asset categories are mutually exclusive published S.122.1 lines; the
``all_other_assets`` residual is the sum of the remaining published asset lines,
not total less categories, so the closure on total financial assets is a check.
Nothing here estimates, identifies, or attributes deposit change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .catalog import (
    BANK_COMPOSITION_REGISTRY,
    BANK_H8_BASE_MONTH,
    BANK_H8_LINES,
    BANK_H8_MONTH,
    BANK_Z1_COLUMNS,
    BANK_Z1_END_QUARTER,
    BANK_Z1_FIRST_QUARTER,
    BANK_Z1_LINES,
)
from .config import project_paths
from .reserve_factor_ledger import _sha256
from .tier2_regression_series import read_pinned_input, require_clean_commit
from .trc_export import load_fiscus_inputs
from .trc_reserve_component import _numeric, z1_quarterly

SCHEMA_VERSION = "bank_composition_v1"
HALF_UNIT = 0.5  # USD million: Z.1 rounds every published line to the nearest million
H8_UNIT = 0.0001  # USD billion: published precision of the H.8 levels distributed by FRED
OUTPUT_FILES = {
    "quarterly": "bank_composition_z1_quarterly_v1.csv",
    "annual": "bank_composition_z1_annual_v1.csv",
    "holdings": "bank_composition_z1_holdings_v1.csv",
    "h8": "bank_composition_h8_v1.csv",
    "receipt": "bank_composition_v1_receipt.json",
}
ASSET_CATEGORIES = [c.key for c in BANK_Z1_COLUMNS if c.side == "asset_category"]
LIABILITY_COLUMNS = [c.key for c in BANK_Z1_COLUMNS if c.side == "liability"]
DEPOSIT_PARTS = ["checkable_deposits", "time_savings_deposits", "interbank_liabilities"]
FLOW_COLUMNS = [
    *ASSET_CATEGORIES, "total_financial_assets", "asset_closure_gap", "deposits_level_change",
    "deposits_transactions", "deposits_flow_level_gap", *DEPOSIT_PARTS, "nondeposit_liabilities",
]
LABELS = [
    "Z.1 corporate and foreign bonds include private-label MBS and CMOs, asset-backed securities, and foreign "
    "bonds; the category is not pure corporate bonds",
    "Z.1 transactions exclude valuation changes; Z.1 levels include them (securities levels are market-value "
    "LM series), so level changes and summed transactions differ",
    "H.8 covers commercial banks only, here domestically chartered commercial banks; it excludes savings "
    "institutions and credit unions and so differs from the Z.1 U.S.-chartered depository institution "
    "perimeter, which includes savings institutions",
    "These are legal-sector bank transactions. They illustrate N in dD = F + N and are not the exclusive "
    "posting cells: a bank purchase from the Federal Reserve or a foreign seller does not post to covered "
    "nonbank deposits",
    "H.8 other securities, non-MBS is the closest H.8 proxy for corporate bonds; it also holds municipal "
    "securities, asset-backed securities, other domestic and foreign debt, and fund and equity holdings",
    "H.8 closed-end residential loans combine first and junior liens; H.8 publishes no first-lien split",
    "H.8 monthly levels are seasonally adjusted averages of Wednesday values; 12-month changes are level "
    "differences and are not adjusted for H.8 breaks such as divestitures to nonbanks or reclassifications",
    "Z.1 total currency and deposits of U.S.-chartered institutions includes interbank liabilities as well as "
    "checkable and time and savings deposits of all holder sectors",
]
BOUNDARIES = [
    "Descriptive composition tables; no estimation, identification, attribution, or causal interpretation",
    "Z.1 rows are calendar-quarter transactions or quarter-end levels; H.8 rows are monthly averages; the "
    "two sources differ in perimeter and clock and are not additive",
    "all_other_assets is the sum of named published asset lines; asset_closure_gap is published rounding only",
]


def _z1(frame: pd.DataFrame, key: str, first: pd.Period, end: pd.Period) -> pd.Series:
    """Integer USD million on the closed window [first, end]; a short, gapped, or non-integer series raises."""
    series = z1_quarterly(frame, key).sort_index()
    if series.index.max() < end:
        raise ValueError(f"{key}: ends {series.index.max()} before the required {end}; refusing to truncate")
    window = series.loc[first:end]
    expected = pd.period_range(first, end, freq="Q")
    missing = expected.difference(window.index)
    if len(missing):
        raise ValueError(f"{key}: missing quarters {[str(q) for q in missing[:5]]}")
    if not window.eq(window.round()).all():
        raise ValueError(f"{key}: Z.1 values must be whole USD million")
    return window.astype("int64")


def _sum_lines(frames: dict[str, pd.DataFrame], measure: str, first: pd.Period, end: pd.Period) -> pd.DataFrame:
    """Each output column summed from its registry lines, USD million."""
    columns = {}
    for line in BANK_Z1_LINES:
        key = f"z1_fu{line.code}" if measure == "transactions" else f"z1_{line.level_prefix.lower()}{line.code}"
        series = _z1(frames[key], key, first, end)
        columns[line.column] = columns.get(line.column, 0) + series
    return pd.DataFrame(columns)


def _codes(render) -> dict[str, list[str]]:
    codes: dict[str, list[str]] = {}
    for line in BANK_Z1_LINES:
        codes.setdefault(line.column, []).append(render(line))
    return codes


def _closure_bound(n_lines: int) -> float:
    return HALF_UNIT * (n_lines + 1)


def _check_closure(gap: pd.Series, n_lines: int, label: str) -> dict:
    bound = _closure_bound(n_lines)
    worst = float(gap.abs().max())
    if worst > bound:
        raise ValueError(f"{label}: closure gap {worst} USD million exceeds the rounding bound {bound}")
    return {"max_abs_usd_million": worst, "bound_usd_million": bound, "n_lines": n_lines}


def _billions(frame: pd.DataFrame) -> pd.DataFrame:
    return frame / 1000.0


def _period_label(year: int, quarters: list[int]) -> str:
    if quarters == [1, 2, 3, 4]:
        return str(year)
    if quarters == [1, 2]:
        return f"{year}H1"
    return f"{year}Q1-Q{quarters[-1]}"


def build_z1_tables(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Quarterly and annual transactions, end-quarter holdings, and closure statistics."""
    first, end = pd.Period(BANK_Z1_FIRST_QUARTER, "Q"), pd.Period(BANK_Z1_END_QUARTER, "Q")
    tx = _sum_lines(frames, "transactions", first, end)
    levels = _sum_lines(frames, "levels", first - 1, end)
    n_asset_lines = sum(1 for line in BANK_Z1_LINES if line.column in ASSET_CATEGORIES)
    closure = {}
    for measure, frame in [("transactions", tx), ("levels", levels)]:
        gap = frame["total_financial_assets"] - frame[ASSET_CATEGORIES].sum(axis=1)
        closure[f"assets_{measure}"] = _check_closure(gap, n_asset_lines, f"S.122.1 assets ({measure})")
        deposit_gap = frame["deposits"] - frame[DEPOSIT_PARTS].sum(axis=1)
        closure[f"deposits_{measure}"] = _check_closure(deposit_gap, len(DEPOSIT_PARTS), f"S.122.1 deposits ({measure})")

    flows = tx[[*ASSET_CATEGORIES, "total_financial_assets", *DEPOSIT_PARTS]].copy()
    flows["asset_closure_gap"] = tx["total_financial_assets"] - tx[ASSET_CATEGORIES].sum(axis=1)
    flows["deposits_level_change"] = levels["deposits"].diff().loc[first:end].astype("int64")
    flows["deposits_transactions"] = tx["deposits"]
    flows["deposits_flow_level_gap"] = flows["deposits_level_change"] - flows["deposits_transactions"]
    flows["nondeposit_liabilities"] = tx["total_liabilities"] - tx["deposits"]
    flows = flows[FLOW_COLUMNS]

    quarterly = _billions(flows)
    quarterly.insert(0, "period", [str(q) for q in flows.index])
    annual_rows = []
    for year, block in flows.groupby(flows.index.year):
        quarters = [int(q.quarter) for q in block.index]
        row = _billions(block.sum().to_frame().T).iloc[0].to_dict()
        annual_rows.append({"period": _period_label(int(year), quarters), "n_quarters": len(quarters), **row})
    annual = pd.DataFrame(annual_rows)

    at_end = levels.loc[end]
    total = int(at_end["total_financial_assets"])
    level_codes = _codes(lambda line: f"{line.level_prefix}{line.code}.Q")
    labels = {c.key: c.label for c in BANK_Z1_COLUMNS}
    rows = [
        {"category": key, "label": labels[key], "role": role, "z1_level_codes": " + ".join(level_codes[key]),
         "level_usd_bn": int(at_end[key]) / 1000.0,
         "share_of_total_financial_assets": int(at_end[key]) / total if role != "memo_liability" else None}
        for key, role in [*((k, "asset_category") for k in ASSET_CATEGORIES), ("total_financial_assets", "total"),
                          *((k, "memo_liability") for k in LIABILITY_COLUMNS)]
    ]
    holdings = pd.DataFrame(rows)
    holdings.insert(0, "quarter", str(end))
    stats = {"closure": closure, "quarterly_sample": {"first": str(first), "last": str(end), "n": int(len(flows))},
             "annual_periods": annual["period"].tolist()}
    return quarterly, annual, holdings, stats


def _h8(frame: pd.DataFrame, key: str, scale_to_bn: float) -> pd.Series:
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if not dates.dt.day.eq(1).all() or dates.duplicated().any():
        raise ValueError(f"{key}: monthly observations must be unique first-of-month dates")
    values = pd.Series(_numeric(frame["value"], key).to_numpy() * scale_to_bn, index=dates.dt.to_period("M"))
    for month in (BANK_H8_BASE_MONTH, BANK_H8_MONTH):
        if pd.Period(month, "M") not in values.index:
            last = values.index.max() if len(values) else None
            raise ValueError(f"{key}: no observation for {month} (last {last}); refusing to substitute or truncate")
    return values


def build_h8_table(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """Base-month and latest-month levels, 12-month change, and hierarchy closure, USD billion."""
    base, month = pd.Period(BANK_H8_BASE_MONTH, "M"), pd.Period(BANK_H8_MONTH, "M")
    level = {}
    for line in BANK_H8_LINES:
        series = _h8(frames[f"h8_{line.key}"], f"h8_{line.key}", line.usd_million_per_unit / 1000.0)
        level[line.key] = {"base": float(series[base]), "month": float(series[month])}
    closure = {}
    for parent in {line.parent for line in BANK_H8_LINES if line.parent}:
        children = [line.key for line in BANK_H8_LINES if line.parent == parent]
        bound = H8_UNIT * (len(children) + 1)
        gaps = {when: level[parent][when] - sum(level[child][when] for child in children) for when in ("base", "month")}
        worst = max(abs(gap) for gap in gaps.values())
        if worst > bound:
            raise ValueError(f"H.8 {parent}: children differ from the published parent by {worst} USD billion")
        closure[parent] = {"children": children, "max_abs_gap_usd_bn": round(worst, 6), "bound_usd_bn": round(bound, 6)}
    rows = []
    for line in BANK_H8_LINES:
        before, after = level[line.key]["base"], level[line.key]["month"]
        rows.append({
            "key": line.key, "h8_table4_line": line.line, "label": line.label, "parent": line.parent,
            "fred_id": line.series_id, f"level_{BANK_H8_BASE_MONTH}_usd_bn": round(before, 4),
            f"level_{BANK_H8_MONTH}_usd_bn": round(after, 4), "change_12m_usd_bn": round(after - before, 4),
            "pct_change_12m": round(100.0 * (after - before) / before, 3),
        })
    return pd.DataFrame(rows), {"closure": dict(sorted(closure.items()))}


def column_metadata() -> dict:
    """Label, measure, source codes, and definition of every output column."""
    codes = _codes(lambda line: line.code)
    base = {c.key: {"label": c.label, "definition": c.definition} for c in BANK_Z1_COLUMNS}
    flow = {
        key: {**base[key], "measure": "transactions, not seasonally adjusted, not annualized",
              "z1_codes": [f"FU{code}.Q" for code in codes[key]]}
        for key in [*ASSET_CATEGORIES, "total_financial_assets", *DEPOSIT_PARTS]
    }
    flow.update({
        "period": {"definition": "Calendar quarter (quarterly) or calendar year; YYYYH1 sums Q1 and Q2"},
        "n_quarters": {"definition": "Quarters summed into the annual row"},
        "asset_closure_gap": {"definition": "total_financial_assets less the sum of the asset categories; "
                                            "published Z.1 rounding only", "measure": "transactions"},
        "deposits_level_change": {"label": "Change in total currency and deposits (thesis deposit outcome)",
                                  "definition": "Quarter-end level change of FL764100005.Q (FRED BOGZ1FL764100005Q); "
                                                "includes series breaks and reclassifications",
                                  "measure": "level change", "z1_codes": ["FL764100005.Q"]},
        "deposits_transactions": {**base["deposits"], "measure": "transactions", "z1_codes": ["FU764100005.Q"]},
        "deposits_flow_level_gap": {"definition": "deposits_level_change less deposits_transactions: series breaks "
                                                  "and reclassifications (deposits carry no market valuation)"},
        "nondeposit_liabilities": {"label": "Nondeposit liabilities",
                                   "definition": "Total liabilities less total currency and deposits",
                                   "measure": "transactions", "z1_codes": ["FU764190005.Q", "minus FU764100005.Q"]},
    })
    level_codes = _codes(lambda line: f"{line.level_prefix}{line.code}.Q")
    holdings = {key: {**base[key], "measure": f"level at end of {BANK_Z1_END_QUARTER}", "z1_codes": level_codes[key]}
                for key in base}
    holdings["share_of_total_financial_assets"] = {
        "definition": "Level divided by total financial assets; empty for memo liability rows"}
    h8 = {line.key: {"label": line.label, "fred_id": line.series_id, "h8_table4_line": line.line,
                     "parent": line.parent} for line in BANK_H8_LINES}
    return {"z1_flows": flow, "z1_holdings": holdings, "h8": h8}


def _z1_vintage(records: dict[str, dict]) -> dict:
    """One Z.1 release package must serve every Z.1 input."""
    seen = {(r["source_metadata"].get("release_date"), r["source_metadata"].get("package_sha256"), r["vintage"])
            for key, r in records.items() if key.startswith("z1_")}
    if len(seen) != 1 or None in next(iter(seen)):
        raise ValueError(f"Z.1 inputs must come from one release package; found {sorted(map(str, seen))}")
    release_date, package_sha256, vintage = next(iter(seen))
    return {"release_date": release_date, "package_sha256": package_sha256, "vintage": vintage}


def _coverage(frames: dict[str, pd.DataFrame]) -> dict:
    return {key: {"first": frame["date"].iloc[0], "last": frame["date"].iloc[-1], "n": int(len(frame))}
            for key, frame in frames.items()}


def write_bank_composition_export(*, root: Path | str, inputs_manifest_sha256: str) -> dict:
    """Bind the composition tables to a clean commit and the pinned fiscus manifest."""
    paths = project_paths(root)
    root = paths.root
    producer_commit = require_clean_commit(root)
    manifest_path = root / BANK_COMPOSITION_REGISTRY.manifest
    manifest_raw, manifest_record = read_pinned_input(root, manifest_path, inputs_manifest_sha256, "inputs_manifest")
    manifest = json.loads(manifest_raw)
    frames, input_records = load_fiscus_inputs(root, manifest, BANK_COMPOSITION_REGISTRY)
    entries = manifest["inputs"]
    z1_vintage = _z1_vintage(input_records)

    quarterly, annual, holdings, z1_stats = build_z1_tables(frames)
    h8, h8_stats = build_h8_table(frames)
    payloads = {
        role: frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        for role, frame in [("quarterly", quarterly), ("annual", annual), ("holdings", holdings), ("h8", h8)]
    }
    output_paths = {role: paths.processed / name for role, name in OUTPUT_FILES.items()}
    protected = {manifest_path.resolve()} | {(root / r["file"]).resolve() for r in input_records.values()}
    if {path.resolve() for path in output_paths.values()} & protected:
        raise ValueError("Output paths cannot overwrite inputs")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "producer_commit": producer_commit,
        "units": "USD billion",
        "labels": LABELS,
        "boundaries": BOUNDARIES,
        "z1": {"table": "S.122.1 U.S.-chartered depository institutions (formerly F.111 and L.111)",
               "perimeter": "U.S.-chartered commercial banks and savings institutions, including IBFs; credit "
                            "unions are a separate Z.1 sector",
               "source_url": next(r["source_url"] for k, r in input_records.items() if k.startswith("z1_")),
               **z1_vintage, "first_quarter": BANK_Z1_FIRST_QUARTER, "end_quarter": BANK_Z1_END_QUARTER},
        "h8": {"table": "H.8 Table 4: domestically chartered commercial banks, seasonally adjusted, monthly "
                        "averages of Wednesday levels",
               "perimeter_choice": "domestically chartered commercial banks (available; all commercial banks not used)",
               "base_month": BANK_H8_BASE_MONTH, "month": BANK_H8_MONTH,
               "fred_vintages": {r["series_id"]: r["vintage"] for k, r in entries.items() if k.startswith("h8_")}},
        "inputs": {"inputs_manifest": {**manifest_record, "fiscus": manifest.get("fiscus", {}),
                                       "acquired_at_utc": manifest.get("acquired_at_utc")},
                   "fiscus_inputs": input_records},
        "outputs": {role: {"path": str(output_paths[role].relative_to(root)), "sha256": _sha256(data)}
                    for role, data in payloads.items()},
        "columns": column_metadata(),
        "closure": {"z1": z1_stats["closure"], "h8": h8_stats["closure"]},
        "samples": {"z1_quarterly": z1_stats["quarterly_sample"], "z1_annual_periods": z1_stats["annual_periods"]},
        "coverage": _coverage(frames),
    }
    text = json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    for role, data in payloads.items():
        output_paths[role].parent.mkdir(parents=True, exist_ok=True)
        output_paths[role].write_bytes(data)
    output_paths["receipt"].write_text(text, encoding="utf-8")
    return receipt
