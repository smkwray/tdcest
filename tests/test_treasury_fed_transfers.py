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

VINTAGE = MeasurementVintage("fixture", "2021Q2", "2021-06-30")
ESF_WINDOW = (pd.Timestamp("2020-01-01"), pd.Timestamp("2021-06-30"))
DS_WINDOW = (pd.Timestamp("2019-10-01"), pd.Timestamp("2021-06-30"))
ESF = [  # DTS Table II ESF economic-recovery withdrawals; a negative withdrawal returns cash
    ("2020-04-13", 10000),  # facility equity; H.4.1 records it on 2020-05-13
    ("2020-05-11", 37500),  # facility equity
    ("2020-09-25", 595),  # a direct loan to a business: no H.4.1 contribution change
    ("2021-01-05", -41294),  # equity returned
    ("2021-04-12", -1634),  # equity returned with 134 of earnings against an H.4.1 change of 1,500
]
CONTRIBUTIONS = {"2020-05-13": 47500, "2021-01-06": 6206, "2021-04-14": 4706}  # H.4.1 level from each date
DOMESTIC = {  # DTS Table III-A Domestic Series postings
    ("2019-10-15", "Redemptions"): 4522,  # zero-coupon bond maturity, another holder
    ("2020-05-22", "Issues"): 40375,  # LLC purchase
    ("2020-06-15", "Issues"): 1,  # reinvested interest
    ("2020-07-15", "Redemptions"): 5026,  # zero-coupon bond maturity, another holder
    ("2021-01-04", "Redemptions"): 35200,  # LLC redemption
}
Z1 = {"2020Q2": 40376, "2020Q3": 40376, "2020Q4": 40376, "2021Q1": 5176, "2021Q2": 5176}


def esf_frame(rows=ESF):
    return pd.DataFrame([dict(record_date=d, account_type="Federal Reserve Account", transaction_type="Withdrawals",
                              transaction_catg="ESF - Economic Recovery Programs", transaction_today_amt=str(a))
                         for d, a in rows])


def contributions_frame(levels=CONTRIBUTIONS):
    dates = pd.date_range("2019-12-25", "2021-06-30", freq="W-WED")
    level = pd.Series(0.0, index=dates)
    for date, value in sorted(levels.items()):
        level[dates >= pd.Timestamp(date)] = value
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "value": level.map("{:g}".format).to_numpy()})


def domestic_frame(postings=DOMESTIC):
    rows = []
    for day in pd.bdate_range(*DS_WINDOW):
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
    for month in pd.date_range("2019-09-30", "2021-06-30", freq="ME"):
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
                  z1_frame=z1_frame(), vintage=VINTAGE)
    return build_treasury_fed_transfers(**{**frames, **overrides})


def postings_by_date(ledger):
    return ledger.postings.set_index(["date", "dts_line"])


def test_h41_lag_and_earnings_inclusive_return_classify_as_facility_equity():
    ledger = build()
    esf = ledger.postings.loc[ledger.postings.leg.eq("facility_equity")].set_index("date")
    # The April payment matches the 2020-05-13 H.4.1 change together with the May payment.
    assert esf.loc[["2020-04-13", "2020-05-11"], "match_wednesday"].eq("2020-05-13").all()
    assert esf.loc[["2020-04-13", "2020-05-11"], "classification"].eq("facility_equity_payment").all()
    # A return carrying earnings is the facility's cash in full: 1,634 against an H.4.1 change of 1,500.
    assert esf.loc["2021-04-12", "classification"] == "facility_equity_return"
    assert esf.loc["2021-04-12", "internal_cash_effect"] == 1634
    match = ledger.matches.set_index("h41_wednesday")
    assert match.loc["2020-05-13", "posting_dates"] == "2020-04-13|2020-05-11"
    assert match.loc["2021-04-14", "cash_minus_equity_change"] == 134


def test_non_facility_esf_payment_stays_in_tdc():
    ledger = build()
    row = ledger.postings.set_index("date").loc["2020-09-25"]
    assert row.classification == "esf_unmatched" and row.cash_effect == -595 and row.internal_cash_effect == 0
    q = ledger.quarterly.set_index("quarter").loc["2020Q3"]
    assert q.internal_cash_tx == 0 and q.esf_unmatched_cash_tx == -595 and q.esf_unmatched_dates == "2020-09-25:-595"


def test_quarterly_and_weekly_internal_cash_follow_dts_dates():
    ledger = build()
    q = ledger.quarterly.set_index("quarter")
    # Equity paid (-47,500) less the LLC purchase (+40,375); reinvested interest moves no cash.
    assert q.loc["2020Q2", ["facility_equity_cash_tx", "llc_treasury_securities_cash_tx", "internal_cash_tx"]].tolist() == [
        -47500, 40375, -7125]
    assert q.loc["2020Q2", "llc_capitalized_interest_memo"] == 1
    assert q.loc["2021Q1", "internal_cash_tx"] == 41294 - 35200
    assert q.loc["2021Q2", "internal_cash_tx"] == 1634
    # The zero-coupon maturities belong to another holder and stay in TDC.
    assert q.loc["2020Q3", ["internal_cash_tx", "other_domestic_series_cash_tx"]].tolist() == [0, -5026]
    assert q.loc["2002Q1":"2020Q1", "internal_cash_tx"].eq(0).all()
    w = ledger.weekly.set_index("date")
    assert w.loc["2020-04-15", "facility_equity_cash_tx"] == -10000  # DTS week, not the H.4.1 week
    assert w.loc["2020-05-13", "facility_equity_cash_tx"] == -37500
    assert w.loc["2020-05-27", "llc_treasury_securities_cash_tx"] == 40375
    assert w["internal_cash_tx"].sum() == q["internal_cash_tx"].sum()
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


def test_h41_change_without_dated_cash_or_outside_tolerance_raises():
    with pytest.raises(ValueError, match="no dated DTS ESF cash"):
        build(esf_frame=esf_frame([row for row in ESF if row[0] != "2020-04-13"]))
    # Cash 16 percent above the equity change is not a return with earnings.
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
    missing = domestic_frame({k: v for k, v in DOMESTIC.items() if k[0] != "2020-07-15"})
    with pytest.raises(ValueError, match="2020-07-15 .* no unique DTS redemption"):
        build(domestic_series_frame=missing)


def test_malformed_cash_is_never_zero_filled():
    bad = esf_frame()
    bad.loc[2, "transaction_today_amt"] = "null"
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
    frames = {("weekly-trc", "internal_dts"): esf_frame(),
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
    assert list(support.columns) == ["date", "value"] and len(support) == 78 and support.value.notna().all()
    assert support.set_index("date").loc["2020-06-30", "value"] == -7125
    assert receipt["stats"]["esf_unmatched"]["cash_effect"] == -595
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
