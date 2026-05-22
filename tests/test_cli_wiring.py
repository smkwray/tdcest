from __future__ import annotations

import argparse
from pathlib import Path

import tdc_estimator.cli as cli


def _namespace(**kwargs: object) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def test_build_parser_exposes_expected_commands():
    parser = cli.build_parser()
    subparsers_action = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))

    assert set(subparsers_action.choices) == {
        "download",
        "estimate",
        "plot",
        "site-export",
        "build",
        "demo",
        "fed-coupon-proxy",
        "fed-interest-components",
        "tier2-coupon-proxies",
        "tier3-support-files",
        "tier3-source-input",
        "mmf-rrp-support",
        "sec-nmfp-mmf-support",
        "fed-remit-mts-support",
        "mts-previous-issues-manifest",
        "mts-table4-target-history",
        "mts-table4-target-receipts",
        "mts-table5-target-history",
        "mts-table5-target-outlays",
        "mts-stitched-target-receipts",
        "mts-stitched-target-outlays",
        "mts-previous-issue-coverage",
        "mts-target-overlap-audit",
        "gse-on-rrp-support",
        "bill-discount-validation",
        "treasury-interest-components",
        "bill-discount-allocation",
        "tier2-interest-component-candidate",
        "tier2-interest-source-constraints",
        "ffiec-interest-constraints",
        "ncua-interest-constraints",
        "tier2-interest-source-window-validation",
        "tier2-interest-default-switch-review",
        "tier2-tips-treatment-decision",
        "tier2-component-support-export",
        "tier2-component-anchor-comparison",
        "fed-component-extension-export",
        "tier2-component-default-decision",
        "tier2-component-delta-attribution",
        "tier2-cu-split-sensitivity",
        "tier2-live-delta-acceptance",
        "tier2-regression-backcast",
        "tier2-regression-series",
    }


def test_cmd_download_wires_dependencies(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))
    monkeypatch.setattr(cli, "BASE_FRED_SERIES", ["required-series"])
    monkeypatch.setattr(cli, "all_fred_series", lambda include_optional: ["all-series"] if include_optional else ["unexpected"])

    def fake_download_fred_bundle(specs, raw_dir, *, api_key, start_date, end_date, continue_on_error, project_root):
        calls["fred"] = {
            "specs": list(specs),
            "raw_dir": Path(raw_dir),
            "api_key": api_key,
            "start_date": start_date,
            "end_date": end_date,
            "continue_on_error": continue_on_error,
            "project_root": Path(project_root),
        }
        return {"kind": "fred"}

    def fake_download_treasury_bundle(specs, raw_dir, *, continue_on_error, project_root):
        calls["treasury"] = {
            "specs": list(specs),
            "raw_dir": Path(raw_dir),
            "continue_on_error": continue_on_error,
            "project_root": Path(project_root),
        }
        return {"kind": "treasury"}

    def fake_write_json(path, payload):
        calls["write_json"] = {"path": Path(path), "payload": payload}

    monkeypatch.setattr(cli, "download_fred_bundle", fake_download_fred_bundle)
    monkeypatch.setattr(cli, "download_treasury_bundle", fake_download_treasury_bundle)
    monkeypatch.setattr(cli, "write_json", fake_write_json)
    monkeypatch.setenv("FRED_API_KEY", "env-key")

    exit_code = cli.cmd_download(
        _namespace(
            root=tmp_path,
            required_only=True,
            include_treasury_support=True,
            fred_api_key=None,
            start_date="2024-01-01",
            end_date="2024-03-31",
        )
    )

    assert exit_code == 0
    assert calls["fred"]["specs"] == ["required-series"]
    assert calls["fred"]["raw_dir"] == tmp_path / "raw"
    assert calls["fred"]["api_key"] == "env-key"
    assert calls["fred"]["start_date"] == "2024-01-01"
    assert calls["fred"]["end_date"] == "2024-03-31"
    assert calls["fred"]["continue_on_error"] is True
    assert calls["fred"]["project_root"] == tmp_path
    assert calls["treasury"]["specs"] == cli.TREASURY_DATASETS
    assert calls["treasury"]["project_root"] == tmp_path
    assert calls["write_json"]["path"] == tmp_path / "processed" / "download_summary.json"
    assert calls["write_json"]["payload"]["fred_manifest"] == {"kind": "fred"}
    assert calls["write_json"]["payload"]["treasury_manifest"] == {"kind": "treasury"}


