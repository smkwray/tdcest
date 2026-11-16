"""Quarterly interest on marketable debt, its debt and rate effects and its holder split.

The fixture FiscalData lines vary by month, the allocation repeats each family pool on every
sector row as the producer does, and the excluded lines and the Federal Financing Bank are
large enough to dominate the result if they leaked in. Expected values are written out here
from the stated method, independently of the module.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
import pytest

from tdc_estimator import catalog
from tdc_estimator.cli import main
from tdc_estimator.interest_rate_debt import (
    ALLOCATION_FILE,
    DEBT_KEY,
    INTEREST_KEY,
    OUTPUT_FILES,
    build_interest_rate_debt,
)
from tdc_estimator.trc_export import load_fiscus_inputs

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = catalog.FISCUS_REGISTRIES["interest-rate-debt"]
QUARTERS = pd.period_range(*catalog.INTEREST_RATE_DEBT_SAMPLE, freq="Q")
BASE = pd.Period(catalog.INTEREST_RATE_DEBT_BASE_QUARTER, "Q")
FLOW_MONTHS = pd.period_range(QUARTERS[0].asfreq("M", "start"), QUARTERS[-1].asfreq("M", "end"), freq="M")
DEBT_MONTHS = pd.period_range(FLOW_MONTHS[0] - 1, FLOW_MONTHS[-1], freq="M")
PUBLIC, GAS = "INTEREST EXPENSE ON PUBLIC ISSUES", "INTEREST EXPENSE ON GOVT ACCOUNT SERIES"
ACCRUED, DISCOUNT, PREMIUM = "ACCRUED INTEREST EXPENSE", "AMORTIZED DISCOUNT", "AMORTIZED PREMIUM"
LINES = [  # (group, type, family, USD per month at month index t)
    (ACCRUED, "Treasury Notes", "coupon_accrual", lambda t: 20e9 + 0.1e9 * t),
    (ACCRUED, "Treasury Bonds", "coupon_accrual", lambda t: 8e9 + 0.02e9 * t),
    (ACCRUED, "Inflation Protected Securities (TIPS)", "coupon_accrual", lambda t: 1e9 + 0.01e9 * t),
    (DISCOUNT, "Treasury Bills", "bill_discount", lambda t: 5e9 + 0.05e9 * t),
    (ACCRUED, "Treasury Floating Rate Notes (FRN)", "frn_interest", lambda t: 0.5e9 + 0.01e9 * t),
    (ACCRUED, "Int. Expense Inflation Compensation (TIPS)", "tips_ic", lambda t: 2e9 + 1e9 * np.sin(t)),
    (DISCOUNT, "Treasury Notes", "amortization", lambda t: 0.6e9 + 0.0 * t),
    (PREMIUM, "Treasury Bonds", "amortization", lambda t: -0.3e9 - 0.001e9 * t),
]
EXCLUDED = [  # (category, group, type): nonmarketable or off-perimeter lines
    (PUBLIC, "SAVINGS BONDS", "Series I"),
    (PUBLIC, ACCRUED, "State & Local Government-C/I's, Notes & Bonds"),
    (PUBLIC, ACCRUED, "Foreign Series - C/I, Notes & Bonds"),
    (PUBLIC, ACCRUED, "Matured Debt"),
    (GAS, "CASH BASIS GAS PAYMENTS", "Interest Payments"),
]
FAMILIES = list(catalog.INTEREST_POOL_FAMILIES)
FED_FROM = {"coupon_accrual": QUARTERS[0], "bill_discount": pd.Period("2019Q2", "Q"),
            "frn_interest": pd.Period("2024Q3", "Q")}


def make_interest(excluded_usd: float = 50e9, lines=LINES) -> pd.DataFrame:
    rows = []
    t = np.arange(len(FLOW_MONTHS))
    values = [np.asarray(value(t), dtype=float) for *_, value in lines]
    for n, month in enumerate(FLOW_MONTHS):
        date = month.end_time.strftime("%Y-%m-%d")
        rows += [(date, PUBLIC, group, typ, f"{v[n]:.2f}") for (group, typ, *_), v in zip(lines, values, strict=True)]
        rows += [(date, category, group, typ, f"{excluded_usd:.2f}") for category, group, typ in EXCLUDED]
    return pd.DataFrame(rows, columns=["record_date", "expense_catg_desc", "expense_group_desc",
                                       "expense_type_desc", "month_expense_amt"])


def quarterly_by_family() -> pd.DataFrame:
    """FiscalData family sums by quarter, USD million, from the same arithmetic as the fixture strings."""
    t = np.arange(len(FLOW_MONTHS))
    frame = pd.DataFrame({n: np.round(np.asarray(value(t), dtype=float), 2) for n, (*_, value) in enumerate(LINES)},
                         index=FLOW_MONTHS)
    by_family = frame.T.groupby([family for *_, family, _ in LINES]).sum().T
    return by_family.groupby(FLOW_MONTHS.asfreq("Q")).sum() / 1e6


def month_end_debt() -> np.ndarray:
    """Marketable debt less FFB, USD million: 4.5% growth to 2020, then faster and bumpy."""
    t = np.arange(len(DEBT_MONTHS)) / 12
    return np.round(12_000_000 * np.exp(0.045 * t + 0.04 * np.clip(t - 5.0, 0, None)) + 50_000 * np.sin(3 * t), 4)


def make_mspd(ffb: float = 900_000.0, debt: np.ndarray | None = None) -> pd.DataFrame:
    """Embedded totals, class subtotals with varying labels, and CUSIP rows with reopening duplicates."""
    debt = month_end_debt() if debt is None else debt
    rows = []
    for month, total in zip(DEBT_MONTHS, debt, strict=True):
        date = month.end_time.strftime("%Y-%m-%d")
        bills, frn = 0.2 * total, 0.05 * total
        notes = total - bills - frn
        rows += [
            (date, "Bills Maturity Value", "Total Matured Treasury Bills", "*"),
            (date, "Bills Maturity Value", "Total Treasury Bills", f"{bills:.4f}"),
            (date, "Bills Maturity Value", "912796AA1", f"{bills:.4f}"),
            (date, "Notes", "912828AA1", f"{notes - 30:.4f}"),
            (date, "Notes", "912828AA1", ""),  # a reopening row carries no amount
            (date, "Notes", "Total Matured Treasury Notes", "30.0000"),
            (date, "Notes", "Total Treasury Notes", f"{notes:.4f}"),
            (date, "Floating Rate Notes", "Treasury Floating Rate Notes", f"{frn - 40:.4f}"),
            (date, "Floating Rate Notes", "Total Tresasury Floating Rate Notes", f"{frn:.4f}"),
            (date, "Federal Financing Bank", "", f"{ffb:.4f}"),
            (date, "Total Marketable", "", f"{total + ffb:.4f}"),
        ]
    return pd.DataFrame(rows, columns=["record_date", "security_class1_desc", "security_class2_desc",
                                       "outstanding_amt"])


def sector_fractions(quarter: pd.Period) -> dict[str, float]:
    """Allocated fractions of the allocation pool; foreign holders lose share after the base quarter."""
    after = max((quarter - BASE).n, 0)
    return {"row": 0.45 - 0.004 * after, "bank": 0.04 + 0.001 * after, "credit_union": 0.01}


def make_allocation(pools: pd.DataFrame | None = None) -> pd.DataFrame:
    """The producer's shape: one row per quarter-end x sector group x family, pools repeated across sectors."""
    pools = quarterly_by_family() if pools is None else pools
    rows = []
    for quarter in QUARTERS:
        for family in FAMILIES:
            pool = pools.loc[quarter, family]
            fed = 0.2 * pool if quarter >= FED_FROM[family] else np.nan
            available = pool - (0.0 if np.isnan(fed) else fed)
            for sector, fraction in sector_fractions(quarter).items():
                mid = fraction * available
                rows.append({"date": quarter.end_time.strftime("%Y-%m-%d"), "sector_group": sector,
                             "component_family": family, "official_component_pool_mil": pool,
                             "fed_exact_component_mil": fed, "allocation_pool_mil": available,
                             "component_anchored_interest_mil": mid, "component_anchored_interest_low_mil": 0.9 * mid,
                             "component_anchored_interest_high_mil": 1.2 * mid})
    return pd.DataFrame(rows)


