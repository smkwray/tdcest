from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import load_treasury_table
from .tier3_support import TIER3_SUPPORT_KEYS, load_tier3_quarterly_input_table

BANK_OUTLAY_LABELS = ["Financial Agent Services"]
ROW_OUTLAY_COMPONENT_LABELS = {
    "row_outlay_ida_contribution": "Contribution to the International Development Association",
    "row_outlay_foreign_ag_service": "Foreign Agricultural Service",
    "row_outlay_foreign_military_financing": "Foreign Military Financing Program",
    "row_outlay_international_disaster": "International Disaster Assistance",
    "row_outlay_international_monetary": "International Monetary Programs",
    "row_outlay_international_narcotics": "International Narcotics Control and Law Enforcement",
    "row_outlay_international_orgs": "International Organizations and Conferences",
}
MINT_LABELS = ["United States Mint"]
DEFAULT_ROW_OUTLAY_COMPONENT_KEYS = [
    "row_outlay_ida_contribution",
    "row_outlay_foreign_ag_service",
    "row_outlay_international_disaster",
    "row_outlay_international_monetary",
    "row_outlay_international_orgs",
]
CORE_INSTITUTIONAL_ROW_OUTLAY_COMPONENT_KEYS = [
    "row_outlay_ida_contribution",
    "row_outlay_international_monetary",
    "row_outlay_international_orgs",
]
HUMANITARIAN_ROW_OUTLAY_COMPONENT_KEYS = [
    "row_outlay_international_disaster",
]
AGENCY_ROW_OUTLAY_COMPONENT_KEYS = [
    "row_outlay_foreign_ag_service",
]
SECURITY_ROW_OUTLAY_COMPONENT_KEYS = [
    "row_outlay_foreign_military_financing",
    "row_outlay_international_narcotics",
]


def _load_mts_outlays(path: Path | str) -> pd.DataFrame:
    df = load_treasury_table(path).copy()
    required = {"record_date", "classification_desc", "current_month_net_outly_amt"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"MTS outlays file {path} is missing required columns: {missing}")
    out = df.loc[:, ["record_date", "classification_desc", "current_month_net_outly_amt"]].copy()
    out["record_date"] = pd.to_datetime(out["record_date"])
    out["classification_desc"] = out["classification_desc"].fillna("").astype(str)
    out["current_month_net_outly_amt"] = pd.to_numeric(out["current_month_net_outly_amt"], errors="coerce").fillna(0.0)
    return out


def _full_quarter_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    monthly = pd.to_datetime(df["record_date"]).dt.to_period("M")
    coverage = monthly.groupby(monthly.dt.asfreq("Q")).nunique()
    full = coverage[coverage >= 3].index.to_timestamp("Q")
    return pd.DatetimeIndex(full).sort_values()


def _quarterly_outlay_sum(df: pd.DataFrame, labels: list[str]) -> pd.Series:
    sub = df.loc[df["classification_desc"].isin(labels), ["record_date", "current_month_net_outly_amt"]].copy()
    if sub.empty:
        return pd.Series(dtype="float64")
    series = sub.groupby(sub["record_date"].dt.to_period("Q"))["current_month_net_outly_amt"].sum()
    series.index = series.index.to_timestamp("Q")
    return series.sort_index() / 1_000_000.0


def build_tier3_source_diagnostics(
    *,
    mts_outlays_path: Path | str,
    start: str = "2022-09-30",
) -> pd.DataFrame:
    outlays = _load_mts_outlays(mts_outlays_path)
    full_quarters = _full_quarter_index(outlays)
    diag = pd.DataFrame(index=full_quarters)

    diag["bank_noninterest_outlay_source"] = _quarterly_outlay_sum(outlays, BANK_OUTLAY_LABELS).reindex(full_quarters).fillna(0.0)

    for key, label in ROW_OUTLAY_COMPONENT_LABELS.items():
        diag[key] = _quarterly_outlay_sum(outlays, [label]).reindex(full_quarters).fillna(0.0)

    row_component_cols = list(ROW_OUTLAY_COMPONENT_LABELS.keys())
    diag["row_outlay_total_selected"] = diag[row_component_cols].sum(axis=1, min_count=1)
    diag["row_outlay_security_selected"] = diag[SECURITY_ROW_OUTLAY_COMPONENT_KEYS].sum(axis=1, min_count=1)
    diag["row_outlay_core_institutional_selected"] = diag[CORE_INSTITUTIONAL_ROW_OUTLAY_COMPONENT_KEYS].sum(axis=1, min_count=1)
    diag["row_outlay_humanitarian_addon_selected"] = diag[HUMANITARIAN_ROW_OUTLAY_COMPONENT_KEYS].sum(axis=1, min_count=1)
    diag["row_outlay_agency_addon_selected"] = diag[AGENCY_ROW_OUTLAY_COMPONENT_KEYS].sum(axis=1, min_count=1)
    diag["row_outlay_humanitarian_development_selected"] = diag[
        ["row_outlay_ida_contribution", "row_outlay_foreign_ag_service", "row_outlay_international_disaster"]
    ].sum(axis=1, min_count=1)
    diag["row_outlay_institutions_selected"] = diag[
        ["row_outlay_international_monetary", "row_outlay_international_orgs"]
    ].sum(axis=1, min_count=1)
    diag["row_outlay_default_selected"] = diag[DEFAULT_ROW_OUTLAY_COMPONENT_KEYS].sum(axis=1, min_count=1)
    diag["row_outlay_broad_selected"] = diag["row_outlay_total_selected"]

    diag["mint_net_outlay_source"] = _quarterly_outlay_sum(outlays, MINT_LABELS).reindex(full_quarters).fillna(0.0)
    diag["mint_cb_cash_factor_source"] = (-diag["mint_net_outlay_source"]).clip(lower=0.0)

    return diag.loc[diag.index >= pd.Timestamp(start)].copy()


def build_source_backed_tier3_input_table(
    *,
    mts_outlays_path: Path | str,
    base_quarterly_input_path: Path | str | None = None,
    start: str = "2022-09-30",
    row_profile: str = "default",
) -> pd.DataFrame:
    if row_profile not in {"default", "broad"}:
        raise ValueError(f"Unsupported row_profile {row_profile!r}. Expected 'default' or 'broad'.")
    outlays = _load_mts_outlays(mts_outlays_path)
    full_quarters = _full_quarter_index(outlays)

    if base_quarterly_input_path is not None and Path(base_quarterly_input_path).exists():
        table = load_tier3_quarterly_input_table(base_quarterly_input_path).copy()
    else:
        table = pd.DataFrame(index=full_quarters)

    table = table.sort_index()
    for key in TIER3_SUPPORT_KEYS:
        if key not in table.columns:
            table[key] = 0.0

    source_index = table.index.union(full_quarters)
    table = table.reindex(source_index).sort_index()

    bank_outlay = _quarterly_outlay_sum(outlays, BANK_OUTLAY_LABELS).reindex(full_quarters).fillna(0.0)
    diagnostics = build_tier3_source_diagnostics(mts_outlays_path=mts_outlays_path, start=start)
    row_column = "row_outlay_default_selected" if row_profile == "default" else "row_outlay_broad_selected"
    row_outlay = diagnostics[row_column].reindex(full_quarters).fillna(0.0)
    mint_factor = diagnostics["mint_cb_cash_factor_source"].reindex(full_quarters).fillna(0.0)

    table.loc[full_quarters, "bank_noninterest_outlay_proxy"] = bank_outlay
    table.loc[full_quarters, "row_noninterest_outlay_proxy"] = row_outlay
    table.loc[full_quarters, "bank_nonborrow_receipt_proxy"] = table.loc[
        full_quarters, "bank_nonborrow_receipt_proxy"
    ].fillna(0.0)
    table.loc[full_quarters, "row_nonborrow_receipt_proxy"] = table.loc[
        full_quarters, "row_nonborrow_receipt_proxy"
    ].fillna(0.0)
    table.loc[full_quarters, "mint_cb_cash_factor_proxy"] = mint_factor

    return table.loc[table.index >= pd.Timestamp(start), TIER3_SUPPORT_KEYS].copy()


