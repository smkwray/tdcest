from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import TREASURY_DATASETS, TreasuryDataset
from .download import download_treasury_dataset
from .treasury_interest_components import build_treasury_interest_component_pools
from .utils import ensure_dir


BILL_DISCOUNT_BENCHMARK_COLUMN = "treasury_bill_amortized_discount_mil"
BANK_PROXY_COLUMN = "bank_tsy_bill_discount_interest_proxy"
ROW_PROXY_COLUMN = "row_tsy_bill_discount_interest_proxy"
CREDIT_UNION_PROXY_COLUMN = "credit_union_tsy_bill_discount_interest_proxy"


def treasury_interest_expense_dataset() -> TreasuryDataset:
    for spec in TREASURY_DATASETS:
        if spec.key == "interest_expense":
            return spec
    raise KeyError("Treasury interest_expense dataset is not registered.")


def ensure_treasury_interest_expense_file(
    treasury_interest_path: Path | str,
    *,
    raw_dir: Path | str | None = None,
    project_root: Path | str | None = None,
) -> Path:
    path = Path(treasury_interest_path)
    if path.exists():
        return path
    download_dir = Path(raw_dir) if raw_dir is not None else path.parent
    download_treasury_dataset(treasury_interest_expense_dataset(), download_dir, project_root=project_root)
    if path.exists():
        return path
    default_path = download_dir / "treasury__interest_expense.csv"
    if default_path.exists():
        return default_path
    raise FileNotFoundError(f"Treasury interest expense download did not create {path}.")


def quarterly_treasury_bill_amortized_discount(treasury_interest_expense: pd.DataFrame) -> pd.Series:
    source = treasury_interest_expense.copy()
    if "expense_catg_desc" not in source.columns:
        source["expense_catg_desc"] = "INTEREST EXPENSE ON PUBLIC ISSUES"
    pools = build_treasury_interest_component_pools(source)
    if pools.empty:
        return pd.Series(dtype="float64", name=BILL_DISCOUNT_BENCHMARK_COLUMN)

    bills = pools.loc[
        pools["component_key"].eq("bill_amortized_discount")
        & pools["included_in_bill_discount_pool"].fillna(False),
        ["date", "quarter_expense_mil"],
    ].copy()
    if bills.empty:
        return pd.Series(dtype="float64", name=BILL_DISCOUNT_BENCHMARK_COLUMN)

    bills["date"] = pd.to_datetime(bills["date"], errors="coerce")
    bills["quarter_expense_mil"] = pd.to_numeric(bills["quarter_expense_mil"], errors="coerce")
    bills = bills.dropna(subset=["date", "quarter_expense_mil"])
    out = bills.groupby("date")["quarter_expense_mil"].sum().sort_index()
    out.name = BILL_DISCOUNT_BENCHMARK_COLUMN
    return out


def _read_proxy(path: Path | str, column: str) -> pd.Series:
    proxy_path = Path(path)
    if not proxy_path.exists():
        return pd.Series(dtype="float64", name=column)
    df = pd.read_csv(proxy_path)
    if "date" not in df.columns:
        raise ValueError(f"{proxy_path} must contain a date column.")
    value_column = column if column in df.columns else "value" if "value" in df.columns else None
    if value_column is None:
        raise ValueError(f"{proxy_path} must contain {column} or value columns.")
    dates = pd.to_datetime(df["date"], errors="coerce")
    values = pd.to_numeric(df[value_column], errors="coerce")
    series = pd.Series(values.to_numpy(), index=dates, name=column).dropna()
    return series.groupby(series.index).last().sort_index()


def _ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    clean_denominator = denominator.where(denominator.abs() > 0)
    return numerator / clean_denominator


def build_bill_discount_validation_table(
    treasury_interest_expense: pd.DataFrame,
    bank_proxy: pd.Series | None = None,
    row_proxy: pd.Series | None = None,
    credit_union_proxy: pd.Series | None = None,
) -> pd.DataFrame:
    benchmark = quarterly_treasury_bill_amortized_discount(treasury_interest_expense)
    series = [benchmark]
    for candidate, name in [
        (bank_proxy, BANK_PROXY_COLUMN),
        (row_proxy, ROW_PROXY_COLUMN),
        (credit_union_proxy, CREDIT_UNION_PROXY_COLUMN),
    ]:
        series.append(pd.Series(dtype="float64", name=name) if candidate is None else candidate.rename(name))

    index = pd.DatetimeIndex([])
    for item in series:
        index = pd.DatetimeIndex(index.union(pd.DatetimeIndex(item.index)))
    index = pd.DatetimeIndex(index).sort_values()

    out = pd.DataFrame(index=index)
    for item in series:
        out[item.name] = item.reindex(index)

    out["bank_row_proxy_mil"] = out[[BANK_PROXY_COLUMN, ROW_PROXY_COLUMN]].sum(axis=1, min_count=1)
    out["bank_row_cu_proxy_mil"] = out[[BANK_PROXY_COLUMN, ROW_PROXY_COLUMN, CREDIT_UNION_PROXY_COLUMN]].sum(
        axis=1, min_count=1
    )
    out["bank_row_share_of_aggregate"] = _ratio(out["bank_row_proxy_mil"], out[BILL_DISCOUNT_BENCHMARK_COLUMN])
    out["bank_row_cu_share_of_aggregate"] = _ratio(out["bank_row_cu_proxy_mil"], out[BILL_DISCOUNT_BENCHMARK_COLUMN])
    out["has_treasury_bill_benchmark"] = out[BILL_DISCOUNT_BENCHMARK_COLUMN].notna()
    out["has_all_sector_proxies"] = out[[BANK_PROXY_COLUMN, ROW_PROXY_COLUMN, CREDIT_UNION_PROXY_COLUMN]].notna().all(
        axis=1
    )
    out.index.name = "date"
    return out.reset_index()