def build(interest=None, mspd=None, allocation=None):
    return build_interest_rate_debt(make_interest() if interest is None else interest,
                                    make_mspd() if mspd is None else mspd,
                                    make_allocation() if allocation is None else allocation)


def expected_aggregate() -> pd.DataFrame:
    pools = quarterly_by_family()
    debt = pd.Series(month_end_debt(), index=DEBT_MONTHS)
    D = pd.Series([(debt[q.asfreq("M", "start") - 1] / 2 + debt[q.asfreq("M", "start")]
                    + debt[q.asfreq("M", "start") + 1] + debt[q.asfreq("M", "end")] / 2) / 3 / 1000
                   for q in QUARTERS], index=QUARTERS)
    days = pd.Series([(q.end_time - q.start_time).days + 1 for q in QUARTERS], index=QUARTERS)
    interest = pools[FAMILIES].sum(axis=1) / 1000  # each family pool once
    return pd.DataFrame({"I": interest, "D": D, "days": days, "r": interest / (D * days / 365),
                         "amortization": pools["amortization"] / 1000})


def test_aggregate_columns_follow_the_stated_method_and_the_splits_add_to_the_gap():
    aggregate, _, record = build()
    rows = aggregate.set_index("quarter")
    e = expected_aggregate().set_axis(QUARTERS.astype(str))
    assert list(rows.index) == list(QUARTERS.astype(str))
    # Interest counts each family pool once, although every sector row repeats it.
    np.testing.assert_allclose(rows["interest"], e["I"], rtol=1e-12)
    np.testing.assert_allclose(rows["avg_marketable_debt"], e["D"], rtol=1e-12)
    np.testing.assert_array_equal(rows["days"], e["days"])
    np.testing.assert_allclose(rows["effective_rate_pct"], 100 * e["r"], rtol=1e-12)

    fit = (QUARTERS >= pd.Period(catalog.INTEREST_RATE_DEBT_FIT_WINDOW[0])) & (
        QUARTERS <= pd.Period(catalog.INTEREST_RATE_DEBT_FIT_WINDOW[1]))
    x = np.arange(len(QUARTERS))[fit].astype(float)
    x -= x.mean()
    y = np.log(e["D"].to_numpy()[fit])
    g = float((x * y).sum() / (x * x).sum())  # OLS slope per quarter, written out
    rc = e["r"][str(BASE)]
    assert record["counterfactual"]["g"] == pytest.approx(g, rel=1e-10)
    assert record["counterfactual"]["rc"] == pytest.approx(rc, rel=1e-12)

    after = rows.loc[str(BASE):]
    trend_debt = e["D"][str(BASE)] * np.exp(g * np.arange(len(after)))
    year = after["days"].to_numpy() / 365
    np.testing.assert_allclose(after["trend_debt"], trend_debt, rtol=1e-10)
    np.testing.assert_allclose(after["trend_interest"], trend_debt * rc * year, rtol=1e-10)
    np.testing.assert_allclose(after["debt_only_interest"], after["avg_marketable_debt"] * rc * year, rtol=1e-12)
    gap = after["interest"] - after["trend_interest"]
    for debt, rate in [("debt_effect", "rate_effect"), ("debt_effect_even", "rate_effect_even")]:
        assert (after[debt] + after[rate] - gap).abs().max() <= 1e-9, debt
    # The fixture debt runs above trend after the base quarter, so both splits give it a positive share.
    assert (after.iloc[1:][["debt_effect", "debt_effect_even"]] > 0).all().all()
    assert rows.loc[:str(BASE - 1), "trend_debt":"rate_effect_even"].isna().all().all()
    assert rows.loc[:str(BASE - 1), ["interest", "effective_rate_pct", "pool_minus_fiscaldata"]].notna().all().all()


