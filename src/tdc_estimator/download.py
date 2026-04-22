from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

from .catalog import FredSeries, TreasuryDataset
from .config import FRED_API_BASE, FRED_GRAPH_CSV_BASE, TREASURY_API_BASE, USER_AGENT
from .utils import ensure_dir, project_relative_path, utc_now_iso, write_json


def _urlopen_text(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def fred_csv_url(series_id: str, start_date: str | None = None, end_date: str | None = None) -> str:
    params: dict[str, str] = {"id": series_id}
    if start_date:
        params["cosd"] = start_date
    if end_date:
        params["coed"] = end_date
    return f"{FRED_GRAPH_CSV_BASE}?{urllib.parse.urlencode(params)}"


def fred_api_url(series_id: str, api_key: str, start_date: str | None = None, end_date: str | None = None) -> str:
    params: dict[str, str] = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    if start_date:
        params["observation_start"] = start_date
    if end_date:
        params["observation_end"] = end_date
    return f"{FRED_API_BASE}?{urllib.parse.urlencode(params)}"


def download_fred_series(
    spec: FredSeries,
    raw_dir: Path | str,
    *,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    raw_path = ensure_dir(raw_dir) / f"fred__{spec.key}.csv"
    if api_key:
        url = fred_api_url(spec.series_id, api_key=api_key, start_date=start_date, end_date=end_date)
        text = _urlopen_text(url)
        payload = json.loads(text)
        rows = [{"date": item["date"], "value": item["value"]} for item in payload.get("observations", [])]
        pd.DataFrame(rows).to_csv(raw_path, index=False)
        mode = "fred_api_json"
    else:
        url = fred_csv_url(spec.series_id, start_date=start_date, end_date=end_date)
        text = _urlopen_text(url)
        raw_path.write_text(text, encoding="utf-8")
        mode = "fred_graph_csv"

    return {
        "key": spec.key,
        "series_id": spec.series_id,
        "path": project_relative_path(raw_path, project_root),
        "url": url,
        "downloaded_at_utc": utc_now_iso(),
        "mode": mode,
    }


def _build_treasury_url(endpoint: str, params: dict[str, str] | None = None) -> str:
    params = dict(params or {})
    if "page[size]" not in params:
        params["page[size]"] = "10000"
    return f"{TREASURY_API_BASE}{endpoint}?{urllib.parse.urlencode(params)}"


def download_treasury_dataset(
    spec: TreasuryDataset,
    raw_dir: Path | str,
    *,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    raw_dir = ensure_dir(raw_dir)
    rows: list[dict[str, Any]] = []
    page_count = 0
    params = dict(spec.params or {})
    if "page[size]" not in params:
        params["page[size]"] = "10000"

    first_url = _build_treasury_url(spec.endpoint, params)
    text = _urlopen_text(first_url)
    payload = json.loads(text)
    rows.extend(payload.get("data", []))
    page_count = 1

    meta = payload.get("meta", {}) or {}
    total_pages = int(meta.get("total-pages") or 1)

    if total_pages > 1:
        for page_number in range(2, total_pages + 1):
            page_params = dict(params)
            page_params["page[number]"] = str(page_number)
            text = _urlopen_text(_build_treasury_url(spec.endpoint, page_params))
            payload = json.loads(text)
            rows.extend(payload.get("data", []))
            page_count += 1
    else:
        next_url = payload.get("links", {}).get("next")
        while next_url:
            page_count += 1
            if next_url.startswith("http"):
                url = next_url
            elif next_url.startswith("?") or next_url.startswith("&"):
                joiner = "" if next_url.startswith("?") else "?"
                url = f"{TREASURY_API_BASE}{spec.endpoint}{joiner}{next_url.lstrip('?&')}"
            else:
                url = f"{TREASURY_API_BASE}{next_url}"
            text = _urlopen_text(url)
            payload = json.loads(text)
            rows.extend(payload.get("data", []))
            next_url = payload.get("links", {}).get("next")

    raw_path = raw_dir / f"treasury__{spec.key}.csv"
    pd.DataFrame(rows).to_csv(raw_path, index=False)

    return {
        "key": spec.key,
        "endpoint": spec.endpoint,
        "path": project_relative_path(raw_path, project_root),
        "downloaded_at_utc": utc_now_iso(),
        "pages": page_count,
        "rows": len(rows),
    }


def download_fred_bundle(
    specs: list[FredSeries],
    raw_dir: Path | str,
    *,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    continue_on_error: bool = True,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for spec in specs:
        try:
            results.append(
                download_fred_series(
                    spec,
                    raw_dir,
                    api_key=api_key,
                    start_date=start_date,
                    end_date=end_date,
                    project_root=project_root,
                )
            )
        except Exception as exc:
            entry = {"key": spec.key, "series_id": spec.series_id, "error": str(exc)}
            errors.append(entry)
            if not continue_on_error:
                raise

    manifest = {
        "kind": "fred_download_manifest",
        "downloaded_at_utc": utc_now_iso(),
        "results": results,
        "errors": errors,
    }
    write_json(Path(raw_dir) / "manifest_fred.json", manifest)
    return manifest


def download_treasury_bundle(
    specs: list[TreasuryDataset],
    raw_dir: Path | str,
    *,
    continue_on_error: bool = True,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for spec in specs:
        try:
            results.append(download_treasury_dataset(spec, raw_dir, project_root=project_root))
        except Exception as exc:
            entry = {"key": spec.key, "endpoint": spec.endpoint, "error": str(exc)}
            errors.append(entry)
            if not continue_on_error:
                raise

    manifest = {
        "kind": "treasury_download_manifest",
        "downloaded_at_utc": utc_now_iso(),
        "results": results,
        "errors": errors,
    }
    write_json(Path(raw_dir) / "manifest_treasury.json", manifest)
    return manifest
