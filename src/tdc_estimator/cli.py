from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Sequence

import pandas as pd

from .bill_discount_validation import ensure_treasury_interest_expense_file, write_bill_discount_validation
from .bill_discount_allocator import write_bill_discount_allocation
from .catalog import BASE_FRED_SERIES, TREASURY_DATASETS, all_fred_series
from .config import ensure_project_dirs, project_paths
from .demo import generate_synthetic_raw_bundle
from .download import download_fred_bundle, download_treasury_bundle
from .fed_coupon import (
    resolve_wamest_soma_path,
    write_quarterly_fed_coupon_interest_proxy_from_soma_csvs,
    write_quarterly_fed_coupon_interest_proxy_with_wamest_backcast,
)
from .fed_interest_components import write_fed_interest_components_from_soma_csvs
from .fed_component_extension_export import write_fed_component_extension_support
from .gse_rrp_boundary import write_gse_on_rrp_support
from .ffiec_interest_constraints import write_ffiec_interest_constraints_from_extracted_root
from .interest_source_constraints import write_interest_source_constraints
from .interest_source_window_validation import write_interest_source_window_validation
from .ncua_interest_constraints import write_ncua_interest_constraints_from_cache
from .pipeline import run_estimation_pipeline
from .ratewall_du_ru_methodology import write_ratewall_du_ru_methodology_panel
from .monetary_route_bridge import write_monetary_route_bridge
from .mmf_route_split_context import write_mmf_route_split_context
from .route_admissibility_registry import write_route_admissibility_registry
from .tdcsim_private_route_allocation_sensitivity import (
    write_tdcsim_private_route_allocation_sensitivity,
)
from .tdcsim_private_route_support_contract import (
    write_tdcsim_private_route_support_contract,
)
from .tdc_empirical_anchor import write_tdc_empirical_anchor
from .z1_domestic_nonbank_sector_context import (
    write_z1_domestic_nonbank_sector_context,
)
from .mmf_rrp import download_sec_nmfp_zips, write_ofr_mmf_aggregate_support, write_sec_nmfp_fund_month_support
from .mts_previous_issues import (
    write_stitched_previous_targets_with_fiscaldata,
    write_table4_target_history_as_fiscaldata_receipts,
    write_table5_target_history_as_fiscaldata_outlays,
    write_mts_previous_issue_coverage_report,
    write_mts_previous_issues_manifest,
    write_mts_table4_target_history_from_manifest,
    write_mts_table5_target_history_from_manifest,
    write_mts_target_overlap_audit,
)
from .mts_remittances import write_fed_remittance_mts_support
from .sector_coupon import (
    DEFAULT_BANK_SECTOR_KEYS,
    DEFAULT_CREDIT_UNION_SECTOR_KEYS,
    DEFAULT_ROW_SECTOR_KEYS,
    resolve_wamest_artifact_paths,
    write_quarterly_tier2_bill_discount_interest_proxies,
    write_quarterly_tier2_coupon_interest_proxies,
)
from .tier3_source import write_source_backed_tier3_input_table
from .tier3_support import (
    build_tier3_support_table,
    derive_quarterly_date_spine,
    load_tier3_quarterly_input_table,
    write_tier3_support_files,
)
from .tier2_interest_component_candidate import write_tier2_interest_component_candidate
from .tier2_component_anchor_comparison import write_tier2_component_anchor_comparison
from .tier2_component_default_decision import write_tier2_component_default_decision
from .tier2_component_delta_attribution import write_tier2_component_delta_attribution
from .tier2_component_support_export import write_tier2_component_support_exports
from .tier2_cu_split_sensitivity import write_tier2_cu_split_sensitivity
from .tier2_interest_default_switch_review import write_tier2_interest_default_switch_review
from .tier2_live_delta_acceptance import write_tier2_live_delta_acceptance
from .tier2_regression_backcast import write_tier2_regression_backcast
from .tier2_regression_series import write_tier2_regression_series
from .tier2_tips_treatment_decision import write_tier2_tips_treatment_decision
from .treasury_interest_components import write_treasury_interest_component_pools
from .utils import project_relative_path, write_json
from .wamest_interest_contract import resolve_wamest_interest_contract_paths


