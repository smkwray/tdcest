import numpy as np
import pandas as pd
import pytest

from tdc_estimator.fed_coupon import (
    estimate_quarterly_fed_coupon_interest_from_soma_snapshots,
)
from tdc_estimator.interest_allocation_comparison import (
    COMPONENTS,
    DATES,
    PARITY_COLUMNS,
    allocate_corrected,
    assert_baseline_parity,
    corrected_exposures,
    partition_fed_schedule,
    residual_only_contracts,
    run,
)
from tdc_estimator.tier2_interest_component_candidate import SECTOR_GROUPS


def expected_grid():
    sectors = [s for group in SECTOR_GROUPS.values() for s in group] + ["fed", "money_market_funds", "households_nonprofits"]
    return pd.DataFrame([{"date": d, "sector_key": s} for d in DATES for s in sectors])


@pytest.fixture
def exposure_inputs():
    sectors = [s for group in SECTOR_GROUPS.values() for s in group] + ["fed", "money_market_funds", "households_nonprofits"]
    canonical, weights = [], []
    shares = dict(zip([v[0] for v in COMPONENTS.values()], [.4, .2, .2, .1]))
    for date in DATES:
        for sector in sectors:
            eligible = sector != "households_nonprofits"
            canonical.append(dict(date=date, sector_key=sector, level=100 if eligible else -10,
                                  other_residual_share=.1, **shares))
            for component, (share, _, _) in COMPONENTS.items():
                weights.append({"date": date, "sector_key": sector, "component_key": component,
                    "gross_interest_weight": 100*shares[share] if eligible else np.nan,
                    "eligible_for_gross_interest": eligible,
                    "weight_class": "gross_long_holder_amount" if eligible else "statistical_residual"})
    return pd.DataFrame(canonical), pd.DataFrame(weights)


def test_constraints_preserve_residual_and_exclude_signed_ineligible(exposure_inputs):
    canonical, weights = exposure_inputs
    constraints = pd.DataFrame([
        {"date": DATES[0], "sector_key": "bank_broad_private_depositories_marketable_proxy", "level_mil": 150,
             "constraint_status": "usable_level_constraint_wamest_split_fallback", "fallback_split_accepted": True},
        {"date": DATES[0], "sector_key": "money_market_funds", "level_mil": 200, "bill_weight_proxy": .5,
             "constraint_status": "usable_denominator_constraint"},
    ])
    out = corrected_exposures(canonical, weights, constraints, expected_holders=expected_grid())
    assert "households_nonprofits" not in set(out.sector_key)
    bank = out[out.date.eq(DATES[0]) & out.sector_key.isin(SECTOR_GROUPS["bank"])]
    assert bank.unassigned_residual.sum() == pytest.approx(15)
    assert bank[list(COMPONENTS)].to_numpy().sum() == pytest.approx(135)
    mmf = out[out.date.eq(DATES[0]) & out.sector_key.eq("money_market_funds")].iloc[0]
    assert mmf.bill_amortized_discount == 100
    assert mmf.unassigned_residual == pytest.approx(12.5)
    assert mmf[list(COMPONENTS)].sum() + mmf.unassigned_residual == pytest.approx(200)
    with pytest.raises(ValueError, match="Overlapping"):
        corrected_exposures(canonical, weights, pd.concat([constraints, constraints.iloc[[0]]]), expected_holders=expected_grid())


@pytest.mark.parametrize("fault", ["flag", "canonical", "component", "date", "whole_holder"])
def test_corrected_grid_fails_closed(exposure_inputs, fault):
    canonical, weights = exposure_inputs
    if fault == "flag":
        weights.eligible_for_gross_interest = weights.eligible_for_gross_interest.astype(object)
        weights.loc[0, "eligible_for_gross_interest"] = "maybe"
    elif fault == "canonical":
        canonical = canonical.iloc[1:]
    elif fault == "component":
        weights = weights.iloc[1:]
    elif fault == "whole_holder":
        canonical = canonical[canonical.sector_key.ne("fed")]
        weights = weights[weights.sector_key.ne("fed")]
    else:
        remove = canonical.date.eq(DATES[0]) & canonical.sector_key.eq("fed")
        canonical = canonical[~remove]
        weights = weights[~(weights.date.eq(DATES[0]) & weights.sector_key.eq("fed"))]
    with pytest.raises(ValueError):
        corrected_exposures(canonical, weights, pd.DataFrame(), expected_holders=expected_grid())


def test_scalar_bucket_mapping_and_multibucket_rejection():
    old = pd.DataFrame([{"date": DATES[0], "sector_key": "a", "component_key": "coupon_accrual",
                            "bucket_key": "coupon_accrual_pool_share_excluding_frn", "bucket_weight": .8}])
    new = pd.DataFrame([
        {"date": DATES[0], "sector_key": "a", "component_key": k, "bucket_key": s, "bucket_weight": v}
        for k, s, v in [("coupon_accrual", "fixed_coupon_share", .4), ("tips_accrued_interest", "tips_share", .2)]
    ])
    def amounts(frame):
        return frame.assign(central_weight=frame.bucket_weight*100, gross_interest_weight=frame.bucket_weight*100,
                            gross_interest_low_weight=frame.bucket_weight*100,
                            gross_interest_high_weight=frame.bucket_weight*100)
    canonical = pd.DataFrame([{"date": DATES[0], "sector_key": "a", "level": 100, "other_residual_share": .2}])
    a, b = residual_only_contracts(amounts(old), old, amounts(new), new, canonical)
    assert len(b) == 1 and b.bucket_weight.iloc[0] == pytest.approx(.6)
    assert a.gross_interest_weight.iloc[0] == pytest.approx(60)
    with pytest.raises(ValueError, match="not exactly canonical residual"):
        residual_only_contracts(amounts(old), old, amounts(new), new, canonical.assign(other_residual_share=.1))
    bad = pd.concat([new, new.iloc[[0]].assign(bucket_key="extra")])
    with pytest.raises(ValueError, match="one scalar bucket"):
        residual_only_contracts(amounts(old), old, amounts(new), bad, canonical)


