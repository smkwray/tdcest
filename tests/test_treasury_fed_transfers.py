"""Treasury-Fed internal-transfer ledger: classification courts on dated public postings.

The fixture follows the 2020-2021 facility episode in miniature: equity paid on 2020-04-13 that
H.4.1 records only in the 2020-05-13 week, an LLC purchase of nonmarketable Treasury securities,
reinvested interest, a zero-coupon Domestic Series maturity held by another holder, a
non-facility ESF payment, returns of equity (one with earnings) and an LLC redemption.
"""

from __future__ import annotations

import hashlib
import json
import subprocess

import numpy as np
import pandas as pd
import pytest

from tdc_estimator.catalog import MEASUREMENT_VINTAGES, MeasurementVintage, fiscus_registries
from tdc_estimator.cli import main
from tdc_estimator.treasury_fed_transfers import (
    OUTPUT_FILES,
    SUPPORT_FILE,
    build_treasury_fed_transfers,
)

VINTAGE = MeasurementVintage("fixture", "2021Q4", "2021-12-31")
ESF_WINDOW = (pd.Timestamp("2020-01-01"), pd.Timestamp("2021-12-31"))
DS_WINDOW = (pd.Timestamp("2019-10-01"), pd.Timestamp("2021-12-31"))
CALENDAR = pd.bdate_range(*DS_WINDOW)  # the fixture's DTS publication dates
ESF = [  # DTS Table II ESF economic-recovery withdrawals; a negative withdrawal returns cash
    ("2020-04-13", 10000),  # facility equity; H.4.1 records it on 2020-05-13
    ("2020-05-11", 37500),  # facility equity
    ("2020-06-16", 17500),  # facility equity
    ("2020-09-25", 595),  # a direct loan to a business: no H.4.1 contribution change
    ("2021-01-05", -41294),  # equity returned
    ("2021-04-12", -1634),  # MMLF: 1,500 of protection returned with 134 of fees, both from the Boston Fed
    ("2021-06-29", -10049),  # CPFF: 10,000 of equity and 49 of income distributions
    ("2021-09-24", -1017),  # 1,000 of equity and 17 of undocumented earnings
    ("2021-10-15", -501),  # 500 of equity; 1 is rounding of two published millions
    ("2021-11-19", -5601),  # another facility's 5,139 of equity and CCF's operating-account earnings
    ("2021-12-14", -2),  # CCF's expense-reserve distribution; no equity change
    ("2021-12-17", -976),  # 976 returned against an equity reduction of 1,000
]
CONTRIBUTIONS = {"2020-05-13": 47500, "2020-06-17": 65000, "2021-01-06": 23706, "2021-04-14": 22206,
                 "2021-06-30": 12206, "2021-09-29": 11206, "2021-10-20": 10706, "2021-11-24": 5567,
                 "2021-12-22": 4567}  # H.4.1 level from each date
DOMESTIC = {  # DTS Table III-A Domestic Series postings
    ("2019-10-15", "Redemptions"): 4522,  # zero-coupon bond maturity, another holder
    ("2020-05-22", "Issues"): 40375,  # LLC purchase
    ("2020-06-15", "Issues"): 1,  # reinvested interest
    ("2020-07-15", "Redemptions"): 5026,  # zero-coupon bond maturity, another holder
    ("2021-01-04", "Redemptions"): 35200,  # LLC redemption
}
Z1 = {"2020Q2": 40376, "2020Q3": 40376, "2020Q4": 40376, "2021Q1": 5176, "2021Q2": 5176, "2021Q3": 5176,
      "2021Q4": 5176}


def esf_frame(rows=ESF):
    """One ESF row on every publication date from the category's first posting, zero where nothing moved."""
    amounts = dict(rows)
    days = CALENDAR[CALENDAR >= pd.Timestamp(min(amounts))]
    return pd.DataFrame([dict(record_date=str(d.date()), account_type="Federal Reserve Account",
                              transaction_type="Withdrawals", transaction_catg="ESF - Economic Recovery Programs",
                              transaction_today_amt=str(amounts.get(str(d.date()), 0))) for d in days])


def calendar_frame(days=CALENDAR):
    return pd.DataFrame({"record_date": [str(d.date()) for d in days]})