def _existing_path(*candidates: Path | str | None) -> Path | None:
    for candidate in candidates:
        if candidate is None:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    return None


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
    mmf_support_path = None
    if getattr(args, "include_mmf_support", False):
        mmf_support_path = write_ofr_mmf_aggregate_support(
            out_path=paths.raw / "support__mmf_fund_month.csv",
            raw_json_path=paths.raw / "ofr__mmf_dataset.json",
        )

    summary = {
        "fred_manifest": fred_manifest,
        "treasury_manifest": treasury_manifest,
        "mmf_support_path": str(mmf_support_path) if mmf_support_path is not None else None,
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
    run_estimation_pipeline(raw_dir=paths.raw, processed_dir=paths.processed, figures_dir=paths.figures)
    print(f"Wrote figures to {paths.figures}")
    return 0


def cmd_site_export(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    run_estimation_pipeline(raw_dir=paths.raw, processed_dir=paths.processed, site_dir=paths.site)
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
    if getattr(args, "include_mmf_support", False):
        write_ofr_mmf_aggregate_support(
            out_path=paths.raw / "support__mmf_fund_month.csv",
            raw_json_path=paths.raw / "ofr__mmf_dataset.json",
        )

    run_estimation_pipeline(
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
    if args.wamest_root is not None:
        sector_maturity_path, sector_panel_path, curve_path = resolve_wamest_artifact_paths(
            wamest_root=args.wamest_root,
            prefer_normalized_sector_panel=True,
        )
        written = write_quarterly_fed_coupon_interest_proxy_with_wamest_backcast(
            soma_paths=soma_files,
            sector_maturity_path=sector_maturity_path,
            sector_panel_path=sector_panel_path,
            curve_path=curve_path,
            out_path=out_path,
        )
    else:
        written = write_quarterly_fed_coupon_interest_proxy_from_soma_csvs(soma_files, out_path)
    print(f"Wrote Fed coupon-interest proxy to {written}")
    return 0


def cmd_fed_interest_components(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    soma_files = args.soma_file
    if args.wamest_root is not None:
        soma_files = [str(resolve_wamest_soma_path(args.wamest_root, soma_file=soma_files[0] if soma_files else None))]
    if not soma_files:
        raise ValueError("Fed interest components require either --soma-file or --wamest-root.")
    out_csv = Path(args.out) if args.out else (paths.raw / "support__fed_treasury_interest_components.csv")
    out_md = (
        Path(args.markdown_out)
        if args.markdown_out
        else (paths.processed / "fed_treasury_interest_components.md")
    )
    written_csv, written_md = write_fed_interest_components_from_soma_csvs(
        soma_paths=soma_files,
        out_csv_path=out_csv,
        out_markdown_path=out_md,
        auction_security_master_path=args.auction_file,
        frn_daily_indexes_path=args.frn_index_file,
    )
    print(f"Wrote Fed Treasury interest components to {written_csv}")
    if written_md is not None:
        print(f"Wrote Fed Treasury interest component summary to {written_md}")
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
            prefer_normalized_sector_panel=True,
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
    args_credit_union_out = getattr(args, "credit_union_out", None)
    credit_union_out = (
        Path(args_credit_union_out)
        if args_credit_union_out
        else (paths.raw / "support__credit_union_tsy_coupon_interest_proxy.csv")
    )
    args_credit_union_sector_key = getattr(args, "credit_union_sector_key", None)
    written = write_quarterly_tier2_coupon_interest_proxies(
        sector_maturity_path=sector_maturity_file,
        sector_panel_path=sector_panel_file,
        curve_path=curve_file,
        bank_out_path=bank_out,
        row_out_path=row_out,
        credit_union_out_path=credit_union_out,
        bank_sector_keys=args.bank_sector_key or DEFAULT_BANK_SECTOR_KEYS,
        row_sector_keys=args.row_sector_key or DEFAULT_ROW_SECTOR_KEYS,
        credit_union_sector_keys=args_credit_union_sector_key or DEFAULT_CREDIT_UNION_SECTOR_KEYS,
    )
    bank_written, row_written = written[0], written[1]
    credit_union_written = written[2] if len(written) > 2 else credit_union_out
    print(f"Wrote Tier 2 bank coupon-interest proxy to {bank_written}")
    print(f"Wrote Tier 2 ROW coupon-interest proxy to {row_written}")
    print(f"Wrote Tier 2 credit-union coupon-interest proxy to {credit_union_written}")
    if getattr(args, "include_bill_discount", False):
        bill_wam_file = args.bill_wam_file
        if bill_wam_file is None and args.wamest_root is not None:
            candidate = Path(args.wamest_root) / "data" / "processed" / "treasury_bill_wam_support.csv"
            if candidate.exists():
                bill_wam_file = str(candidate)
        bank_bill_out = (
            Path(args.bank_bill_out)
            if args.bank_bill_out
            else (paths.raw / "support__bank_tsy_bill_discount_interest_proxy.csv")
        )
        row_bill_out = (
            Path(args.row_bill_out)
            if args.row_bill_out
            else (paths.raw / "support__row_tsy_bill_discount_interest_proxy.csv")
        )
        credit_union_bill_out = (
            Path(args.credit_union_bill_out)
            if args.credit_union_bill_out
            else (paths.raw / "support__credit_union_tsy_bill_discount_interest_proxy.csv")
        )
        bill_written = write_quarterly_tier2_bill_discount_interest_proxies(
            sector_maturity_path=sector_maturity_file,
            sector_panel_path=sector_panel_file,
            curve_path=curve_file,
            bill_wam_path=bill_wam_file,
            bank_out_path=bank_bill_out,
            row_out_path=row_bill_out,
            credit_union_out_path=credit_union_bill_out,
            bank_sector_keys=args.bank_sector_key or DEFAULT_BANK_SECTOR_KEYS,
            row_sector_keys=args.row_sector_key or DEFAULT_ROW_SECTOR_KEYS,
            credit_union_sector_keys=args_credit_union_sector_key or DEFAULT_CREDIT_UNION_SECTOR_KEYS,
        )
        print(f"Wrote Tier 2 bank bill-discount interest proxy to {bill_written[0]}")
        print(f"Wrote Tier 2 ROW bill-discount interest proxy to {bill_written[1]}")
        print(f"Wrote Tier 2 credit-union bill-discount interest proxy to {bill_written[2]}")
    return 0


def cmd_ratewall_du_ru_methodology(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    z1_path = _existing_path(
        args.z1_holder_absorption_file,
        paths.root
        / "../tdcmix/data/processed/z1_exact_holder_absorption_panel.csv",
        paths.root
        / "../tdcmix/data/processed/holder_absorption_panel_exact_primary.csv",
    )
    if z1_path is None:
        raise ValueError(
            "RateWall DU/RU methodology export requires a Z.1 holder absorption "
            "panel. Pass --z1-holder-absorption-file or build tdcmix first."
        )
    csv_path = Path(args.out) if args.out else (
        paths.processed / "ratewall_du_ru_methodology_panel.csv"
    )
    markdown_path = Path(args.markdown_out) if args.markdown_out else (
        paths.processed / "ratewall_du_ru_methodology_panel.md"
    )
    written_csv, written_md, frame = write_ratewall_du_ru_methodology_panel(
        du_fiscal_flow_path=args.du_fiscal_flow_file
        or (paths.processed / "tdc_du_fiscal_flow_research.csv"),
        interest_method_path=args.interest_method_file
        or (paths.processed / "tier2_regression_interest_backcast_wide.csv"),
        z1_holder_absorption_path=z1_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )
    print(f"Wrote RateWall DU/RU methodology panel to {written_csv}")
    if written_md is not None:
        print(f"Wrote RateWall DU/RU methodology summary to {written_md}")
    print(f"Generated {len(frame)} methodology rows")
    return 0


def cmd_monetary_route_bridge(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    quarterly_path = (
        Path(args.quarterly_file)
        if args.quarterly_file
        else paths.processed / "quarterly_inputs.csv"
    )
    methodology_path = (
        Path(args.ratewall_du_ru_methodology_file)
        if args.ratewall_du_ru_methodology_file
        else paths.processed / "ratewall_du_ru_methodology_panel.csv"
    )
    if not quarterly_path.exists():
        raise ValueError(
            "Monetary route bridge requires quarterly inputs. Run `tdc estimate` "
            "or pass --quarterly-file."
        )
    quarterly = pd.read_csv(quarterly_path)
    methodology = (
        pd.read_csv(methodology_path) if methodology_path.exists() else pd.DataFrame()
    )
    csv_path = (
        Path(args.out)
        if args.out
        else paths.processed / "tdc_domestic_nonbank_monetary_route_bridge.csv"
    )
    markdown_path = (
        Path(args.markdown_out)
        if args.markdown_out
        else paths.processed / "tdc_domestic_nonbank_monetary_route_bridge.md"
    )
    written_csv, written_md, frame = write_monetary_route_bridge(
        quarterly=quarterly,
        ratewall_du_ru_methodology=methodology,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )
    print(f"Wrote monetary route bridge to {written_csv}")
    if written_md is not None:
        print(f"Wrote monetary route bridge summary to {written_md}")
    print(f"Generated {len(frame)} route rows")
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


def cmd_mmf_rrp_support(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_path = Path(args.out) if args.out else (paths.raw / "support__mmf_fund_month.csv")
    raw_json_path = None if args.no_raw_json else (paths.raw / "ofr__mmf_dataset.json")
    written = write_ofr_mmf_aggregate_support(out_path=out_path, raw_json_path=raw_json_path)
    print(f"Wrote OFR aggregate MMF/RRP support file to {written}")
    return 0


def cmd_sec_nmfp_mmf_support(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_path = Path(args.out) if args.out else (paths.raw / "support__mmf_fund_month.csv")
    zip_paths = [Path(path) for path in args.zip]
    if args.download:
        zip_paths.extend(
            download_sec_nmfp_zips(
                start=args.start,
                end=args.end,
                cache_dir=Path(args.cache_dir) if args.cache_dir else (paths.raw / "sec_nmfp_cache"),
            )
        )
    if not zip_paths:
        raise SystemExit("No SEC N-MFP ZIP files supplied. Pass --zip or --download.")
    written = write_sec_nmfp_fund_month_support(
        zip_paths=zip_paths,
        out_path=out_path,
        start=args.start if args.download else None,
        end=args.end if args.download else None,
    )
    print(f"Wrote SEC N-MFP fund-month MMF/RRP support file to {written}")
    return 0


def _nmfp_zip_paths(args: argparse.Namespace, default_cache_dir: Path) -> list[Path]:
    zip_paths = [Path(path) for path in getattr(args, "zip", [])]
    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir
    if getattr(args, "download", False):
        zip_paths.extend(
            download_sec_nmfp_zips(
                start=args.start,
                end=args.end,
                cache_dir=cache_dir,
            )
        )
    if not zip_paths:
        zip_paths = sorted(cache_dir.glob("*_nmfp.zip"))
    if not zip_paths:
        raise SystemExit(
            "No SEC N-MFP ZIP files supplied or found. Pass --zip, use "
            "--download, or populate data/raw/sec_nmfp_cache."
        )
    return sorted(set(zip_paths))


def cmd_mmf_route_split_context(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    zip_paths = _nmfp_zip_paths(args, paths.raw / "sec_nmfp_cache")
    csv_path = (
        Path(args.out)
        if args.out
        else paths.processed / "tdc_mmf_route_split_context.csv"
    )
    markdown_path = (
        Path(args.markdown_out)
        if args.markdown_out
        else paths.processed / "tdc_mmf_route_split_context.md"
    )
    written_csv, written_md, frame = write_mmf_route_split_context(
        zip_paths=zip_paths,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )
    print(f"Wrote MMF route split context to {written_csv}")
    if written_md is not None:
        print(f"Wrote MMF route split context summary to {written_md}")
    print(f"Generated {len(frame)} context rows from {len(zip_paths)} SEC N-MFP ZIPs")
    return 0


def cmd_route_admissibility_registry(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    monetary_path = (
        Path(args.monetary_route_bridge_file)
        if args.monetary_route_bridge_file
        else paths.processed / "tdc_domestic_nonbank_monetary_route_bridge.csv"
    )
    mmf_path = (
        Path(args.mmf_route_split_context_file)
        if args.mmf_route_split_context_file
        else paths.processed / "tdc_mmf_route_split_context.csv"
    )
    missing = [str(path) for path in (monetary_path, mmf_path) if not path.exists()]
    if missing:
        raise ValueError(
            "Route admissibility registry requires existing route bridge/context "
            "inputs. Missing: " + ", ".join(missing)
        )
    csv_path = (
        Path(args.out)
        if args.out
        else paths.processed / "tdc_route_admissibility_registry.csv"
    )
    markdown_path = (
        Path(args.markdown_out)
        if args.markdown_out
        else paths.processed / "tdc_route_admissibility_registry.md"
    )
    written_csv, written_md, frame = write_route_admissibility_registry(
        monetary_route_bridge_path=monetary_path,
        mmf_route_split_context_path=mmf_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )
    print(f"Wrote route admissibility registry to {written_csv}")
    if written_md is not None:
        print(f"Wrote route admissibility registry summary to {written_md}")
    print(f"Generated {len(frame)} route rules")
    return 0


def cmd_z1_domestic_nonbank_sector_context(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    z1_path = _existing_path(
        args.z1_holder_absorption_file,
        paths.root
        / "../tdcmix/data/processed/z1_exact_holder_absorption_panel.csv",
        paths.root
        / "../tdcmix/data/processed/holder_absorption_panel_exact_primary.csv",
    )
    if z1_path is None:
        raise ValueError(
            "Z.1 domestic nonbank sector context requires a holder absorption "
            "panel. Pass --z1-holder-absorption-file or build tdcmix first."
        )
    csv_path = (
        Path(args.out)
        if args.out
        else paths.processed / "tdc_z1_domestic_nonbank_sector_context.csv"
    )
    markdown_path = (
        Path(args.markdown_out)
        if args.markdown_out
        else paths.processed / "tdc_z1_domestic_nonbank_sector_context.md"
    )
    written_csv, written_md, frame = write_z1_domestic_nonbank_sector_context(
        z1_holder_absorption_path=z1_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )
    print(f"Wrote Z.1 domestic nonbank sector context to {written_csv}")
    if written_md is not None:
        print(f"Wrote Z.1 domestic nonbank sector context summary to {written_md}")
    print(f"Generated {len(frame)} sector context rows")
    return 0


def cmd_tdcsim_private_route_allocation_sensitivity(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    z1_flow_path = _existing_path(
        args.z1_flow_file,
        paths.root / "../tdcmix/data/processed/z1_exact_holder_absorption_panel.csv",
        paths.root / "../tdcmix/data/processed/holder_absorption_panel_exact_primary.csv",
    )
    z1_stock_path = _existing_path(
        args.z1_stock_file,
        paths.root / "../tsyparty/data/interim/z1_holdings_long.csv",
        paths.root / "../wamest/data/interim/z1_series_panel_full.csv",
    )
    mmf_path = _existing_path(
        args.mmf_route_split_context_file,
        paths.processed / "tdc_mmf_route_split_context.csv",
    )
    missing: list[str] = []
    if z1_flow_path is None:
        missing.append("Z.1 F.210 holder absorption flow panel")
    if z1_stock_path is None:
        missing.append("Z.1 L.210 holder stock panel")
    if mmf_path is None:
        missing.append("SEC N-MFP MMF route split context")
    if missing:
        raise ValueError(
            "TDCSim Private route allocation sensitivity requires existing "
            "source panels. Missing: " + ", ".join(missing)
        )
    csv_path = (
        Path(args.out)
        if args.out
        else paths.processed / "tdc_tdcsim_private_route_allocation_sensitivity.csv"
    )
    markdown_path = (
        Path(args.markdown_out)
        if args.markdown_out
        else paths.processed / "tdc_tdcsim_private_route_allocation_sensitivity.md"
    )
    written_csv, written_md, frame = (
        write_tdcsim_private_route_allocation_sensitivity(
            z1_flow_path=z1_flow_path,
            z1_stock_path=z1_stock_path,
            mmf_route_split_context_path=mmf_path,
            csv_path=csv_path,
            markdown_path=markdown_path,
        )
    )
    support_contract_path = (
        Path(args.support_contract_out)
        if args.support_contract_out
        else paths.processed / "tdc_tdcsim_private_route_support_contract.csv"
    )
    written_support_csv, support_frame = write_tdcsim_private_route_support_contract(
        sensitivity_path=written_csv,
        csv_path=support_contract_path,
    )
    print(f"Wrote TDCSim Private route allocation sensitivity to {written_csv}")
    if written_md is not None:
        print(f"Wrote TDCSim Private route allocation summary to {written_md}")
    print(f"Wrote TDCSim Private route support contract to {written_support_csv}")
    print(f"Generated {len(frame)} bounded noncanonical sensitivity rows")
    print(f"Generated {len(support_frame)} bounded support contract rows")
    return 0


def cmd_fed_remit_mts_support(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_path = Path(args.out) if args.out else (paths.raw / "support__fed_remit_mts.csv")
    cache_dir = Path(args.cache_dir) if args.cache_dir else (paths.raw / "mts_pdf_cache")
    written = write_fed_remittance_mts_support(
        out_path=out_path,
        start=args.start,
        end=args.end,
        cache_dir=cache_dir,
        mts_receipts_path=paths.raw / "treasury__mts_receipts.csv",
    )
    print(f"Wrote MTS Fed remittance support to {written}")
    return 0


def cmd_mts_previous_issues_manifest(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_path = Path(args.out) if args.out else (paths.raw / "treasury__mts_previous_issues_manifest.csv")
    cache_dir = Path(args.cache_dir) if args.cache_dir else (paths.raw / "mts_previous_issues")
    written = write_mts_previous_issues_manifest(
        out_path=out_path,
        start=args.start,
        end=args.end,
        cache_dir=cache_dir,
    )
    print(f"Wrote MTS previous-issues manifest to {written}")
    return 0


def cmd_mts_table5_target_history(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else (paths.raw / "treasury__mts_previous_issues_manifest.csv")
    )
    out_path = Path(args.out) if args.out else (paths.raw / "treasury__mts_table5_target_history.csv")
    written = write_mts_table5_target_history_from_manifest(
        manifest_path=manifest_path,
        out_path=out_path,
        require_cached_text=not args.download_missing_text,
    )
    print(f"Wrote MTS Table 5 target history to {written}")
    return 0


def cmd_mts_table4_target_history(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else (paths.raw / "treasury__mts_previous_issues_manifest.csv")
    )
    out_path = Path(args.out) if args.out else (paths.raw / "treasury__mts_table4_target_history.csv")
    written = write_mts_table4_target_history_from_manifest(
        manifest_path=manifest_path,
        out_path=out_path,
        require_cached_text=not args.download_missing_text,
    )
    print(f"Wrote MTS Table 4 target history to {written}")
    return 0


def cmd_mts_table4_target_receipts(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    history_path = (
        Path(args.history)
        if args.history
        else (paths.raw / "treasury__mts_table4_target_history.csv")
    )
    out_path = Path(args.out) if args.out else (paths.raw / "treasury__mts_receipts_previous_targets.csv")
    written = write_table4_target_history_as_fiscaldata_receipts(history_path=history_path, out_path=out_path)
    print(f"Wrote MTS Table 4 target receipts to {written}")
    return 0


def cmd_mts_table5_target_outlays(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    history_path = (
        Path(args.history)
        if args.history
        else (paths.raw / "treasury__mts_table5_target_history.csv")
    )
    out_path = Path(args.out) if args.out else (paths.raw / "treasury__mts_outlays_previous_targets.csv")
    written = write_table5_target_history_as_fiscaldata_outlays(history_path=history_path, out_path=out_path)
    print(f"Wrote MTS Table 5 target outlays to {written}")
    return 0


def cmd_mts_stitched_target_receipts(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    previous_path = (
        Path(args.previous_targets)
        if args.previous_targets
        else (paths.raw / "treasury__mts_receipts_previous_targets.csv")
    )
    fiscaldata_path = Path(args.fiscaldata) if args.fiscaldata else (paths.raw / "treasury__mts_receipts.csv")
    out_path = Path(args.out) if args.out else (paths.raw / "treasury__mts_receipts_stitched_targets.csv")
    written = write_stitched_previous_targets_with_fiscaldata(
        previous_targets_path=previous_path,
        fiscaldata_path=fiscaldata_path,
        out_path=out_path,
    )
    print(f"Wrote stitched MTS target receipts to {written}")
    return 0


def cmd_mts_stitched_target_outlays(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    previous_path = (
        Path(args.previous_targets)
        if args.previous_targets
        else (paths.raw / "treasury__mts_outlays_previous_targets.csv")
    )
    fiscaldata_path = Path(args.fiscaldata) if args.fiscaldata else (paths.raw / "treasury__mts_outlays.csv")
    out_path = Path(args.out) if args.out else (paths.raw / "treasury__mts_outlays_stitched_targets.csv")
    written = write_stitched_previous_targets_with_fiscaldata(
        previous_targets_path=previous_path,
        fiscaldata_path=fiscaldata_path,
        out_path=out_path,
    )
    print(f"Wrote stitched MTS target outlays to {written}")
    return 0


def cmd_mts_previous_issue_coverage(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    manifest_path = Path(args.manifest) if args.manifest else (paths.raw / "treasury__mts_previous_issues_manifest.csv")
    table4_path = Path(args.table4_history) if args.table4_history else (paths.raw / "treasury__mts_table4_target_history.csv")
    table5_path = Path(args.table5_history) if args.table5_history else (paths.raw / "treasury__mts_table5_target_history.csv")
    csv_path = Path(args.out) if args.out else (paths.processed / "mts_previous_issue_coverage_report.csv")
    markdown_path = Path(args.markdown_out) if args.markdown_out else (paths.processed / "mts_previous_issue_coverage_report.md")
    written_csv, written_md = write_mts_previous_issue_coverage_report(
        manifest_path=manifest_path,
        table4_history_path=table4_path,
        table5_history_path=table5_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )
    print(f"Wrote MTS previous-issue coverage report to {written_csv}")
    if written_md is not None:
        print(f"Wrote MTS previous-issue coverage summary to {written_md}")
    return 0


def cmd_mts_target_overlap_audit(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    table4_history_path = (
        Path(args.table4_history)
        if args.table4_history
        else (paths.raw / "treasury__mts_table4_target_history_overlap.csv")
    )
    table5_history_path = (
        Path(args.table5_history)
        if args.table5_history
        else (paths.raw / "treasury__mts_table5_target_history_overlap.csv")
    )
    csv_path = Path(args.out) if args.out else (paths.processed / "mts_target_overlap_audit.csv")
    markdown_path = Path(args.markdown_out) if args.markdown_out else (paths.processed / "mts_target_overlap_audit.md")
    written_csv, written_md = write_mts_target_overlap_audit(
        table4_history_path=table4_history_path,
        table4_fiscaldata_path=Path(args.table4_fiscaldata) if args.table4_fiscaldata else (paths.raw / "treasury__mts_receipts.csv"),
        table5_history_path=table5_history_path,
        table5_fiscaldata_path=Path(args.table5_fiscaldata) if args.table5_fiscaldata else (paths.raw / "treasury__mts_outlays.csv"),
        csv_path=csv_path,
        markdown_path=markdown_path,
        tolerance_dollars=args.tolerance_dollars,
    )
    print(f"Wrote MTS target overlap audit to {written_csv}")
    if written_md is not None:
        print(f"Wrote MTS target overlap audit summary to {written_md}")
    return 0


def cmd_gse_on_rrp_support(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_path = Path(args.out) if args.out else (paths.raw / "support__gse_on_rrp.csv")
    raw_json_path = None if args.no_raw_json else (paths.raw / "nyfed__reverse_repo_propositions.json")
    written = write_gse_on_rrp_support(
        out_path=out_path,
        start=args.start,
        end=args.end,
        raw_json_path=raw_json_path,
    )
    print(f"Wrote NY Fed GSE ON RRP support file to {written}")
    return 0


def cmd_bill_discount_validation(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    treasury_interest_path = (
        Path(args.treasury_interest_file)
        if args.treasury_interest_file
        else (paths.raw / "treasury__interest_expense.csv")
    )
    if args.download_treasury_interest or not treasury_interest_path.exists():
        treasury_interest_path = ensure_treasury_interest_expense_file(
            treasury_interest_path,
            raw_dir=paths.raw,
            project_root=paths.root,
        )
    out_csv = Path(args.out) if args.out else (paths.processed / "bill_discount_validation.csv")
    out_md = Path(args.markdown_out) if args.markdown_out else (paths.processed / "bill_discount_validation.md")
    written_csv, written_md = write_bill_discount_validation(
        treasury_interest_path=treasury_interest_path,
        bank_proxy_path=Path(args.bank_proxy_file)
        if args.bank_proxy_file
        else (paths.raw / "support__bank_tsy_bill_discount_interest_proxy.csv"),
        row_proxy_path=Path(args.row_proxy_file)
        if args.row_proxy_file
        else (paths.raw / "support__row_tsy_bill_discount_interest_proxy.csv"),
        credit_union_proxy_path=Path(args.credit_union_proxy_file)
        if args.credit_union_proxy_file
        else (paths.raw / "support__credit_union_tsy_bill_discount_interest_proxy.csv"),
        out_csv_path=out_csv,
        out_markdown_path=out_md,
    )
    print(f"Wrote bill-discount validation table to {written_csv}")
    if written_md is not None:
        print(f"Wrote bill-discount validation summary to {written_md}")
    return 0


def cmd_treasury_interest_components(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    treasury_interest_path = (
        Path(args.treasury_interest_file)
        if args.treasury_interest_file
        else (paths.raw / "treasury__interest_expense.csv")
    )
    if args.download_treasury_interest or not treasury_interest_path.exists():
        treasury_interest_path = ensure_treasury_interest_expense_file(
            treasury_interest_path,
            raw_dir=paths.raw,
            project_root=paths.root,
        )
    out_csv = Path(args.out) if args.out else (paths.processed / "treasury_interest_component_pools_q.csv")
    out_md = (
        Path(args.markdown_out)
        if args.markdown_out
        else (paths.processed / "treasury_interest_component_pools_q.md")
    )
    written_csv, written_md = write_treasury_interest_component_pools(
        treasury_interest_path=treasury_interest_path,
        out_csv_path=out_csv,
        out_markdown_path=out_md,
    )
    print(f"Wrote Treasury interest component pools to {written_csv}")
    if written_md is not None:
        print(f"Wrote Treasury interest component summary to {written_md}")
    return 0


def cmd_bill_discount_allocation(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    treasury_interest_path = (
        Path(args.treasury_interest_file)
        if args.treasury_interest_file
        else (paths.raw / "treasury__interest_expense.csv")
    )
    if args.download_treasury_interest or not treasury_interest_path.exists():
        treasury_interest_path = ensure_treasury_interest_expense_file(
            treasury_interest_path,
            raw_dir=paths.raw,
            project_root=paths.root,
        )
    out_csv = Path(args.out) if args.out else (paths.processed / "sector_bill_discount_allocations.csv")
    out_md = (
        Path(args.markdown_out)
        if args.markdown_out
        else (paths.processed / "bill_discount_allocation_validation.md")
    )
    written_csv, written_md = write_bill_discount_allocation(
        treasury_interest_path=treasury_interest_path,
        bank_proxy_path=Path(args.bank_proxy_file)
        if args.bank_proxy_file
        else (paths.raw / "support__bank_tsy_bill_discount_interest_proxy.csv"),
        row_proxy_path=Path(args.row_proxy_file)
        if args.row_proxy_file
        else (paths.raw / "support__row_tsy_bill_discount_interest_proxy.csv"),
        credit_union_proxy_path=Path(args.credit_union_proxy_file)
        if args.credit_union_proxy_file
        else (paths.raw / "support__credit_union_tsy_bill_discount_interest_proxy.csv"),
        out_csv_path=out_csv,
        out_markdown_path=out_md,
    )
    print(f"Wrote bill-discount allocation diagnostic to {written_csv}")
    if written_md is not None:
        print(f"Wrote bill-discount allocation summary to {written_md}")
    return 0


def cmd_tier2_interest_component_candidate(args: argparse.Namespace) -> int:
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
            prefer_normalized_sector_panel=True,
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
            "Tier 2 interest component candidate requires explicit sector files or --wamest-root. Missing: "
            + ", ".join(missing)
        )
    treasury_interest_path = (
        Path(args.treasury_interest_file)
        if args.treasury_interest_file
        else (paths.raw / "treasury__interest_expense.csv")
    )
    if args.download_treasury_interest or not treasury_interest_path.exists():
        treasury_interest_path = ensure_treasury_interest_expense_file(
            treasury_interest_path,
            raw_dir=paths.raw,
            project_root=paths.root,
        )
    bill_wam_file = args.bill_wam_file
    if bill_wam_file is None and args.wamest_root is not None:
        candidate = Path(args.wamest_root) / "data" / "processed" / "treasury_bill_wam_support.csv"
        if candidate.exists():
            bill_wam_file = str(candidate)
    interest_allocation_weights_path = None
    component_bucket_weights_path = None
    if args.wamest_root is not None:
        contract_paths = resolve_wamest_interest_contract_paths(args.wamest_root)
        interest_allocation_weights_path = contract_paths["sector_interest_allocation_weights"]
        component_bucket_weights_path = contract_paths["sector_component_bucket_weights"]
    out_csv = Path(args.out) if args.out else (paths.processed / "tier2_interest_component_candidate.csv")
    out_md = (
        Path(args.markdown_out)
        if args.markdown_out
        else (paths.processed / "tier2_interest_component_candidate.md")
    )
    current_proxy_paths = {
        ("bank", "coupon_accrual"): paths.raw / "support__bank_tsy_coupon_interest_proxy.csv",
        ("row", "coupon_accrual"): paths.raw / "support__row_tsy_coupon_interest_proxy.csv",
        ("credit_union", "coupon_accrual"): paths.raw / "support__credit_union_tsy_coupon_interest_proxy.csv",
        ("bank", "bill_amortized_discount"): paths.raw / "support__bank_tsy_bill_discount_interest_proxy.csv",
        ("row", "bill_amortized_discount"): paths.raw / "support__row_tsy_bill_discount_interest_proxy.csv",
        (
            "credit_union",
            "bill_amortized_discount",
        ): paths.raw / "support__credit_union_tsy_bill_discount_interest_proxy.csv",
    }
    written_csv, written_md = write_tier2_interest_component_candidate(
        treasury_interest_path=treasury_interest_path,
        sector_maturity_path=sector_maturity_file,
        sector_panel_path=sector_panel_file,
        curve_path=curve_file,
        bill_wam_path=bill_wam_file,
        fed_components_path=args.fed_components_file
        or (paths.raw / "support__fed_treasury_interest_components.csv"),
        interest_allocation_weights_path=interest_allocation_weights_path,
        component_bucket_weights_path=component_bucket_weights_path,
        source_constraints_path=args.source_constraints_file
        or (paths.processed / "tier2_interest_source_constraints.csv"),
        current_proxy_paths=current_proxy_paths,
        out_csv_path=out_csv,
        out_markdown_path=out_md,
    )
    print(f"Wrote Tier 2 interest component candidate to {written_csv}")
    if written_md is not None:
        print(f"Wrote Tier 2 interest component candidate summary to {written_md}")
    return 0


def cmd_interest_source_constraints(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_csv = Path(args.out) if args.out else (paths.processed / "tier2_interest_source_constraints.csv")
    out_md = (
        Path(args.markdown_out)
        if args.markdown_out
        else (paths.processed / "tier2_interest_source_constraints.md")
    )
    wamest_root = _existing_path(os.getenv("WAMEST_ROOT"), paths.root.parent / "wamest")
    default_ffiec = paths.processed / "ffiec_interest_constraints_normalized.csv"
    bank_ffiec_path = args.bank_ffiec_file or _existing_path(
        default_ffiec,
        (wamest_root / "data" / "external" / "normalized" / "ffiec_call_reports_ffiec.csv")
        if wamest_root is not None
        else None,
    )
    default_ncua = paths.processed / "ncua_interest_constraints_normalized.csv"
    credit_union_ncua_path = args.credit_union_ncua_file or _existing_path(
        default_ncua,
        (wamest_root / "data" / "external" / "normalized" / "ncua_call_reports_ncua.csv")
        if wamest_root is not None
        else None,
    )
    row_tic_path = args.row_tic_file or _existing_path(
        os.getenv("TDCEST_ROW_TIC_FILE"),
        paths.root.parent / "tgarefill" / "data" / "raw" / "treasury_home" / "tic" / "slt_table3.txt",
    )
    written_csv, written_md, _ = write_interest_source_constraints(
        out_path=out_csv,
        markdown_out_path=out_md,
        bank_ffiec_path=bank_ffiec_path,
        credit_union_ncua_path=credit_union_ncua_path,
        mmf_path=args.mmf_file or (paths.raw / "support__mmf_fund_month.csv"),
        row_tic_path=row_tic_path,
    )
    print(f"Wrote Tier 2 interest source constraints to {written_csv}")
    print(f"Wrote Tier 2 interest source constraint summary to {written_md}")
    return 0


def cmd_ffiec_interest_constraints(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_csv = Path(args.out) if args.out else (paths.processed / "ffiec_interest_constraints_normalized.csv")
    extracted_root = args.extracted_root or _existing_path(
        os.getenv("TDCEST_FFIEC_EXTRACTED_ROOT"),
        paths.root.parent / "slrwatch" / "data" / "staging" / "call_reports",
    )
    if extracted_root is None:
        raise ValueError(
            "FFIEC constraints require --extracted-root, TDCEST_FFIEC_EXTRACTED_ROOT, "
            "or a sibling slrwatch checkout with data/staging/call_reports."
        )
    written_csv, frame = write_ffiec_interest_constraints_from_extracted_root(
        extracted_root=extracted_root,
        out_path=out_csv,
    )
    print(f"Wrote normalized FFIEC interest constraints to {written_csv} ({len(frame):,} rows)")
    return 0


def cmd_ncua_interest_constraints(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_csv = Path(args.out) if args.out else (paths.processed / "ncua_interest_constraints_normalized.csv")
    written_csv, frame = write_ncua_interest_constraints_from_cache(
        cache_dir=args.cache_dir or (paths.raw / "_cache_ncua_call_report"),
        out_path=out_csv,
    )
    print(f"Wrote normalized NCUA interest constraints to {written_csv} ({len(frame):,} rows)")
    return 0


def cmd_interest_source_window_validation(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_csv = Path(args.out) if args.out else (paths.processed / "tier2_interest_source_window_validation.csv")
    out_md = (
        Path(args.markdown_out)
        if args.markdown_out
        else (paths.processed / "tier2_interest_source_window_validation.md")
    )
    written_csv, written_md, _ = write_interest_source_window_validation(
        candidate_path=args.candidate_file or (paths.processed / "tier2_interest_component_candidate.csv"),
        constraints_path=args.source_constraints_file or (paths.processed / "tier2_interest_source_constraints.csv"),
        out_path=out_csv,
        markdown_out_path=out_md,
    )
    print(f"Wrote Tier 2 interest source-window validation to {written_csv}")
    print(f"Wrote Tier 2 interest source-window validation summary to {written_md}")
    return 0


def cmd_tier2_interest_default_switch_review(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_csv = Path(args.out) if args.out else (paths.processed / "tier2_interest_default_switch_review.csv")
    out_md = (
        Path(args.markdown_out)
        if args.markdown_out
        else (paths.processed / "tier2_interest_default_switch_review.md")
    )
    written_csv, written_md, _ = write_tier2_interest_default_switch_review(
        candidate_path=args.candidate_file or (paths.processed / "tier2_interest_component_candidate.csv"),
        source_window_validation_path=args.source_window_validation_file
        or (paths.processed / "tier2_interest_source_window_validation.csv"),
        component_pools_path=args.component_pools_file or (paths.processed / "treasury_interest_component_pools_q.csv"),
        tips_treatment_decision_path=args.tips_treatment_decision_file
        or (paths.processed / "tier2_tips_treatment_decision.csv"),
        csv_path=out_csv,
        markdown_path=out_md,
    )
    print(f"Wrote Tier 2 interest default-switch review to {written_csv}")
    print(f"Wrote Tier 2 interest default-switch summary to {written_md}")
    return 0


def cmd_tier2_tips_treatment_decision(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out_csv = Path(args.out) if args.out else (paths.processed / "tier2_tips_treatment_decision.csv")
    out_md = (
        Path(args.markdown_out)
        if args.markdown_out
        else (paths.processed / "tier2_tips_treatment_decision.md")
    )
    written_csv, written_md, _ = write_tier2_tips_treatment_decision(
        component_pools_path=args.component_pools_file or (paths.processed / "treasury_interest_component_pools_q.csv"),
        csv_path=out_csv,
        markdown_path=out_md,
    )
    print(f"Wrote Tier 2 TIPS treatment decision to {written_csv}")
    print(f"Wrote Tier 2 TIPS treatment decision summary to {written_md}")
    return 0


def cmd_tier2_component_support_export(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    written_paths, written_md, _ = write_tier2_component_support_exports(
        candidate_path=args.candidate_file or (paths.processed / "tier2_interest_component_candidate.csv"),
        out_dir=args.out_dir or paths.raw,
        markdown_path=args.markdown_out
        or (paths.processed / "tier2_component_anchored_support_exports.md"),
    )
    for sector, path in written_paths.items():
        print(f"Wrote Tier 2 component support export for {sector} to {path}")
    print(f"Wrote Tier 2 component support export summary to {written_md}")
    return 0


def cmd_tier2_regression_backcast(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    legacy_proxy_paths = {
        "bank_tsy_coupon_interest_proxy": paths.raw / "support__bank_tsy_coupon_interest_proxy.csv",
        "bank_tsy_bill_discount_interest_proxy": paths.raw / "support__bank_tsy_bill_discount_interest_proxy.csv",
        "row_tsy_coupon_interest_proxy": paths.raw / "support__row_tsy_coupon_interest_proxy.csv",
        "row_tsy_bill_discount_interest_proxy": paths.raw / "support__row_tsy_bill_discount_interest_proxy.csv",
        "credit_union_tsy_coupon_interest_proxy": paths.raw / "support__credit_union_tsy_coupon_interest_proxy.csv",
        "credit_union_tsy_bill_discount_interest_proxy": paths.raw
        / "support__credit_union_tsy_bill_discount_interest_proxy.csv",
    }
    csv_path, md_path, _ = write_tier2_regression_backcast(
        candidate_path=args.candidate_file or (paths.processed / "tier2_interest_component_candidate.csv"),
        legacy_proxy_paths=legacy_proxy_paths,
        out_csv_path=args.out or (paths.processed / "tier2_regression_interest_backcast.csv"),
        out_markdown_path=args.markdown_out or (paths.processed / "tier2_regression_interest_backcast.md"),
        out_wide_csv_path=args.wide_out or (paths.processed / "tier2_regression_interest_backcast_wide.csv"),
    )
    print(f"Wrote Tier 2 regression interest backcast to {csv_path}")
    print(f"Wrote Tier 2 regression interest backcast summary to {md_path}")
    return 0


def cmd_tier2_regression_series(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    csv_path, md_path, _ = write_tier2_regression_series(
        estimates_path=args.estimates_file or (paths.processed / "tdc_estimates.csv"),
        components_path=args.components_file or (paths.processed / "tdc_components.csv"),
        regression_backcast_wide_path=args.backcast_wide_file
        or (paths.processed / "tier2_regression_interest_backcast_wide.csv"),
        out_csv_path=args.out or (paths.processed / "tdc_tier2_regression_series.csv"),
        out_markdown_path=args.markdown_out or (paths.processed / "tdc_tier2_regression_series.md"),
    )
    print(f"Wrote Tier 2 regression-corrected TDC series to {csv_path}")
    print(f"Wrote Tier 2 regression-corrected TDC summary to {md_path}")
    return 0


def cmd_tier2_component_anchor_comparison(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    comparison_csv, comparison_md, acceptance_md, _ = write_tier2_component_anchor_comparison(
        estimates_path=args.estimates_file or (paths.processed / "tdc_estimates.csv"),
        comparison_csv_path=args.out or (paths.processed / "tier2_component_anchored_estimator_comparison.csv"),
        comparison_markdown_path=args.markdown_out
        or (paths.processed / "tier2_component_anchored_estimator_comparison.md"),
        acceptance_markdown_path=args.acceptance_out
        or (paths.processed / "tier2_component_anchored_promotion_acceptance.md"),
        default_switch_review_path=args.default_switch_review_file
        or (paths.processed / "tier2_interest_default_switch_review.csv"),
        default_decision_path=args.default_decision_file
        or (paths.processed / "tier2_component_anchored_default_decision.csv"),
    )
    print(f"Wrote Tier 2 component estimator comparison to {comparison_csv}")
    print(f"Wrote Tier 2 component estimator comparison summary to {comparison_md}")
    print(f"Wrote Tier 2 component promotion acceptance memo to {acceptance_md}")
    return 0


def cmd_fed_component_extension_export(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    csv_path, md_path, _ = write_fed_component_extension_support(
        fed_components_path=args.fed_components_file
        or (paths.raw / "support__fed_treasury_interest_components.csv"),
        out_path=args.out or (paths.raw / "support__fed_tier1_component_extension_proxy.csv"),
        markdown_path=args.markdown_out or (paths.processed / "fed_tier1_component_extension_support.md"),
    )
    print(f"Wrote Fed Tier 1 component extension support to {csv_path}")
    print(f"Wrote Fed Tier 1 component extension summary to {md_path}")
    return 0


def cmd_tier2_component_default_decision(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    cu_split_path = (
        Path(args.cu_split_sensitivity_file)
        if args.cu_split_sensitivity_file
        else (paths.processed / "tier2_cu_split_sensitivity.csv")
    )
    live_delta_path = (
        Path(args.live_delta_acceptance_file)
        if args.live_delta_acceptance_file
        else (paths.processed / "tier2_live_delta_acceptance.csv")
    )
    csv_path, md_path, _ = write_tier2_component_default_decision(
        default_switch_review_path=args.default_switch_review_file
        or (paths.processed / "tier2_interest_default_switch_review.csv"),
        comparison_path=args.comparison_file
        or (paths.processed / "tier2_component_anchored_estimator_comparison.csv"),
        cu_split_sensitivity_path=cu_split_path if cu_split_path.exists() else None,
        live_delta_acceptance_path=live_delta_path if live_delta_path.exists() else None,
        out_csv_path=args.out or (paths.processed / "tier2_component_anchored_default_decision.csv"),
        out_markdown_path=args.markdown_out
        or (paths.processed / "tier2_component_anchored_default_decision.md"),
    )
    print(f"Wrote Tier 2 component default decision to {csv_path}")
    print(f"Wrote Tier 2 component default decision summary to {md_path}")
    return 0


def cmd_tier2_component_delta_attribution(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    csv_path, md_path, _ = write_tier2_component_delta_attribution(
        candidate_path=args.candidate_file or (paths.processed / "tier2_interest_component_candidate.csv"),
        out_csv_path=args.out or (paths.processed / "tier2_component_delta_attribution.csv"),
        out_markdown_path=args.markdown_out or (paths.processed / "tier2_component_delta_attribution.md"),
    )
    print(f"Wrote Tier 2 component delta attribution to {csv_path}")
    print(f"Wrote Tier 2 component delta attribution summary to {md_path}")
    return 0


def cmd_tier2_cu_split_sensitivity(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    csv_path, md_path, _ = write_tier2_cu_split_sensitivity(
        candidate_path=args.candidate_file or (paths.processed / "tier2_interest_component_candidate.csv"),
        ncua_constraints_path=args.ncua_constraints_file
        or (paths.processed / "ncua_interest_constraints_normalized.csv"),
        out_csv_path=args.out or (paths.processed / "tier2_cu_split_sensitivity.csv"),
        out_markdown_path=args.markdown_out or (paths.processed / "tier2_cu_split_sensitivity.md"),
    )
    print(f"Wrote Tier 2 CU split sensitivity to {csv_path}")
    print(f"Wrote Tier 2 CU split sensitivity summary to {md_path}")
    return 0


def cmd_tier2_live_delta_acceptance(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    csv_path, md_path, _ = write_tier2_live_delta_acceptance(
        delta_attribution_path=args.delta_attribution_file
        or (paths.processed / "tier2_component_delta_attribution.csv"),
        out_csv_path=args.out or (paths.processed / "tier2_live_delta_acceptance.csv"),
        out_markdown_path=args.markdown_out or (paths.processed / "tier2_live_delta_acceptance.md"),
    )
    print(f"Wrote Tier 2 live delta acceptance to {csv_path}")
    print(f"Wrote Tier 2 live delta acceptance summary to {md_path}")
    return 0


def cmd_tdc_empirical_anchor(args: argparse.Namespace) -> int:
    paths = project_paths(args.root)
    ensure_project_dirs(paths)
    out, manifest, _, _ = write_tdc_empirical_anchor(
        processed_dir=paths.processed,
        estimates_file=args.estimates_file,
        components_file=args.components_file,
        method_meta_file=args.method_meta_file,
        out=args.out,
        manifest_out=args.manifest_out,
    )
    print(f"Wrote TDC empirical anchor to {out} and {manifest}")
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
    p_download.add_argument("--include-mmf-support", action="store_true", help="Also download OFR aggregate MMF support data for the MMF/RRP adjustment.")
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
    p_build.add_argument("--include-mmf-support", action="store_true", help="Also download OFR aggregate MMF support data for the MMF/RRP adjustment.")
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

    p_fed_components = sub.add_parser(
        "fed-interest-components",
        parents=[root_parent],
        help="Build Fed Treasury interest component support from SOMA holdings, with non-coupon placeholders.",
    )
    p_fed_components.add_argument(
        "--soma-file",
        nargs="+",
        default=None,
        help="One or more CSV files containing SOMA Treasury holdings snapshots.",
    )
    p_fed_components.add_argument(
        "--wamest-root",
        default=None,
        help="Optional wamest repo root. If provided, the conventional normalized SOMA artifact is inferred.",
    )
    p_fed_components.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/support__fed_treasury_interest_components.csv under --root.",
    )
    p_fed_components.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/fed_treasury_interest_components.md under --root.",
    )
    p_fed_components.add_argument(
        "--auction-file",
        default=None,
        help="Optional Treasury auction/security master CSV for SOMA bill-discount accrual.",
    )
    p_fed_components.add_argument(
        "--frn-index-file",
        default=None,
        help="Optional FiscalData FRN daily indexes CSV for SOMA FRN interest accrual.",
    )
    p_fed_components.set_defaults(func=cmd_fed_interest_components)

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
        "--credit-union-out",
        default=None,
        help="Output CSV path for the credit-union proxy. Defaults to data/raw/support__credit_union_tsy_coupon_interest_proxy.csv under --root.",
    )
    p_tier2_coupon.add_argument(
        "--include-bill-discount",
        action="store_true",
        help="Also write bill-discount interest robustness proxies for bank, ROW, and credit-union sectors.",
    )
    p_tier2_coupon.add_argument(
        "--bill-wam-file",
        default=None,
        help="Optional Treasury bill weighted-average-maturity support file. Defaults to wamest data/processed/treasury_bill_wam_support.csv when --wamest-root is supplied.",
    )
    p_tier2_coupon.add_argument(
        "--bank-bill-out",
        default=None,
        help="Output CSV path for bank bill-discount robustness proxy. Defaults to data/raw/support__bank_tsy_bill_discount_interest_proxy.csv under --root.",
    )
    p_tier2_coupon.add_argument(
        "--row-bill-out",
        default=None,
        help="Output CSV path for ROW bill-discount robustness proxy. Defaults to data/raw/support__row_tsy_bill_discount_interest_proxy.csv under --root.",
    )
    p_tier2_coupon.add_argument(
        "--credit-union-bill-out",
        default=None,
        help="Output CSV path for credit-union bill-discount robustness proxy. Defaults to data/raw/support__credit_union_tsy_bill_discount_interest_proxy.csv under --root.",
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
    p_tier2_coupon.add_argument(
        "--credit-union-sector-key",
        action="append",
        default=None,
        help="Optional credit-union sector key override. Repeat to specify multiple sectors. Defaults to credit_unions_marketable_proxy.",
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

    p_mmf_rrp = sub.add_parser(
        "mmf-rrp-support",
        parents=[root_parent],
        help="Build the MMF/RRP support file from the OFR aggregate MMF dataset.",
    )
    p_mmf_rrp.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/support__mmf_fund_month.csv under --root.",
    )
    p_mmf_rrp.add_argument(
        "--no-raw-json",
        action="store_true",
        help="Do not save the raw OFR MMF dataset JSON alongside the support CSV.",
    )
    p_mmf_rrp.set_defaults(func=cmd_mmf_rrp_support)

    p_sec_nmfp = sub.add_parser(
        "sec-nmfp-mmf-support",
        parents=[root_parent],
        help="Build a fund-month MMF/RRP support file from SEC Form N-MFP ZIP files.",
    )
    p_sec_nmfp.add_argument(
        "--zip",
        action="append",
        default=[],
        help="SEC N-MFP ZIP file to include. May be passed more than once.",
    )
    p_sec_nmfp.add_argument(
        "--download",
        action="store_true",
        help="Download SEC N-MFP ZIPs for --start/--end into the cache directory before building support.",
    )
    p_sec_nmfp.add_argument("--start", default="2013-09-30", help="First SEC N-MFP report month to download.")
    p_sec_nmfp.add_argument("--end", default="2025-12-31", help="Last SEC N-MFP report month to download.")
    p_sec_nmfp.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for downloaded SEC N-MFP ZIPs. Defaults to data/raw/sec_nmfp_cache under --root.",
    )
    p_sec_nmfp.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/support__mmf_fund_month.csv under --root.",
    )
    p_sec_nmfp.set_defaults(func=cmd_sec_nmfp_mmf_support)

    p_mmf_route_split = sub.add_parser(
        "mmf-route-split-context",
        parents=[root_parent],
        help="Export SEC N-MFP retail/institutional MMF Treasury and ON-RRP route context.",
    )
    p_mmf_route_split.add_argument(
        "--zip",
        action="append",
        default=[],
        help="SEC N-MFP ZIP file to include. May be passed more than once.",
    )
    p_mmf_route_split.add_argument(
        "--download",
        action="store_true",
        help="Download SEC N-MFP ZIPs for --start/--end into the cache directory before building context.",
    )
    p_mmf_route_split.add_argument(
        "--start",
        default="2013-09-30",
        help="First SEC N-MFP report month to download.",
    )
    p_mmf_route_split.add_argument(
        "--end",
        default="2025-12-31",
        help="Last SEC N-MFP report month to download.",
    )
    p_mmf_route_split.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for SEC N-MFP ZIPs. Defaults to data/raw/sec_nmfp_cache under --root.",
    )
    p_mmf_route_split.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tdc_mmf_route_split_context.csv.",
    )
    p_mmf_route_split.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tdc_mmf_route_split_context.md.",
    )
    p_mmf_route_split.set_defaults(func=cmd_mmf_route_split_context)

    p_route_admissibility = sub.add_parser(
        "route-admissibility-registry",
        parents=[root_parent],
        help="Export quarterless route admissibility guardrails for TDC/RateWall route use.",
    )
    p_route_admissibility.add_argument(
        "--monetary-route-bridge-file",
        default=None,
        help="Monetary route bridge CSV. Defaults to data/processed/tdc_domestic_nonbank_monetary_route_bridge.csv.",
    )
    p_route_admissibility.add_argument(
        "--mmf-route-split-context-file",
        default=None,
        help="MMF route split context CSV. Defaults to data/processed/tdc_mmf_route_split_context.csv.",
    )
    p_route_admissibility.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tdc_route_admissibility_registry.csv.",
    )
    p_route_admissibility.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tdc_route_admissibility_registry.md.",
    )
    p_route_admissibility.set_defaults(func=cmd_route_admissibility_registry)

    p_z1_nonbank_sector = sub.add_parser(
        "z1-domestic-nonbank-sector-context",
        parents=[root_parent],
        help="Export Z.1 domestic nonbank sector Treasury holder context.",
    )
    p_z1_nonbank_sector.add_argument(
        "--z1-holder-absorption-file",
        default=None,
        help="Z.1 exact holder absorption CSV. Defaults to sibling tdcmix processed outputs.",
    )
    p_z1_nonbank_sector.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tdc_z1_domestic_nonbank_sector_context.csv.",
    )
    p_z1_nonbank_sector.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tdc_z1_domestic_nonbank_sector_context.md.",
    )
    p_z1_nonbank_sector.set_defaults(func=cmd_z1_domestic_nonbank_sector_context)

    p_tdcsim_private_route = sub.add_parser(
        "tdcsim-private-route-allocation-sensitivity",
        parents=[root_parent],
        help="Export bounded noncanonical TDCSim Private route sensitivity rows.",
    )
    p_tdcsim_private_route.add_argument(
        "--z1-flow-file",
        default=None,
        help="Z.1 F.210 holder absorption CSV. Defaults to sibling tdcmix processed outputs.",
    )
    p_tdcsim_private_route.add_argument(
        "--z1-stock-file",
        default=None,
        help="Z.1 L.210 holder stock CSV. Defaults to sibling tsyparty/wamest outputs.",
    )
    p_tdcsim_private_route.add_argument(
        "--mmf-route-split-context-file",
        default=None,
        help="MMF route split context CSV. Defaults to data/processed/tdc_mmf_route_split_context.csv.",
    )
    p_tdcsim_private_route.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tdc_tdcsim_private_route_allocation_sensitivity.csv.",
    )
    p_tdcsim_private_route.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tdc_tdcsim_private_route_allocation_sensitivity.md.",
    )
    p_tdcsim_private_route.add_argument(
        "--support-contract-out",
        default=None,
        help="Output support-contract CSV path. Defaults to data/processed/tdc_tdcsim_private_route_support_contract.csv.",
    )
    p_tdcsim_private_route.set_defaults(
        func=cmd_tdcsim_private_route_allocation_sensitivity
    )

    p_fed_remit_mts = sub.add_parser(
        "fed-remit-mts-support",
        parents=[root_parent],
        help="Build Fed remittance cash-flow support from Monthly Treasury Statement Table 4 PDFs.",
    )
    p_fed_remit_mts.add_argument("--start", default="2002-01-31", help="First MTS month to parse.")
    p_fed_remit_mts.add_argument("--end", default="2025-12-31", help="Last MTS month to parse.")
    p_fed_remit_mts.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for downloaded MTS PDFs. Defaults to data/raw/mts_pdf_cache under --root.",
    )
    p_fed_remit_mts.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/support__fed_remit_mts.csv under --root.",
    )
    p_fed_remit_mts.set_defaults(func=cmd_fed_remit_mts_support)

    p_mts_previous = sub.add_parser(
        "mts-previous-issues-manifest",
        parents=[root_parent],
        help="Build the pre-FiscalData Monthly Treasury Statement previous-issues manifest.",
    )
    p_mts_previous.add_argument("--start", default="2003-01-31", help="First MTS issue month-end to inventory.")
    p_mts_previous.add_argument("--end", default="2015-02-28", help="Last pre-FiscalData issue month-end to inventory.")
    p_mts_previous.add_argument(
        "--cache-dir",
        default=None,
        help="Directory for previous-issue MTS cache paths. Defaults to data/raw/mts_previous_issues under --root.",
    )
    p_mts_previous.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/treasury__mts_previous_issues_manifest.csv under --root.",
    )
    p_mts_previous.set_defaults(func=cmd_mts_previous_issues_manifest)

    p_mts_table5_history = sub.add_parser(
        "mts-table5-target-history",
        parents=[root_parent],
        help="Parse cached pre-FiscalData MTS previous-issue text for selected Table 5 target lines.",
    )
    p_mts_table5_history.add_argument(
        "--manifest",
        default=None,
        help="Previous-issues manifest CSV. Defaults to data/raw/treasury__mts_previous_issues_manifest.csv under --root.",
    )
    p_mts_table5_history.add_argument(
        "--download-missing-text",
        action="store_true",
        help="Download/extract PDFs for rows whose text cache is missing. Without this, only cached text is parsed.",
    )
    p_mts_table5_history.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/treasury__mts_table5_target_history.csv under --root.",
    )
    p_mts_table5_history.set_defaults(func=cmd_mts_table5_target_history)

    p_mts_table4_history = sub.add_parser(
        "mts-table4-target-history",
        parents=[root_parent],
        help="Parse cached pre-FiscalData MTS previous-issue text for selected Table 4 target lines.",
    )
    p_mts_table4_history.add_argument(
        "--manifest",
        default=None,
        help="Previous-issues manifest CSV. Defaults to data/raw/treasury__mts_previous_issues_manifest.csv under --root.",
    )
    p_mts_table4_history.add_argument(
        "--download-missing-text",
        action="store_true",
        help="Download/extract PDFs for rows whose text cache is missing. Without this, only cached text is parsed.",
    )
    p_mts_table4_history.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/treasury__mts_table4_target_history.csv under --root.",
    )
    p_mts_table4_history.set_defaults(func=cmd_mts_table4_target_history)

    p_mts_table4_receipts = sub.add_parser(
        "mts-table4-target-receipts",
        parents=[root_parent],
        help="Convert parsed MTS Table 4 target history from printed millions to FiscalData-style dollar receipt columns.",
    )
    p_mts_table4_receipts.add_argument(
        "--history",
        default=None,
        help="Parsed Table 4 target-history CSV. Defaults to data/raw/treasury__mts_table4_target_history.csv under --root.",
    )
    p_mts_table4_receipts.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/treasury__mts_receipts_previous_targets.csv under --root.",
    )
    p_mts_table4_receipts.set_defaults(func=cmd_mts_table4_target_receipts)

    p_mts_table5_outlays = sub.add_parser(
        "mts-table5-target-outlays",
        parents=[root_parent],
        help="Convert parsed MTS Table 5 target history from printed millions to FiscalData-style dollar outlay columns.",
    )
    p_mts_table5_outlays.add_argument(
        "--history",
        default=None,
        help="Parsed Table 5 target-history CSV. Defaults to data/raw/treasury__mts_table5_target_history.csv under --root.",
    )
    p_mts_table5_outlays.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/treasury__mts_outlays_previous_targets.csv under --root.",
    )
    p_mts_table5_outlays.set_defaults(func=cmd_mts_table5_target_outlays)

    p_mts_stitched_receipts = sub.add_parser(
        "mts-stitched-target-receipts",
        parents=[root_parent],
        help="Stitch historical MTS target receipts with current FiscalData MTS receipts.",
    )
    p_mts_stitched_receipts.add_argument(
        "--previous-targets",
        default=None,
        help="Historical target receipts CSV. Defaults to data/raw/treasury__mts_receipts_previous_targets.csv under --root.",
    )
    p_mts_stitched_receipts.add_argument(
        "--fiscaldata",
        default=None,
        help="FiscalData MTS receipts CSV. Defaults to data/raw/treasury__mts_receipts.csv under --root.",
    )
    p_mts_stitched_receipts.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/treasury__mts_receipts_stitched_targets.csv under --root.",
    )
    p_mts_stitched_receipts.set_defaults(func=cmd_mts_stitched_target_receipts)

    p_mts_stitched_outlays = sub.add_parser(
        "mts-stitched-target-outlays",
        parents=[root_parent],
        help="Stitch historical MTS target outlays with current FiscalData MTS outlays.",
    )
    p_mts_stitched_outlays.add_argument(
        "--previous-targets",
        default=None,
        help="Historical target outlays CSV. Defaults to data/raw/treasury__mts_outlays_previous_targets.csv under --root.",
    )
    p_mts_stitched_outlays.add_argument(
        "--fiscaldata",
        default=None,
        help="FiscalData MTS outlays CSV. Defaults to data/raw/treasury__mts_outlays.csv under --root.",
    )
    p_mts_stitched_outlays.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/treasury__mts_outlays_stitched_targets.csv under --root.",
    )
    p_mts_stitched_outlays.set_defaults(func=cmd_mts_stitched_target_outlays)

    p_mts_previous_coverage = sub.add_parser(
        "mts-previous-issue-coverage",
        parents=[root_parent],
        help="Write a coverage report for parsed pre-FiscalData MTS previous issues.",
    )
    p_mts_previous_coverage.add_argument("--manifest", default=None, help="Previous-issues manifest CSV.")
    p_mts_previous_coverage.add_argument("--table4-history", default=None, help="Parsed Table 4 target-history CSV.")
    p_mts_previous_coverage.add_argument("--table5-history", default=None, help="Parsed Table 5 target-history CSV.")
    p_mts_previous_coverage.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/mts_previous_issue_coverage_report.csv under --root.",
    )
    p_mts_previous_coverage.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/mts_previous_issue_coverage_report.md under --root.",
    )
    p_mts_previous_coverage.set_defaults(func=cmd_mts_previous_issue_coverage)

    p_mts_overlap = sub.add_parser(
        "mts-target-overlap-audit",
        parents=[root_parent],
        help="Compare parsed MTS previous-issue target lines against FiscalData rows in an overlap window.",
    )
    p_mts_overlap.add_argument("--table4-history", default=None, help="Parsed overlap Table 4 target-history CSV.")
    p_mts_overlap.add_argument("--table5-history", default=None, help="Parsed overlap Table 5 target-history CSV.")
    p_mts_overlap.add_argument("--table4-fiscaldata", default=None, help="FiscalData MTS Table 4 receipts CSV.")
    p_mts_overlap.add_argument("--table5-fiscaldata", default=None, help="FiscalData MTS Table 5 outlays CSV.")
    p_mts_overlap.add_argument(
        "--tolerance-dollars",
        type=float,
        default=500_000.0,
        help="Allowed absolute difference from published whole-million PDF rounding. Defaults to 500,000.",
    )
    p_mts_overlap.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/mts_target_overlap_audit.csv under --root.",
    )
    p_mts_overlap.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/mts_target_overlap_audit.md under --root.",
    )
    p_mts_overlap.set_defaults(func=cmd_mts_target_overlap_audit)

    p_gse_rrp = sub.add_parser(
        "gse-on-rrp-support",
        parents=[root_parent],
        help="Build quarter-end GSE ON RRP support from the NY Fed reverse-repo propositions API.",
    )
    p_gse_rrp.add_argument("--start", default="2013-09-23", help="First operation date to request.")
    p_gse_rrp.add_argument("--end", default="2025-12-31", help="Last operation date to request.")
    p_gse_rrp.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/support__gse_on_rrp.csv under --root.",
    )
    p_gse_rrp.add_argument(
        "--no-raw-json",
        action="store_true",
        help="Do not save the raw NY Fed JSON response alongside the support CSV.",
    )
    p_gse_rrp.set_defaults(func=cmd_gse_on_rrp_support)

    p_bill_validation = sub.add_parser(
        "bill-discount-validation",
        parents=[root_parent],
        help="Validate sector bill-discount interest proxies against Treasury aggregate bill amortized discount.",
    )
    p_bill_validation.add_argument(
        "--treasury-interest-file",
        default=None,
        help="FiscalData interest-expense CSV. Defaults to data/raw/treasury__interest_expense.csv under --root.",
    )
    p_bill_validation.add_argument(
        "--download-treasury-interest",
        action="store_true",
        help="Download the FiscalData interest-expense file before writing the validation output.",
    )
    p_bill_validation.add_argument(
        "--bank-proxy-file",
        default=None,
        help="Bank bill-discount proxy CSV. Defaults to data/raw/support__bank_tsy_bill_discount_interest_proxy.csv under --root.",
    )
    p_bill_validation.add_argument(
        "--row-proxy-file",
        default=None,
        help="ROW bill-discount proxy CSV. Defaults to data/raw/support__row_tsy_bill_discount_interest_proxy.csv under --root.",
    )
    p_bill_validation.add_argument(
        "--credit-union-proxy-file",
        default=None,
        help="Credit-union bill-discount proxy CSV. Defaults to data/raw/support__credit_union_tsy_bill_discount_interest_proxy.csv under --root.",
    )
    p_bill_validation.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/bill_discount_validation.csv under --root.",
    )
    p_bill_validation.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown summary path. Defaults to data/processed/bill_discount_validation.md under --root.",
    )
    p_bill_validation.set_defaults(func=cmd_bill_discount_validation)

    p_interest_components = sub.add_parser(
        "treasury-interest-components",
        parents=[root_parent],
        help="Build a quarterly component ledger from Treasury interest-expense rows.",
    )
    p_interest_components.add_argument(
        "--treasury-interest-file",
        default=None,
        help="FiscalData interest-expense CSV. Defaults to data/raw/treasury__interest_expense.csv under --root.",
    )
    p_interest_components.add_argument(
        "--download-treasury-interest",
        action="store_true",
        help="Download the FiscalData interest-expense file before writing the component ledger.",
    )
    p_interest_components.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/treasury_interest_component_pools_q.csv under --root.",
    )
    p_interest_components.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown summary path. Defaults to data/processed/treasury_interest_component_pools_q.md under --root.",
    )
    p_interest_components.set_defaults(func=cmd_treasury_interest_components)

    p_bill_allocation = sub.add_parser(
        "bill-discount-allocation",
        parents=[root_parent],
        help="Build a conservative bill-discount allocation diagnostic with an explicit residual.",
    )
    p_bill_allocation.add_argument(
        "--treasury-interest-file",
        default=None,
        help="FiscalData interest-expense CSV. Defaults to data/raw/treasury__interest_expense.csv under --root.",
    )
    p_bill_allocation.add_argument(
        "--download-treasury-interest",
        action="store_true",
        help="Download the FiscalData interest-expense file before writing the allocation diagnostic.",
    )
    p_bill_allocation.add_argument(
        "--bank-proxy-file",
        default=None,
        help="Bank bill-discount proxy CSV. Defaults to data/raw/support__bank_tsy_bill_discount_interest_proxy.csv under --root.",
    )
    p_bill_allocation.add_argument(
        "--row-proxy-file",
        default=None,
        help="ROW bill-discount proxy CSV. Defaults to data/raw/support__row_tsy_bill_discount_interest_proxy.csv under --root.",
    )
    p_bill_allocation.add_argument(
        "--credit-union-proxy-file",
        default=None,
        help="Credit-union bill-discount proxy CSV. Defaults to data/raw/support__credit_union_tsy_bill_discount_interest_proxy.csv under --root.",
    )
    p_bill_allocation.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/sector_bill_discount_allocations.csv under --root.",
    )
    p_bill_allocation.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown summary path. Defaults to data/processed/bill_discount_allocation_validation.md under --root.",
    )
    p_bill_allocation.set_defaults(func=cmd_bill_discount_allocation)

    p_tier2_component_candidate = sub.add_parser(
        "tier2-interest-component-candidate",
        parents=[root_parent],
        help="Build the Tier 2 component-anchored interest allocation that feeds promoted canonical rows.",
    )
    p_tier2_component_candidate.add_argument(
        "--treasury-interest-file",
        default=None,
        help="FiscalData interest-expense CSV. Defaults to data/raw/treasury__interest_expense.csv under --root.",
    )
    p_tier2_component_candidate.add_argument(
        "--download-treasury-interest",
        action="store_true",
        help="Download the FiscalData interest-expense file before writing the candidate output.",
    )
    p_tier2_component_candidate.add_argument(
        "--sector-maturity-file",
        default=None,
        help="CSV file containing sector-level coupon_share and coupon-only maturity rows.",
    )
    p_tier2_component_candidate.add_argument(
        "--sector-panel-file",
        default=None,
        help="CSV file containing sector-level Treasury holdings by quarter.",
    )
    p_tier2_component_candidate.add_argument(
        "--curve-file",
        default=None,
        help="Wide Treasury curve CSV with date and maturity columns.",
    )
    p_tier2_component_candidate.add_argument(
        "--wamest-root",
        default=None,
        help="Optional wamest repo root. If provided, conventional artifact paths are inferred.",
    )
    p_tier2_component_candidate.add_argument(
        "--bill-wam-file",
        default=None,
        help="Optional Treasury bill WAM support file. Defaults from wamest when --wamest-root is supplied.",
    )
    p_tier2_component_candidate.add_argument(
        "--fed-components-file",
        default=None,
        help="Fed component support CSV. Defaults to data/raw/support__fed_treasury_interest_components.csv.",
    )
    p_tier2_component_candidate.add_argument(
        "--source-constraints-file",
        default=None,
        help="Optional TIC/regulatory/MMF constraint CSV. Defaults to data/processed/tier2_interest_source_constraints.csv if present.",
    )
    p_tier2_component_candidate.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tier2_interest_component_candidate.csv under --root.",
    )
    p_tier2_component_candidate.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown summary path. Defaults to data/processed/tier2_interest_component_candidate.md.",
    )
    p_tier2_component_candidate.set_defaults(func=cmd_tier2_interest_component_candidate)

    p_interest_constraints = sub.add_parser(
        "tier2-interest-source-constraints",
        parents=[root_parent],
        help="Extract local TIC, regulatory, and MMF constraints for Tier 2 interest allocation.",
    )
    p_interest_constraints.add_argument(
        "--bank-ffiec-file",
        default=None,
        help="Normalized FFIEC Call Report Treasury/maturity file. Defaults to data/processed/ffiec_interest_constraints_normalized.csv when present, else WAMEST_ROOT or a sibling wamest checkout when available.",
    )
    p_interest_constraints.add_argument(
        "--credit-union-ncua-file",
        default=None,
        help="Normalized NCUA Call Report Treasury/maturity file. Defaults to data/processed/ncua_interest_constraints_normalized.csv when present, else WAMEST_ROOT or a sibling wamest checkout when available.",
    )
    p_interest_constraints.add_argument(
        "--mmf-file",
        default=None,
        help="MMF fund-month support file. Defaults to data/raw/support__mmf_fund_month.csv under --root.",
    )
    p_interest_constraints.add_argument(
        "--row-tic-file",
        default=None,
        help="ROW TIC SLT Table 3 holder-position file or pointer. Defaults to TDCEST_ROW_TIC_FILE or a sibling tgarefill checkout when available.",
    )
    p_interest_constraints.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tier2_interest_source_constraints.csv under --root.",
    )
    p_interest_constraints.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tier2_interest_source_constraints.md under --root.",
    )
    p_interest_constraints.set_defaults(func=cmd_interest_source_constraints)

    p_ffiec_constraints = sub.add_parser(
        "ffiec-interest-constraints",
        parents=[root_parent],
        help="Normalize local FFIEC RCB Call Report extracts into Treasury level/bucket constraints.",
    )
    p_ffiec_constraints.add_argument(
        "--extracted-root",
        default=None,
        help="Directory containing quarter/extracted FFIEC Call Report folders. Defaults to TDCEST_FFIEC_EXTRACTED_ROOT or a sibling slrwatch checkout when available.",
    )
    p_ffiec_constraints.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/ffiec_interest_constraints_normalized.csv.",
    )
    p_ffiec_constraints.set_defaults(func=cmd_ffiec_interest_constraints)

    p_ncua_constraints = sub.add_parser(
        "ncua-interest-constraints",
        parents=[root_parent],
        help="Normalize cached NCUA 5300 Call Report ZIPs into Treasury level constraints.",
    )
    p_ncua_constraints.add_argument(
        "--cache-dir",
        default=None,
        help="Directory containing call-report-data-YYYY-MM.zip files. Defaults to data/raw/_cache_ncua_call_report.",
    )
    p_ncua_constraints.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/ncua_interest_constraints_normalized.csv.",
    )
    p_ncua_constraints.set_defaults(func=cmd_ncua_interest_constraints)

    p_interest_window = sub.add_parser(
        "tier2-interest-source-window-validation",
        parents=[root_parent],
        help="Validate source-constraint coverage across the Tier 2 component-candidate window.",
    )
    p_interest_window.add_argument(
        "--candidate-file",
        default=None,
        help="Tier 2 component candidate CSV. Defaults to data/processed/tier2_interest_component_candidate.csv.",
    )
    p_interest_window.add_argument(
        "--source-constraints-file",
        default=None,
        help="Tier 2 source constraints CSV. Defaults to data/processed/tier2_interest_source_constraints.csv.",
    )
    p_interest_window.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tier2_interest_source_window_validation.csv.",
    )
    p_interest_window.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tier2_interest_source_window_validation.md.",
    )
    p_interest_window.set_defaults(func=cmd_interest_source_window_validation)

    p_default_switch = sub.add_parser(
        "tier2-interest-default-switch-review",
        parents=[root_parent],
        help="Review whether the component-anchored Tier 2 interest candidate is ready to replace live defaults.",
    )
    p_default_switch.add_argument(
        "--candidate-file",
        default=None,
        help="Tier 2 component candidate CSV. Defaults to data/processed/tier2_interest_component_candidate.csv.",
    )
    p_default_switch.add_argument(
        "--source-window-validation-file",
        default=None,
        help="Source-window validation CSV. Defaults to data/processed/tier2_interest_source_window_validation.csv.",
    )
    p_default_switch.add_argument(
        "--component-pools-file",
        default=None,
        help="Treasury interest component pools CSV. Defaults to data/processed/treasury_interest_component_pools_q.csv.",
    )
    p_default_switch.add_argument(
        "--tips-treatment-decision-file",
        default=None,
        help="TIPS treatment decision CSV. Defaults to data/processed/tier2_tips_treatment_decision.csv when present.",
    )
    p_default_switch.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tier2_interest_default_switch_review.csv.",
    )
    p_default_switch.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tier2_interest_default_switch_review.md.",
    )
    p_default_switch.set_defaults(func=cmd_tier2_interest_default_switch_review)

    p_tips_decision = sub.add_parser(
        "tier2-tips-treatment-decision",
        parents=[root_parent],
        help="Write the default treatment decision for TIPS coupon accrual versus TIPS inflation compensation.",
    )
    p_tips_decision.add_argument(
        "--component-pools-file",
        default=None,
        help="Treasury interest component pools CSV. Defaults to data/processed/treasury_interest_component_pools_q.csv.",
    )
    p_tips_decision.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tier2_tips_treatment_decision.csv.",
    )
    p_tips_decision.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tier2_tips_treatment_decision.md.",
    )
    p_tips_decision.set_defaults(func=cmd_tier2_tips_treatment_decision)

    p_component_support = sub.add_parser(
        "tier2-component-support-export",
        parents=[root_parent],
        help="Export component-anchored Tier 2 candidate totals as staged support series.",
    )
    p_component_support.add_argument(
        "--candidate-file",
        default=None,
        help="Tier 2 component candidate CSV. Defaults to data/processed/tier2_interest_component_candidate.csv.",
    )
    p_component_support.add_argument(
        "--out-dir",
        default=None,
        help="Output directory for support CSVs. Defaults to data/raw.",
    )
    p_component_support.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown summary path. Defaults to data/processed/tier2_component_anchored_support_exports.md.",
    )
    p_component_support.set_defaults(func=cmd_tier2_component_support_export)

    p_tier2_regression_backcast = sub.add_parser(
        "tier2-regression-backcast",
        parents=[root_parent],
        help="Build regression-grade Tier 2 interest backcast with explicit method tiers.",
    )
    p_tier2_regression_backcast.add_argument(
        "--candidate-file",
        default=None,
        help="Tier 2 component candidate CSV. Defaults to data/processed/tier2_interest_component_candidate.csv.",
    )
    p_tier2_regression_backcast.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tier2_regression_interest_backcast.csv.",
    )
    p_tier2_regression_backcast.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tier2_regression_interest_backcast.md.",
    )
    p_tier2_regression_backcast.add_argument(
        "--wide-out",
        default=None,
        help="Output wide CSV path. Defaults to data/processed/tier2_regression_interest_backcast_wide.csv.",
    )
    p_tier2_regression_backcast.set_defaults(func=cmd_tier2_regression_backcast)

    p_tier2_regression_series = sub.add_parser(
        "tier2-regression-series",
        parents=[root_parent],
        help="Build regression-corrected TDC series using the Tier 2 regression interest backcast.",
    )
    p_tier2_regression_series.add_argument(
        "--estimates-file",
        default=None,
        help="TDC estimates CSV. Defaults to data/processed/tdc_estimates.csv.",
    )
    p_tier2_regression_series.add_argument(
        "--components-file",
        default=None,
        help="TDC components CSV. Defaults to data/processed/tdc_components.csv.",
    )
    p_tier2_regression_series.add_argument(
        "--backcast-wide-file",
        default=None,
        help="Wide Tier 2 regression backcast CSV. Defaults to data/processed/tier2_regression_interest_backcast_wide.csv.",
    )
    p_tier2_regression_series.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tdc_tier2_regression_series.csv.",
    )
    p_tier2_regression_series.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tdc_tier2_regression_series.md.",
    )
    p_tier2_regression_series.set_defaults(func=cmd_tier2_regression_series)

    p_component_comparison = sub.add_parser(
        "tier2-component-anchor-comparison",
        parents=[root_parent],
        help="Compare live Tier 2 estimator rows with staged component-anchored rows.",
    )
    p_component_comparison.add_argument(
        "--estimates-file",
        default=None,
        help="Estimator CSV. Defaults to data/processed/tdc_estimates.csv.",
    )
    p_component_comparison.add_argument(
        "--default-switch-review-file",
        default=None,
        help="Default-switch review CSV. Defaults to data/processed/tier2_interest_default_switch_review.csv.",
    )
    p_component_comparison.add_argument(
        "--default-decision-file",
        default=None,
        help="Strict default decision CSV. Defaults to data/processed/tier2_component_anchored_default_decision.csv.",
    )
    p_component_comparison.add_argument(
        "--out",
        default=None,
        help="Output comparison CSV path. Defaults to data/processed/tier2_component_anchored_estimator_comparison.csv.",
    )
    p_component_comparison.add_argument(
        "--markdown-out",
        default=None,
        help="Output comparison Markdown path. Defaults to data/processed/tier2_component_anchored_estimator_comparison.md.",
    )
    p_component_comparison.add_argument(
        "--acceptance-out",
        default=None,
        help="Output promotion acceptance Markdown path. Defaults to data/processed/tier2_component_anchored_promotion_acceptance.md.",
    )
    p_component_comparison.set_defaults(func=cmd_tier2_component_anchor_comparison)

    p_fed_component_extension = sub.add_parser(
        "fed-component-extension-export",
        parents=[root_parent],
        help="Export exact SOMA bill-discount plus FRN interest as a staged Fed Tier 1 extension support series.",
    )
    p_fed_component_extension.add_argument(
        "--fed-components-file",
        default=None,
        help="Fed component support CSV. Defaults to data/raw/support__fed_treasury_interest_components.csv.",
    )
    p_fed_component_extension.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/support__fed_tier1_component_extension_proxy.csv.",
    )
    p_fed_component_extension.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/fed_tier1_component_extension_support.md.",
    )
    p_fed_component_extension.set_defaults(func=cmd_fed_component_extension_export)

    p_component_default_decision = sub.add_parser(
        "tier2-component-default-decision",
        parents=[root_parent],
        help="Apply strict default-switch gates to the component-anchored Tier 2 family.",
    )
    p_component_default_decision.add_argument(
        "--default-switch-review-file",
        default=None,
        help="Default-switch review CSV. Defaults to data/processed/tier2_interest_default_switch_review.csv.",
    )
    p_component_default_decision.add_argument(
        "--comparison-file",
        default=None,
        help="Component estimator comparison CSV. Defaults to data/processed/tier2_component_anchored_estimator_comparison.csv.",
    )
    p_component_default_decision.add_argument(
        "--cu-split-sensitivity-file",
        default=None,
        help="Optional CU split sensitivity CSV. Defaults to data/processed/tier2_cu_split_sensitivity.csv if present.",
    )
    p_component_default_decision.add_argument(
        "--live-delta-acceptance-file",
        default=None,
        help="Optional live-delta acceptance CSV. Defaults to data/processed/tier2_live_delta_acceptance.csv if present.",
    )
    p_component_default_decision.add_argument(
        "--out",
        default=None,
        help="Output decision CSV path. Defaults to data/processed/tier2_component_anchored_default_decision.csv.",
    )
    p_component_default_decision.add_argument(
        "--markdown-out",
        default=None,
        help="Output decision Markdown path. Defaults to data/processed/tier2_component_anchored_default_decision.md.",
    )
    p_component_default_decision.set_defaults(func=cmd_tier2_component_default_decision)

    p_component_delta = sub.add_parser(
        "tier2-component-delta-attribution",
        parents=[root_parent],
        help="Decompose live-versus-component Tier 2 interest deltas by sector and component.",
    )
    p_component_delta.add_argument(
        "--candidate-file",
        default=None,
        help="Tier 2 component candidate CSV. Defaults to data/processed/tier2_interest_component_candidate.csv.",
    )
    p_component_delta.add_argument(
        "--out",
        default=None,
        help="Output attribution CSV path. Defaults to data/processed/tier2_component_delta_attribution.csv.",
    )
    p_component_delta.add_argument(
        "--markdown-out",
        default=None,
        help="Output attribution Markdown path. Defaults to data/processed/tier2_component_delta_attribution.md.",
    )
    p_component_delta.set_defaults(func=cmd_tier2_component_delta_attribution)

    p_cu_split = sub.add_parser(
        "tier2-cu-split-sensitivity",
        parents=[root_parent],
        help="Quantify a nondefault CU bill/coupon split using NCUA's broad all-investment <=1y share.",
    )
    p_cu_split.add_argument(
        "--candidate-file",
        default=None,
        help="Tier 2 component candidate CSV. Defaults to data/processed/tier2_interest_component_candidate.csv.",
    )
    p_cu_split.add_argument(
        "--ncua-constraints-file",
        default=None,
        help="Normalized NCUA constraint CSV. Defaults to data/processed/ncua_interest_constraints_normalized.csv.",
    )
    p_cu_split.add_argument(
        "--out",
        default=None,
        help="Output CU split sensitivity CSV path. Defaults to data/processed/tier2_cu_split_sensitivity.csv.",
    )
    p_cu_split.add_argument(
        "--markdown-out",
        default=None,
        help="Output CU split sensitivity Markdown path. Defaults to data/processed/tier2_cu_split_sensitivity.md.",
    )
    p_cu_split.set_defaults(func=cmd_tier2_cu_split_sensitivity)

    p_live_delta = sub.add_parser(
        "tier2-live-delta-acceptance",
        parents=[root_parent],
        help="Record acceptance of live WAMEST/H.15 versus component-anchored Tier 2 deltas.",
    )
    p_live_delta.add_argument(
        "--delta-attribution-file",
        default=None,
        help="Tier 2 component delta attribution CSV. Defaults to data/processed/tier2_component_delta_attribution.csv.",
    )
    p_live_delta.add_argument(
        "--out",
        default=None,
        help="Output live-delta acceptance CSV path. Defaults to data/processed/tier2_live_delta_acceptance.csv.",
    )
    p_live_delta.add_argument(
        "--markdown-out",
        default=None,
        help="Output live-delta acceptance Markdown path. Defaults to data/processed/tier2_live_delta_acceptance.md.",
    )
    p_live_delta.set_defaults(func=cmd_tier2_live_delta_acceptance)

    p_tdc_empirical_anchor = sub.add_parser(
        "tdc-empirical-anchor",
        parents=[root_parent],
        help="Export the tdcsfc-facing empirical TDC anchor CSV and manifest.",
    )
    p_tdc_empirical_anchor.add_argument(
        "--estimates-file",
        default=None,
        help="TDC estimates CSV. Defaults to data/processed/tdc_estimates.csv.",
    )
    p_tdc_empirical_anchor.add_argument(
        "--components-file",
        default=None,
        help="TDC components CSV. Defaults to data/processed/tdc_components.csv.",
    )
    p_tdc_empirical_anchor.add_argument(
        "--method-meta-file",
        default=None,
        help="Method metadata JSON. Defaults to data/processed/method_meta.json.",
    )
    p_tdc_empirical_anchor.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tdc_empirical_anchor.csv.",
    )
    p_tdc_empirical_anchor.add_argument(
        "--manifest-out",
        default=None,
        help="Output manifest JSON path. Defaults to data/processed/tdc_empirical_anchor_manifest.json.",
    )
    p_tdc_empirical_anchor.set_defaults(func=cmd_tdc_empirical_anchor)

    p_ratewall_du_ru = sub.add_parser(
        "ratewall-du-ru-methodology",
        parents=[root_parent],
        help="Export the TDC-EST/Z.1 DU/RU methodology panel for RateWall.",
    )
    p_ratewall_du_ru.add_argument(
        "--du-fiscal-flow-file",
        default=None,
        help="TDC-EST DU fiscal-flow research CSV. Defaults to data/processed/tdc_du_fiscal_flow_research.csv.",
    )
    p_ratewall_du_ru.add_argument(
        "--interest-method-file",
        default=None,
        help="TDC-EST interest-method tier CSV. Defaults to data/processed/tier2_regression_interest_backcast_wide.csv.",
    )
    p_ratewall_du_ru.add_argument(
        "--z1-holder-absorption-file",
        default=None,
        help="Z.1 holder absorption CSV. Defaults to the sibling tdcmix exact holder panel.",
    )
    p_ratewall_du_ru.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/ratewall_du_ru_methodology_panel.csv.",
    )
    p_ratewall_du_ru.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/ratewall_du_ru_methodology_panel.md.",
    )
    p_ratewall_du_ru.set_defaults(func=cmd_ratewall_du_ru_methodology)

    p_monetary_route = sub.add_parser(
        "monetary-route-bridge",
        parents=[root_parent],
        help="Export M1/M2/deposit-pass-through route labels for domestic nonbank and MMF routes.",
    )
    p_monetary_route.add_argument(
        "--quarterly-file",
        default=None,
        help="Quarterly inputs CSV. Defaults to data/processed/quarterly_inputs.csv.",
    )
    p_monetary_route.add_argument(
        "--ratewall-du-ru-methodology-file",
        default=None,
        help="RateWall DU/RU methodology CSV. Defaults to data/processed/ratewall_du_ru_methodology_panel.csv.",
    )
    p_monetary_route.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/processed/tdc_domestic_nonbank_monetary_route_bridge.csv.",
    )
    p_monetary_route.add_argument(
        "--markdown-out",
        default=None,
        help="Output Markdown path. Defaults to data/processed/tdc_domestic_nonbank_monetary_route_bridge.md.",
    )
    p_monetary_route.set_defaults(func=cmd_monetary_route_bridge)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
