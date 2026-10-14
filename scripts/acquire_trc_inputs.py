"""Acquire the inputs of one fiscus registry through fiscus into caller-owned files.

Run from the repository root with the package importable, for example

    PYTHONPATH=src python scripts/acquire_trc_inputs.py [--registry trc|h41-ledger|weekly-trc|bank-composition] [--fiscus-project ../fiscus] [--refresh]
        [--root DATA_ROOT --vintage NAME]

Every input comes from one registry in `tdc_estimator.catalog.FISCUS_REGISTRIES`
(`trc` by default) through `uv run --project <fiscus> fiscus ...`. Payloads are
exported with `fiscus cache export` into the registry's input directory,
verified against the fiscus artifact SHA-256, and described in the registry's
manifest together with `fiscus provenance`. FRED requests use the keyless public
route (FRED_API_KEY is removed from the child environment) so the request
identity does not depend on a private credential.

``--vintage`` selects the request windows of a measurement vintage and ``--root``
the data tree that receives its inputs and manifest (the repository root by
default); fiscus itself always runs from the repository root.
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

from tdc_estimator.catalog import (
    DEFAULT_VINTAGE, FISCUS_REGISTRIES, MEASUREMENT_VINTAGES, WEEKLY_TRC_OVERLAY, fiscus_registries,
)

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr.strip()}"
        )
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--registry",
        choices=sorted(FISCUS_REGISTRIES),
        default="trc",
        help="input registry to acquire",
    )
    parser.add_argument(
        "--fiscus-project",
        default="../fiscus",
        help="fiscus checkout, relative to the repository root",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="bypass the fiscus latest pointer and re-read sources",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="data tree that receives the inputs and manifest, relative to the repository root or absolute",
    )
    parser.add_argument(
        "--vintage",
        choices=sorted(MEASUREMENT_VINTAGES),
        default=DEFAULT_VINTAGE.name,
        help="measurement vintage whose endpoint closes the request windows",
    )
    parser.add_argument("--snapshot-worker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.data_root = (ROOT / args.root).resolve()
    if Path(args.fiscus_project).is_absolute():
        raise SystemExit("--fiscus-project must be relative to the repository root")
    env = {key: value for key, value in os.environ.items() if key != "FRED_API_KEY"}
    if args.registry == "weekly-trc":
        env["FISCUS_EXTRA_CATALOG"] = str(WEEKLY_TRC_OVERLAY)
    if args.snapshot_worker:
        return acquire_snapshots(args)
    fiscus = ["uv", "run", "--quiet", "--project", args.fiscus_project, "fiscus"]
    registry = fiscus_registries(MEASUREMENT_VINTAGES[args.vintage])[args.registry]
    out_dir = args.data_root / registry.input_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = {}
    for spec in registry.inputs:
        discovery = json.loads(
            run(
                [*fiscus, "find-series", spec.dataset_id, "--limit", "20"],
                cwd=ROOT,
                env=env,
            )
        )
        if spec.dataset_id not in {
            item["id"] for item in discovery["results"]
        } and not spec.dataset_id.startswith(("fred.", "z1.")):
            raise SystemExit(f"{spec.key}: dataset was not discovered by fiscus")
        if spec.snapshot_window:
            response = json.loads(
                run(
                    [
                        "uv",
                        "run",
                        "--quiet",
                        "--project",
                        args.fiscus_project,
                        "--with-editable",
                        ".",
                        "python",
                        "scripts/acquire_trc_inputs.py",
                        "--registry",
                        args.registry,
                        "--snapshot-worker",
                        spec.key,
                        "--root",
                        str(args.data_root),
                        "--vintage",
                        args.vintage,
                        *(["--refresh"] if args.refresh else []),
                    ],
                    cwd=ROOT,
                    env=env,
                )
            )
            inputs[spec.key] = response
            print(
                f"{spec.key}: {response['sha256']} ({response['byte_count']} bytes)",
                file=sys.stderr,
            )
            continue
        response = json.loads(
            run(
                [*fiscus, *spec.argv, *(["--refresh"] if args.refresh else [])],
                cwd=ROOT,
                env=env,
            )
        )
        if response["dataset"]["id"] != spec.dataset_id:
            raise SystemExit(
                f"{spec.key}: fiscus returned dataset {response['dataset']['id']}"
            )
        artifact = response["artifact"]
        relative = registry.input_dir / f"{spec.key}.csv"
        run(
            [*fiscus, "cache", "export", artifact["cache_key"], "--out", str(args.data_root / relative)],
            cwd=ROOT,
            env=env,
        )
        payload = (args.data_root / relative).read_bytes()
        if (
            hashlib.sha256(payload).hexdigest() != artifact["sha256"]
            or len(payload) != artifact["byte_count"]
        ):
            raise SystemExit(
                f"{spec.key}: exported bytes differ from the fiscus artifact"
            )
        provenance = json.loads(
            run([*fiscus, "provenance", artifact["cache_key"]], cwd=ROOT, env=env)
        )
        manifest = provenance["manifest"]
        if (
            not provenance.get("sha256_verified")
            or manifest["sha256"] != artifact["sha256"]
        ):
            raise SystemExit(
                f"{spec.key}: fiscus provenance does not verify the artifact"
            )
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
        print(
            f"{spec.key}: {artifact['sha256']} ({artifact['byte_count']} bytes)",
            file=sys.stderr,
        )

    version = run(
        [
            "uv",
            "run",
            "--quiet",
            "--project",
            args.fiscus_project,
            "python",
            "-c",
            "import importlib.metadata as m; print(m.version('fiscus'))",
        ],
        cwd=ROOT,
        env=env,
    ).strip()
    commit = subprocess.run(
        ["git", "-C", args.fiscus_project, "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    dirty = subprocess.run(
        ["git", "-C", args.fiscus_project, "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
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
    (args.data_root / registry.manifest).write_text(text, encoding="utf-8")
    print(f"{registry.manifest}: {hashlib.sha256(text.encode('utf-8')).hexdigest()}")
    return 0


def acquire_snapshots(args) -> int:
    """Consolidate weekly fiscus exports; retain each original cache identity, including empty snapshots."""
    import csv
    import tempfile
    import pandas as pd
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date, timedelta
    from fiscus.service import FiscusService
    from fiscus.executors.soma import ASOF_DATES_URL, SOMA_POLICY
    from tdc_estimator.weekly_trc import snapshot_date_mapping

    # Use the existing fiscus executor's source/request policy for discovery.
    with FiscusService() as service:
        response = service.soma.requester.get(ASOF_DATES_URL, policy=SOMA_POLICY)
        available = response.json().get("soma", {}).get("asOfDates")
        if not isinstance(available, list) or not available:
            raise ValueError("SOMA: empty or malformed as-of date list")
        asof_list_record = {
            "source_url": ASOF_DATES_URL,
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "retrieved_at_utc": datetime.now(UTC).isoformat(),
        }

    registry = fiscus_registries(MEASUREMENT_VINTAGES[args.vintage])[args.registry]
    spec = next(s for s in registry.inputs if s.key == args.snapshot_worker)
    start, end = map(date.fromisoformat, spec.snapshot_window)
    days = [start + timedelta(days=n) for n in range(0, (end - start).days + 1, 7)]

    def fetch(day):
        with FiscusService() as service, tempfile.TemporaryDirectory() as tmp:
            response = service.soma_holdings(asof=day.isoformat(), refresh=args.refresh)
            artifact = response["artifact"]
            path = Path(tmp) / "snapshot.csv"
            service.export_artifact(artifact["cache_key"], path)
            raw = path.read_bytes()
            provenance = service.provenance(artifact["cache_key"])
            if (
                hashlib.sha256(raw).hexdigest() != artifact["sha256"]
                or not provenance["sha256_verified"]
            ):
                raise ValueError(f"{day}: snapshot hash does not verify")
            rows = list(csv.DictReader(raw.decode().splitlines()))
            if any(row["asOfDate"] != day.isoformat() for row in rows):
                raise ValueError(
                    f"{day}: snapshot rows have a different source as-of date"
                )
            record = {
                **artifact,
                **response["provenance"],
                "asof": day.isoformat(),
                "status": "source_reported" if rows else "unavailable_empty_snapshot",
            }
            return rows, record

    all_rows, snapshots = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for n, (rows, record) in enumerate(pool.map(fetch, days), 1):
            target = days[n - 1]
            record.update(
                effective_wednesday=str(target), substitution_reason="exact_wednesday"
            )
            if not rows:
                mapping = snapshot_date_mapping(
                    [target], [d for d in available if d != str(target)]
                )
                replacement = mapping.get(pd.Timestamp(target))
                if replacement:
                    rows, substitute = fetch(date.fromisoformat(replacement["asof"]))
                    if not rows:
                        raise ValueError(
                            f"SOMA: listed substitute {replacement['asof']} is empty"
                        )
                    record = {
                        **substitute,
                        **replacement,
                        "original_empty_snapshot": record,
                    }
            all_rows.extend(rows)
            snapshots.append(record)
            if n % 100 == 0:
                print(f"SOMA: {n}/{len(days)} snapshots", file=sys.stderr, flush=True)
    relative = registry.input_dir / f"{spec.key}.csv"
    fields = sorted({key for row in all_rows for key in row})
    if not fields:
        raise ValueError("SOMA: no nonempty snapshots")
    with (args.data_root / relative).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)
    raw = (args.data_root / relative).read_bytes()
    record = {
        "dataset_id": spec.dataset_id,
        "argv": list(spec.argv),
        "file": relative.as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw),
        "cache_key": "consolidated_fiscus_snapshots",
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "vintage": "individual_snapshot_vintages",
        "source_url": snapshots[-1]["source_url"],
        "source_metadata": {
            "snapshots": snapshots,
            "snapshot_window": list(spec.snapshot_window),
            "asof_date_list": asof_list_record,
        },
        "row_count": len(all_rows),
        "data_coverage": {"start": str(start), "end": str(end)},
        "clock": spec.clock,
        "units": spec.units,
        "usd_million_per_unit": spec.usd_million_per_unit,
        "series_id": spec.series_id,
    }
    print(json.dumps(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