def test_historical_parity_rejects_denominator_change():
    frame = pd.DataFrame([dict(date=d, sector_group=s, component_key=c, **{k: 1.0 for k in PARITY_COLUMNS})
        for d in DATES for s in SECTOR_GROUPS for c in ["coupon_accrual", "bill_amortized_discount", "frn_accrued_interest"]])
    assert assert_baseline_parity(frame, frame)["rows"] == 144
    changed = frame.copy(); changed.loc[0, "denominator_raw_weight_mil"] = 2
    with pytest.raises(ValueError, match="denominator_raw_weight"):
        assert_baseline_parity(frame, changed)
    missing = frame.copy(); missing.loc[0, "fed_exact_component_mil"] = np.nan
    assert assert_baseline_parity(missing, missing)["matched_missing_cells"]["fed_exact_component_mil"] == 1
    with pytest.raises(ValueError, match="missingness differs"):
        assert_baseline_parity(frame, missing)


def test_each_fixed_coupon_pool_required(exposure_inputs):
    canonical, weights = exposure_inputs
    exposure = corrected_exposures(canonical, weights, pd.DataFrame(), expected_holders=expected_grid())
    pools = pd.DataFrame([{"date": d, "component_key": "notes_accrued_interest",
                              "included_in_marketable_public_issue_pool": True, "quarter_expense_mil": 100} for d in DATES])
    fed = pd.DataFrame({"date": DATES})
    partition = pd.DataFrame({"date": DATES, "coupon": 1.0})
    with pytest.raises(ValueError, match="Missing component payment pool"):
        allocate_corrected(pools, exposure, fed, partition)


def test_missing_fed_component_remains_unavailable(exposure_inputs):
    canonical, weights = exposure_inputs
    exposure = corrected_exposures(canonical, weights, pd.DataFrame(), expected_holders=expected_grid())
    pools = pd.DataFrame([{"date": d, "component_key": k,
        "included_in_marketable_public_issue_pool": True, "quarter_expense_mil": 100}
        for d in DATES for _, keys, _ in COMPONENTS.values() for k in keys])
    fed = pd.DataFrame({"date": DATES, **{v[2]: 1.0 for k, v in COMPONENTS.items() if k != "coupon_accrual"}})
    fed.loc[0, "fed_tsy_frn_interest_proxy"] = np.nan
    partition = pd.DataFrame({"date": DATES, "coupon": 1.0})
    out = allocate_corrected(pools, exposure, fed, partition)
    missing = out[out.date.eq(DATES[0]) & out.component_key.eq("frn_accrued_interest")]
    assert len(missing) == len(SECTOR_GROUPS)
    assert missing.component_anchored_interest_mil.isna().all()
    assert missing.allocation_status.eq("unavailable_fed_component").all()
    totals = out.groupby(["date", "sector_group"]).component_anchored_interest_mil.sum(min_count=4)
    assert totals.loc[DATES[0]].isna().all()
    assert totals.loc[DATES[1]].notna().all()


def test_fed_partition_preserves_snapshot_grid_and_original_aggregate():
    raw = pd.DataFrame([{"as_of_date": date, "maturity_date": maturity, "par_value": 1e8,
                            "coupon": rate, "security_type": kind}
        for date in pd.date_range("2021-12-31", "2025-12-31", freq="QE")
        for kind, maturity, rate in [("Treasury Note", "2050-03-31", 3), ("Treasury Note", "2050-06-30", 3),
                                     ("TIPS", "2050-03-31", 1), ("TIPS", "2050-06-30", 1), ("FRN", "2050-03-31", 0)]])
    original = raw.copy(deep=True)
    total = estimate_quarterly_fed_coupon_interest_from_soma_snapshots(raw)
    fed = pd.DataFrame({"date": DATES, "fed_tsy_coupon_interest_proxy": total.reindex(DATES).to_numpy()})
    out, gaps = partition_fed_schedule(raw, fed)
    pd.testing.assert_frame_equal(raw, original)
    assert max(gaps.values()) < 1e-6
    assert out.frn.eq(0).all()
    assert out.coupon.sum() > out.tips.sum() > 0
    with pytest.raises(ValueError, match="does not reproduce"):
        partition_fed_schedule(raw, fed.assign(fed_tsy_coupon_interest_proxy=0))


def test_uncommitted_producer_rejected_before_read_or_destination(tmp_path):
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="committed producer"):
        run(tmp_path / "missing-plan.json", output, "invalid")
    assert not output.exists()
