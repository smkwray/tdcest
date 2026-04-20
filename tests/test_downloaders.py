from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tdc_estimator.catalog import FredSeries, TreasuryDataset
from tdc_estimator.download import (
    download_fred_series,
    download_treasury_dataset,
    fred_api_url,
    fred_csv_url,
    _build_treasury_url,
)


def test_fred_url_builders_include_expected_query_params():
    assert fred_csv_url("SERIES", start_date="2024-01-01", end_date="2024-03-31") == (
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES&cosd=2024-01-01&coed=2024-03-31"
    )
    assert fred_api_url("SERIES", api_key="abc123", start_date="2024-01-01", end_date="2024-03-31") == (
        "https://api.stlouisfed.org/fred/series/observations?"
        "series_id=SERIES&api_key=abc123&file_type=json&observation_start=2024-01-01&observation_end=2024-03-31"
    )


def test_download_fred_series_uses_graph_csv_when_no_api_key(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    def fake_urlopen_text(url: str, timeout: int = 60) -> str:
        calls["url"] = url
        calls["timeout"] = timeout
        return "date,value\n2024-03-31,1.5\n"

    monkeypatch.setattr("tdc_estimator.download._urlopen_text", fake_urlopen_text)

    spec = FredSeries(key="fed_tsy_tx", series_id="SERIES", description="desc", agg="sum", required=True)
    result = download_fred_series(spec, tmp_path, start_date="2024-01-01", end_date="2024-03-31")

    assert result["mode"] == "fred_graph_csv"
    assert result["url"] == "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES&cosd=2024-01-01&coed=2024-03-31"
    assert Path(result["path"]).read_text(encoding="utf-8") == "date,value\n2024-03-31,1.5\n"
    assert calls["url"] == result["url"]


def test_download_fred_series_emits_project_relative_path_when_root_supplied(monkeypatch, tmp_path: Path):
    def fake_urlopen_text(url: str, timeout: int = 60) -> str:
        return "date,value\n2024-03-31,1.5\n"

    monkeypatch.setattr("tdc_estimator.download._urlopen_text", fake_urlopen_text)

    spec = FredSeries(key="fed_tsy_tx", series_id="SERIES", description="desc", agg="sum", required=True)
    raw_dir = tmp_path / "data" / "raw"
    result = download_fred_series(spec, raw_dir, project_root=tmp_path)

    assert result["path"] == "data/raw/fred__fed_tsy_tx.csv"


def test_download_fred_series_uses_api_json_when_key_present(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    def fake_urlopen_text(url: str, timeout: int = 60) -> str:
        calls["url"] = url
        calls["timeout"] = timeout
        return json.dumps({"observations": [{"date": "2024-03-31", "value": "2.5"}]})

    monkeypatch.setattr("tdc_estimator.download._urlopen_text", fake_urlopen_text)

    spec = FredSeries(key="fed_tsy_tx", series_id="SERIES", description="desc", agg="sum", required=True)
    result = download_fred_series(spec, tmp_path, api_key="abc123", start_date="2024-01-01", end_date="2024-03-31")

    assert result["mode"] == "fred_api_json"
    assert result["url"] == (
        "https://api.stlouisfed.org/fred/series/observations?"
        "series_id=SERIES&api_key=abc123&file_type=json&observation_start=2024-01-01&observation_end=2024-03-31"
    )
    frame = pd.read_csv(result["path"])
    assert frame.to_dict(orient="records") == [{"date": "2024-03-31", "value": 2.5}]
    assert calls["url"] == result["url"]


def test_download_treasury_dataset_follows_relative_pagination(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    pages = {
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/deposits_withdrawals_operating_cash?sort=-record_date&page%5Bsize%5D=10000": json.dumps(
            {"data": [{"record_date": "2024-03-31", "transaction_type": "Deposits", "transaction_today_amt": "10"}], "links": {"next": "/v1/accounting/dts/deposits_withdrawals_operating_cash?page%5Bsize%5D=10000&sort=-record_date&page%5Bnumber%5D=2"}}
        ),
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/deposits_withdrawals_operating_cash?page%5Bsize%5D=10000&sort=-record_date&page%5Bnumber%5D=2": json.dumps(
            {"data": [{"record_date": "2024-04-01", "transaction_type": "Withdrawals", "transaction_today_amt": "11"}], "links": {}}
        ),
    }

    def fake_urlopen_text(url: str, timeout: int = 60) -> str:
        calls.append(url)
        return pages[url]

    monkeypatch.setattr("tdc_estimator.download._urlopen_text", fake_urlopen_text)

    spec = TreasuryDataset(
        key="dts_operating_cash_balance",
        endpoint="/v1/accounting/dts/deposits_withdrawals_operating_cash",
        description="desc",
        params={"sort": "-record_date"},
    )
    result = download_treasury_dataset(spec, tmp_path)

    assert result["pages"] == 2
    assert result["rows"] == 2
    assert calls == list(pages)
    frame = pd.read_csv(result["path"])
    assert frame.to_dict(orient="records") == [
        {"record_date": "2024-03-31", "transaction_type": "Deposits", "transaction_today_amt": 10},
        {"record_date": "2024-04-01", "transaction_type": "Withdrawals", "transaction_today_amt": 11},
    ]


def test_download_treasury_dataset_emits_project_relative_path_when_root_supplied(monkeypatch, tmp_path: Path):
    pages = {
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/deposits_withdrawals_operating_cash?sort=-record_date&page%5Bsize%5D=10000": json.dumps(
            {"data": [{"record_date": "2024-03-31", "transaction_type": "Deposits", "transaction_today_amt": "10"}], "links": {}}
        )
    }

    def fake_urlopen_text(url: str, timeout: int = 60) -> str:
        return pages[url]

    monkeypatch.setattr("tdc_estimator.download._urlopen_text", fake_urlopen_text)

    spec = TreasuryDataset(
        key="dts_operating_cash_balance",
        endpoint="/v1/accounting/dts/deposits_withdrawals_operating_cash",
        description="desc",
        params={"sort": "-record_date"},
    )
    raw_dir = tmp_path / "data" / "raw"
    result = download_treasury_dataset(spec, raw_dir, project_root=tmp_path)

    assert result["path"] == "data/raw/treasury__dts_operating_cash_balance.csv"


