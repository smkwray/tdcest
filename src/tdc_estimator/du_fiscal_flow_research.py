from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import load_treasury_table
from .sector_coupon import (
    estimate_quarterly_sector_coupon_interest_proxy,
    read_sector_maturity_table,
    read_sector_panel_table,
    read_table,
    resolve_first_existing,
    resolve_wamest_artifact_paths,
)

OUTLAY_TOTAL_LABEL = "Total Outlays"
OUTLAY_INTEREST_GROSS_LABEL = "Total--Interest on Treasury Debt Securities (Gross)"
RECEIPT_TOTAL_LABEL = "Total -- Receipts"
RECEIPT_FED_EARNINGS_LABEL = "Deposit of Earnings, Federal Reserve System"
DEFAULT_DU_PRIVATE_NONFINANCIAL_SECTOR_KEYS = [
    "households_nonprofits",
    "nonfinancial_corporates",
    "nonfinancial_noncorporate_business",
]
DEFAULT_DU_PRIVATE_FINANCIAL_NONBANK_SECTOR_KEYS = [
    "life_insurers",
    "private_defined_benefit_pensions",
    "private_defined_contribution_pensions",
    "property_casualty_insurers",
]
DEFAULT_WAMEST_ROOT_CANDIDATES = [
    Path("../wamest"),
    Path(__file__).resolve().parents[3] / "wamest",
]
DEFAULT_WAMEST_TRANSACTION_PANEL_CANDIDATES = [
    Path("outputs/full_coverage_release/z1_series_auto_full.csv"),
    Path("data/external/normalized/z1_series_fred.csv"),
]
DEFAULT_WAMEST_INVENTORY_CANDIDATES = [
    Path("outputs/full_coverage_release/required_sector_inventory.csv"),
]
DEFAULT_DU_NARROW_COUPON_SECTOR_KEYS = tuple(DEFAULT_DU_PRIVATE_NONFINANCIAL_SECTOR_KEYS)
DEFAULT_DU_BROAD_COUPON_SECTOR_KEYS = tuple(
    DEFAULT_DU_PRIVATE_NONFINANCIAL_SECTOR_KEYS + DEFAULT_DU_PRIVATE_FINANCIAL_NONBANK_SECTOR_KEYS
)
DEFAULT_WAMEST_COUPON_PANEL_SUPPLEMENT_CANDIDATES = [
    Path("data/interim/z1_sector_panel_full.csv"),
]


