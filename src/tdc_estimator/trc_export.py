"""Hash-pinned writer for the opt-in Treasury component of reserves (TRC) export."""

from __future__ import annotations

from pathlib import Path
import hashlib
import io
import json

import pandas as pd

from .catalog import TRC_REGISTRY, FiscusRegistry
from .config import project_paths
from .mmf_rrp import MMF_ON_RRP_ROUTE_LIMITATION
from .settlement_routes import route_registry_frame
from .tier2_regression_series import read_pinned_input, require_clean_commit
from .trc_reserve_component import (
    LEGS_SOURCE_KEY,
    QUARTERLY_SOURCE_KEY,
    TGA_SOURCE_TRANSITION,
    TrcInputs,
    build_trc_components,
    build_trc_series,
)

TRC_SCHEMA_VERSION = "trc_quarterly_series_v1"
MANIFEST_SCHEMA_VERSION = TRC_REGISTRY.schema_version
FISCUS_INPUT_DIR = TRC_REGISTRY.input_dir
INPUTS_MANIFEST = TRC_REGISTRY.manifest
LEGS_FILE = "tdc_regression_legs_v1.csv"
QUARTERLY_FILE = "quarterly_inputs.csv"
TRC_OUTPUT_FILES = {
    "route_registry": "trc_route_registry_v1.csv",
    "components": "trc_quarterly_components_v1.csv",
    "series": "trc_quarterly_series_v1.csv",
    "receipt": "trc_quarterly_series_v1_receipt.json",
}
MANIFEST_IDENTITY_FIELDS = [
    "dataset_id", "argv", "file", "sha256", "byte_count", "cache_key", "retrieved_at_utc",
    "vintage", "source_url", "source_metadata", "row_count", "data_coverage",
]
BOUNDARIES = [
    "Additive descriptive accounting proxy; frozen TDC artifacts are read under pinned hashes and never rewritten",
    "No estimation, identification, or causal interpretation",
    "Headline perimeter is aggregate reserve balances; reserves plus ON RRP, H.3 total reserves, and US-chartered reserves are memo rows only",
    "Preferred row is core plus the proportional MMF/ON RRP route and carries partial_one_sided_route_coverage",
    MMF_ON_RRP_ROUTE_LIMITATION,
    "GSE ON RRP and foreign-official direct-account corrections are nondefault bounds; custody changes identify ownership, not the settling account, and never form a point value",
    "Custody holdings report zero before mid-2007; those leading zeros are treated as non-reporting, so the foreign-official bound starts when custody is first reported",
    "TT&L balances are commercial-bank claims and stay out of the TRC cash leg; SFP enters once; Z.1 Treasury operating cash is not used in the TRC cash leg",
    "The non-Treasury residual is defined as Z.1 reserve change less TRC and closes by construction",
    "The measured TDC-TRC wedge is a reconciliation of producer legs, not an identity; u carries source and clock differences",
    "Change in TT&L is unavailable before 2006 because machine-readable DTS Table I begins 2005-10-03",
    "All four 2002 TRC observations are unavailable: no H.4.1 TGA level precedes 2002-12-18",
    "Fed Treasury transactions are Z.1 FU713061103 and the SOMA coupon term is the existing proxy; neither is a security-level cash ledger",
    "Treasury cash holdings, coin, currency, gold and SDR certificate entries remain in the non-Treasury remainder",
    "H.3 total reserves include vault cash used to satisfy reserve requirements before April 2020",
    "ON RRP and foreign-official remainder cells mix H.4.1 last-Wednesday factor changes with calendar-quarter route allocations",
    "The all-H.4.1 clock diagnostic moves only the reserve and Treasury Fed-deposit levels to last Wednesdays; Fed transaction, coupon, remittance, and MMF legs stay calendar-quarter flows",
]
CLOCKS = {
    "reserve_outcome": "Z.1 FU713113003 calendar-quarter transactions",
    "tga": {
        "2003Q1-2005Q4": "H.4.1 WDTGAL last Wednesday on or before quarter end, both endpoints",
        "2006Q1-2025Q4": "DTS Table I final business day close, both endpoints",
    },
    "sfp": "DTS Table I final business day close; structural zero before the program and after the line is discontinued at a zero balance",
    "ttl": "DTS Table I final business day close of Tax and Loan Note Accounts and their Short-Term Cash Investments successor",
    "fed_legs": "Z.1 and existing producer calendar-quarter flows from the frozen regression legs",
    "mmf_route": "calendar-quarter sum of fund-month route adjustments from quarterly_inputs",
    "h41_factors": "H.4.1 last Wednesday on or before quarter end",
    "h3_memo": "H.3 monthly average, final month of the quarter",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_fiscus_inputs(
    root: Path, manifest: dict, registry: FiscusRegistry = TRC_REGISTRY,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    """Read every input of ``registry`` named by the manifest and verify its bytes."""
    if manifest.get("schema_version") != registry.schema_version:
        raise ValueError("inputs manifest: unexpected schema_version")
    entries = manifest.get("inputs", {})
    expected = {spec.key: spec for spec in registry.inputs}
    if set(entries) != set(expected):
        raise ValueError(f"inputs manifest: keys differ from the registry {sorted(set(entries) ^ set(expected))}")
    frames, records = {}, {}
    input_dir = (root / registry.input_dir).resolve()
    for key, spec in expected.items():
        entry = entries[key]
        missing = [field for field in MANIFEST_IDENTITY_FIELDS if field not in entry]
        if missing:
            raise ValueError(f"inputs manifest {key}: missing fields {missing}")
        if entry["dataset_id"] != spec.dataset_id or tuple(entry["argv"]) != spec.argv:
            raise ValueError(f"inputs manifest {key}: request differs from the registry")
        path = (root / entry["file"]).resolve()
        if path.parent != input_dir:
            raise ValueError(f"inputs manifest {key}: file must sit in {registry.input_dir}")
        raw, _ = read_pinned_input(root, path, entry["sha256"], key)
        if len(raw) != entry["byte_count"]:
            raise ValueError(f"{key}: byte count differs from the manifest")
        frames[key] = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
        records[key] = {field: entry[field] for field in MANIFEST_IDENTITY_FIELDS}
    return frames, records


def write_trc_export(
    *, root: Path | str, legs_sha256: str, quarterly_sha256: str, inputs_manifest_sha256: str,
) -> dict:
    """Bind the TRC export to a clean commit, pinned frozen inputs, and a pinned fiscus manifest."""
    paths = project_paths(root)
    root = paths.root
    producer_commit = require_clean_commit(root)
    legs_path, quarterly_path = paths.processed / LEGS_FILE, paths.processed / QUARTERLY_FILE
    manifest_path = root / INPUTS_MANIFEST
    legs_raw, legs_record = read_pinned_input(root, legs_path, legs_sha256, LEGS_SOURCE_KEY)
    quarterly_raw, quarterly_record = read_pinned_input(root, quarterly_path, quarterly_sha256, QUARTERLY_SOURCE_KEY)
    manifest_raw, manifest_record = read_pinned_input(root, manifest_path, inputs_manifest_sha256, "inputs_manifest")
    manifest = json.loads(manifest_raw)
    frames, input_records = load_fiscus_inputs(root, manifest)

    output_paths = {role: paths.processed / name for role, name in TRC_OUTPUT_FILES.items()}
    inputs_on_disk = {legs_path.resolve(), quarterly_path.resolve(), manifest_path.resolve()} | {
        (root / record["file"]).resolve() for record in input_records.values()
    }
    if {path.resolve() for path in output_paths.values()} & inputs_on_disk:
        raise ValueError("Output paths cannot overwrite inputs")

    components, stats = build_trc_components(TrcInputs(
        legs=pd.read_csv(io.BytesIO(legs_raw)), quarterly=pd.read_csv(io.BytesIO(quarterly_raw)), sources=frames,
    ))
    source_hashes = {key: record["sha256"] for key, record in input_records.items()}
    source_hashes[LEGS_SOURCE_KEY] = legs_record["sha256"]
    source_hashes[QUARTERLY_SOURCE_KEY] = quarterly_record["sha256"]
    series = build_trc_series(components, source_hashes)
    payloads = {
        "route_registry": route_registry_frame().to_csv(index=False, lineterminator="\n").encode("utf-8"),
        "components": components.to_csv(index=False, lineterminator="\n").encode("utf-8"),
        "series": series.to_csv(index=False, lineterminator="\n").encode("utf-8"),
    }
    available = series.loc[~series["measurement_status"].str.startswith("unavailable")]
    receipt = {
        "schema_version": TRC_SCHEMA_VERSION,
        "producer_commit": producer_commit,
        "units": "USD million",
        "sample": {"shell_start": components["quarter"].iloc[0], "shell_end": components["quarter"].iloc[-1],
                   "observed_trc_start": components.loc[components["trc_preferred"].notna(), "quarter"].iloc[0],
                   "n_quarters": int(components["quarter"].nunique())},
        "inputs": {
            LEGS_SOURCE_KEY: legs_record, QUARTERLY_SOURCE_KEY: quarterly_record,
            "inputs_manifest": {**manifest_record, "fiscus": manifest.get("fiscus", {}),
                                "acquired_at_utc": manifest.get("acquired_at_utc")},
            "fiscus_inputs": input_records,
        },
        "outputs": {role: {"path": str(output_paths[role].relative_to(root)), "sha256": _sha256(data)}
                    for role, data in payloads.items()},
        "clocks": CLOCKS,
        "tga_source_transition": {
            "first_dts_change_quarter": str(TGA_SOURCE_TRANSITION),
            "first_dts_level_quarter": stats["dts_first_quarter"],
            "rule": "Changes before the transition use H.4.1 levels at both endpoints; changes from it use DTS levels at both endpoints",
        },
        "series_availability": {
            series_id: {"first": group["quarter"].min(), "last": group["quarter"].max(), "n": int(len(group))}
            for series_id, group in available.groupby("series_id")
        },
        "cross_checks": stats,
        "boundaries": BOUNDARIES,
    }
    for path in output_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    for role, data in payloads.items():
        output_paths[role].write_bytes(data)
    output_paths["receipt"].write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt
