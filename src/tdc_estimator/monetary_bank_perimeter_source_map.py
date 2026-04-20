from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_monetary_bank_perimeter_source_map(
    perimeter_gap_review: pd.DataFrame | None,
) -> pd.DataFrame:
    if perimeter_gap_review is None or perimeter_gap_review.empty:
        return pd.DataFrame()

    review = perimeter_gap_review.iloc[0]
    missing = set(str(review.get("missing_source_families") or "").split(";"))

    rows = [
        {
            "source_family_key": "bank_only_liquid_deposit_subcomponents",
            "currently_loaded": bool(review.get("has_bank_only_liquid_deposit_subcomponents")),
            "missing_for_next_step": "bank_only_liquid_deposit_subcomponents" in missing,
            "current_repo_stance": "loaded_broad_context_not_subcomponent",
            "provider": "Federal Reserve / FRED",
            "candidate_series_or_product": "ODSACBM027SBOG; fallback ODSACBM027NBOG or ODSACBW027SBOG; rejected ODSACBM027NBOG plus WDDNS pair",
            "official_source_family": "H.8 other deposits broad context versus rejected H.8 plus H.6 demand-deposit mix",
            "frequency": "monthly plus weekly/monthly",
            "intended_use": "Approximate bank-only liquid deposit subcomponents inside the commercial-bank target.",
            "notes": "Keep the ODS plus WDDNS pair rejected for now. Current methods review says it likely double counts demand deposits. Seasonally adjusted H.8 Other Deposits, All Commercial Banks is now the best loaded broad bank-deposit context candidate, but it remains too broad to treat as a true bank-only liquid-deposit subcomponent.",
        },
        {
            "source_family_key": "large_time_or_wholesale_deposit_components",
            "currently_loaded": bool(review.get("has_large_time_or_wholesale_deposit_components")),
            "missing_for_next_step": "large_time_or_wholesale_deposit_components" in missing,
            "current_repo_stance": (
                "loaded_context_series"
                if bool(review.get("has_large_time_or_wholesale_deposit_components"))
                else "best_next_load"
            ),
            "provider": "Federal Reserve / FRED",
            "candidate_series_or_product": "LTDACBM027SBOG",
            "official_source_family": "H.8 large time deposits, all commercial banks",
            "frequency": "monthly",
            "intended_use": "Split the bank-minus-liquid wedge into a large-time/wholesale bank-deposit component.",
            "notes": "This is the cleanest currently identified public official candidate for the large-time or wholesale bank-deposit bucket.",
        },
        {
            "source_family_key": "bank_vs_broad_depository_bridge",
            "currently_loaded": bool(review.get("has_bank_vs_broad_depository_bridge")),
            "missing_for_next_step": "bank_vs_broad_depository_bridge" in missing,
            "current_repo_stance": (
                "bridge_sides_loaded"
                if bool(review.get("has_bank_vs_broad_depository_bridge"))
                else (
                "credit_union_side_loaded_fdic_thrift_missing"
                if bool(review.get("has_credit_union_bridge_side")) and not bool(review.get("has_thrift_savings_bridge_side"))
                else "best_next_bridge_intake"
                )
            ),
            "provider": "NCUA plus FDIC",
            "candidate_series_or_product": "NCUA final quarterly Call Report ZIPs plus AcctDesc.txt and Call Report instructions; FDIC BankFind Suite quarterly financial data for savings institutions",
            "official_source_family": "Credit-union shares and deposits plus FDIC-insured savings-institution deposits",
            "frequency": "quarterly",
            "intended_use": "Bridge commercial-bank deposits back to a broader depository concept by making the nonbank depository side explicit.",
            "notes": "NCUA ZIPs are the credit-union side and the FDIC financial API is the thrift side. Once both are loaded, the repo can make the nonbank depository side explicit, even though bank-only liquid subcomponents remain unresolved.",
        },
    ]
    return pd.DataFrame(rows)


def render_monetary_bank_perimeter_source_map_markdown(source_map: pd.DataFrame) -> str:
    title = "# Monetary Bank Perimeter Source Map"
    intro = (
        "Candidate official source families for decomposing the remaining bank-minus-liquid or perimeter wedge. "
        "This artifact translates the perimeter-gap review into a concrete source roadmap."
    )
    if source_map.empty:
        return "\n".join([title, "", intro, "", "No monetary bank perimeter source map is available."])

    header = [
        "| Missing family | Currently loaded? | Missing for next step? | Current repo stance | Provider | Candidate series/product | Official source family | Frequency | Intended use | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows = []
    for _, row in source_map.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["source_family_key"]),
                    str(bool(row["currently_loaded"])),
                    str(bool(row["missing_for_next_step"])),
                    str(row["current_repo_stance"]),
                    str(row["provider"]),
                    str(row["candidate_series_or_product"]),
                    str(row["official_source_family"]),
                    str(row["frequency"]),
                    str(row["intended_use"]),
                    str(row["notes"]),
                ]
            )
            + " |"
        )
    return "\n".join([title, "", intro, "", *header, *rows, ""])


def write_monetary_bank_perimeter_source_map(
    *,
    monetary_bank_perimeter_gap_review: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    source_map = build_monetary_bank_perimeter_source_map(monetary_bank_perimeter_gap_review)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    source_map.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_bank_perimeter_source_map_markdown(source_map), encoding="utf-8")

    return csv_path, markdown_path, source_map