def test_download_treasury_dataset_follows_query_only_pagination(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    pages = {
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/deposits_withdrawals_operating_cash?sort=-record_date&page%5Bsize%5D=10000": json.dumps(
            {"data": [{"record_date": "2024-03-31", "transaction_type": "Deposits", "transaction_today_amt": "10"}], "links": {"next": "&page%5Bnumber%5D=2&page%5Bsize%5D=10000"}}
        ),
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/deposits_withdrawals_operating_cash?page%5Bnumber%5D=2&page%5Bsize%5D=10000": json.dumps(
            {"data": [{"record_date": "2024-04-01", "transaction_type": "Withdrawals", "transaction_today_amt": "11"}], "links": {}}
        ),
    }

    def fake_urlopen_text(url: str, timeout: int = 60) -> str:
        calls.append(url)
        return pages[url]

    monkeypatch.setattr("tdc_estimator.download._urlopen_text", fake_urlopen_text)

    spec = TreasuryDataset(
        key="dts_operating_cash_balance",
        endpoint="/v1/accounting/dts/deposits_withdrawals_operating_cash",
        description="desc",
        params={"sort": "-record_date"},
    )
    result = download_treasury_dataset(spec, tmp_path)

    assert result["pages"] == 2
    assert result["rows"] == 2
    assert calls == list(pages)


def test_build_treasury_url_fills_default_page_size():
    assert _build_treasury_url("/v1/example", {"sort": "-record_date"}) == (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/example?"
        "sort=-record_date&page%5Bsize%5D=10000"
    )
