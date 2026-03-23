from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import BASE_FRED_SERIES, OPTIONAL_FRED_SERIES
from .utils import ensure_dir


def _write_series(path: Path, dates: pd.DatetimeIndex, values: np.ndarray, value_col: str = "value") -> None:
    df = pd.DataFrame({"date": pd.to_datetime(dates), value_col: values})
    df.to_csv(path, index=False)


def _quarter_index(start: str = "2011-03-31", periods: int = 60) -> pd.DatetimeIndex:
    return pd.date_range(start=start, periods=periods, freq="QE-DEC")


def _weekly_wednesdays(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="W-WED")


def _month_ends(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="ME")


def generate_synthetic_raw_bundle(raw_dir: Path | str, seed: int = 7) -> None:
    raw_dir = ensure_dir(raw_dir)
    rng = np.random.default_rng(seed)
    q = _quarter_index()
    n = len(q)

    # Quarterly transaction series
    fed_tsy_tx = 25 + rng.normal(0, 12, n)
    us_chartered_tsy_tx = 60 + rng.normal(0, 25, n)
    foreign_offices_tsy_tx = 8 + rng.normal(0, 6, n)
    affiliated_areas_tsy_tx = 2 + rng.normal(0, 2, n)
    np_credit_unions_tsy_tx = 4 + rng.normal(0, 3, n)
    corp_credit_unions_tsy_tx = 0.8 + rng.normal(0, 1.0, n)
    ncua_capitalization_deposit_tx = 0.2 + rng.normal(0, 0.15, n)
    row_tsy_tx = 42 + rng.normal(0, 20, n)
    treasury_operating_cash_tx = 15 + rng.normal(0, 60, n)

    crisis_slice = slice(34, 40)
    treasury_operating_cash_tx[crisis_slice] += np.array([120, 250, -180, -220, 160, 90])
    row_tsy_tx[crisis_slice] += np.array([40, 50, 20, -10, 35, 20])
    np_credit_unions_tsy_tx[crisis_slice] += np.array([2.0, 3.0, 1.0, -1.5, 2.5, 1.0])
    corp_credit_unions_tsy_tx[crisis_slice] += np.array([0.2, 0.4, 0.3, -0.2, 0.1, 0.1])
    ncua_capitalization_deposit_tx[crisis_slice] += np.array([0.05, 0.10, 0.08, -0.03, 0.02, 0.01])

    credit_unions_total_tsy_tx = (
        np_credit_unions_tsy_tx + corp_credit_unions_tsy_tx + ncua_capitalization_deposit_tx
    )
    gdp_deflator = np.linspace(82.0, 124.0, n) + rng.normal(0, 0.6, n)

    quarterly_values = {
        "fed_tsy_tx": fed_tsy_tx,
        "us_chartered_tsy_tx": us_chartered_tsy_tx,
        "foreign_offices_tsy_tx": foreign_offices_tsy_tx,
        "affiliated_areas_tsy_tx": affiliated_areas_tsy_tx,
        "np_credit_unions_tsy_tx": np_credit_unions_tsy_tx,
        "corp_credit_unions_tsy_tx": corp_credit_unions_tsy_tx,
        "ncua_capitalization_deposit_tx": ncua_capitalization_deposit_tx,
        "row_tsy_tx": row_tsy_tx,
        "treasury_operating_cash_tx": treasury_operating_cash_tx,
        "credit_unions_total_tsy_tx": credit_unions_total_tsy_tx,
        "gdp_deflator": gdp_deflator,
    }

    for spec in [*BASE_FRED_SERIES, *OPTIONAL_FRED_SERIES]:
        if spec.key == "fed_remit_or_deferred":
            continue
        if spec.key not in quarterly_values:
            continue
        _write_series(raw_dir / f"fred__{spec.key}.csv", q, quarterly_values[spec.key])

    # Weekly remittance / deferred-asset series
    weekly = _weekly_wednesdays(q.min() - pd.Timedelta(days=84), q.max())
    w_values = rng.normal(1.4, 0.5, len(weekly))
    late = weekly >= pd.Timestamp("2022-09-01")
    w_values[late] = -np.linspace(1, 210, late.sum()) + rng.normal(0, 4, late.sum())
    early_positive = (weekly >= pd.Timestamp("2020-01-01")) & (weekly < pd.Timestamp("2022-09-01"))
    w_values[early_positive] = rng.normal(1.8, 0.5, early_positive.sum())
    _write_series(raw_dir / "fred__fed_remit_or_deferred.csv", weekly, w_values)

    # Quarterly levels consistent-ish with transactions
    level_starts = {
        "fed_tsy_level": 1800.0,
        "us_chartered_tsy_level": 900.0,
        "foreign_offices_tsy_level": 120.0,
        "affiliated_areas_tsy_level": 25.0,
        "np_credit_unions_tsy_level": 82.0,
        "corp_credit_unions_tsy_level": 12.0,
        "ncua_capitalization_deposit_level": 4.0,
        "credit_unions_total_tsy_level": 98.0,
        "row_tsy_level": 4800.0,
        "treasury_operating_cash_level": 290.0,
    }
    tx_map = {
        "fed_tsy_level": fed_tsy_tx,
        "us_chartered_tsy_level": us_chartered_tsy_tx,
        "foreign_offices_tsy_level": foreign_offices_tsy_tx,
        "affiliated_areas_tsy_level": affiliated_areas_tsy_tx,
        "np_credit_unions_tsy_level": np_credit_unions_tsy_tx,
        "corp_credit_unions_tsy_level": corp_credit_unions_tsy_tx,
        "ncua_capitalization_deposit_level": ncua_capitalization_deposit_tx,
        "credit_unions_total_tsy_level": credit_unions_total_tsy_tx,
        "row_tsy_level": row_tsy_tx,
        "treasury_operating_cash_level": treasury_operating_cash_tx,
    }
    for key, start in level_starts.items():
        jitter = rng.normal(0, 3 if key != "ncua_capitalization_deposit_level" else 0.15, n)
        values = start + np.cumsum(tx_map[key] + jitter)
        _write_series(raw_dir / f"fred__{key}.csv", q, values)

    # Monthly/weekly optional macro series
    monthly = _month_ends(q.min() - pd.offsets.MonthEnd(2), q.max())
    m = len(monthly)

    m2 = 11000 + np.cumsum(rng.normal(45, 18, m))
    currency = 1400 + np.cumsum(rng.normal(7, 3, m))
    bank_credit = 9000 + np.cumsum(rng.normal(35, 15, m))
    _write_series(raw_dir / "fred__m2.csv", monthly, m2)
    _write_series(raw_dir / "fred__currency.csv", monthly, currency)
    _write_series(raw_dir / "fred__bank_credit.csv", weekly, 9000 + np.cumsum(rng.normal(8, 5, len(weekly))))
    _write_series(raw_dir / "fred__tga_weekly.csv", weekly, 300 + np.cumsum(rng.normal(0.5, 20, len(weekly))))

    # Minimal placeholder Treasury support datasets
    mts = pd.DataFrame(
        {
            "record_date": monthly.astype(str),
            "classification_desc": ["Deposit of Earnings, Federal Reserve System"] * len(monthly),
            "net_rcpt_amt": np.where(
                monthly < pd.Timestamp("2022-09-30"),
                rng.normal(500, 100, len(monthly)),
                rng.normal(0, 20, len(monthly)).clip(min=0),
            ),
        }
    )
    mts.to_csv(raw_dir / "treasury__mts_receipts.csv", index=False)

    dts = pd.DataFrame(
        {
            "record_date": weekly.astype(str),
            "account_type": ["Treasury General Account"] * len(weekly),
            "close_today_bal": 300 + np.cumsum(rng.normal(0.5, 20, len(weekly))),
        }
    )
    dts.to_csv(raw_dir / "treasury__dts_operating_cash_balance.csv", index=False)
