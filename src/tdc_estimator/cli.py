from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Sequence

import pandas as pd

from .catalog import BASE_FRED_SERIES, TREASURY_DATASETS, all_fred_series
from .config import ensure_project_dirs, project_paths
from .demo import generate_synthetic_raw_bundle
from .download import download_fred_bundle, download_treasury_bundle
from .fed_coupon import (
    resolve_wamest_soma_path,
    write_quarterly_fed_coupon_interest_proxy_from_soma_csvs,
)
from .pipeline import run_estimation_pipeline
from .sector_coupon import (
    DEFAULT_BANK_SECTOR_KEYS,
    DEFAULT_ROW_SECTOR_KEYS,
    resolve_wamest_artifact_paths,
    write_quarterly_tier2_coupon_interest_proxies,
)
from .tier3_source import write_source_backed_tier3_input_table
from .tier3_support import (
    build_tier3_support_table,
    derive_quarterly_date_spine,
    load_tier3_quarterly_input_table,
    write_tier3_support_files,
)
from .utils import project_relative_path, write_json


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
        project_root=paths.root,
    )

    treasury_manifest = None
    if args.include_treasury_support:
        treasury_manifest = download_treasury_bundle(
            TREASURY_DATASETS,
            paths.raw,
            continue_on_error=True,
            project_root=paths.root,
        )

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
        project_root=paths.root,
    )
    if args.include_treasury_support:
        download_treasury_bundle(
            TREASURY_DATASETS,
            paths.raw,
            continue_on_error=True,
            project_root=paths.root,
        )

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
        figures_dir=paths.figures,
        site_dir=paths.site,
    )
    summary = {
        "target": project_relative_path(target, root),
        "estimates_path": project_relative_path(result["estimates_path"], root),
        "components_path": project_relative_path(result["components_path"], root),
        "corrections_path": project_relative_path(result["corrections_path"], root),
        "post2022_attribution_path": project_relative_path(result["post2022_attribution_path"], root),
        "post2022_attribution_markdown_path": project_relative_path(result["post2022_attribution_markdown_path"], root),
        "figure_outputs": [project_relative_path(path, root) for path in result["figure_outputs"]],
        "site_outputs": {key: project_relative_path(path, root) for key, path in result["site_outputs"].items()},
    }
    write_json(target / "demo_summary.json", summary)
    print(f"Wrote demo outputs to {target}")
    return 0


