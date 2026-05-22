from __future__ import annotations

import pandas as pd

from tdc_estimator.tier3_component_crosswalk import (
    build_tier3_component_crosswalk,
    render_tier3_component_crosswalk_markdown,
    validate_tier3_component_crosswalk,
    write_tier3_component_crosswalk,
)


def test_build_tier3_component_crosswalk_covers_core_components() -> None:
    crosswalk = build_tier3_component_crosswalk()

    assert {
        "outlay_banks",
        "outlay_row_core_institutional",
        "outlay_row_narrow",
        "outlay_row_humanitarian_addon",
        "outlay_row_agency_addon",
        "outlay_row_broad_sensitivity",
        "receipt_banks_strict_depository",
        "receipt_banks_depository_bhc_central",
        "receipt_banks_finance_upper",
        "receipt_row_bea_anchor",
        "receipt_row_mrv_overlay",
        "cashfactor_mint",
    }.issubset(set(crosswalk["component_key"]))

    row_broad = crosswalk.loc[crosswalk["component_key"].eq("outlay_row_broad_sensitivity")].iloc[0]
    assert row_broad["quality_code"] == "sensitivity_only"
    assert "Foreign Military Financing Program" in row_broad["label_paths"]

    cashfactor = crosswalk.loc[crosswalk["component_key"].eq("cashfactor_mint")].iloc[0]
    assert cashfactor["payer_identity_grade"] == "A_direct_cash_payer"
    assert cashfactor["cash_basis_grade"] == "A_mts_modified_cash"


def test_validate_tier3_component_crosswalk_passes_generated_rows() -> None:
    crosswalk = build_tier3_component_crosswalk()
    validation = validate_tier3_component_crosswalk(crosswalk)

    assert not validation.empty
    assert set(validation["status"]) == {"pass"}


def test_validate_tier3_component_crosswalk_flags_bad_method() -> None:
    crosswalk = build_tier3_component_crosswalk()
    crosswalk.loc[crosswalk.index[0], "method"] = "not_a_method"

    validation = validate_tier3_component_crosswalk(crosswalk)

    method_row = validation.loc[validation["check_name"].eq("method_enums")].iloc[0]
    assert method_row["status"] == "fail"
    assert "not_a_method" in method_row["details"]


def test_render_tier3_component_crosswalk_markdown_mentions_live_default_guardrail() -> None:
    crosswalk = build_tier3_component_crosswalk()

    markdown = render_tier3_component_crosswalk_markdown(crosswalk)

    assert "Tier 3 Component Crosswalk" in markdown
    assert "Tier 2 as the headline" in markdown
    assert "Broad ROW outlays" in markdown


def test_write_tier3_component_crosswalk_outputs_files(tmp_path) -> None:
    csv_path = tmp_path / "crosswalk.csv"
    markdown_path = tmp_path / "crosswalk.md"
    validation_path = tmp_path / "validation.csv"

    _, _, crosswalk = write_tier3_component_crosswalk(
        csv_path=csv_path,
        markdown_path=markdown_path,
        validation_path=validation_path,
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert validation_path.exists()
    assert len(pd.read_csv(csv_path)) == len(crosswalk)