def test_annualizing_on_calendar_days_keeps_a_constant_daily_rate_flat():
    """Quarters run 90 to 92 days; a constant daily accrual on constant debt is one rate, not four."""
    daily = 1e9
    days_in_month = FLOW_MONTHS.days_in_month.to_numpy().astype(float)

    def per_month(t):
        return daily * days_in_month[np.asarray(t, dtype=int)]

    lines = [(ACCRUED, "Treasury Notes", "coupon_accrual", per_month),
             (DISCOUNT, "Treasury Bills", "bill_discount", per_month),
             (ACCRUED, "Treasury Floating Rate Notes (FRN)", "frn_interest", per_month)]
    pools = pd.DataFrame({family: [daily * ((q.end_time - q.start_time).days + 1) / 1e6 for q in QUARTERS]
                          for family in FAMILIES}, index=QUARTERS)
    aggregate, _, _ = build(make_interest(lines=lines), make_mspd(debt=np.full(len(DEBT_MONTHS), 20_000_000.0)),
                            make_allocation(pools))
    assert set(aggregate["days"]) == {90, 91, 92}
    rate = 100 * 3 * daily * 365 / 20_000_000e6
    np.testing.assert_allclose(aggregate["effective_rate_pct"], rate, rtol=1e-12)
    # Constant debt and rate leave nothing to split.
    after = aggregate[aggregate["quarter"] >= str(BASE)]
    assert after[["debt_effect", "rate_effect"]].abs().max().max() < 1e-9


