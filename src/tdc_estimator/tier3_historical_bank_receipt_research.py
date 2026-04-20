from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_START = "2022-09-30"


def _series(df: pd.DataFrame | None, column: str, index: pd.DatetimeIndex) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(0.0, index=index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").reindex(index).fillna(0.0)


def _meta(df: pd.DataFrame | None, column: str, index: pd.DatetimeIndex) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(index=index, dtype="object")
    return df[column].reindex(index)


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_tier3_historical_bank_receipt_research(
    estimates: pd.DataFrame,
    *,
    bank_receipt_historical_promotion: pd.DataFrame | None = None,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    if estimates is None or estimates.empty or "tdc_tier3_fiscal_corrected_bank_only_ru_flow" not in estimates.columns:
        return pd.DataFrame()
    if bank_receipt_historical_promotion is None or bank_receipt_historical_promotion.empty:
        return pd.DataFrame()

    index = pd.DatetimeIndex(estimates.index).sort_values().unique()
    frame = pd.DataFrame(index=index)
    frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] = pd.to_numeric(
        estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"], errors="coerce"
    ).reindex(index)

    historical = bank_receipt_historical_promotion.copy()
    if "quarter_end" in historical.columns:
        historical["quarter_end"] = pd.to_datetime(historical["quarter_end"])
        historical = historical.set_index("quarter_end")
    else:
        historical.index = pd.to_datetime(historical.index)

    frame["bank_receipt_historical_default_candidate_delta_mil"] = _series(
        historical, "age_eligible_default_candidate_mil", index
    )
    frame["bank_receipt_historical_lower_bound_delta_mil"] = _series(
        historical, "age_eligible_lower_bound_candidate_mil", index
    )
    frame["historical_window_status"] = _meta(historical, "historical_window_status", index)
    frame["promotion_readiness_label"] = _meta(historical, "promotion_readiness_label", index)
    frame["recommended_historical_variant"] = _meta(historical, "recommended_historical_variant", index)
    frame["share_age_eligible_for_default"] = (
        _meta(historical, "share_age_eligible_for_default", index).fillna(False).astype(bool)
    )

    frame["tdc_tier3_bank_only_plus_historical_bank_receipt_candidate"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] + frame["bank_receipt_historical_default_candidate_delta_mil"]
    )
    frame["tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] + frame["bank_receipt_historical_lower_bound_delta_mil"]
    )

    nonzero_mask = (
        frame["bank_receipt_historical_default_candidate_delta_mil"].ne(0.0)
        | frame["bank_receipt_historical_lower_bound_delta_mil"].ne(0.0)
    )
    frame = frame.loc[frame.index >= pd.Timestamp(start)].copy()
    frame = frame.dropna(subset=["tdc_tier3_fiscal_corrected_bank_only_ru_flow"], how="any")
    return frame.loc[nonzero_mask].copy()


def render_tier3_historical_bank_receipt_research_markdown(research: pd.DataFrame) -> str:
    title = "# Tier 3 Historical Bank Receipt Research Surface"
    intro = (
        "Research-only historical Tier 3 surface that applies the age-eligible Table 5.1 bank receipt window to the "
        "default Tier 3 bank-only series. This artifact leaves the live estimator unchanged and excludes stale-share "
        "current quarters by construction."
    )
    if research.empty:
        return "\n".join([title, "", intro, "", "No historical age-eligible bank receipt quarters are available."])

    latest = research.sort_index().iloc[-1]
    latest_date = research.index.max()
    summary = (
        f"Latest historical age-eligible quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Default Tier 3 {_format_millions(latest['tdc_tier3_fiscal_corrected_bank_only_ru_flow'])}; "
        f"historical dep+BHC bank-receipt candidate {_format_millions(latest['bank_receipt_historical_default_candidate_delta_mil'])}; "
        f"historical strict-depository lower bound {_format_millions(latest['bank_receipt_historical_lower_bound_delta_mil'])}; "
        f"research series with historical dep+BHC candidate {_format_millions(latest['tdc_tier3_bank_only_plus_historical_bank_receipt_candidate'])}."
    )

    header = [
        "| Quarter | Default Tier 3 | Historical dep+BHC delta | Historical strict lower bound | Research dep+BHC series | Window status |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    rows: list[str] = []
    for date, row in research.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    _format_millions(row.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow")),
                    _format_millions(row.get("bank_receipt_historical_default_candidate_delta_mil")),
                    _format_millions(row.get("bank_receipt_historical_lower_bound_delta_mil")),
                    _format_millions(row.get("tdc_tier3_bank_only_plus_historical_bank_receipt_candidate")),
                    str(row.get("historical_window_status", "n/a")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- This surface uses only quarters that still satisfy the bridge's current stale-share policy.",
        "- `Research dep+BHC series` is not a live default estimator; it is a historical research variant only.",
        "- Current stale-share quarters are excluded here on purpose and remain visible in the separate bank historical-promotion review.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_tier3_historical_bank_receipt_research(
    estimates: pd.DataFrame,
    *,
    bank_receipt_historical_promotion: pd.DataFrame | None,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = DEFAULT_START,
) -> tuple[Path, Path, pd.DataFrame]:
    research = build_tier3_historical_bank_receipt_research(
        estimates,
        bank_receipt_historical_promotion=bank_receipt_historical_promotion,
        start=start,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    research.to_csv(csv_path, index=True, index_label="date")

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_tier3_historical_bank_receipt_research_markdown(research), encoding="utf-8")

    return csv_path, markdown_path, research