def test_cmd_estimate_delegates_to_pipeline(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))

    def fake_run_estimation_pipeline(**kwargs):
        calls["pipeline"] = kwargs
        return {
            "estimates_path": str(tmp_path / "processed" / "tdc_estimates.csv"),
            "figure_outputs": [str(tmp_path / "figures" / "tdc_method_comparison.png")],
            "site_outputs": {"summary_json": str(tmp_path / "site" / "summary.json")},
        }

    monkeypatch.setattr(cli, "run_estimation_pipeline", fake_run_estimation_pipeline)

    exit_code = cli.cmd_estimate(_namespace(root=tmp_path))

    assert exit_code == 0
    assert calls["pipeline"]["raw_dir"] == tmp_path / "raw"
    assert calls["pipeline"]["processed_dir"] == tmp_path / "processed"
    assert "figures_dir" not in calls["pipeline"]
    assert "site_dir" not in calls["pipeline"]


def test_cmd_plot_delegates_to_pipeline(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))

    def fake_run_estimation_pipeline(**kwargs):
        calls["pipeline"] = kwargs
        return {"estimates_path": str(tmp_path / "processed" / "tdc_estimates.csv")}

    monkeypatch.setattr(cli, "run_estimation_pipeline", fake_run_estimation_pipeline)

    exit_code = cli.cmd_plot(_namespace(root=tmp_path))

    assert exit_code == 0
    assert calls["pipeline"]["raw_dir"] == tmp_path / "raw"
    assert calls["pipeline"]["processed_dir"] == tmp_path / "processed"
    assert calls["pipeline"]["figures_dir"] == tmp_path / "figures"
    assert "site_dir" not in calls["pipeline"]


def test_cmd_site_export_delegates_to_pipeline(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))

    def fake_run_estimation_pipeline(**kwargs):
        calls["pipeline"] = kwargs
        return {"site_outputs": {"summary_json": str(tmp_path / "site" / "summary.json")}}

    monkeypatch.setattr(cli, "run_estimation_pipeline", fake_run_estimation_pipeline)

    exit_code = cli.cmd_site_export(_namespace(root=tmp_path))

    assert exit_code == 0
    assert calls["pipeline"]["raw_dir"] == tmp_path / "raw"
    assert calls["pipeline"]["processed_dir"] == tmp_path / "processed"
    assert calls["pipeline"]["site_dir"] == tmp_path / "site"
    assert "figures_dir" not in calls["pipeline"]


def test_cmd_build_runs_download_and_pipeline(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))
    monkeypatch.setattr(cli, "BASE_FRED_SERIES", ["required-series"])
    monkeypatch.setattr(cli, "all_fred_series", lambda include_optional: ["all-series"])

    def fake_download_fred_bundle(specs, raw_dir, *, api_key, start_date, end_date, continue_on_error, project_root):
        calls["fred"] = {
            "specs": list(specs),
            "raw_dir": Path(raw_dir),
            "api_key": api_key,
            "start_date": start_date,
            "end_date": end_date,
            "continue_on_error": continue_on_error,
            "project_root": Path(project_root),
        }
        return {"kind": "fred"}

    def fake_download_treasury_bundle(specs, raw_dir, *, continue_on_error, project_root):
        calls["treasury"] = {
            "specs": list(specs),
            "raw_dir": Path(raw_dir),
            "continue_on_error": continue_on_error,
            "project_root": Path(project_root),
        }
        return {"kind": "treasury"}

    def fake_run_estimation_pipeline(**kwargs):
        calls["pipeline"] = kwargs
        return {"estimates_path": str(tmp_path / "processed" / "tdc_estimates.csv")}

    monkeypatch.setattr(cli, "download_fred_bundle", fake_download_fred_bundle)
    monkeypatch.setattr(cli, "download_treasury_bundle", fake_download_treasury_bundle)
    monkeypatch.setattr(cli, "run_estimation_pipeline", fake_run_estimation_pipeline)
    monkeypatch.setenv("FRED_API_KEY", "env-key")

    exit_code = cli.cmd_build(
        _namespace(
            root=tmp_path,
            required_only=True,
            include_treasury_support=True,
            fred_api_key=None,
            start_date=None,
            end_date=None,
        )
    )

    assert exit_code == 0
    assert calls["fred"]["specs"] == ["required-series"]
    assert calls["fred"]["api_key"] == "env-key"
    assert calls["fred"]["project_root"] == tmp_path
    assert calls["treasury"]["specs"] == cli.TREASURY_DATASETS
    assert calls["treasury"]["project_root"] == tmp_path
    assert calls["pipeline"]["raw_dir"] == tmp_path / "raw"
    assert calls["pipeline"]["processed_dir"] == tmp_path / "processed"
    assert calls["pipeline"]["figures_dir"] == tmp_path / "figures"
    assert calls["pipeline"]["site_dir"] == tmp_path / "site"