def test_pool_reconciles_to_fiscaldata_family_by_family():
    aggregate, _, record = build()
    # The pool leaves out the amortized discount and premium on coupon securities, and nothing else.
    np.testing.assert_allclose(aggregate["pool_minus_fiscaldata"], -expected_aggregate()["amortization"], rtol=1e-12)
    assert record["reconciliation"]["family_pool_vs_fiscaldata"]["max_abs_gap_usd_million"] < 1e-6
    off = quarterly_by_family()
    off.loc[pd.Period("2021Q3"), "bill_discount"] += 1.0  # USD 1 million: a different release of the lines
    with pytest.raises(ValueError, match="differs from FiscalData bill_discount by .* in 2021Q3"):
        build(allocation=make_allocation(off))


def test_holders_are_exact_fed_allocated_sectors_and_a_residual_that_sums_to_interest():
    aggregate, holders, record = build()
    allocation = make_allocation()
    allocation["quarter"] = pd.PeriodIndex(pd.to_datetime(allocation["date"]), freq="Q").astype(str)
    mid = allocation.pivot_table(index="quarter", columns="sector_group", values="component_anchored_interest_mil",
                                 aggfunc="sum") / 1000
    fed = allocation.drop_duplicates(["quarter", "component_family"]).groupby("quarter")[
        "fed_exact_component_mil"].sum() / 1000
    table = holders.set_index(["quarter", "holder"])
    interest = aggregate.set_index("quarter")["interest"]
    np.testing.assert_allclose(table.xs("fed", level="holder")["interest"], fed, rtol=1e-12)
    np.testing.assert_allclose(table.xs("foreign", level="holder")["interest"], mid["row"], rtol=1e-12)
    np.testing.assert_allclose(table.xs("banks_credit_unions", level="holder")["interest"],
                               mid["bank"] + mid["credit_union"], rtol=1e-12)
    np.testing.assert_allclose(table.xs("deposit_users", level="holder")["interest"],
                               interest - fed - mid.sum(axis=1), rtol=1e-12)
    np.testing.assert_allclose(holders.groupby("quarter")["interest"].sum(), interest, rtol=1e-12)
    np.testing.assert_allclose(holders.groupby("quarter")["share"].sum(), 1.0, rtol=1e-12)
    # Deposit-user bounds come from the allocated holders' opposite bounds; the Fed has no band.
    users = table.xs("deposit_users", level="holder")
    np.testing.assert_allclose(users["interest_low"], interest - fed - 1.2 * mid.sum(axis=1), rtol=1e-12)
    np.testing.assert_allclose(users["interest_high"], interest - fed - 0.9 * mid.sum(axis=1), rtol=1e-12)
    fed_rows = table.xs("fed", level="holder")
    assert (fed_rows["interest_low"] == fed_rows["interest"]).all()
    assert (fed_rows["interest_high"] == fed_rows["interest"]).all()
    assert list(holders["holder"].iloc[:4]) == list(catalog.INTEREST_HOLDERS)
    assert record["holders"]["fed_exact_absent"] == [
        {"component_family": "bill_discount", "quarters": 17, "first": "2015Q1", "last": "2019Q1"},
        {"component_family": "frn_interest", "quarters": 38, "first": "2015Q1", "last": "2024Q2"}]


