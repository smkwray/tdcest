from __future__ import annotations

from tdc_estimator.theory_measurement_map import build_theory_measurement_map


def test_theory_measurement_map_contains_theoretical_and_implemented_rows() -> None:
    frame = build_theory_measurement_map()

    assert not frame.empty
    assert "theory_du_facing_identity" in frame["equation_key"].values
    assert "implemented_tier3_fiscal_correction" in frame["equation_key"].values

    treasury_cash = frame.loc[frame["equation_key"].eq("theory_treasury_cash_constraint")].iloc[0]
    assert treasury_cash["equation_family"] == "theoretical_identity"
    assert "TOC" in treasury_cash["latex"]

    tier3 = frame.loc[frame["equation_key"].eq("implemented_tier3_fiscal_correction")].iloc[0]
    assert tier3["implementation_status"] == "implemented_live_bounded"