def test_cmd_demo_runs_offline_build(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}
    demo_target = tmp_path / "examples" / "demo_build"
    demo_target.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cli, "generate_synthetic_raw_bundle", lambda raw_dir, seed: calls.update({"synthetic": {"raw_dir": Path(raw_dir), "seed": seed}}))
    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "examples" / "demo_build" / "data" / "raw", processed=tmp_path / "examples" / "demo_build" / "data" / "processed", figures=tmp_path / "examples" / "demo_build" / "figures", site=tmp_path / "examples" / "demo_build" / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))
    monkeypatch.setattr(cli.shutil, "rmtree", lambda path: calls.setdefault("rmtree", Path(path)))

    def fake_run_estimation_pipeline(**kwargs):
        calls["pipeline"] = kwargs
        return {
            "estimates_path": str(tmp_path / "examples" / "demo_build" / "data" / "processed" / "tdc_estimates.csv"),
            "components_path": str(tmp_path / "examples" / "demo_build" / "data" / "processed" / "tdc_components.csv"),
            "corrections_path": str(tmp_path / "examples" / "demo_build" / "data" / "processed" / "tdc_corrections.csv"),
            "post2022_attribution_path": str(tmp_path / "examples" / "demo_build" / "data" / "processed" / "tdc_post2022_bank_only_attribution.csv"),
            "post2022_attribution_markdown_path": str(tmp_path / "examples" / "demo_build" / "data" / "processed" / "tdc_post2022_bank_only_attribution.md"),
            "figure_outputs": [str(tmp_path / "examples" / "demo_build" / "figures" / "tdc_method_comparison.png")],
            "site_outputs": {"summary_json": str(tmp_path / "examples" / "demo_build" / "site" / "summary.json")},
        }

    monkeypatch.setattr(cli, "run_estimation_pipeline", fake_run_estimation_pipeline)

    exit_code = cli.cmd_demo(_namespace(root=tmp_path, seed=11))

    assert exit_code == 0
    assert calls["synthetic"] == {"raw_dir": tmp_path / "examples" / "demo_build" / "data" / "raw", "seed": 11}
    assert calls["pipeline"]["raw_dir"] == tmp_path / "examples" / "demo_build" / "data" / "raw"
    assert calls["pipeline"]["processed_dir"] == tmp_path / "examples" / "demo_build" / "data" / "processed"
    assert calls["pipeline"]["figures_dir"] == tmp_path / "examples" / "demo_build" / "figures"
    assert calls["pipeline"]["site_dir"] == tmp_path / "examples" / "demo_build" / "site"


def test_cmd_fed_coupon_proxy_writes_default_support_path(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))

    def fake_write_quarterly_fed_coupon_interest_proxy_from_soma_csvs(soma_file, out_path):
        calls["fed_coupon"] = {"soma_file": soma_file, "out_path": Path(out_path)}
        return Path(out_path)

    monkeypatch.setattr(cli, "write_quarterly_fed_coupon_interest_proxy_from_soma_csvs", fake_write_quarterly_fed_coupon_interest_proxy_from_soma_csvs)

    exit_code = cli.cmd_fed_coupon_proxy(_namespace(root=tmp_path, soma_file=["input-a.csv", "input-b.csv"], wamest_root=None, out=None))

    assert exit_code == 0
    assert calls["fed_coupon"]["soma_file"] == ["input-a.csv", "input-b.csv"]
    assert calls["fed_coupon"]["out_path"] == tmp_path / "raw" / "support__fed_tsy_coupon_interest_proxy.csv"


def test_cmd_fed_coupon_proxy_can_resolve_from_wamest_root(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))
    monkeypatch.setattr(cli, "resolve_wamest_soma_path", lambda wamest_root, soma_file=None: Path("resolved_soma_holdings.csv"))
    monkeypatch.setattr(
        cli,
        "resolve_wamest_artifact_paths",
        lambda wamest_root, prefer_normalized_sector_panel=False: (
            Path("resolved_sector_maturity.csv"),
            Path("resolved_sector_panel.csv"),
            Path("resolved_curves.csv"),
        ),
    )

    def fake_write_quarterly_fed_coupon_interest_proxy_with_wamest_backcast(**kwargs):
        calls["fed_coupon"] = kwargs
        return Path(kwargs["out_path"])

    monkeypatch.setattr(
        cli,
        "write_quarterly_fed_coupon_interest_proxy_with_wamest_backcast",
        fake_write_quarterly_fed_coupon_interest_proxy_with_wamest_backcast,
    )

    exit_code = cli.cmd_fed_coupon_proxy(_namespace(root=tmp_path, soma_file=None, wamest_root="../wamest", out=None))

    assert exit_code == 0
    assert calls["fed_coupon"]["soma_paths"] == ["resolved_soma_holdings.csv"]
    assert calls["fed_coupon"]["sector_maturity_path"] == Path("resolved_sector_maturity.csv")
    assert calls["fed_coupon"]["sector_panel_path"] == Path("resolved_sector_panel.csv")
    assert calls["fed_coupon"]["curve_path"] == Path("resolved_curves.csv")
    assert calls["fed_coupon"]["out_path"] == tmp_path / "raw" / "support__fed_tsy_coupon_interest_proxy.csv"