def test_shift_share_split_attributes_interest_above_trend_by_base_share_and_share_change():
    aggregate, holders, record = build()
    table = holders.set_index(["quarter", "holder"])
    base = table.xs(str(BASE), level="quarter")
    assert record["counterfactual"]["base_shares"] == pytest.approx(base["share"].to_dict(), rel=1e-12)
    # In the base quarter trend equals actual, so every holder is on trend and nothing has shifted.
    np.testing.assert_allclose(base["trend_interest"], base["interest"], rtol=1e-12)
    assert base[["base_share_part", "shift"]].abs().max().max() < 1e-9
    post = holders[holders["quarter"] > str(BASE)].set_index(["quarter", "holder"])
    agg = aggregate.set_index("quarter")
    gap = post.index.get_level_values("quarter").map(agg["interest"] - agg["trend_interest"]).to_numpy()
    theta_b = post.index.get_level_values("holder").map(base["share"]).to_numpy()
    np.testing.assert_allclose(post["base_share_part"], theta_b * gap, rtol=1e-12)
    np.testing.assert_allclose(post["interest"] - post["trend_interest"], post["base_share_part"] + post["shift"],
                               rtol=0, atol=1e-9)
    assert post.groupby(level="quarter")["shift"].sum().abs().max() < 1e-9
    # Foreign holders lose share after the base quarter in the fixture, so their shift is negative.
    assert (post.xs("foreign", level="holder")["shift"] < 0).all()
    before = holders["quarter"] < str(BASE)
    assert holders.loc[before, ["trend_interest", "base_share_part", "shift"]].isna().all().all()
    for check in record["checks"]["identities"].values():
        assert check["max_abs_gap_usd_billion"] <= check["tolerance"] == 1e-9


def test_inconsistent_or_incomplete_allocation_raises():
    allocation = make_allocation()
    over = allocation.copy()
    hit = (over["date"] == "2023-03-31") & (over["sector_group"] == "row")
    for column in ["component_anchored_interest_mil", "component_anchored_interest_low_mil",
                   "component_anchored_interest_high_mil"]:
        over.loc[hit, column] *= 3  # allocated holders now exceed the pool
    with pytest.raises(ValueError, match=r"exceed the pool in \['2023Q1'\]"):
        build(allocation=over)
    gone = allocation.index[(allocation["date"] == "2017-06-30") & (allocation["sector_group"] == "bank")][:1]
    with pytest.raises(ValueError, match="missing rows"):
        build(allocation=allocation.drop(gone))
    uneven = allocation.copy()
    uneven.loc[uneven.index[0], "official_component_pool_mil"] += 5.0
    with pytest.raises(ValueError, match="differs across sectors"):
        build(allocation=uneven)
    # A missing Fed amount is accepted only where the producer kept the whole pool for allocation.
    taken = allocation.copy()
    early = (taken["date"] == "2016-03-31") & (taken["component_family"] == "frn_interest")
    taken.loc[early, "allocation_pool_mil"] -= 50.0
    with pytest.raises(ValueError, match="no exact Fed amount but the allocation pool"):
        build(allocation=taken)
    blank = allocation.copy()
    blank.loc[5, "component_anchored_interest_mil"] = np.nan
    with pytest.raises(ValueError, match="nonfinite component_anchored_interest_mil"):
        build(allocation=blank)


