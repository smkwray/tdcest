from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.ffiec_interest_constraints import normalize_ffiec_interest_constraints_from_extracted_root


def test_normalize_ffiec_interest_constraints_from_extracted_root(tmp_path: Path):
    extracted = tmp_path / "2025Q4" / "extracted"
    extracted.mkdir(parents=True)
    rcb = extracted / "FFIEC CDR Call Schedule RCB 12312025(1 of 2).txt"
    pd.DataFrame(
        {
            "IDRSSD": ["", "1", "2"],
            "RCFD0211": ["label", "100", "200"],
            "RCFD0213": ["label", "90", "180"],
            "RCFD1286": ["label", "300", "400"],
            "RCFD1287": ["label", "310", "410"],
            "RCFDA549": ["label", "10", "20"],
            "RCFDA550": ["label", "5", "10"],
            "RCFDA551": ["label", "1", "2"],
            "RCFDA552": ["label", "1", "2"],
            "RCFDA553": ["label", "1", "2"],
            "RCFDA554": ["label", "1", "2"],
        }
    ).to_csv(rcb, sep="\t", index=False)

    out = normalize_ffiec_interest_constraints_from_extracted_root(tmp_path)

    assert len(out) == 2
    assert out["date"].iloc[0] == pd.Timestamp("2025-12-31")
    assert out["total_treasuries_amortized_cost"].sum() == 1000
    assert out["treasury_bucket_3m_or_less"].sum() == 30