def write_source_backed_tier3_input_table(
    *,
    mts_outlays_path: Path | str,
    out_path: Path | str,
    base_quarterly_input_path: Path | str | None = None,
    start: str = "2022-09-30",
    row_profile: str = "default",
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = build_source_backed_tier3_input_table(
        mts_outlays_path=mts_outlays_path,
        base_quarterly_input_path=base_quarterly_input_path,
        start=start,
        row_profile=row_profile,
    )
    to_write = table.copy()
    to_write.index.name = "date"
    to_write.to_csv(out_path)
    return out_path


def render_tier3_source_diagnostics_markdown(diagnostics: pd.DataFrame) -> str:
    title = "# Tier 3 Source Diagnostics"
    intro = (
        "Quarter-by-quarter diagnostics for the current MTS outlay-backed Tier 3 partial fiscal shell. "
        "Amounts are in millions. The ROW total is the sum of the selected foreign and international leaf lines; "
        "bank and ROW receipt cells remain missing/not-measured for live-default governance."
    )
    if diagnostics.empty:
        return "\n".join([title, "", intro, "", "No full-quarter MTS outlay coverage is available."])

    latest_date = diagnostics.index.max()
    latest = diagnostics.loc[latest_date]
    component_cols = list(ROW_OUTLAY_COMPONENT_LABELS.keys())
    latest_components = latest[component_cols].sort_values(ascending=False)
    latest_components = latest_components[latest_components > 0]
    top_components = ", ".join(f"{name.replace('row_outlay_', '')}={value:,.3f}" for name, value in latest_components.head(4).items())
    latest_summary = (
        f"Latest source-covered quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Bank outlay {float(latest['bank_noninterest_outlay_source']):,.3f}; "
        f"ROW default {float(latest['row_outlay_default_selected']):,.3f}; "
        f"ROW broad {float(latest['row_outlay_broad_selected']):,.3f}; "
        f"core institutional {float(latest['row_outlay_core_institutional_selected']):,.3f}; "
        f"security {float(latest['row_outlay_security_selected']):,.3f}; "
        f"humanitarian/development {float(latest['row_outlay_humanitarian_development_selected']):,.3f}; "
        f"institutions {float(latest['row_outlay_institutions_selected']):,.3f}; "
        f"mint factor {float(latest['mint_cb_cash_factor_source']):,.3f}. "
        f"Top ROW components: {top_components or 'none'}."
    )

    header = (
        "| Quarter | Bank outlay | ROW core institutional | ROW narrow | ROW broad | Humanitarian add-on | Agency add-on | Security add-on | FMF | Disaster | Foreign ag | IDA | Narcotics | Intl orgs | Intl monetary | Mint factor |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    rows: list[str] = []
    for date, row in diagnostics.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    f"{float(row.get('bank_noninterest_outlay_source', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_core_institutional_selected', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_default_selected', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_broad_selected', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_humanitarian_addon_selected', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_agency_addon_selected', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_security_selected', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_foreign_military_financing', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_international_disaster', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_foreign_ag_service', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_ida_contribution', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_international_narcotics', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_international_orgs', 0.0)):,.3f}",
                    f"{float(row.get('row_outlay_international_monetary', 0.0)):,.3f}",
                    f"{float(row.get('mint_cb_cash_factor_source', 0.0)):,.3f}",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `ROW core institutional` is IDA, International Monetary Programs, and International Organizations and Conferences.",
        "- `ROW narrow` adds International Disaster Assistance and Foreign Agricultural Service; it is a proxy, not proof of ultimate ROW cash recipient.",
        "- Bank and ROW receipt corrections are source-boundary missing cells in the live shell, even when arithmetic support files carry zero placeholders.",
    ]
    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, "", *notes, ""])


def write_tier3_source_diagnostics(
    *,
    mts_outlays_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2022-09-30",
) -> tuple[Path, Path, pd.DataFrame]:
    diagnostics = build_tier3_source_diagnostics(mts_outlays_path=mts_outlays_path, start=start)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = diagnostics.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_tier3_source_diagnostics_markdown(diagnostics), encoding="utf-8")

    return csv_path, markdown_path, diagnostics