def test_ffb_and_nonmarketable_lines_are_excluded():
    aggregate, holders, _ = build(make_interest(excluded_usd=50e9), make_mspd(ffb=900_000.0))
    other, other_holders, _ = build(make_interest(excluded_usd=-7e9), make_mspd(ffb=1.0))
    pd.testing.assert_frame_equal(aggregate, other)
    pd.testing.assert_frame_equal(holders, other_holders)
    np.testing.assert_allclose(aggregate["avg_marketable_debt"], expected_aggregate()["D"], rtol=1e-12)


def test_a_missing_month_or_line_raises_instead_of_truncating():
    interest, mspd = make_interest(), make_mspd()
    with pytest.raises(ValueError, match=r"months \['2021-03'\] lack marketable lines"):
        build(interest[interest["record_date"] != "2021-03-31"], mspd)
    one_line = interest.drop(interest.index[(interest["record_date"] == "2016-11-30")
                                            & (interest["expense_group_desc"] == PREMIUM)])
    with pytest.raises(ValueError, match=r"months \['2016-11'\] lack marketable lines"):
        build(one_line, mspd)
    blank = interest.copy()
    blank.loc[3, "month_expense_amt"] = ""
    with pytest.raises(ValueError, match="missing or nonnumeric"):
        build(blank, mspd)
    opening = mspd[mspd["record_date"] != DEBT_MONTHS[0].end_time.strftime("%Y-%m-%d")]
    with pytest.raises(ValueError, match=rf"month-ends \['{DEBT_MONTHS[0]}'\] lack"):
        build(interest, opening)


def test_a_total_that_disagrees_with_its_class_subtotals_raises():
    mspd = make_mspd()
    row = mspd.index[(mspd["record_date"] == "2022-01-31") & (mspd["security_class1_desc"] == "Total Marketable")]
    off = mspd.copy()
    off.loc[row, "outstanding_amt"] = f"{float(mspd.loc[row[0], 'outstanding_amt']) + 1.0:.4f}"
    _, _, record = build(mspd=off)  # a USD 1 million publication inconsistency
    assert record["checks"]["mspd_subtotals"]["month"] == "2022-01"
    off.loc[row, "outstanding_amt"] = f"{float(mspd.loc[row[0], 'outstanding_amt']) + 5_000.0:.4f}"
    with pytest.raises(ValueError, match="differs from the class subtotals by .* in 2022-01"):
        build(mspd=off)
    duplicate = pd.concat([mspd, mspd[mspd["security_class1_desc"] == "Total Marketable"].iloc[:1]])
    with pytest.raises(ValueError, match="more than one Total Marketable"):
        build(mspd=duplicate)


def git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    subprocess.run(["git", "-C", str(root), *args], check=True, env=env, capture_output=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_repo(root: Path) -> tuple[str, str]:
    """A clean committed checkout with the allocation and a fiscus-shaped manifest; returns their hashes."""
    entries = {}
    for spec, frame in zip(REGISTRY.inputs, [make_interest(), make_mspd()], strict=True):
        relative = REGISTRY.input_dir / f"{spec.key}.csv"
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        data = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        (root / relative).write_bytes(data)
        entries[spec.key] = {
            "dataset_id": spec.dataset_id, "argv": list(spec.argv), "file": relative.as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data), "cache_key": "fixture",
            "retrieved_at_utc": "fixture", "vintage": "fixture", "source_url": "fixture", "source_metadata": {},
            "row_count": len(frame), "data_coverage": {},
        }
    manifest = root / REGISTRY.manifest
    manifest.write_text(json.dumps({"schema_version": REGISTRY.schema_version, "inputs": entries}))
    allocation = root / "data" / "processed" / ALLOCATION_FILE
    allocation.parent.mkdir(parents=True, exist_ok=True)
    make_allocation().to_csv(allocation, index=False, lineterminator="\n")
    (root / ".gitignore").write_text("data/\n")
    (root / "README.md").write_text("fixture\n")
    git(root, "init", "-q")
    git(root, "add", ".gitignore", "README.md")
    git(root, "commit", "-q", "-m", "fixture")
    return sha(manifest), sha(allocation)


def export(root: Path, manifest_sha: str, allocation_sha: str) -> int:
    return main(["interest-rate-debt-export", "--root", str(root), "--inputs-manifest-sha256", manifest_sha,
                 "--allocation-sha256", allocation_sha])


