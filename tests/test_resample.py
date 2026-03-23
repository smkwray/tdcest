from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.io import load_quarterly_fred_series


def test_clip_positive_before_quarter_sum(tmp_path: Path):
    df = pd.DataFrame(
        {
            "date": ["2024-01-03", "2024-02-07", "2024-03-06", "2024-04-03"],
            "value": [10, -5, 4, -1],
        }
    )
    path = tmp_path / "fred__fed_remit_or_deferred.csv"
    df.to_csv(path, index=False)
    series = load_quarterly_fred_series(path, agg="sum", transform="clip_positive")
    assert float(series.iloc[0]) == 14.0
    assert float(series.iloc[1]) == 0.0
