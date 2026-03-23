from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Sequence

from .catalog import BASE_FRED_SERIES, TREASURY_DATASETS, all_fred_series
from .config import ensure_project_dirs, project_paths
from .demo import generate_synthetic_raw_bundle
from .download import download_fred_bundle, download_treasury_bundle
from .pipeline import run_estimation_pipeline
from .utils import write_json


def _default_root() -> Path:
    return Path(".").resolve()


def cmd_download(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)

    fred_specs = BASE_FRED_SERIES if args.required_only else all_fred_series(include_optional=True)
    fred_manifest = download_fred_bundle(
        fred_specs,
        paths.raw,
        api_key=args.fred_api_key or os.getenv("FRED_API_KEY"),
        start_date=args.start_date,
        end_date=args.end_date,
        continue_on_error=True,
    )

    treasury_manifest = None
    if args.include_treasury_support:
        treasury_manifest = download_treasury_bundle(TREASURY_DATASETS, paths.raw, continue_on_error=True)

    summary = {
        "fred_manifest": fred_manifest,
        "treasury_manifest": treasury_manifest,
    }
    write_json(paths.processed / "download_summary.json", summary)
    print(f"Wrote download summary to {paths.processed / 'download_summary.json'}")
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    result = run_estimation_pipeline(raw_dir=paths.raw, processed_dir=paths.processed)
    print(f"Wrote estimates to {result['estimates_path']}")
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    result = run_estimation_pipeline(raw_dir=paths.raw, processed_dir=paths.processed, figures_dir=paths.figures)
    print(f"Wrote figures to {paths.figures}")
    return 0


def cmd_site_export(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    result = run_estimation_pipeline(raw_dir=paths.raw, processed_dir=paths.processed, site_dir=paths.site)
    print(f"Wrote site bundle to {paths.site}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)

    fred_specs = BASE_FRED_SERIES if args.required_only else all_fred_series(include_optional=True)
    download_fred_bundle(
        fred_specs,
        paths.raw,
        api_key=args.fred_api_key or os.getenv("FRED_API_KEY"),
        start_date=args.start_date,
        end_date=args.end_date,
        continue_on_error=True,
    )
    if args.include_treasury_support:
        download_treasury_bundle(TREASURY_DATASETS, paths.raw, continue_on_error=True)

    result = run_estimation_pipeline(
        raw_dir=paths.raw,
        processed_dir=paths.processed,
        figures_dir=paths.figures,
        site_dir=paths.site,
    )
    print(f"Wrote build outputs under {paths.root / 'data'}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    target = root / "examples" / "demo_build"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    paths = project_paths(target)
    ensure_project_dirs(paths)

    generate_synthetic_raw_bundle(paths.raw, seed=args.seed)
    result = run_estimation_pipeline(
        raw_dir=paths.raw,
        processed_dir=paths.processed,
        figures_dir=target / "figures",
        site_dir=target / "site",
    )
    summary = {
        "target": str(target),
        "estimates_path": result["estimates_path"],
        "components_path": result["components_path"],
        "figure_outputs": result["figure_outputs"],
        "site_outputs": result["site_outputs"],
    }
    write_json(target / "demo_summary.json", summary)
    print(f"Wrote demo outputs to {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tdc",
        description="Estimate the Treasury-attributed component of deposits (TDC).",
    )
    parser.add_argument("--root", default=".", help="Project root (defaults to current working directory).")

    sub = parser.add_subparsers(dest="command", required=True)

    p_download = sub.add_parser("download", help="Download raw source data.")
    p_download.add_argument("--required-only", action="store_true", help="Download only the required baseline FRED series.")
    p_download.add_argument("--include-treasury-support", action="store_true", help="Also download supporting Treasury Fiscal Data datasets.")
    p_download.add_argument("--fred-api-key", default=None, help="Optional FRED API key. If omitted, uses the FRED graph CSV endpoint.")
    p_download.add_argument("--start-date", default=None, help="Optional download start date, YYYY-MM-DD.")
    p_download.add_argument("--end-date", default=None, help="Optional download end date, YYYY-MM-DD.")
    p_download.set_defaults(func=cmd_download)

    p_estimate = sub.add_parser("estimate", help="Build processed estimate files from raw data.")
    p_estimate.set_defaults(func=cmd_estimate)

    p_plot = sub.add_parser("plot", help="Build figures from raw data.")
    p_plot.set_defaults(func=cmd_plot)

    p_site = sub.add_parser("site-export", help="Build the static-site data bundle.")
    p_site.set_defaults(func=cmd_site_export)

    p_build = sub.add_parser("build", help="Download, estimate, plot, and site-export in one step.")
    p_build.add_argument("--required-only", action="store_true", help="Download only the required baseline FRED series.")
    p_build.add_argument("--include-treasury-support", action="store_true", help="Also download supporting Treasury Fiscal Data datasets.")
    p_build.add_argument("--fred-api-key", default=None, help="Optional FRED API key. If omitted, uses the FRED graph CSV endpoint.")
    p_build.add_argument("--start-date", default=None, help="Optional download start date, YYYY-MM-DD.")
    p_build.add_argument("--end-date", default=None, help="Optional download end date, YYYY-MM-DD.")
    p_build.set_defaults(func=cmd_build)

    p_demo = sub.add_parser("demo", help="Run the fully offline synthetic demo build.")
    p_demo.add_argument("--seed", type=int, default=7, help="Random seed for the synthetic fixture generator.")
    p_demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