def test_cli_exports_hash_bound_tables_and_refuses_unbound_inputs(tmp_path):
    manifest_sha, allocation_sha = make_repo(tmp_path)
    assert export(tmp_path, manifest_sha, allocation_sha) == 0
    processed = tmp_path / "data" / "processed"
    receipt = json.loads((processed / OUTPUT_FILES["receipt"]).read_text())
    for role in ["aggregate", "holders"]:
        path = tmp_path / receipt["outputs"][role]["path"]
        assert path == processed / OUTPUT_FILES[role]
        assert sha(path) == receipt["outputs"][role]["sha256"]
        assert list(pd.read_csv(path).columns) == list(receipt["columns"][role])
    head = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    assert receipt["producer_commit"] == head.strip()
    assert receipt["inputs"]["interest_allocation"]["sha256"] == allocation_sha
    assert receipt["inputs"]["inputs_manifest"]["sha256"] == manifest_sha
    assert receipt["counterfactual"]["base_quarter"] == catalog.INTEREST_RATE_DEBT_BASE_QUARTER
    assert set(receipt["counterfactual"]["base_shares"]) == set(catalog.INTEREST_HOLDERS)
    by_quarter = receipt["reconciliation"]["pool_minus_fiscaldata_ex_tips_ic_usd_billion"]["by_quarter"]
    assert len(by_quarter) == len(QUARTERS)
    boundaries = " ".join(receipt["boundaries"])
    for phrase in ["no causal claim", "Federal Reserve", "not a market yield", "shift-share", "residual",
                   "credited to covered deposits", "modeled; the Fed's is exact"]:
        assert phrase in boundaries, phrase
    with pytest.raises(ValueError, match="interest_allocation: source hash mismatch"):
        export(tmp_path, manifest_sha, "0" * 64)
    with pytest.raises(ValueError, match="inputs_manifest: source hash mismatch"):
        export(tmp_path, "0" * 64, allocation_sha)
    (tmp_path / "README.md").write_text("changed\n")
    with pytest.raises(ValueError, match="clean committed"):
        export(tmp_path, manifest_sha, allocation_sha)


# The 2026q2 interest allocation with FiscalData and MSPD Table 3 read 2026-11-16, USD billion.
RETAINED_ALLOCATION_SHA256 = "08d81c943fd7f9410dca9aa8675efd8e47dc7d8dbecb737e7ce756e8c54379dd"
RETAINED_BASE_SHARES = {"deposit_users": 0.3867, "fed": 0.1624, "foreign": 0.4033, "banks_credit_unions": 0.0476}


@pytest.mark.integration
def test_retained_inputs_reproduce_the_export():
    root = Path(os.environ.get("TDCEST_INTEREST_ROOT", ROOT / "data" / "refresh_2026q2"))
    allocation_path = root / "data" / "processed" / ALLOCATION_FILE
    receipt_path = root / "data" / "processed" / OUTPUT_FILES["receipt"]
    missing = [str(path) for path in [root / REGISTRY.manifest, allocation_path, receipt_path] if not path.exists()]
    if missing:
        pytest.fail(f"integration inputs absent: {missing}")
    assert sha(allocation_path) == RETAINED_ALLOCATION_SHA256
    frames, _ = load_fiscus_inputs(root, json.loads((root / REGISTRY.manifest).read_text()), REGISTRY)
    aggregate, holders, record = build_interest_rate_debt(frames[INTEREST_KEY], frames[DEBT_KEY],
                                                          pd.read_csv(allocation_path))
    assert round(aggregate.set_index("quarter").loc[str(BASE), "interest"], 3) == 91.003
    assert {k: round(v, 4) for k, v in record["counterfactual"]["base_shares"].items()} == RETAINED_BASE_SHARES
    receipt = json.loads(receipt_path.read_text())
    for role, frame in [("aggregate", aggregate), ("holders", holders)]:
        payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        assert hashlib.sha256(payload).hexdigest() == receipt["outputs"][role]["sha256"], role
