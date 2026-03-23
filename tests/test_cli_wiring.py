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
    }


def test_cmd_download_wires_dependencies(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    monkeypatch.setattr(cli, "project_paths", lambda root: _namespace(root=Path(root), raw=tmp_path / "raw", processed=tmp_path / "processed", figures=tmp_path / "figures", site=tmp_path / "site"))
    monkeypatch.setattr(cli, "ensure_project_dirs", lambda paths: calls.setdefault("ensure_project_dirs", paths))
    monkeypatch.setattr(cli, "BASE_FRED_SERIES", ["required-series"])
    monkeypatch.setattr(cli, "all_fred_series", lambda include_optional: ["all-series"] if include_optional else ["unexpected"])

    def fake_download_fred_bundle(specs, raw_dir, *, api_key, start_date, end_date, continue_on_error):
        calls["fred"] = {
            "specs": list(specs),
            "raw_dir": Path(raw_dir),
            "api_key": api_key,
            "start_date": start_date,
            "end_date": end_date,
            "continue_on_error": continue_on_error,
        }
        return {"kind": "fred"}

    def fake_download_treasury_bundle(specs, raw_dir, *, continue_on_error):
        calls["treasury"] = {
            "specs": list(specs),
            "raw_dir": Path(raw_dir),
            "continue_on_error": continue_on_error,
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
    assert calls["treasury"]["specs"] == cli.TREASURY_DATASETS
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

    def fake_download_fred_bundle(specs, raw_dir, *, api_key, start_date, end_date, continue_on_error):
        calls["fred"] = {
            "specs": list(specs),
            "raw_dir": Path(raw_dir),
            "api_key": api_key,
            "start_date": start_date,
            "end_date": end_date,
            "continue_on_error": continue_on_error,
        }
        return {"kind": "fred"}

    def fake_download_treasury_bundle(specs, raw_dir, *, continue_on_error):
        calls["treasury"] = {
            "specs": list(specs),
            "raw_dir": Path(raw_dir),
            "continue_on_error": continue_on_error,
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
    assert calls["treasury"]["specs"] == cli.TREASURY_DATASETS
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