def test_cmd_tier2_coupon_proxies_writes_default_support_paths(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))

    def fake_write_quarterly_tier2_coupon_interest_proxies(**kwargs):
        calls["tier2_coupon"] = {
            "sector_maturity_path": kwargs["sector_maturity_path"],
            "sector_panel_path": kwargs["sector_panel_path"],
            "curve_path": kwargs["curve_path"],
            "bank_out_path": Path(kwargs["bank_out_path"]),
            "row_out_path": Path(kwargs["row_out_path"]),
            "bank_sector_keys": list(kwargs["bank_sector_keys"]),
            "row_sector_keys": list(kwargs["row_sector_keys"]),
        }
        return Path(kwargs["bank_out_path"]), Path(kwargs["row_out_path"])

    monkeypatch.setattr(cli, "write_quarterly_tier2_coupon_interest_proxies", fake_write_quarterly_tier2_coupon_interest_proxies)

    exit_code = cli.cmd_tier2_coupon_proxies(
        _namespace(
            root=tmp_path,
            sector_maturity_file="sector_effective_maturity.csv",
            sector_panel_file="sector_panel.csv",
            curve_file="h15_curves.csv",
            wamest_root=None,
            bank_out=None,
            row_out=None,
            bank_sector_key=None,
            row_sector_key=None,
        )
    )

    assert exit_code == 0
    assert calls["tier2_coupon"]["sector_maturity_path"] == "sector_effective_maturity.csv"
    assert calls["tier2_coupon"]["sector_panel_path"] == "sector_panel.csv"
    assert calls["tier2_coupon"]["curve_path"] == "h15_curves.csv"
    assert calls["tier2_coupon"]["bank_out_path"] == tmp_path / "raw" / "support__bank_tsy_coupon_interest_proxy.csv"
    assert calls["tier2_coupon"]["row_out_path"] == tmp_path / "raw" / "support__row_tsy_coupon_interest_proxy.csv"
    assert calls["tier2_coupon"]["bank_sector_keys"] == cli.DEFAULT_BANK_SECTOR_KEYS
    assert calls["tier2_coupon"]["row_sector_keys"] == cli.DEFAULT_ROW_SECTOR_KEYS


def test_cmd_tier2_coupon_proxies_can_resolve_from_wamest_root(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))
    monkeypatch.setattr(
        cli,
        "resolve_wamest_artifact_paths",
        lambda wamest_root, sector_maturity_file, sector_panel_file, curve_file, **kwargs: (
            Path("resolved_sector_effective_maturity.csv"),
            Path("resolved_sector_panel.csv"),
            Path("resolved_h15.csv"),
        ),
    )

    def fake_write_quarterly_tier2_coupon_interest_proxies(**kwargs):
        calls["tier2_coupon"] = kwargs
        return Path(kwargs["bank_out_path"]), Path(kwargs["row_out_path"])

    monkeypatch.setattr(cli, "write_quarterly_tier2_coupon_interest_proxies", fake_write_quarterly_tier2_coupon_interest_proxies)

    exit_code = cli.cmd_tier2_coupon_proxies(
        _namespace(
            root=tmp_path,
            sector_maturity_file=None,
            sector_panel_file=None,
            curve_file=None,
            wamest_root="../wamest",
            bank_out=None,
            row_out=None,
            bank_sector_key=None,
            row_sector_key=None,
        )
    )

    assert exit_code == 0
    assert calls["tier2_coupon"]["sector_maturity_path"] == "resolved_sector_effective_maturity.csv"
    assert calls["tier2_coupon"]["sector_panel_path"] == "resolved_sector_panel.csv"
    assert calls["tier2_coupon"]["curve_path"] == "resolved_h15.csv"


