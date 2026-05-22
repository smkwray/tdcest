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
    nominal_gdp_saar_bil = np.linspace(15000.0, 30000.0, n) + rng.normal(0, 80.0, n)

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
        "nominal_gdp_saar_bil": nominal_gdp_saar_bil,
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
    retail_money_market_funds = 1550 + np.cumsum(rng.normal(3, 10, m))
    small_time_deposits = 980 + np.cumsum(rng.normal(1.5, 6, m))
    commercial_bank_deposits = (m2 - currency - retail_money_market_funds * 0.6) + rng.normal(0, 35, m)
    large_time_deposits_all_commercial_banks = 1500 + np.cumsum(rng.normal(4, 16, m))
    other_deposits_all_commercial_banks = np.clip(
        commercial_bank_deposits - large_time_deposits_all_commercial_banks,
        a_min=0.0,
        a_max=None,
    )
    loans_and_leases_bank_credit = 6200 + np.cumsum(rng.normal(28, 10, m))
    treasury_agency_non_mbs_bank_securities = 1200 + np.cumsum(rng.normal(2, 8, m))
    securities_in_bank_credit = treasury_agency_non_mbs_bank_securities + 900 + np.cumsum(rng.normal(4, 6, m))
    bank_credit = loans_and_leases_bank_credit + securities_in_bank_credit
    _write_series(raw_dir / "fred__m2.csv", monthly, m2)
    _write_series(raw_dir / "fred__currency.csv", monthly, currency)
    _write_series(raw_dir / "fred__retail_money_market_funds.csv", monthly, retail_money_market_funds)
    _write_series(raw_dir / "fred__small_time_deposits.csv", monthly, small_time_deposits)
    _write_series(raw_dir / "fred__commercial_bank_deposits.csv", monthly, commercial_bank_deposits)
    _write_series(
        raw_dir / "fred__large_time_deposits_all_commercial_banks.csv",
        monthly,
        large_time_deposits_all_commercial_banks,
    )
    _write_series(
        raw_dir / "fred__other_deposits_all_commercial_banks.csv",
        monthly,
        other_deposits_all_commercial_banks,
    )
    _write_series(raw_dir / "fred__bank_credit.csv", weekly, 9000 + np.cumsum(rng.normal(8, 5, len(weekly))))
    _write_series(raw_dir / "fred__loans_and_leases_bank_credit.csv", monthly, loans_and_leases_bank_credit)
    _write_series(raw_dir / "fred__securities_in_bank_credit.csv", monthly, securities_in_bank_credit)
    _write_series(
        raw_dir / "fred__treasury_agency_non_mbs_bank_securities.csv",
        monthly,
        treasury_agency_non_mbs_bank_securities,
    )
    _write_series(raw_dir / "fred__reserve_balances_with_frb.csv", weekly, 2800000 + np.cumsum(rng.normal(1000, 25000, len(weekly))))
    _write_series(raw_dir / "fred__term_deposits_at_fed.csv", weekly, np.clip(np.cumsum(rng.normal(0, 500, len(weekly))), a_min=0, a_max=None))
    _write_series(raw_dir / "fred__other_deposits_at_fed.csv", weekly, np.clip(20000 + np.cumsum(rng.normal(0, 800, len(weekly))), a_min=0, a_max=None))
    _write_series(raw_dir / "fred__fed_liquidity_credit_loans_net.csv", weekly, np.clip(np.cumsum(rng.normal(0, 1500, len(weekly))), a_min=0, a_max=None))
    _write_series(raw_dir / "fred__reverse_repo_treasury.csv", weekly, np.clip(500 + np.cumsum(rng.normal(0, 20, len(weekly))), a_min=0, a_max=None))
    _write_series(raw_dir / "fred__tga_weekly.csv", weekly, 300 + np.cumsum(rng.normal(0.5, 20, len(weekly))))
    _write_series(raw_dir / "fred__foreign_official_custody_treasuries.csv", weekly, 2500 + np.cumsum(rng.normal(1.0, 18, len(weekly))))
    _write_series(raw_dir / "fred__commercial_bank_borrowings.csv", monthly, np.clip(900 + np.cumsum(rng.normal(6, 18, m)), a_min=0, a_max=None))
    _write_series(raw_dir / "fred__commercial_bank_cash_assets.csv", monthly, 1800 + np.cumsum(rng.normal(4, 22, m)))
    _write_series(raw_dir / "fred__foreign_related_treasury_agency_non_mbs.csv", monthly, 420 + np.cumsum(rng.normal(1.0, 6, m)))
    fed_coupon_proxy = 6 + 0.012 * np.maximum(level_starts["fed_tsy_level"] + np.cumsum(fed_tsy_tx), 0) / 100 + rng.normal(0, 0.5, n)
    bank_sector_level = (
        level_starts["us_chartered_tsy_level"]
        + level_starts["foreign_offices_tsy_level"]
        + level_starts["affiliated_areas_tsy_level"]
        + np.cumsum(us_chartered_tsy_tx + foreign_offices_tsy_tx + affiliated_areas_tsy_tx)
    )
    bank_coupon_proxy = 5 + 0.018 * np.maximum(bank_sector_level, 0) / 100 + rng.normal(0, 0.45, n)
    row_coupon_proxy = 9 + 0.006 * np.maximum(level_starts["row_tsy_level"] + np.cumsum(row_tsy_tx), 0) / 100 + rng.normal(0, 0.65, n)
    credit_union_coupon_proxy = 0.4 + 0.010 * np.maximum(
        level_starts["np_credit_unions_tsy_level"] + np.cumsum(np_credit_unions_tsy_tx), 0
    ) / 100 + rng.normal(0, 0.08, n)
    bank_noninterest_outlay_proxy = 1.2 + rng.normal(0, 0.2, n)
    row_noninterest_outlay_proxy = 0.7 + rng.normal(0, 0.15, n)
    bank_nonborrow_receipt_proxy = 0.35 + rng.normal(0, 0.08, n)
    row_nonborrow_receipt_proxy = 0.15 + rng.normal(0, 0.05, n)
    mint_cb_cash_factor_proxy = 0.1 + rng.normal(0, 0.04, n)
    _write_series(raw_dir / "support__fed_tsy_coupon_interest_proxy.csv", q, np.clip(fed_coupon_proxy, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__bank_tsy_coupon_interest_proxy.csv", q, np.clip(bank_coupon_proxy, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__row_tsy_coupon_interest_proxy.csv", q, np.clip(row_coupon_proxy, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__credit_union_tsy_coupon_interest_proxy.csv", q, np.clip(credit_union_coupon_proxy, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__bank_noninterest_outlay_proxy.csv", q, np.clip(bank_noninterest_outlay_proxy, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__row_noninterest_outlay_proxy.csv", q, np.clip(row_noninterest_outlay_proxy, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__bank_nonborrow_receipt_proxy.csv", q, np.clip(bank_nonborrow_receipt_proxy, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__row_nonborrow_receipt_proxy.csv", q, np.clip(row_nonborrow_receipt_proxy, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__mint_cb_cash_factor_proxy.csv", q, np.clip(mint_cb_cash_factor_proxy, a_min=0.0, a_max=None))
    credit_union_deposits = 950000 + np.cumsum(rng.normal(6500, 9000, n))
    thrift_deposits = 610000 + np.cumsum(rng.normal(3500, 6000, n))
    _write_series(raw_dir / "support__credit_union_deposits.csv", q, np.clip(credit_union_deposits, a_min=0.0, a_max=None))
    _write_series(raw_dir / "support__thrift_deposits.csv", q, np.clip(thrift_deposits, a_min=0.0, a_max=None))
    mmf_rows = []
    for fund_id, offset in [("demo_fund_a", 0.0), ("demo_fund_b", 80.0)]:
        fed_rrp = np.clip(500 + offset + np.cumsum(rng.normal(-2.0, 16.0, m)), a_min=0.0, a_max=None)
        treasury_bills = np.clip(220 + offset / 3 + np.cumsum(rng.normal(3.0, 12.0, m)), a_min=0.0, a_max=None)
        treasury_other = np.clip(90 + offset / 4 + np.cumsum(rng.normal(1.0, 5.0, m)), a_min=0.0, a_max=None)
        other_assets = np.clip(180 + offset / 5 + np.cumsum(rng.normal(0.5, 8.0, m)), a_min=0.0, a_max=None)
        nav = fed_rrp + treasury_bills + treasury_other + other_assets + rng.normal(0.0, 3.0, m)
        for date, rrp, bills, other_tsy, other_asset, nav_value in zip(
            monthly, fed_rrp, treasury_bills, treasury_other, other_assets, nav
        ):
            mmf_rows.append(
                {
                    "date": date,
                    "fund_id": fund_id,
                    "fed_rrp": rrp,
                    "treasury_bills": bills,
                    "treasury_other": other_tsy,
                    "non_treasury_non_fed_rrp_assets": other_asset,
                    "nav": nav_value,
                }
            )
    pd.DataFrame(mmf_rows).to_csv(raw_dir / "support__mmf_fund_month.csv", index=False)
    pd.DataFrame(
        {
            "date": q,
            "source_zip_url": [f"https://ncua.gov/files/publications/analysis/call-report-data-{d.year}-{d.month:02d}.zip" for d in q],
            "source_zip_file": [f"call-report-data-{d.year}-{d.month:02d}.zip" for d in q],
            "total_credit_union_shares_and_deposits_mil": np.clip(credit_union_deposits * 1.02, a_min=0.0, a_max=None),
            "federally_insured_credit_union_shares_and_deposits_mil": np.clip(credit_union_deposits, a_min=0.0, a_max=None),
            "nonfederally_insured_credit_union_shares_and_deposits_mil": np.clip(credit_union_deposits * 0.02, a_min=0.0, a_max=None),
            "total_credit_union_member_shares_mil": np.clip(credit_union_deposits * 0.965, a_min=0.0, a_max=None),
            "federally_insured_credit_union_member_shares_mil": np.clip(credit_union_deposits * 0.96, a_min=0.0, a_max=None),
            "nonfederally_insured_credit_union_member_shares_mil": np.clip(credit_union_deposits * 0.005, a_min=0.0, a_max=None),
            "total_credit_union_implied_nonmember_deposits_mil": np.clip(credit_union_deposits * 0.055, a_min=0.0, a_max=None),
            "federally_insured_credit_union_implied_nonmember_deposits_mil": np.clip(credit_union_deposits * 0.04, a_min=0.0, a_max=None),
            "nonfederally_insured_credit_union_implied_nonmember_deposits_mil": np.clip(credit_union_deposits * 0.015, a_min=0.0, a_max=None),
            "total_credit_union_count": np.full(n, 4500),
            "federally_insured_credit_union_count": np.full(n, 4400),
            "nonfederally_insured_credit_union_count": np.full(n, 100),
        }
    ).to_csv(raw_dir / "ncua__credit_union_deposit_bridge.csv", index=False)
    pd.DataFrame(
        {
            "date": q,
            "source_api_url": [
                "https://api.fdic.gov/banks/financials?filters=%28BKCLASS%3ASB+OR+BKCLASS%3ASI+OR+BKCLASS%3ASL%29"
            ]
            * n,
            "source_cache_file": [f"fdic_financials_savings_institutions_{d.strftime('%Y%m%d')}.json" for d in q],
            "total_savings_institution_deposits_mil": np.clip(thrift_deposits, a_min=0.0, a_max=None),
            "federal_savings_bank_deposits_mil": np.clip(thrift_deposits * 0.42, a_min=0.0, a_max=None),
            "state_savings_bank_deposits_mil": np.clip(thrift_deposits * 0.44, a_min=0.0, a_max=None),
            "state_savings_and_loan_deposits_mil": np.clip(thrift_deposits * 0.14, a_min=0.0, a_max=None),
            "total_savings_institution_count": np.full(n, 520),
            "federal_savings_bank_count": np.full(n, 220),
            "state_savings_bank_count": np.full(n, 245),
            "state_savings_and_loan_count": np.full(n, 55),
        }
    ).to_csv(raw_dir / "fdic__savings_institution_deposit_bridge.csv", index=False)

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