def _maybe(frame: pd.DataFrame, column: str, index: pd.DatetimeIndex) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(index=index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").reindex(index)


def _blend(primary: pd.Series, fallback: pd.Series) -> pd.Series:
    primary = pd.to_numeric(primary, errors="coerce")
    fallback = pd.to_numeric(fallback, errors="coerce").reindex(primary.index)
    return primary.combine_first(fallback)


def _resolve_wamest_root(wamest_root: Path | str | None) -> Path | None:
    if wamest_root is not None:
        candidate = Path(wamest_root)
        return candidate if candidate.exists() else None

    seen: set[Path] = set()
    for candidate in DEFAULT_WAMEST_ROOT_CANDIDATES:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists():
            return candidate
    return None


def _load_wamest_sector_transaction_panel(wamest_root: Path | str | None) -> pd.DataFrame:
    root = _resolve_wamest_root(wamest_root)
    if root is None:
        return pd.DataFrame()

    try:
        panel_path = resolve_first_existing(root, DEFAULT_WAMEST_TRANSACTION_PANEL_CANDIDATES)
        inventory_path = resolve_first_existing(root, DEFAULT_WAMEST_INVENTORY_CANDIDATES)
    except FileNotFoundError:
        return pd.DataFrame()

    panel = read_table(panel_path)
    inventory = read_table(inventory_path)

    series_code_col = next((column for column in ["series_code", "series_key"] if column in panel.columns), None)
    value_col = next((column for column in ["value", "level"] if column in panel.columns), None)
    inventory_code_col = next(
        (
            column
            for column in ["transactions_source_code", "transactions_fred_id"]
            if column in inventory.columns and inventory[column].notna().any()
        ),
        None,
    )
    if (
        series_code_col is None
        or value_col is None
        or "date" not in panel.columns
        or inventory_code_col is None
        or "sector_key" not in inventory.columns
    ):
        return pd.DataFrame()

    code_map = (
        inventory.loc[:, ["sector_key", inventory_code_col]]
        .dropna()
        .drop_duplicates(subset=["sector_key"])
        .rename(columns={inventory_code_col: series_code_col})
    )
    if code_map.empty:
        return pd.DataFrame()

    merged = panel.merge(code_map, on=series_code_col, how="inner")
    if merged.empty:
        return pd.DataFrame()

    out = merged.loc[:, ["date", "sector_key", value_col]].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["value"] = pd.to_numeric(out[value_col], errors="coerce")
    if value_col != "value":
        out = out.drop(columns=[value_col])
    return out.dropna(subset=["date", "sector_key", "value"])


def _sum_wamest_sector_transactions(
    wamest_transactions: pd.DataFrame,
    *,
    sector_keys: list[str],
    index: pd.DatetimeIndex,
) -> pd.Series:
    if wamest_transactions.empty:
        return pd.Series(index=index, dtype="float64")

    subset = wamest_transactions.loc[wamest_transactions["sector_key"].isin(sector_keys), ["date", "value"]].copy()
    if subset.empty:
        return pd.Series(index=index, dtype="float64")

    series = subset.groupby("date")["value"].sum().sort_index()
    return pd.to_numeric(series, errors="coerce").reindex(index)


def _load_du_coupon_sector_panel(
    root: Path,
    default_panel_path: Path,
) -> pd.DataFrame:
    base_panel = read_sector_panel_table(default_panel_path)
    panels = [base_panel]
    for candidate in DEFAULT_WAMEST_COUPON_PANEL_SUPPLEMENT_CANDIDATES:
        path = root / candidate
        if path.exists():
            supplement = read_sector_panel_table(path)
            if "level_units" not in supplement.columns:
                supplement = supplement.copy()
                supplement["level"] = pd.to_numeric(supplement["level"], errors="coerce") * 1_000.0
                supplement["level_units"] = "millions"
            panels.insert(0, supplement)

    combined = pd.concat(panels, ignore_index=True, sort=False)
    if combined.empty:
        return combined
    deduped = combined.drop_duplicates(subset=["date", "sector_key"], keep="first")
    return deduped.sort_values(["date", "sector_key"]).reset_index(drop=True)


def _load_direct_du_coupon_proxies_from_wamest(
    *,
    index: pd.DatetimeIndex,
    wamest_root: Path | str | None = None,
    narrow_sector_keys: tuple[str, ...] = DEFAULT_DU_NARROW_COUPON_SECTOR_KEYS,
    broad_sector_keys: tuple[str, ...] = DEFAULT_DU_BROAD_COUPON_SECTOR_KEYS,
) -> tuple[pd.Series, pd.Series]:
    empty_narrow = pd.Series(index=index, dtype="float64", name="du_coupon_proxy_direct_narrow")
    empty_broad = pd.Series(index=index, dtype="float64", name="du_coupon_proxy_direct_broad")

    root = _resolve_wamest_root(wamest_root)
    if root is None:
        return empty_narrow, empty_broad

    try:
        sector_maturity_path, sector_panel_path, curve_path = resolve_wamest_artifact_paths(root)
    except FileNotFoundError:
        return empty_narrow, empty_broad

    try:
        sector_maturity = read_sector_maturity_table(sector_maturity_path)
        sector_panel = _load_du_coupon_sector_panel(root, sector_panel_path)
        curves = read_table(curve_path)
        narrow = estimate_quarterly_sector_coupon_interest_proxy(
            sector_maturity=sector_maturity,
            sector_panel=sector_panel,
            curves=curves,
            sector_keys=narrow_sector_keys,
            series_name="du_coupon_proxy_direct_narrow",
        ).reindex(index)
        broad = estimate_quarterly_sector_coupon_interest_proxy(
            sector_maturity=sector_maturity,
            sector_panel=sector_panel,
            curves=curves,
            sector_keys=broad_sector_keys,
            series_name="du_coupon_proxy_direct_broad",
        ).reindex(index)
    except (FileNotFoundError, ValueError, KeyError):
        return empty_narrow, empty_broad

    narrow.name = "du_coupon_proxy_direct_narrow"
    broad.name = "du_coupon_proxy_direct_broad"
    return narrow, broad


def _quarterly_single_label_sum(
    path: Path | str,
    *,
    label: str,
    value_column: str,
) -> pd.Series:
    df = load_treasury_table(path).copy()
    required = {"record_date", "classification_desc", value_column}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Treasury table {path} is missing required columns: {missing}")

    subset = df.loc[df["classification_desc"].eq(label), ["record_date", value_column]].copy()
    if subset.empty:
        return pd.Series(dtype="float64")

    subset["record_date"] = pd.to_datetime(subset["record_date"])
    subset[value_column] = pd.to_numeric(subset[value_column], errors="coerce")
    subset = subset.dropna(subset=[value_column])
    if subset.empty:
        return pd.Series(dtype="float64")

    series = subset.groupby(subset["record_date"].dt.to_period("Q"))[value_column].sum()
    series.index = series.index.to_timestamp("Q")
    return (series.sort_index() / 1_000_000.0).astype("float64")


def build_du_fiscal_flow_research(
    quarterly: pd.DataFrame,
    components: pd.DataFrame,
    *,
    mts_outlays_path: Path | str,
    mts_receipts_path: Path | str,
    wamest_root: Path | str | None = None,
) -> pd.DataFrame:
    index = pd.DatetimeIndex(quarterly.index.union(components.index)).sort_values().unique()
    out = pd.DataFrame(index=index)

    out["treasury_total_outlays_mts"] = _quarterly_single_label_sum(
        mts_outlays_path,
        label=OUTLAY_TOTAL_LABEL,
        value_column="current_month_net_outly_amt",
    ).reindex(index)
    out["treasury_total_outlays_fred"] = _maybe(quarterly, "federal_current_expenditures_nsa_q", index)
    out["treasury_interest_gross_mts"] = _quarterly_single_label_sum(
        mts_outlays_path,
        label=OUTLAY_INTEREST_GROSS_LABEL,
        value_column="current_month_net_outly_amt",
    ).reindex(index)
    out["treasury_interest_gross_fred"] = _maybe(quarterly, "federal_interest_payments_nsa_q", index)
    out["treasury_total_receipts_mts"] = _quarterly_single_label_sum(
        mts_receipts_path,
        label=RECEIPT_TOTAL_LABEL,
        value_column="current_month_net_rcpt_amt",
    ).reindex(index)
    out["treasury_total_receipts_fred"] = _maybe(quarterly, "federal_current_receipts_nsa_q", index)
    out["fed_earnings_receipt_mts"] = _quarterly_single_label_sum(
        mts_receipts_path,
        label=RECEIPT_FED_EARNINGS_LABEL,
        value_column="current_month_net_rcpt_amt",
    ).reindex(index)

    out["treasury_total_outlays_proxy"] = _blend(
        out["treasury_total_outlays_mts"],
        out["treasury_total_outlays_fred"],
    )
    out["treasury_interest_gross_proxy"] = _blend(
        out["treasury_interest_gross_mts"],
        out["treasury_interest_gross_fred"],
    )
    out["treasury_total_receipts_proxy"] = _blend(
        out["treasury_total_receipts_mts"],
        out["treasury_total_receipts_fred"],
    )

    wamest_transactions = _load_wamest_sector_transaction_panel(wamest_root)
    wamest_private_nonfinancial_flow = _sum_wamest_sector_transactions(
        wamest_transactions,
        sector_keys=DEFAULT_DU_PRIVATE_NONFINANCIAL_SECTOR_KEYS,
        index=index,
    )
    wamest_private_financial_nonbank_flow = _sum_wamest_sector_transactions(
        wamest_transactions,
        sector_keys=DEFAULT_DU_PRIVATE_FINANCIAL_NONBANK_SECTOR_KEYS,
        index=index,
    )

    domestic_financial_tx = _maybe(quarterly, "domestic_financial_tsy_tx", index)
    fed_tsy_tx = _maybe(components, "fed_tsy_tx", index)
    bank_depository_tsy_tx = _maybe(components, "bank_depository_tsy_tx", index)
    credit_union_total_tsy_tx = _maybe(
        components,
        "credit_unions_total_tsy_tx_direct" if "credit_unions_total_tsy_tx_direct" in components.columns else "credit_unions_total_tsy_tx_reconstructed",
        index,
    )

    fallback_narrow_security_flow = -_maybe(quarterly, "domestic_nonfinancial_tsy_tx", index)
    fallback_private_financial_nonbank_flow = -(
        domestic_financial_tx - fed_tsy_tx - bank_depository_tsy_tx - credit_union_total_tsy_tx.fillna(0.0)
    )
    out["du_domestic_nonfinancial_security_flow_proxy"] = _blend(
        -wamest_private_nonfinancial_flow,
        fallback_narrow_security_flow,
    )
    out["du_other_domestic_financial_nonru_security_flow_proxy"] = _blend(
        -wamest_private_financial_nonbank_flow,
        fallback_private_financial_nonbank_flow,
    )
    out["du_broad_private_security_flow_proxy"] = (
        out["du_domestic_nonfinancial_security_flow_proxy"]
        + out["du_other_domestic_financial_nonru_security_flow_proxy"]
    )

    out["du_noninterest_outlay_proxy"] = (
        out["treasury_total_outlays_proxy"]
        - out["treasury_interest_gross_proxy"]
        - _maybe(components, "bank_noninterest_outlay_proxy", index).fillna(0.0)
        - _maybe(components, "row_noninterest_outlay_proxy", index).fillna(0.0)
    )
    out["du_receipt_proxy"] = (
        out["treasury_total_receipts_proxy"]
        - out["fed_earnings_receipt_mts"].fillna(0.0)
        - _maybe(components, "bank_nonborrow_receipt_proxy", index).fillna(0.0)
        - _maybe(components, "row_nonborrow_receipt_proxy", index).fillna(0.0)
    )
    out["du_coupon_proxy_residual"] = (
        out["treasury_interest_gross_proxy"]
        - _maybe(components, "fed_tsy_coupon_interest_proxy", index).fillna(0.0)
        - _maybe(components, "bank_tsy_coupon_interest_proxy", index).fillna(0.0)
        - _maybe(components, "row_tsy_coupon_interest_proxy", index).fillna(0.0)
    )
    direct_narrow_coupon, direct_broad_coupon = _load_direct_du_coupon_proxies_from_wamest(
        index=index,
        wamest_root=wamest_root,
    )
    out["du_coupon_proxy_direct_narrow"] = _blend(direct_narrow_coupon, out["du_coupon_proxy_residual"])
    out["du_coupon_proxy_direct_broad"] = _blend(direct_broad_coupon, out["du_coupon_proxy_residual"])

    out["tdc_du_fiscal_flow_first_pass_narrow"] = (
        out["du_domestic_nonfinancial_security_flow_proxy"]
        + out["du_noninterest_outlay_proxy"]
        - out["du_receipt_proxy"]
        - out["du_coupon_proxy_direct_narrow"]
    )
    out["tdc_du_fiscal_flow_first_pass_broad"] = (
        out["du_broad_private_security_flow_proxy"]
        + out["du_noninterest_outlay_proxy"]
        - out["du_receipt_proxy"]
        - out["du_coupon_proxy_direct_broad"]
    )

    return out.dropna(how="all").sort_index()


def render_du_fiscal_flow_research_markdown(frame: pd.DataFrame) -> str:
    title = "# DU Fiscal-Flow Research"
    intro = (
        "First-pass DU-facing fiscal-flow surface. Amounts are in millions. "
        "This is not yet a promoted headline estimator. It combines total MTS cash totals with DU-side Treasury-security proxies "
        "and direct DU coupon estimation where available."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No DU fiscal-flow research rows were available."])

    latest_date = frame.index.max()
    latest = frame.loc[latest_date]
    latest_summary = (
        f"Latest quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Narrow DU first pass {float(latest.get('tdc_du_fiscal_flow_first_pass_narrow', float('nan'))):,.3f}; "
        f"broad DU first pass {float(latest.get('tdc_du_fiscal_flow_first_pass_broad', float('nan'))):,.3f}; "
        f"DU noninterest outlay proxy {float(latest.get('du_noninterest_outlay_proxy', float('nan'))):,.3f}; "
        f"DU receipt proxy {float(latest.get('du_receipt_proxy', float('nan'))):,.3f}; "
        f"DU direct narrow coupon proxy {float(latest.get('du_coupon_proxy_direct_narrow', float('nan'))):,.3f}; "
        f"DU direct broad coupon proxy {float(latest.get('du_coupon_proxy_direct_broad', float('nan'))):,.3f}; "
        f"DU coupon residual fallback {float(latest.get('du_coupon_proxy_residual', float('nan'))):,.3f}."
    )

    header = (
        "| Quarter | Narrow DU security | Broad DU security | DU noninterest outlays | DU receipts | DU coupon narrow | DU coupon broad | DU coupon residual fallback | Narrow DU first pass | Broad DU first pass |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    rows: list[str] = []
    for date, row in frame.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    f"{float(pd.to_numeric(row.get('du_domestic_nonfinancial_security_flow_proxy'), errors='coerce')):,.3f}",
                    f"{float(pd.to_numeric(row.get('du_broad_private_security_flow_proxy'), errors='coerce')):,.3f}",
                    f"{float(pd.to_numeric(row.get('du_noninterest_outlay_proxy'), errors='coerce')):,.3f}",
                    f"{float(pd.to_numeric(row.get('du_receipt_proxy'), errors='coerce')):,.3f}",
                    f"{float(pd.to_numeric(row.get('du_coupon_proxy_direct_narrow'), errors='coerce')):,.3f}",
                    f"{float(pd.to_numeric(row.get('du_coupon_proxy_direct_broad'), errors='coerce')):,.3f}",
                    f"{float(pd.to_numeric(row.get('du_coupon_proxy_residual'), errors='coerce')):,.3f}",
                    f"{float(pd.to_numeric(row.get('tdc_du_fiscal_flow_first_pass_narrow'), errors='coerce')):,.3f}",
                    f"{float(pd.to_numeric(row.get('tdc_du_fiscal_flow_first_pass_broad'), errors='coerce')):,.3f}",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `narrow` prefers a direct `wamest` sum of private nonfinancial DU sectors: households/nonprofits, nonfinancial corporates, and nonfinancial noncorporate business.",
        "- `broad` adds a direct `wamest` sum of private financial nonbank DU sectors where available; otherwise it falls back to the older domestic-financial residual proxy.",
        "- Total outlays, receipts, and interest use MTS where available and otherwise fall back to quarterly BEA/FRED NSA federal current expenditures, current receipts, and interest payments.",
        "- DU coupon terms now prefer direct `wamest` sector coupon estimates where level and maturity coverage exist, and otherwise fall back quarter-by-quarter to the residual Treasury-interest proxy minus Fed, bank, and ROW coupon proxies.",
        "- The DU receipt term currently subtracts the explicit Fed earnings receipt line from total MTS receipts before removing any live bank/ROW receipt support terms.",
    ]
    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, "", *notes, ""])


def write_du_fiscal_flow_research(
    *,
    quarterly: pd.DataFrame,
    components: pd.DataFrame,
    mts_outlays_path: Path | str,
    mts_receipts_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    wamest_root: Path | str | None = None,
) -> tuple[Path, Path, pd.DataFrame]:
    if not Path(mts_outlays_path).exists() or not Path(mts_receipts_path).exists():
        frame = pd.DataFrame()
    else:
        try:
            frame = build_du_fiscal_flow_research(
                quarterly,
                components,
                mts_outlays_path=mts_outlays_path,
                mts_receipts_path=mts_receipts_path,
                wamest_root=wamest_root,
            )
        except ValueError:
            frame = pd.DataFrame()

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = frame.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_du_fiscal_flow_research_markdown(frame), encoding="utf-8")
    return csv_path, markdown_path, frame