def contributions_frame(levels=CONTRIBUTIONS):
    dates = pd.date_range("2019-12-25", "2022-01-05", freq="W-WED")
    level = pd.Series(0.0, index=dates)
    for date, value in sorted(levels.items()):
        level[dates >= pd.Timestamp(date)] = value
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "value": level.map("{:g}".format).to_numpy()})


def domestic_frame(postings=DOMESTIC):
    rows = []
    for day in CALENDAR:
        fiscal_year = day.year + (day.month >= 10)
        for line in ("Issues", "Redemptions"):
            rows.append(dict(record_date=str(day.date()), security_market="Nonmarketable", security_type="Domestic Series",
                             transaction_type=line, transaction_today_amt=postings.get((str(day.date()), line), 0),
                             record_fiscal_year=str(fiscal_year)))
    frame = pd.DataFrame(rows)
    frame["transaction_fytd_amt"] = frame.groupby(["transaction_type", "record_fiscal_year"])["transaction_today_amt"].cumsum()
    return frame.astype(str)


def mspd_frame(zero_coupon=(("2019-10-15", 4522.0), ("2020-07-15", 5026.13), ("2030-01-15", 5002.232))):
    rows = []
    for month in pd.date_range("2019-09-30", "2021-12-31", freq="ME"):
        detail = [("Zero-coupon Treasury Bond", maturity, amount) for maturity, amount in zero_coupon
                  if pd.Timestamp(maturity) > month]
        spv = (40375.0 if month >= pd.Timestamp("2020-05-31") else 0.0) + (1.4 if month >= pd.Timestamp("2020-06-30") else 0.0)
        spv -= 35200.0 if month >= pd.Timestamp("2021-01-31") else 0.0
        if spv:
            detail.append(("SPV Demand", "null", spv))
        if month < pd.Timestamp("2020-01-01"):
            detail.append(("Fixed Term Certificates", "null", "*"))  # another holder, printed below half a million
        for line, (label, maturity, amount) in enumerate(detail):
            rows.append(dict(record_date=str(month.date()), security_class1_desc="Domestic Series", security_class2_desc=label,
                             maturity_date=maturity, current_month_outstanding_amt=amount if amount == "*" else f"{amount:.6f}",
                             src_line_nbr=str(line)))
        total = sum(a for *_, a in detail if a != "*")
        rows.append(dict(record_date=str(month.date()), security_class1_desc="Total Domestic Series", security_class2_desc="null",
                         maturity_date="null", current_month_outstanding_amt=f"{total:.6f}", src_line_nbr="99"))
    return pd.DataFrame(rows)


def z1_frame(levels=Z1):
    quarters = pd.period_range("2001Q4", VINTAGE.quarter_end, freq="Q")
    return pd.DataFrame({"date": quarters.end_time.strftime("%Y-%m-%d"),
                         "value": [str(levels.get(str(q), 0)) for q in quarters]})


def build(**overrides):
    frames = dict(esf_frame=esf_frame(), esf_window=ESF_WINDOW, contributions_frame=contributions_frame(),
                  domestic_series_frame=domestic_frame(), domestic_series_window=DS_WINDOW, mspd_frame=mspd_frame(),
                  z1_frame=z1_frame(), calendar_frame=calendar_frame(), calendar_window=DS_WINDOW, vintage=VINTAGE)
    return build_treasury_fed_transfers(**{**frames, **overrides})


def esf_postings_by_date(ledger):
    return ledger.postings.loc[ledger.postings.family.eq("esf_economic_recovery")].set_index("date")


def test_h41_lag_and_mmlf_fees_settled_by_the_boston_fed_are_internal():
    ledger = build()
    esf = esf_postings_by_date(ledger)
    # The April payment matches the 2020-05-13 H.4.1 change together with the May payment.
    assert esf.loc[["2020-04-13", "2020-05-11"], "match_wednesday"].eq("2020-05-13").all()
    assert esf.loc[["2020-04-13", "2020-05-11"], "equity_principal_cash"].tolist() == [-10000, -37500]
    # MMLF: the Boston Fed returned the 1,500 protection and paid the 134 fees, so all of it leaves the cash term.
    mmlf = esf.loc["2021-04-12"]
    assert (mmlf.equity_principal_cash, mmlf.internal_cash_effect, mmlf.retained_cash_effect) == (1500, 1634, 0)
    assert mmlf.settlement_status == "facility_earnings_documented_fed_settlement"


