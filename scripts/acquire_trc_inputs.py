"""Acquire the TRC export or H.4.1 ledger inputs through fiscus into caller-owned files.

Run from the repository root with the package importable, for example

    PYTHONPATH=src python scripts/acquire_trc_inputs.py [--registry trc|h41-ledger] [--fiscus-project ../fiscus] [--refresh]

Every input comes from one registry in `tdc_estimator.catalog.FISCUS_REGISTRIES`
(`trc` by default) through `uv run --project <fiscus> fiscus ...`. Payloads are
exported with `fiscus cache export` into the registry's input directory,
verified against the fiscus artifact SHA-256, and described in the registry's
manifest together with `fiscus provenance`. FRED requests use the keyless public
route (FRED_API_KEY is removed from the child environment) so the request
identity does not depend on a private credential.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from tdc_estimator.catalog import FISCUS_REGISTRIES

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr.strip()}")
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", choices=sorted(FISCUS_REGISTRIES), default="trc", help="input registry to acquire")
    parser.add_argument("--fiscus-project", default="../fiscus", help="fiscus checkout, relative to the repository root")
    parser.add_argument("--refresh", action="store_true", help="bypass the fiscus latest pointer and re-read sources")
    args = parser.parse_args(argv)
    if Path(args.fiscus_project).is_absolute():
        raise SystemExit("--fiscus-project must be relative to the repository root")
    env = {key: value for key, value in os.environ.items() if key != "FRED_API_KEY"}
    fiscus = ["uv", "run", "--quiet", "--project", args.fiscus_project, "fiscus"]
    registry = FISCUS_REGISTRIES[args.registry]
    out_dir = ROOT / registry.input_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = {}
    for spec in registry.inputs:
        response = json.loads(run([*fiscus, *spec.argv, *(["--refresh"] if args.refresh else [])], cwd=ROOT, env=env))
        if response["dataset"]["id"] != spec.dataset_id:
            raise SystemExit(f"{spec.key}: fiscus returned dataset {response['dataset']['id']}")
        artifact = response["artifact"]
        relative = registry.input_dir / f"{spec.key}.csv"
        run([*fiscus, "cache", "export", artifact["cache_key"], "--out", str(relative)], cwd=ROOT, env=env)
        payload = (ROOT / relative).read_bytes()
        if hashlib.sha256(payload).hexdigest() != artifact["sha256"] or len(payload) != artifact["byte_count"]:
            raise SystemExit(f"{spec.key}: exported bytes differ from the fiscus artifact")
        provenance = json.loads(run([*fiscus, "provenance", artifact["cache_key"]], cwd=ROOT, env=env))
        manifest = provenance["manifest"]
        if not provenance.get("sha256_verified") or manifest["sha256"] != artifact["sha256"]:
            raise SystemExit(f"{spec.key}: fiscus provenance does not verify the artifact")
        inputs[spec.key] = {
            "dataset_id": spec.dataset_id,
            "argv": list(spec.argv),
            "request_params": manifest.get("params", {}),
            "file": relative.as_posix(),
            "sha256": artifact["sha256"],
            "byte_count": artifact["byte_count"],
            "cache_key": artifact["cache_key"],
            "cache_hit": response.get("cache_hit"),
            "retrieved_at_utc": manifest["retrieved_at_utc"],
            "vintage": manifest["vintage"],
            "source_url": manifest["source_url"],
            "source_metadata": manifest.get("source_metadata", {}),
            "row_count": manifest.get("row_count"),
            "data_coverage": manifest.get("data_coverage"),
            "catalog_verified_on": manifest.get("catalog_verified_on"),
            "series_id": spec.series_id,
            "units": spec.units,
            "usd_million_per_unit": spec.usd_million_per_unit,
            "clock": spec.clock,
        }
        print(f"{spec.key}: {artifact['sha256']} ({artifact['byte_count']} bytes)", file=sys.stderr)

    version = run(["uv", "run", "--quiet", "--project", args.fiscus_project, "python", "-c",
                   "import importlib.metadata as m; print(m.version('fiscus'))"], cwd=ROOT, env=env).strip()
    commit = subprocess.run(["git", "-C", args.fiscus_project, "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", args.fiscus_project, "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True)
    document = {
        "schema_version": registry.schema_version,
        "acquired_at_utc": datetime.now(UTC).isoformat(),
        "fiscus": {
            "version": version,
            "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
            "git_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
            "refresh": args.refresh,
            "fred_route": "keyless_public_graph_csv",
        },
        "inputs": inputs,
    }
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if "api_key" in text.lower():
        raise SystemExit("manifest would record a credential-bearing URL")
    (ROOT / registry.manifest).write_text(text, encoding="utf-8")
    print(f"{registry.manifest}: {hashlib.sha256(text.encode('utf-8')).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