def test_cmd_tier3_support_files_uses_raw_date_spine(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))
    monkeypatch.setattr(cli, "derive_quarterly_date_spine", lambda raw_dir: cli.pd.to_datetime(["2024-03-31", "2024-06-30"]))

    def fake_build_tier3_support_table(*, dates, quarterly_input, fill_value):
        calls["table"] = {"dates": list(dates), "quarterly_input": quarterly_input, "fill_value": fill_value}
        return cli.pd.DataFrame(index=cli.pd.DatetimeIndex(dates))

    def fake_write_tier3_support_files(*, raw_dir, table, overwrite):
        calls["write"] = {"raw_dir": Path(raw_dir), "table": table, "overwrite": overwrite}
        return {"bank_noninterest_outlay_proxy": str(Path(raw_dir) / "support__bank_noninterest_outlay_proxy.csv")}

    monkeypatch.setattr(cli, "build_tier3_support_table", fake_build_tier3_support_table)
    monkeypatch.setattr(cli, "write_tier3_support_files", fake_write_tier3_support_files)

    exit_code = cli.cmd_tier3_support_files(_namespace(root=tmp_path, quarterly_input=None, fill_value=0.0, overwrite=False))

    assert exit_code == 0
    assert calls["table"]["dates"] == list(cli.pd.to_datetime(["2024-03-31", "2024-06-30"]))
    assert calls["table"]["quarterly_input"] is None
    assert calls["table"]["fill_value"] == 0.0
    assert calls["write"]["raw_dir"] == tmp_path / "raw"
    assert calls["write"]["overwrite"] is False


def test_cmd_tier3_support_files_can_use_curated_quarterly_input(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}
    curated = cli.pd.DataFrame(
        {"bank_noninterest_outlay_proxy": [1.0]},
        index=cli.pd.to_datetime(["2024-03-31"]),
    )

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))
    monkeypatch.setattr(cli, "derive_quarterly_date_spine", lambda raw_dir: cli.pd.to_datetime(["2023-12-31", "2024-03-31"]))
    monkeypatch.setattr(cli, "load_tier3_quarterly_input_table", lambda path: curated)

    def fake_build_tier3_support_table(*, dates, quarterly_input, fill_value):
        calls["table"] = {"dates": list(dates), "quarterly_input": quarterly_input, "fill_value": fill_value}
        return curated

    def fake_write_tier3_support_files(*, raw_dir, table, overwrite):
        calls["write"] = {"raw_dir": Path(raw_dir), "table": table, "overwrite": overwrite}
        return {"bank_noninterest_outlay_proxy": str(Path(raw_dir) / "support__bank_noninterest_outlay_proxy.csv")}

    monkeypatch.setattr(cli, "build_tier3_support_table", fake_build_tier3_support_table)
    monkeypatch.setattr(cli, "write_tier3_support_files", fake_write_tier3_support_files)

    exit_code = cli.cmd_tier3_support_files(
        _namespace(root=tmp_path, quarterly_input="curated.csv", fill_value=1.25, overwrite=True)
    )

    assert exit_code == 0
    assert calls["table"]["dates"] == list(cli.pd.to_datetime(["2023-12-31", "2024-03-31"]))
    assert calls["table"]["quarterly_input"] is curated
    assert calls["table"]["fill_value"] == 1.25
    assert calls["write"]["overwrite"] is True


def test_cmd_tier3_source_input_writes_default_examples_path(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))

    def fake_write_source_backed_tier3_input_table(*, mts_outlays_path, out_path, base_quarterly_input_path, start, row_profile):
        calls["source"] = {
            "mts_outlays_path": Path(mts_outlays_path),
            "out_path": Path(out_path),
            "base_quarterly_input_path": base_quarterly_input_path,
            "start": start,
            "row_profile": row_profile,
        }
        return Path(out_path)

    monkeypatch.setattr(cli, "write_source_backed_tier3_input_table", fake_write_source_backed_tier3_input_table)

    exit_code = cli.cmd_tier3_source_input(
        _namespace(
            root=tmp_path,
            mts_outlays_file=None,
            base_input=None,
            out=None,
            start="2022-09-30",
            row_profile="default",
        )
    )

    assert exit_code == 0
    assert calls["source"]["mts_outlays_path"] == tmp_path / "raw" / "treasury__mts_outlays.csv"
    assert calls["source"]["out_path"] == tmp_path / "examples" / "tier3-quarterly-input-template.csv"
    assert calls["source"]["base_quarterly_input_path"] is None
    assert calls["source"]["start"] == "2022-09-30"
    assert calls["source"]["row_profile"] == "default"