def test_cpff_receipt_splits_preferred_account_earnings_from_operating_account_distributions():
    cpff = esf_postings_by_date(build()).loc["2021-06-29"]
    # 10,000 of equity and 4.830 of preferred-account earnings settled at the Fed; 44.235 came from State Street.
    assert cpff.internal_cash_effect == pytest.approx(10004.830)
    assert cpff.retained_cash_effect == pytest.approx(44.170)
    assert cpff.settlement_status == "facility_earnings_split_documented"


def test_ccf_distributions_stay_in_the_cash_term_with_or_without_a_same_day_equity_return():
    esf = esf_postings_by_date(build())
    november, december = esf.loc["2021-11-19"], esf.loc["2021-12-14"]
    # November shares its DTS posting with another facility's 5,139 equity return; only that principal leaves.
    assert (november.internal_cash_effect, november.retained_cash_effect) == (5139, 462)
    assert november.settlement_status == "facility_earnings_commercial_settlement_documented_retained"
    assert (december.internal_cash_effect, december.retained_cash_effect) == (0, 2)
    assert december.classification == "facility_earnings_documented"
    assert december.settlement_status == november.settlement_status


def test_undocumented_excess_is_retained_rounding_and_shortfall_are_principal():
    esf = esf_postings_by_date(build())
    assert (esf.loc["2021-09-24", "internal_cash_effect"], esf.loc["2021-09-24", "retained_cash_effect"]) == (1000, 17)
    assert esf.loc["2021-09-24", "settlement_status"] == "facility_earnings_settlement_account_unverified_retained"
    assert esf.loc["2021-10-15", ["internal_cash_effect", "settlement_status"]].tolist() == [501, "equity_principal_rounding"]
    # 976 returned against a 1,000 reduction: all the cash is principal; the rest of the reduction moved no cash.
    assert esf.loc["2021-12-17", ["internal_cash_effect", "settlement_status"]].tolist() == [976, "equity_principal_shortfall"]


def test_non_facility_esf_payment_stays_in_the_cash_term():
    ledger = build()
    row = esf_postings_by_date(ledger).loc["2020-09-25"]
    assert row.classification == "esf_unclassified" and row.cash_effect == -595 and row.internal_cash_effect == 0
    q = ledger.quarterly.set_index("quarter").loc["2020Q3"]
    assert q.internal_cash_tx == 0 and q.esf_unclassified_cash_tx == -595 and q.esf_retained_dates == "2020-09-25:-595"


def test_quarterly_and_weekly_internal_cash_follow_dts_dates():
    ledger = build()
    q = ledger.quarterly.set_index("quarter")
    # Equity paid (-65,000) less the LLC purchase (+40,375); reinvested interest moves no cash.
    assert q.loc["2020Q2", ["facility_internal_cash_tx", "llc_treasury_securities_cash_tx", "internal_cash_tx"]].tolist() == [
        -65000, 40375, -24625]
    assert q.loc["2020Q2", "llc_capitalized_interest_memo"] == 1
    assert q.loc["2021Q1", "internal_cash_tx"] == 41294 - 35200
    assert q.loc["2021Q2", "internal_cash_tx"] == pytest.approx(1634 + 10004.830)
    assert q.loc["2021Q3", "internal_cash_tx"] == 1000 and q.loc["2021Q4", "internal_cash_tx"] == 501 + 5139 + 976
    assert q.loc["2021Q4", "facility_receipt_retained_tx"] == 464
    # The zero-coupon maturities belong to another holder and stay in TDC.
    assert q.loc["2020Q3", ["internal_cash_tx", "other_domestic_series_cash_tx"]].tolist() == [0, -5026]
    assert q.loc["2002Q1":"2020Q1", "internal_cash_tx"].eq(0).all()
    w = ledger.weekly.set_index("date")
    assert w.loc["2020-04-15", "facility_internal_cash_tx"] == -10000  # DTS week, not the H.4.1 week
    assert w.loc["2020-05-13", "facility_internal_cash_tx"] == -37500
    assert w.loc["2020-05-27", "llc_treasury_securities_cash_tx"] == 40375
    assert w["internal_cash_tx"].sum() == pytest.approx(q["internal_cash_tx"].sum())
    # The first week starts before the DTS ESF window: no ESF cash is reported, and the liability is zero.
    assert pd.isna(w.loc["2020-01-01", "esf_cash_tx"]) and w.loc["2020-01-01", "equity_basis"].startswith("zero_h41")


