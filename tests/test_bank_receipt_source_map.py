from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bank_receipt_source_map import (
    build_bank_receipt_source_map,
    render_bank_receipt_source_map_markdown,
    write_bank_receipt_source_map,
)


def _sample_readiness() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "perimeter_contamination",
                "status": "pass",
                "metric_value": "table51_bank_minor_industry_bridge",
                "details": "Table 5.1 bank-minor bridge loaded.",
            },
            {
                "check_name": "stale_share_rule",
                "status": "fail",
                "metric_value": "4",
                "details": "Latest bridge quarter is 2026-03-31 using tax-year 2022 with share status `carry_forward_latest`.",
            },
            {
                "check_name": "share_stability",
                "status": "warn",
                "details": "Public share history exists through 2022.",
            },
        ]
    )


def _sample_historical() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quarter_end": "2024-12-31",
                "share_age_eligible_for_default": True,
            },
            {
                "quarter_end": "2026-03-31",
                "share_age_eligible_for_default": False,
            },
        ]
    )


def test_build_bank_receipt_source_map_marks_fresher_share_as_missing() -> None:
    source_map = build_bank_receipt_source_map(
        bank_receipt_default_readiness=_sample_readiness(),
        bank_receipt_historical_promotion=_sample_historical(),
    )

    fresher = source_map.loc[source_map["source_family_key"].eq("fresher_public_irs_bank_minor_shares")].iloc[0]
    loaded = source_map.loc[source_map["source_family_key"].eq("publication16_table51_bank_minor_history")].iloc[0]

    assert bool(loaded["currently_loaded"]) is True
    assert bool(fresher["still_missing_for_current_default"]) is True


def test_write_bank_receipt_source_map_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "bank_receipt_source_map.csv"
    markdown_path = tmp_path / "bank_receipt_source_map.md"

    _, _, source_map = write_bank_receipt_source_map(
        csv_path=csv_path,
        markdown_path=markdown_path,
        bank_receipt_default_readiness=_sample_readiness(),
        bank_receipt_historical_promotion=_sample_historical(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(source_map)
    markdown = render_bank_receipt_source_map_markdown(source_map)
    assert "Bank Receipt Source Map" in markdown
    assert "fresher_public_irs_bank_minor_shares" in markdown