def cmd_fed_coupon_proxy(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    soma_files = args.soma_file
    if args.wamest_root is not None:
        soma_files = [str(resolve_wamest_soma_path(args.wamest_root, soma_file=soma_files[0] if soma_files else None))]
    if not soma_files:
        raise ValueError("Fed coupon proxy requires either --soma-file or --wamest-root.")
    out_path = Path(args.out) if args.out else (paths.raw / "support__fed_tsy_coupon_interest_proxy.csv")
    written = write_quarterly_fed_coupon_interest_proxy_from_soma_csvs(soma_files, out_path)
    print(f"Wrote Fed coupon-interest proxy to {written}")
    return 0


def cmd_tier2_coupon_proxies(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    sector_maturity_file = args.sector_maturity_file
    sector_panel_file = args.sector_panel_file
    curve_file = args.curve_file
    if args.wamest_root is not None:
        sector_maturity_path, sector_panel_path, curve_path = resolve_wamest_artifact_paths(
            wamest_root=args.wamest_root,
            sector_maturity_file=sector_maturity_file,
            sector_panel_file=sector_panel_file,
            curve_file=curve_file,
        )
        sector_maturity_file = str(sector_maturity_path)
        sector_panel_file = str(sector_panel_path)
        curve_file = str(curve_path)
    missing = [
        name
        for name, value in [
            ("--sector-maturity-file", sector_maturity_file),
            ("--sector-panel-file", sector_panel_file),
            ("--curve-file", curve_file),
        ]
        if not value
    ]
    if missing:
        raise ValueError(
            "Tier 2 coupon proxies require either explicit sector files or --wamest-root. Missing: "
            + ", ".join(missing)
        )
    bank_out = Path(args.bank_out) if args.bank_out else (paths.raw / "support__bank_tsy_coupon_interest_proxy.csv")
    row_out = Path(args.row_out) if args.row_out else (paths.raw / "support__row_tsy_coupon_interest_proxy.csv")
    bank_written, row_written = write_quarterly_tier2_coupon_interest_proxies(
        sector_maturity_path=sector_maturity_file,
        sector_panel_path=sector_panel_file,
        curve_path=curve_file,
        bank_out_path=bank_out,
        row_out_path=row_out,
        bank_sector_keys=args.bank_sector_key or DEFAULT_BANK_SECTOR_KEYS,
        row_sector_keys=args.row_sector_key or DEFAULT_ROW_SECTOR_KEYS,
    )
    print(f"Wrote Tier 2 bank coupon-interest proxy to {bank_written}")
    print(f"Wrote Tier 2 ROW coupon-interest proxy to {row_written}")
    return 0


def cmd_tier3_support_files(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    dates = derive_quarterly_date_spine(paths.raw)
    quarterly_input = None
    if args.quarterly_input is not None:
        quarterly_input = load_tier3_quarterly_input_table(args.quarterly_input)
        dates = pd.DatetimeIndex(dates.union(quarterly_input.index))
    table = build_tier3_support_table(
        dates=dates,
        quarterly_input=quarterly_input,
        fill_value=float(args.fill_value),
    )
    written = write_tier3_support_files(raw_dir=paths.raw, table=table, overwrite=bool(args.overwrite))
    for key, path in written.items():
        print(f"Wrote Tier 3 support file for {key} to {path}")
    return 0


def cmd_tier3_source_input(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_path = Path(args.out) if args.out else (paths.root / "examples" / "tier3-quarterly-input-template.csv")
    base_path = args.base_input
    if base_path is None and out_path.exists():
        base_path = str(out_path)
    written = write_source_backed_tier3_input_table(
        mts_outlays_path=args.mts_outlays_file or (paths.raw / "treasury__mts_outlays.csv"),
        out_path=out_path,
        base_quarterly_input_path=base_path,
        start=args.start,
        row_profile=args.row_profile,
    )
    print(f"Wrote Tier 3 source-backed quarterly input table to {written}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tdc",
        description="Estimate the Treasury-attributed component of deposits (TDC).",
    )

    root_parent = argparse.ArgumentParser(add_help=False)
    root_parent.add_argument("--root", default=".", help="Project root (defaults to current working directory).")

    sub = parser.add_subparsers(dest="command", required=True)

    p_download = sub.add_parser("download", parents=[root_parent], help="Download raw source data.")
    p_download.add_argument("--required-only", action="store_true", help="Download only the required baseline FRED series.")
    p_download.add_argument("--include-treasury-support", action="store_true", help="Also download supporting Treasury Fiscal Data datasets.")
    p_download.add_argument("--fred-api-key", default=None, help="Optional FRED API key. If omitted, uses the FRED graph CSV endpoint.")
    p_download.add_argument("--start-date", default=None, help="Optional download start date, YYYY-MM-DD.")
    p_download.add_argument("--end-date", default=None, help="Optional download end date, YYYY-MM-DD.")
    p_download.set_defaults(func=cmd_download)

    p_estimate = sub.add_parser("estimate", parents=[root_parent], help="Build processed estimate files from raw data.")
    p_estimate.set_defaults(func=cmd_estimate)

    p_plot = sub.add_parser("plot", parents=[root_parent], help="Build figures from raw data.")
    p_plot.set_defaults(func=cmd_plot)

    p_site = sub.add_parser("site-export", parents=[root_parent], help="Build the static-site data bundle.")
    p_site.set_defaults(func=cmd_site_export)

    p_build = sub.add_parser("build", parents=[root_parent], help="Download, estimate, plot, and site-export in one step.")
    p_build.add_argument("--required-only", action="store_true", help="Download only the required baseline FRED series.")
    p_build.add_argument("--include-treasury-support", action="store_true", help="Also download supporting Treasury Fiscal Data datasets.")
    p_build.add_argument("--fred-api-key", default=None, help="Optional FRED API key. If omitted, uses the FRED graph CSV endpoint.")
    p_build.add_argument("--start-date", default=None, help="Optional download start date, YYYY-MM-DD.")
    p_build.add_argument("--end-date", default=None, help="Optional download end date, YYYY-MM-DD.")
    p_build.set_defaults(func=cmd_build)

    p_demo = sub.add_parser("demo", parents=[root_parent], help="Run the fully offline synthetic demo build.")
    p_demo.add_argument("--seed", type=int, default=7, help="Random seed for the synthetic fixture generator.")
    p_demo.set_defaults(func=cmd_demo)

    p_fed_coupon = sub.add_parser(
        "fed-coupon-proxy",
        parents=[root_parent],
        help="Build a quarterly Fed Treasury coupon-interest proxy from SOMA holdings snapshots.",
    )
    p_fed_coupon.add_argument(
        "--soma-file",
        nargs="+",
        default=None,
        help="One or more CSV files containing SOMA Treasury holdings snapshots.",
    )
    p_fed_coupon.add_argument(
        "--wamest-root",
        default=None,
        help="Optional wamest repo root. If provided, the conventional normalized SOMA holdings artifact is inferred automatically unless --soma-file is also supplied.",
    )
    p_fed_coupon.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/support__fed_tsy_coupon_interest_proxy.csv under --root.",
    )
    p_fed_coupon.set_defaults(func=cmd_fed_coupon_proxy)

    p_tier2_coupon = sub.add_parser(
        "tier2-coupon-proxies",
        parents=[root_parent],
        help="Build quarterly bank and ROW Treasury coupon-interest proxies from sector maturity, sector panel, and curve files.",
    )
    p_tier2_coupon.add_argument(
        "--sector-maturity-file",
        default=None,
        help="CSV file containing sector-level coupon_share and coupon-only maturity rows, such as a wamest sector_effective_maturity export.",
    )
    p_tier2_coupon.add_argument(
        "--sector-panel-file",
        default=None,
        help="CSV file containing sector-level holdings levels by quarter, such as a wamest sector panel export.",
    )
    p_tier2_coupon.add_argument(
        "--curve-file",
        default=None,
        help="Wide Treasury curve CSV with a date column and maturity columns such as 1y, 2y, 5y, and 10y.",
    )
    p_tier2_coupon.add_argument(
        "--wamest-root",
        default=None,
        help="Optional wamest repo root. If provided, conventional artifact paths are inferred automatically and can be overridden by the explicit file flags above.",
    )
    p_tier2_coupon.add_argument(
        "--bank-out",
        default=None,
        help="Output CSV path for the bank-sector proxy. Defaults to data/raw/support__bank_tsy_coupon_interest_proxy.csv under --root.",
    )
    p_tier2_coupon.add_argument(
        "--row-out",
        default=None,
        help="Output CSV path for the ROW proxy. Defaults to data/raw/support__row_tsy_coupon_interest_proxy.csv under --root.",
    )
    p_tier2_coupon.add_argument(
        "--bank-sector-key",
        action="append",
        default=None,
        help="Optional bank sector key override. Repeat to specify multiple sectors. Defaults to the Tier 0 bank block.",
    )
    p_tier2_coupon.add_argument(
        "--row-sector-key",
        action="append",
        default=None,
        help="Optional ROW sector key override. Repeat to specify multiple sectors. Defaults to foreigners_total.",
    )
    p_tier2_coupon.set_defaults(func=cmd_tier2_coupon_proxies)

    p_tier3_support = sub.add_parser(
        "tier3-support-files",
        parents=[root_parent],
        help="Seed or update Tier 3 fiscal support CSVs under data/raw.",
    )
    p_tier3_support.add_argument(
        "--quarterly-input",
        default=None,
        help="Optional quarterly CSV with a date column and one or more Tier 3 support columns. Missing support columns are filled with --fill-value.",
    )
    p_tier3_support.add_argument(
        "--fill-value",
        type=float,
        default=0.0,
        help="Default value used when writing missing Tier 3 support columns. Defaults to 0.0.",
    )
    p_tier3_support.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Tier 3 support files. By default existing files are left in place.",
    )
    p_tier3_support.set_defaults(func=cmd_tier3_support_files)

    p_tier3_source = sub.add_parser(
        "tier3-source-input",
        parents=[root_parent],
        help="Build a source-backed Tier 3 quarterly input table from MTS outlays.",
    )
    p_tier3_source.add_argument(
        "--mts-outlays-file",
        default=None,
        help="MTS outlays CSV. Defaults to data/raw/treasury__mts_outlays.csv under --root.",
    )
    p_tier3_source.add_argument(
        "--base-input",
        default=None,
        help="Optional existing quarterly Tier 3 input table to overlay source-backed quarters onto.",
    )
    p_tier3_source.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to examples/tier3-quarterly-input-template.csv under --root.",
    )
    p_tier3_source.add_argument(
        "--start",
        default="2022-09-30",
        help="Earliest quarter to retain in the output table. Defaults to 2022-09-30.",
    )
    p_tier3_source.add_argument(
        "--row-profile",
        choices=["default", "broad"],
        default="default",
        help="ROW outlay profile for source-backed Tier 3 input generation. Defaults to the narrower default profile; use broad to include the security add-on lines.",
    )
    p_tier3_source.set_defaults(func=cmd_tier3_source_input)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