def test_support_series_is_explicit_in_every_quarter():
    q = build().quarterly
    expected = pd.period_range("2002Q1", VINTAGE.quarter_end, freq="Q")
    assert q.quarter.tolist() == expected.astype(str).tolist()
    assert np.isfinite(q.internal_cash_tx).all()
    assert q.date.tolist() == expected.end_time.strftime("%Y-%m-%d").tolist()
    before = q.set_index("quarter").loc[:"2019Q3"]
    assert before.equity_basis.eq("zero_h41_contribution_liability_zero_before_dts_window").all()
    assert before.llc_basis.eq("zero_z1_llc_level_zero_before_dts_window").all()
    assert q.set_index("quarter").loc["2021Q1", "reconciliation_status"] == "reconciled_within_rounding"


def test_settlement_exceptions_must_reconcile_and_fall_on_a_posting():
    from tdc_estimator.catalog import TREASURY_FED_SETTLEMENT_EXCEPTIONS, SettlementException

    wrong = (*TREASURY_FED_SETTLEMENT_EXCEPTIONS[:3],
             SettlementException("CCF", "2021-11-19", 300.0, "State Street", "earnings", "retained", "fixture"),
             TREASURY_FED_SETTLEMENT_EXCEPTIONS[4])
    with pytest.raises(ValueError, match="2021-11-19 total"):
        build(exceptions=wrong)
    stale = (*TREASURY_FED_SETTLEMENT_EXCEPTIONS,
             SettlementException("CCF", "2021-12-15", 1.0, "State Street", "earnings", "retained", "fixture"))
    with pytest.raises(ValueError, match="without an ESF posting"):
        build(exceptions=stale)


def test_h41_change_without_dated_cash_or_outside_tolerance_raises():
    with pytest.raises(ValueError, match="no dated DTS ESF cash"):
        build(esf_frame=esf_frame([row for row in ESF if row[0] != "2020-04-13"]))
    # Cash 16 percent above the equity change does not identify the 2021-04-14 change.
    with pytest.raises(ValueError, match="2021-04-14 has no dated DTS ESF cash"):
        build(esf_frame=esf_frame([(d, -1750 if d == "2021-04-12" else a) for d, a in ESF]))


def test_failed_z1_reconciliation_or_unknown_holder_raises():
    with pytest.raises(ValueError, match="differ from Z.1"):
        build(z1_frame=z1_frame({**Z1, "2021Q1": Z1["2021Q1"] + 100}))
    # Without the MSPD maturity the 2020-07-15 redemption would be read as the LLCs' and the level breaks.
    with pytest.raises(ValueError, match="differ from Z.1"):
        build(mspd_frame=mspd_frame(zero_coupon=(("2019-10-15", 4522.0), ("2030-01-15", 5002.232))))
    with pytest.raises(ValueError, match="before any DTS LLC posting"):
        build(z1_frame=z1_frame({**Z1, "2019Q4": 10}))
    starred = mspd_frame()
    starred.loc[starred.security_class2_desc.eq("SPV Demand").idxmax(), "current_month_outstanding_amt"] = "*"
    with pytest.raises(ValueError, match="printed below half a million"):
        build(mspd_frame=starred)
    unknown = mspd_frame()
    unknown.loc[0, "security_class2_desc"] = "Another holder"
    with pytest.raises(ValueError, match="unknown holder classes"):
        build(mspd_frame=unknown)


def test_missing_domestic_row_raises_although_fytd_and_z1_still_reconcile():
    frame = domestic_frame()
    issue = frame.record_date.eq("2020-05-22") & frame.transaction_type.eq("Issues")
    with pytest.raises(ValueError, match="without both Issues and Redemptions"):
        build(domestic_series_frame=frame.loc[~issue])


