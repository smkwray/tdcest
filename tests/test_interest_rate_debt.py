"""Interest on marketable debt split into debt and rate effects: fixture economics through the production builders.

The fixture interest lines vary by month so that a calendar-year or wrong-line sum gives a
different total, and the excluded lines and the Federal Financing Bank are large enough to
dominate the result if they leaked in. Expected values are computed here from the stated
method, independently of the module.
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
    DEBT_KEY,
    INTEREST_KEY,
    OUTPUT_FILES,
    build_interest_rate_debt,
)
from tdc_estimator.trc_export import load_fiscus_inputs

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = catalog.FISCUS_REGISTRIES["interest-rate-debt"]
FIRST, LAST = catalog.INTEREST_RATE_DEBT_SAMPLE
BASE = catalog.INTEREST_RATE_DEBT_BASE_YEAR
FLOW_MONTHS = pd.period_range(f"{FIRST - 1}-10", f"{LAST}-09", freq="M")
DEBT_MONTHS = pd.period_range(f"{FIRST - 1}-09", f"{LAST}-09", freq="M")
PUBLIC, GAS = "INTEREST EXPENSE ON PUBLIC ISSUES", "INTEREST EXPENSE ON GOVT ACCOUNT SERIES"
ACCRUED, DISCOUNT, PREMIUM = "ACCRUED INTEREST EXPENSE", "AMORTIZED DISCOUNT", "AMORTIZED PREMIUM"
MARKETABLE = [  # (group, type, USD per month at month index t)
    (ACCRUED, "Treasury Notes", lambda t: 20e9 + 0.1e9 * t),
    (ACCRUED, "Inflation Protected Securities (TIPS)", lambda t: 1e9 + 0.01e9 * t),
    (ACCRUED, "Int. Expense Inflation Compensation (TIPS)", lambda t: 2e9 + 1e9 * np.sin(t)),
    (DISCOUNT, "Treasury Bills", lambda t: 5e9 + 0.05e9 * t),
    (PREMIUM, "Treasury Notes", lambda t: -1e9 - 0.01e9 * t),
]
EXCLUDED = [  # (category, group, type): nonmarketable or off-perimeter lines
    (PUBLIC, "SAVINGS BONDS", "Series I"),
    (PUBLIC, ACCRUED, "State & Local Government-C/I's, Notes & Bonds"),
    (PUBLIC, ACCRUED, "Foreign Series - C/I, Notes & Bonds"),
    (PUBLIC, DISCOUNT, "Domestic Series Bonds"),
    (PUBLIC, ACCRUED, "Matured Debt"),
    (PUBLIC, "MISCELLANEOUS INTEREST EXPENSE", "Limited Payability"),
    (GAS, "CASH BASIS GAS PAYMENTS", "Interest Payments"),
]


def make_interest(excluded_usd: float = 50e9, premium_scale: float = 1.0) -> pd.DataFrame:
    rows = []
    for t, month in enumerate(FLOW_MONTHS):
        date = month.end_time.strftime("%Y-%m-%d")
        for group, typ, value in MARKETABLE:
            amount = value(t) * (premium_scale if group == PREMIUM else 1.0)
            rows.append((date, PUBLIC, group, typ, f"{amount:.2f}"))
        rows += [(date, category, group, typ, f"{excluded_usd:.2f}") for category, group, typ in EXCLUDED]
    return pd.DataFrame(rows, columns=["record_date", "expense_catg_desc", "expense_group_desc",
                                       "expense_type_desc", "month_expense_amt"])


def month_end_debt() -> np.ndarray:
    """Marketable debt less FFB, USD million: 4.5% growth to 2019, then faster and bumpy."""
    t = np.arange(len(DEBT_MONTHS)) / 12
    return np.round(12_000_000 * np.exp(0.045 * t + 0.04 * np.clip(t - 5.5, 0, None)) + 50_000 * np.sin(3 * t), 4)


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
            (date, "Bills Maturity Value", "Total Unmatured Treasury Bills", f"{bills:.4f}"),
            (date, "Bills Maturity Value", "Total Treasury Bills", f"{bills:.4f}"),
            (date, "Bills Maturity Value", "912796AA1", f"{bills:.4f}"),
            (date, "Notes", "912828AA1", f"{(notes - 30) / 2:.4f}"),
            (date, "Notes", "912828AA1", ""),  # a reopening row carries no amount
            (date, "Notes", "912828BB2", f"{(notes - 30) / 2:.4f}"),
            (date, "Notes", "Total Matured Treasury Notes", "30.0000"),
            (date, "Notes", "Total Unmatured Treasury Notes", f"{notes - 30:.4f}"),
            (date, "Notes", "Total Treasury Notes", f"{notes:.4f}"),
            (date, "Floating Rate Notes", "Matured Treasury Floating Rate Notes", "40.0000"),
            (date, "Floating Rate Notes", "Treasury Floating Rate Notes", f"{frn - 40:.4f}"),
            (date, "Floating Rate Notes", "Total Tresasury Floating Rate Notes", f"{frn:.4f}"),
            (date, "Federal Financing Bank", "", f"{ffb:.4f}"),
            (date, "Total Marketable", "", f"{total + ffb:.4f}"),
        ]
    return pd.DataFrame(rows, columns=["record_date", "security_class1_desc", "security_class2_desc",
                                       "outstanding_amt"])


def expected_flows() -> pd.DataFrame:
    """Fiscal-year I, IC and D written out from the method."""
    t = np.arange(len(FLOW_MONTHS))
    fy = FLOW_MONTHS.year + (FLOW_MONTHS.month >= 10)
    interest = sum(value(t) for _, _, value in MARKETABLE) / 1e9
    tips = MARKETABLE[2][2](t) / 1e9
    debt = pd.Series(month_end_debt(), index=DEBT_MONTHS)
    avg = {}
    for year in range(FIRST, LAST + 1):
        v = debt.loc[pd.Period(f"{year - 1}-09"):pd.Period(f"{year}-09")].to_numpy()
        assert len(v) == 13
        avg[year] = (v[0] / 2 + v[1:12].sum() + v[12] / 2) / 12 / 1000
    return pd.DataFrame({"I": pd.Series(interest).groupby(fy).sum(), "IC": pd.Series(tips).groupby(fy).sum(),
                         "D": pd.Series(avg)})


def test_columns_follow_the_stated_method_and_the_split_adds_exactly_to_the_gap():
    table, record = build_interest_rate_debt(make_interest(), make_mspd())
    flows = expected_flows()
    rows = table.set_index("fiscal_year")
    assert list(rows.index) == list(range(FIRST, LAST + 1))
    np.testing.assert_allclose(rows["interest"], flows["I"], rtol=1e-12)
    np.testing.assert_allclose(rows["tips_inflation_compensation"], flows["IC"], rtol=1e-12)
    np.testing.assert_allclose(rows["avg_marketable_debt"], flows["D"], rtol=1e-12)
    np.testing.assert_allclose(rows["effective_rate_pct"], 100 * flows["I"] / flows["D"], rtol=1e-12)

    fit = np.arange(catalog.INTEREST_RATE_DEBT_FIT_WINDOW[0], catalog.INTEREST_RATE_DEBT_FIT_WINDOW[1] + 1)
    x, y = fit - fit.mean(), np.log(flows["D"].loc[fit].to_numpy())
    g = float((x * y).sum() / (x * x).sum())  # OLS slope written out
    rc = flows["I"][BASE] / flows["D"][BASE]
    assert record["counterfactual"]["g"] == pytest.approx(g, rel=1e-10)
    assert record["counterfactual"]["rc"] == pytest.approx(rc, rel=1e-12)
    assert record["counterfactual"]["pooled_rate"] == pytest.approx(
        flows["I"].loc[fit].sum() / flows["D"].loc[fit].sum(), rel=1e-12)

    after = rows.loc[BASE:]
    years = after.index.to_numpy()
    trend = flows["D"][BASE] * np.exp(g * (years - BASE))
    np.testing.assert_allclose(after["trend_debt"], trend, rtol=1e-10)
    np.testing.assert_allclose(after["trend_interest"], trend * rc, rtol=1e-10)
    np.testing.assert_allclose(after["debt_effect"], (flows["D"].loc[BASE:] - trend) * rc, rtol=1e-9)
    gap = after["interest"] - after["trend_interest"]
    for debt, rate in [("debt_effect", "rate_effect"), ("debt_effect_even", "rate_effect_even")]:
        assert (after[debt] + after[rate] - gap).abs().max() <= 1e-9, debt
    # The fixture debt runs above trend after the base year, so both splits must give it a positive share.
    assert (after.loc[BASE + 1:, ["debt_effect", "debt_effect_even"]] > 0).all().all()
    for check in record["checks"]["identities"].values():
        assert check["max_abs_gap_usd_billion"] <= check["tolerance"] == 1e-9
    # Before the base year there is no counterfactual.
    assert rows.loc[:BASE - 1, "trend_debt":].isna().all().all()
    assert rows.loc[:BASE - 1, "interest":"effective_rate_pct"].notna().all().all()


def test_trend_debt_equals_actual_in_the_base_year_so_the_base_year_has_no_effects():
    table, _ = build_interest_rate_debt(make_interest(), make_mspd())
    base = table.set_index("fiscal_year").loc[BASE]
    assert base["trend_debt"] == base["avg_marketable_debt"]
    assert base["trend_interest"] == pytest.approx(base["interest"], rel=1e-12)
    for column in ["debt_effect", "rate_effect", "debt_effect_even", "rate_effect_even", "rate_effect_tips"]:
        assert base[column] == pytest.approx(0.0, abs=1e-9), column


def test_ffb_and_nonmarketable_lines_are_excluded():
    table, _ = build_interest_rate_debt(make_interest(excluded_usd=50e9), make_mspd(ffb=900_000.0))
    other, _ = build_interest_rate_debt(make_interest(excluded_usd=-7e9), make_mspd(ffb=1.0))
    pd.testing.assert_frame_equal(table, other)
    # Debt is Total Marketable less FFB, not Total Marketable.
    np.testing.assert_allclose(table["avg_marketable_debt"], expected_flows()["D"], rtol=1e-12)


def test_premium_lines_reduce_interest():
    base, _ = build_interest_rate_debt(make_interest(premium_scale=1.0), make_mspd())
    larger, _ = build_interest_rate_debt(make_interest(premium_scale=3.0), make_mspd())
    t = np.arange(len(FLOW_MONTHS))
    premium = pd.Series(MARKETABLE[4][2](t) / 1e9).groupby(FLOW_MONTHS.year + (FLOW_MONTHS.month >= 10)).sum()
    assert (premium < 0).all()
    np.testing.assert_allclose(larger["interest"] - base["interest"], 2 * premium.to_numpy(), rtol=1e-12)
    assert (larger["interest"] < base["interest"]).all()


def test_a_missing_month_or_line_raises_instead_of_truncating():
    interest, mspd = make_interest(), make_mspd()
    dropped = interest[interest["record_date"] != "2021-03-31"]
    with pytest.raises(ValueError, match=r"months \['2021-03'\] lack marketable lines"):
        build_interest_rate_debt(dropped, mspd)
    one_line = interest.drop(interest.index[(interest["record_date"] == "2016-11-30")
                                            & (interest["expense_group_desc"] == PREMIUM)])
    with pytest.raises(ValueError, match=r"months \['2016-11'\] lack marketable lines"):
        build_interest_rate_debt(one_line, mspd)
    last = interest[interest["record_date"] != f"{LAST}-09-30"]
    with pytest.raises(ValueError, match=rf"months \['{LAST}-09'\]"):
        build_interest_rate_debt(last, mspd)
    blank = interest.copy()
    blank.loc[3, "month_expense_amt"] = ""
    with pytest.raises(ValueError, match="missing or nonnumeric"):
        build_interest_rate_debt(blank, mspd)
    no_ffb = mspd.drop(mspd.index[(mspd["record_date"] == "2018-06-30")
                                  & (mspd["security_class1_desc"] == "Federal Financing Bank")])
    with pytest.raises(ValueError, match=r"month-ends \['2018-06'\] lack"):
        build_interest_rate_debt(interest, no_ffb)
    opening = mspd[mspd["record_date"] != f"{FIRST - 1}-09-30"]
    with pytest.raises(ValueError, match=rf"month-ends \['{FIRST - 1}-09'\] lack"):
        build_interest_rate_debt(interest, opening)


def test_a_total_that_disagrees_with_its_class_subtotals_raises():
    interest, mspd = make_interest(), make_mspd()
    row = mspd.index[(mspd["record_date"] == "2022-01-31") & (mspd["security_class1_desc"] == "Total Marketable")]
    off = mspd.copy()
    off.loc[row, "outstanding_amt"] = f"{float(mspd.loc[row[0], 'outstanding_amt']) + 1.0:.4f}"
    _, record = build_interest_rate_debt(interest, off)  # a USD 1 million publication inconsistency
    assert record["checks"]["mspd_subtotals"]["month"] == "2022-01"
    assert record["checks"]["mspd_subtotals"]["max_abs_gap_usd_million"] == pytest.approx(1.0, abs=1e-3)
    off.loc[row, "outstanding_amt"] = f"{float(mspd.loc[row[0], 'outstanding_amt']) + 5_000.0:.4f}"
    with pytest.raises(ValueError, match="differs from the class subtotals by .* in 2022-01"):
        build_interest_rate_debt(interest, off)
    duplicate = pd.concat([mspd, mspd[mspd["security_class1_desc"] == "Total Marketable"].iloc[:1]])
    with pytest.raises(ValueError, match="more than one Total Marketable"):
        build_interest_rate_debt(interest, duplicate)


def git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    subprocess.run(["git", "-C", str(root), *args], check=True, env=env, capture_output=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_repo(root: Path) -> str:
    """A clean committed checkout with a fiscus-shaped manifest; returns the manifest hash."""
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
    (root / ".gitignore").write_text("data/\n")
    (root / "README.md").write_text("fixture\n")
    git(root, "init", "-q")
    git(root, "add", ".gitignore", "README.md")
    git(root, "commit", "-q", "-m", "fixture")
    return sha(manifest)


def export(root: Path, manifest_sha: str) -> int:
    return main(["interest-rate-debt-export", "--root", str(root), "--inputs-manifest-sha256", manifest_sha])


def test_cli_exports_a_hash_bound_table_and_refuses_unbound_inputs(tmp_path):
    manifest_sha = make_repo(tmp_path)
    assert export(tmp_path, manifest_sha) == 0
    processed = tmp_path / "data" / "processed"
    receipt = json.loads((processed / OUTPUT_FILES["receipt"]).read_text())
    table_path = tmp_path / receipt["outputs"]["table"]["path"]
    assert table_path == processed / OUTPUT_FILES["table"]
    assert sha(table_path) == receipt["outputs"]["table"]["sha256"]
    head = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    assert receipt["producer_commit"] == head.strip()
    assert receipt["inputs"]["inputs_manifest"]["sha256"] == manifest_sha
    assert set(receipt["inputs"]["fiscus_inputs"]) == {INTEREST_KEY, DEBT_KEY}
    assert receipt["counterfactual"]["fit_window"] == list(catalog.INTEREST_RATE_DEBT_FIT_WINDOW)
    assert receipt["sample"]["n"] == LAST - FIRST + 1
    boundaries = " ".join(receipt["boundaries"])
    for phrase in ["no causal claim", "Federal Reserve", "not a market yield"]:
        assert phrase in boundaries
    table = pd.read_csv(table_path)
    assert list(table.columns) == list(receipt["columns"])
    with pytest.raises(ValueError, match="inputs_manifest: source hash mismatch"):
        export(tmp_path, "0" * 64)
    (tmp_path / "README.md").write_text("changed\n")
    with pytest.raises(ValueError, match="clean committed"):
        export(tmp_path, manifest_sha)


# FY2019 and FY2026 from FiscalData interest expense and MSPD Table 3 read 2026-11-16, USD billion.
RETAINED = {2019: {"interest": 389.14, "avg_marketable_debt": 15785.52, "effective_rate_pct": 2.4652},
            2026: {"interest": 1060.65, "avg_marketable_debt": 30746.98, "trend_interest": 581.74,
                   "debt_effect": 176.23, "rate_effect": 302.68, "debt_effect_even": 211.41,
                   "rate_effect_even": 267.50}}


@pytest.mark.integration
def test_retained_inputs_reproduce_the_export():
    root = Path(os.environ.get("TDCEST_INTEREST_ROOT", ROOT / "data" / "refresh_2026q2"))
    receipt_path = root / "data" / "processed" / OUTPUT_FILES["receipt"]
    missing = [str(path) for path in [root / REGISTRY.manifest, receipt_path] if not path.exists()]
    if missing:
        pytest.fail(f"integration inputs absent: {missing}")
    frames, _ = load_fiscus_inputs(root, json.loads((root / REGISTRY.manifest).read_text()), REGISTRY)
    table, record = build_interest_rate_debt(frames[INTEREST_KEY], frames[DEBT_KEY])
    rows = table.set_index("fiscal_year")
    for year, values in RETAINED.items():
        for column, value in values.items():
            assert round(rows.loc[year, column], 4 if column == "effective_rate_pct" else 2) == value, (year, column)
    assert round(record["counterfactual"]["trend_growth_pct_per_year"], 2) == 5.91
    payload = table.to_csv(index=False, lineterminator="\n").encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == json.loads(receipt_path.read_text())["outputs"]["table"]["sha256"]
