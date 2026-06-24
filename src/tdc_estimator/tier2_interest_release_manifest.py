from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

import pandas as pd

from .utils import write_json


MANIFEST_FILENAME = "support__tier2_component_release_manifest.json"
MANIFEST_SCHEMA_VERSION = "tier2_component_support_release_v1"
DEFAULT_RELEASE_START = "2022-03-31"
DEFAULT_RELEASE_END = "2025-12-31"

COMPONENT_SUPPORT_COLUMNS = {
    "bank": "bank_tier2_component_interest_proxy",
    "row": "row_tier2_component_interest_proxy",
    "credit_union": "credit_union_tier2_component_interest_proxy",
}
COMPONENT_SUPPORT_FILENAMES = {
    sector: f"support__{column}.csv" for sector, column in COMPONENT_SUPPORT_COLUMNS.items()
}
COMPONENT_SUPPORT_KEYS = set(COMPONENT_SUPPORT_COLUMNS.values())


def default_component_release_dates(
    *,
    start: str | pd.Timestamp = DEFAULT_RELEASE_START,
    end: str | pd.Timestamp = DEFAULT_RELEASE_END,
) -> list[str]:
    dates = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="QE-DEC")
    return [date.date().isoformat() for date in dates]


def file_sha256(path: Path | str) -> str:
    target = Path(path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_tier2_component_release_manifest(
    *,
    support_paths: Mapping[str, Path | str],
    candidate_path: Path | str,
    source_constraints_path: Path | str,
    expected_dates: list[str] | None = None,
) -> dict[str, object]:
    dates = expected_dates or default_component_release_dates()
    outputs: dict[str, dict[str, object]] = {}
    for sector, path in support_paths.items():
        support_path = Path(path)
        outputs[sector] = {
            "filename": support_path.name,
            "series_key": COMPONENT_SUPPORT_COLUMNS[sector],
            "sha256": file_sha256(support_path),
        }
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "release_id": f"tier2_component_support_{dates[0]}_{dates[-1]}",
        "expected_dates": dates,
        "required_sectors": sorted(COMPONENT_SUPPORT_COLUMNS),
        "inputs": {
            "candidate": {
                "filename": Path(candidate_path).name,
                "sha256": file_sha256(candidate_path),
            },
            "source_constraints": {
                "filename": Path(source_constraints_path).name,
                "sha256": file_sha256(source_constraints_path),
            },
        },
        "outputs": outputs,
    }


def write_tier2_component_release_manifest(
    *,
    manifest_path: Path | str,
    support_paths: Mapping[str, Path | str],
    candidate_path: Path | str,
    source_constraints_path: Path | str,
    expected_dates: list[str] | None = None,
) -> Path:
    manifest = build_tier2_component_release_manifest(
        support_paths=support_paths,
        candidate_path=candidate_path,
        source_constraints_path=source_constraints_path,
        expected_dates=expected_dates,
    )
    out = Path(manifest_path)
    write_json(out, manifest)
    return out


def read_tier2_component_release_manifest(path: Path | str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_support_frame_dates_and_values(
    frame: pd.DataFrame,
    *,
    date_column: str,
    value_column: str,
    expected_dates: list[str],
    label: str,
) -> None:
    if date_column not in frame.columns or value_column not in frame.columns:
        raise ValueError(f"{label} is missing required columns: {date_column}, {value_column}")
    work = frame.copy()
    work[date_column] = pd.to_datetime(work[date_column], errors="coerce").dt.date.astype(str)
    actual_dates = sorted(work[date_column].dropna().astype(str).tolist())
    if actual_dates != expected_dates:
        raise ValueError(f"{label} date window mismatch: expected {expected_dates}, got {actual_dates}")
    if work[date_column].duplicated().any():
        raise ValueError(f"{label} has duplicate dates")
    values = pd.to_numeric(work[value_column], errors="coerce")
    if values.isna().any() or (~values.apply(lambda value: pd.notna(value) and value > 0.0)).any():
        raise ValueError(f"{label} contains non-finite or non-positive support values")


def validate_tier2_component_release_manifest(
    *,
    raw_dir: Path | str,
    manifest_path: Path | str | None = None,
    expected_dates: list[str] | None = None,
) -> dict[str, object]:
    raw = Path(raw_dir)
    manifest_file = Path(manifest_path) if manifest_path is not None else raw / MANIFEST_FILENAME
    if not manifest_file.exists():
        raise FileNotFoundError(f"Missing certified Tier 2 component support manifest: {manifest_file}")
    manifest = read_tier2_component_release_manifest(manifest_file)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"Unsupported Tier 2 component support manifest schema: {manifest.get('schema_version')}")
    expected = expected_dates or default_component_release_dates()
    manifest_dates = list(manifest.get("expected_dates") or [])
    if manifest_dates != expected:
        raise ValueError(f"Tier 2 component support manifest date window mismatch: {manifest_dates}")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Tier 2 component support manifest missing outputs")
    for sector, value_column in COMPONENT_SUPPORT_COLUMNS.items():
        if sector not in outputs or not isinstance(outputs[sector], dict):
            raise ValueError(f"Tier 2 component support manifest missing output for {sector}")
        filename = str(outputs[sector].get("filename") or "")
        if filename != COMPONENT_SUPPORT_FILENAMES[sector]:
            raise ValueError(f"Tier 2 component support manifest output filename mismatch for {sector}: {filename}")
        path = raw / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing certified Tier 2 component support file: {path}")
        expected_hash = str(outputs[sector].get("sha256") or "")
        actual_hash = file_sha256(path)
        if actual_hash != expected_hash:
            raise ValueError(f"Tier 2 component support hash mismatch for {filename}: expected {expected_hash}, got {actual_hash}")
        validate_support_frame_dates_and_values(
            pd.read_csv(path),
            date_column="date",
            value_column=value_column,
            expected_dates=expected,
            label=filename,
        )
    return manifest