def test_missing_domestic_day_raises():
    frame = domestic_frame()
    # A day with a posting fails the fiscal-year-to-date step; a quiet day fails the publication calendar.
    with pytest.raises(ValueError, match="fiscal-year-to-date steps"):
        build(domestic_series_frame=frame.loc[frame.record_date.ne("2020-05-22")])
    with pytest.raises(ValueError, match="DTS publication calendar; missing \\['2020-05-26'\\]"):
        build(domestic_series_frame=frame.loc[frame.record_date.ne("2020-05-26")])


def test_daily_fytd_step_catches_a_zeroed_posting():
    frame = domestic_frame()
    issue = frame.record_date.eq("2020-05-22") & frame.transaction_type.eq("Issues")
    frame.loc[issue, "transaction_today_amt"] = "0"  # fiscal-year-to-date totals left intact
    with pytest.raises(ValueError, match="fiscal-year-to-date steps"):
        build(domestic_series_frame=frame)


def test_missing_esf_day_raises_against_the_publication_calendar():
    frame = esf_frame()
    with pytest.raises(ValueError, match="DTS ESF economic-recovery cash: dates differ"):
        build(esf_frame=frame.loc[frame.record_date.ne("2020-08-03")])


def test_malformed_cash_is_never_zero_filled():
    bad = esf_frame()
    bad.loc[bad.record_date.eq("2020-09-25"), "transaction_today_amt"] = "null"
    with pytest.raises(ValueError, match="missing or nonnumeric"):
        build(esf_frame=bad)
    gap = contributions_frame()
    with pytest.raises(ValueError, match="consecutive"):
        build(contributions_frame=gap.drop(gap.index[10]))