def build_bill_discount_validation_from_files(
    *,
    treasury_interest_path: Path | str,
    bank_proxy_path: Path | str,
    row_proxy_path: Path | str,
    credit_union_proxy_path: Path | str,
) -> pd.DataFrame:
    treasury = pd.read_csv(treasury_interest_path)
    return build_bill_discount_validation_table(
        treasury,
        bank_proxy=_read_proxy(bank_proxy_path, BANK_PROXY_COLUMN),
        row_proxy=_read_proxy(row_proxy_path, ROW_PROXY_COLUMN),
        credit_union_proxy=_read_proxy(credit_union_proxy_path, CREDIT_UNION_PROXY_COLUMN),
    )


def _format_money(value: object) -> str:
    try:
        if pd.isna(value):
            return "NA"
        return f"${float(value):,.0f} million"
    except Exception:
        return "NA"


def _format_pct(value: object) -> str:
    try:
        if pd.isna(value):
            return "NA"
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "NA"


def summarize_bill_discount_validation(validation: pd.DataFrame) -> str:
    if validation.empty:
        return "# Bill-Discount Validation\n\nNo Treasury bill amortized-discount benchmark rows were available.\n"

    df = validation.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    complete = df[df["has_treasury_bill_benchmark"].fillna(False)].sort_values("date")
    if complete.empty:
        return "# Bill-Discount Validation\n\nNo Treasury bill amortized-discount benchmark rows were available.\n"

    latest = complete.iloc[-1]
    overlap = complete[complete["has_all_sector_proxies"].fillna(False)].copy()
    median_bank_row = np.nan if overlap.empty else overlap["bank_row_share_of_aggregate"].median(skipna=True)
    median_bank_row_cu = np.nan if overlap.empty else overlap["bank_row_cu_share_of_aggregate"].median(skipna=True)

    first_date = complete["date"].min().date().isoformat()
    latest_date = pd.Timestamp(latest["date"]).date().isoformat()
    overlap_start = "NA" if overlap.empty else overlap["date"].min().date().isoformat()

    lines = [
        "# Bill-Discount Validation",
        "",
        (
            f"Treasury bill amortized-discount benchmark coverage runs from {first_date} "
            f"through {latest_date} in the downloaded FiscalData interest-expense file."
        ),
        "",
        (
            f"Latest quarter ({latest_date}): Treasury bill amortized discount is "
            f"{_format_money(latest.get(BILL_DISCOUNT_BENCHMARK_COLUMN))}; bank+ROW proxy is "
            f"{_format_money(latest.get('bank_row_proxy_mil'))}; bank+ROW+credit-union proxy is "
            f"{_format_money(latest.get('bank_row_cu_proxy_mil'))}."
        ),
        "",
        (
            f"Across quarters with all three sector proxies present since {overlap_start}, "
            f"the median bank+ROW proxy share of aggregate bill discount is {_format_pct(median_bank_row)}, "
            f"and the median bank+ROW+credit-union share is {_format_pct(median_bank_row_cu)}."
        ),
        "",
        "Interpretation: the Treasury benchmark is the aggregate public-issue bill discount accrual. "
        "The sector proxies are the estimated holder-specific part that should be removed from Tier 2 "
        "when transaction flows already include bill-discount amortization with the wrong sign for "
        "deposit-incidence interest flows.",
    ]
    return "\n".join(lines) + "\n"


def write_bill_discount_validation(
    *,
    treasury_interest_path: Path | str,
    bank_proxy_path: Path | str,
    row_proxy_path: Path | str,
    credit_union_proxy_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None]:
    validation = build_bill_discount_validation_from_files(
        treasury_interest_path=treasury_interest_path,
        bank_proxy_path=bank_proxy_path,
        row_proxy_path=row_proxy_path,
        credit_union_proxy_path=credit_union_proxy_path,
    )
    out_csv = Path(out_csv_path)
    ensure_dir(out_csv.parent)
    validation.to_csv(out_csv, index=False)

    out_md = None
    if out_markdown_path is not None:
        out_md = Path(out_markdown_path)
        ensure_dir(out_md.parent)
        out_md.write_text(summarize_bill_discount_validation(validation), encoding="utf-8")
    return out_csv, out_md