def _git(root, *args):
    subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c",
                    "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-C", str(root), *args],
                   check=True, capture_output=True)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_cli_writes_hash_bound_ledger_and_support_file(tmp_path, monkeypatch):
    monkeypatch.setitem(MEASUREMENT_VINTAGES, VINTAGE.name, VINTAGE)
    registries = fiscus_registries(VINTAGE)
    frames = {("weekly-trc", "internal_dts"): esf_frame(), ("weekly-trc", "remittances"): calendar_frame(),
              ("h41-ledger", "treasury_contributions_to_credit_facilities"): contributions_frame(),
              ("treasury-fed-transfers", "dts_domestic_series"): domestic_frame(),
              ("treasury-fed-transfers", "mspd_domestic_series"): mspd_frame(),
              ("treasury-fed-transfers", "z1_llc_treasury_level"): z1_frame()}
    hashes = {}
    for name in ["treasury-fed-transfers", "weekly-trc", "h41-ledger"]:
        registry = registries[name]
        (tmp_path / registry.input_dir).mkdir(parents=True, exist_ok=True)
        inputs = {}
        for spec in registry.inputs:
            relative = registry.input_dir / f"{spec.key}.csv"
            frame = frames.get((name, spec.key))
            data = (b"date,value\n" if frame is None else frame.to_csv(index=False, lineterminator="\n").encode())
            (tmp_path / relative).write_bytes(data)
            inputs[spec.key] = {"dataset_id": spec.dataset_id, "argv": list(spec.argv), "file": relative.as_posix(),
                                "sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data), "cache_key": "fixture",
                                "retrieved_at_utc": "fixture", "vintage": "fixture", "source_url": "fixture",
                                "source_metadata": {}, "row_count": 0, "data_coverage": {}}
        (tmp_path / registry.manifest).write_text(json.dumps({"schema_version": registry.schema_version, "inputs": inputs}))
        hashes[name] = _sha(tmp_path / registry.manifest)
    (tmp_path / ".gitignore").write_text("data/\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".gitignore")
    _git(tmp_path, "commit", "-q", "-m", "fixture")
    args = ["treasury-fed-transfer-export", "--root", str(tmp_path), "--inputs-manifest-sha256",
            hashes["treasury-fed-transfers"], "--weekly-trc-manifest-sha256", hashes["weekly-trc"],
            "--h41-ledger-manifest-sha256", hashes["h41-ledger"], "--vintage", VINTAGE.name]
    assert main(args) == 0
    receipt = json.loads((tmp_path / "data/processed" / OUTPUT_FILES["receipt"]).read_text())
    for output in receipt["outputs"].values():
        assert _sha(tmp_path / output["path"]) == output["sha256"]
    support = pd.read_csv(tmp_path / "data/raw" / SUPPORT_FILE)
    assert list(support.columns) == ["date", "value"] and len(support) == 80 and support.value.notna().all()
    assert support.set_index("date").loc["2020-06-30", "value"] == -24625
    assert receipt["stats"]["esf_retained"]["through_data_end"]["esf_unclassified"] == {"n": 1, "net": -595, "abs": 595}
    assert receipt["settlement_exceptions"]["rows"][0]["facility"] == "MMLF"
    (tmp_path / "dirty.txt").write_text("dirty")
    with pytest.raises(ValueError, match="clean committed"):
        main(args)
    (tmp_path / "dirty.txt").unlink()
    with pytest.raises(ValueError, match="hash mismatch"):
        main([*args[:4], "0" * 64, *args[5:]])


@pytest.mark.integration
def test_retained_2026q2_inputs_reproduce_the_ledger():
    import os
    from pathlib import Path

    from tdc_estimator.trc_export import load_fiscus_inputs
    from tdc_estimator.treasury_fed_transfers import query_window, support_frame

    root = Path(os.environ.get("TDCEST_TRANSFERS_ROOT", Path(__file__).resolve().parents[1] / "data" / "refresh_2026q2"))
    vintage = MEASUREMENT_VINTAGES["2026q2"]
    registries = fiscus_registries(vintage)
    receipt_path = root / "data/processed" / OUTPUT_FILES["receipt"]
    needed = [receipt_path, *(root / registries[n].manifest for n in ["treasury-fed-transfers", "weekly-trc", "h41-ledger"])]
    missing = [str(p) for p in needed if not p.exists()]
    if missing:
        pytest.fail(f"integration inputs absent: {missing}")
    frames = {name: load_fiscus_inputs(root, json.loads((root / registries[name].manifest).read_text()), registries[name])[0]
              for name in ["treasury-fed-transfers", "weekly-trc", "h41-ledger"]}

    def window(name, key):
        return query_window(next(s for s in registries[name].inputs if s.key == key).argv)

    ledger = build_treasury_fed_transfers(
        esf_frame=frames["weekly-trc"]["internal_dts"], esf_window=window("weekly-trc", "internal_dts"),
        contributions_frame=frames["h41-ledger"]["treasury_contributions_to_credit_facilities"],
        domestic_series_frame=frames["treasury-fed-transfers"]["dts_domestic_series"],
        domestic_series_window=window("treasury-fed-transfers", "dts_domestic_series"),
        mspd_frame=frames["treasury-fed-transfers"]["mspd_domestic_series"],
        z1_frame=frames["treasury-fed-transfers"]["z1_llc_treasury_level"], vintage=vintage)
    receipt = json.loads(receipt_path.read_text())
    payloads = {role: getattr(ledger, role).to_csv(index=False, lineterminator="\n").encode() for role in
                ["postings", "quarterly", "weekly"]}
    payloads["support"] = support_frame(ledger.quarterly).to_csv(index=False, lineterminator="\n").encode()
    for role, data in payloads.items():
        assert hashlib.sha256(data).hexdigest() == receipt["outputs"][role]["sha256"], role
    q = ledger.quarterly.set_index("quarter")["internal_cash_tx"]
    # 2020Q2: 114,000 of facility equity paid out less 95,625 of LLC Treasury purchases.
    assert q["2020Q2"] == -18375 and q["2021Q1"] == 9122 and q.loc[:"2020Q1"].eq(0).all()
    assert ledger.stats["facility_equity_matches"]["n_h41_changes"] == 21
    assert ledger.stats["z1_reconciliation_max_ratio_to_bound"] < 1
    assert ledger.stats["zero_coupon_maturities_in_dts_window"] == [
        "2019-10-15:-4522", "2020-07-15:-5026", "2020-10-15:-5003", "2021-01-15:-4941"]
