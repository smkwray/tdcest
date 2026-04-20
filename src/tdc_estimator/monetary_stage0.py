from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_START = "2002-12-31"
PARTIAL_TARGET_LABEL = "partial_m2_less_currency_proxy"
DEPOSITORY_TARGET_LABEL = "depository_m2_less_currency_less_retail_mmf"
LIQUID_TARGET_LABEL = "liquid_m2_less_currency_less_retail_mmf_less_small_time"
BANK_TARGET_LABEL = "commercial_bank_deposit_target"


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _quarterly_millions(quarterly: pd.DataFrame, column: str, index: pd.DatetimeIndex) -> pd.Series:
    if column not in quarterly.columns:
        return pd.Series(index=index, dtype="float64")
    return pd.to_numeric(quarterly[column], errors="coerce").reindex(index) * 1000.0


def _quarterly_local_millions(quarterly: pd.DataFrame, column: str, index: pd.DatetimeIndex) -> pd.Series:
    if column not in quarterly.columns:
        return pd.Series(index=index, dtype="float64")
    return pd.to_numeric(quarterly[column], errors="coerce").reindex(index)


def build_monetary_stage0_diagnostics(
    quarterly: pd.DataFrame | None,
    estimates: pd.DataFrame | None,
    *,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    if quarterly is None or quarterly.empty or estimates is None or estimates.empty:
        return pd.DataFrame()
    if not {"m2", "currency"}.issubset(quarterly.columns):
        return pd.DataFrame()

    index = pd.DatetimeIndex(quarterly.index).sort_values().unique()
    frame = pd.DataFrame(index=index)
    frame["m2_level_mil"] = _quarterly_millions(quarterly, "m2", index)
    frame["currency_level_mil"] = _quarterly_millions(quarterly, "currency", index)
    frame["retail_money_market_funds_level_mil"] = _quarterly_millions(quarterly, "retail_money_market_funds", index)
    frame["small_time_deposits_level_mil"] = _quarterly_millions(quarterly, "small_time_deposits", index)
    frame["commercial_bank_deposits_level_mil"] = _quarterly_millions(quarterly, "commercial_bank_deposits", index)
    frame["credit_union_deposits_level_mil"] = _quarterly_local_millions(quarterly, "credit_union_deposits", index)
    frame["thrift_deposits_level_mil"] = _quarterly_local_millions(quarterly, "thrift_deposits", index)
    frame["large_time_deposits_all_commercial_banks_level_mil"] = _quarterly_millions(
        quarterly, "large_time_deposits_all_commercial_banks", index
    )
    frame["other_deposits_all_commercial_banks_level_mil"] = _quarterly_millions(
        quarterly, "other_deposits_all_commercial_banks", index
    )
    frame["bank_credit_level_mil"] = _quarterly_millions(quarterly, "bank_credit", index)
    frame["nonbank_depository_bridge_level_mil"] = pd.to_numeric(
        frame["credit_union_deposits_level_mil"], errors="coerce"
    ) + pd.to_numeric(frame["thrift_deposits_level_mil"], errors="coerce")

    frame["partial_m2_less_currency_level_mil"] = frame["m2_level_mil"] - frame["currency_level_mil"]
    if quarterly.get("retail_money_market_funds") is not None:
        frame["depository_target_level_mil"] = (
            frame["m2_level_mil"] - frame["currency_level_mil"] - frame["retail_money_market_funds_level_mil"]
        )
    else:
        frame["depository_target_level_mil"] = pd.NA
    if {"retail_money_market_funds", "small_time_deposits"}.issubset(quarterly.columns):
        frame["liquid_deposit_target_level_mil"] = (
            frame["m2_level_mil"]
            - frame["currency_level_mil"]
            - frame["retail_money_market_funds_level_mil"]
            - frame["small_time_deposits_level_mil"]
        )
    else:
        frame["liquid_deposit_target_level_mil"] = pd.NA

    frame["delta_partial_m2_less_currency_level_mil"] = frame["partial_m2_less_currency_level_mil"].diff()
    frame["delta_depository_target_level_mil"] = pd.to_numeric(frame["depository_target_level_mil"], errors="coerce").diff()
    frame["delta_liquid_deposit_target_level_mil"] = pd.to_numeric(frame["liquid_deposit_target_level_mil"], errors="coerce").diff()
    frame["delta_commercial_bank_deposits_level_mil"] = frame["commercial_bank_deposits_level_mil"].diff()
    frame["delta_credit_union_deposits_level_mil"] = pd.to_numeric(
        frame["credit_union_deposits_level_mil"], errors="coerce"
    ).diff()
    frame["delta_thrift_deposits_level_mil"] = pd.to_numeric(frame["thrift_deposits_level_mil"], errors="coerce").diff()
    frame["delta_nonbank_depository_bridge_level_mil"] = pd.to_numeric(
        frame["nonbank_depository_bridge_level_mil"], errors="coerce"
    ).diff()
    frame["delta_large_time_deposits_all_commercial_banks_level_mil"] = pd.to_numeric(
        frame["large_time_deposits_all_commercial_banks_level_mil"], errors="coerce"
    ).diff()
    frame["delta_other_deposits_all_commercial_banks_level_mil"] = pd.to_numeric(
        frame["other_deposits_all_commercial_banks_level_mil"], errors="coerce"
    ).diff()
    frame["delta_bank_credit_level_mil"] = frame["bank_credit_level_mil"].diff()

    for estimate_col, out_col in [
        ("tdc_base_bank_only_ru_flow", "tier0_bank_only_flow_mil"),
        ("tdc_tier2_interest_corrected_bank_only_ru_flow", "tier2_bank_only_flow_mil"),
        ("tdc_tier3_fiscal_corrected_bank_only_ru_flow", "tier3_bank_only_flow_mil"),
    ]:
        if estimate_col in estimates.columns:
            frame[out_col] = pd.to_numeric(estimates[estimate_col], errors="coerce").reindex(index)

    for target_delta_col, prefix in [
        ("delta_partial_m2_less_currency_level_mil", "partial_target"),
        ("delta_depository_target_level_mil", "depository_target"),
        ("delta_liquid_deposit_target_level_mil", "liquid_target"),
        ("delta_commercial_bank_deposits_level_mil", "commercial_bank_deposit_target"),
    ]:
        for estimate_out_col in [
            "tier0_bank_only_flow_mil",
            "tier2_bank_only_flow_mil",
            "tier3_bank_only_flow_mil",
        ]:
            if estimate_out_col in frame.columns:
                frame[f"{prefix}_minus_{estimate_out_col}"] = (
                    pd.to_numeric(frame[target_delta_col], errors="coerce") - frame[estimate_out_col]
                )

    frame["partial_target_label"] = PARTIAL_TARGET_LABEL
    frame["depository_target_label"] = DEPOSITORY_TARGET_LABEL
    frame["liquid_target_label"] = LIQUID_TARGET_LABEL
    frame["bank_target_label"] = BANK_TARGET_LABEL
    frame["has_retail_mmf_series"] = "retail_money_market_funds" in quarterly.columns
    frame["has_small_time_series"] = "small_time_deposits" in quarterly.columns
    frame["has_commercial_bank_deposit_series"] = "commercial_bank_deposits" in quarterly.columns
    frame["has_credit_union_deposit_series"] = "credit_union_deposits" in quarterly.columns
    frame["has_thrift_deposit_series"] = "thrift_deposits" in quarterly.columns
    frame["has_large_time_bank_deposit_series"] = "large_time_deposits_all_commercial_banks" in quarterly.columns
    frame["has_other_deposits_bank_series"] = "other_deposits_all_commercial_banks" in quarterly.columns
    frame["target_is_partial"] = ~(
        frame["has_retail_mmf_series"] & frame["has_small_time_series"] & frame["has_commercial_bank_deposit_series"]
    )
    frame["notes"] = (
        "Stage 0 monetary diagnostic. Uses quarter-over-quarter changes in loaded H.6/H.8-style targets where present. "
        "Interpret as a sign/magnitude cross-check, not a replacement estimator."
    )

    frame = frame.loc[frame.index >= pd.Timestamp(start)].copy()
    frame = frame.dropna(
        subset=[
            "delta_partial_m2_less_currency_level_mil",
            "delta_depository_target_level_mil",
            "delta_liquid_deposit_target_level_mil",
            "delta_commercial_bank_deposits_level_mil",
        ],
        how="all",
    )
    return frame


def render_monetary_stage0_diagnostics_markdown(diagnostics: pd.DataFrame) -> str:
    title = "# Monetary Stage 0 Diagnostics"
    intro = (
        "Monetary cross-check around the TDC ladder. "
        "This artifact is not a headline estimator. It compares quarter-over-quarter changes in available "
        "deposit-style targets against Tier 0, Tier 2, and Tier 3."
    )
    if diagnostics.empty:
        return "\n".join([title, "", intro, "", "No monetary Stage 0 diagnostics are available."])

    latest_date = diagnostics.index.max()
    latest = diagnostics.loc[latest_date]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Partial target change {_format_millions(latest.get('delta_partial_m2_less_currency_level_mil'))}; "
        f"depository target change {_format_millions(latest.get('delta_depository_target_level_mil'))}; "
        f"liquid target change {_format_millions(latest.get('delta_liquid_deposit_target_level_mil'))}; "
        f"commercial-bank-deposit change {_format_millions(latest.get('delta_commercial_bank_deposits_level_mil'))}; "
        f"credit-union-deposit change {_format_millions(latest.get('delta_credit_union_deposits_level_mil'))}; "
        f"thrift-deposit change {_format_millions(latest.get('delta_thrift_deposits_level_mil'))}; "
        f"nonbank-depository-bridge change {_format_millions(latest.get('delta_nonbank_depository_bridge_level_mil'))}; "
        f"large-time-deposit change {_format_millions(latest.get('delta_large_time_deposits_all_commercial_banks_level_mil'))}; "
        f"other-deposits change {_format_millions(latest.get('delta_other_deposits_all_commercial_banks_level_mil'))}; "
        f"Tier 0 {_format_millions(latest.get('tier0_bank_only_flow_mil'))}; "
        f"Tier 2 {_format_millions(latest.get('tier2_bank_only_flow_mil'))}; "
        f"Tier 3 {_format_millions(latest.get('tier3_bank_only_flow_mil'))}; "
        f"bank-credit change {_format_millions(latest.get('delta_bank_credit_level_mil'))}."
    )

    header = [
        "| Quarter | Partial target | Depository target | Liquid target | Bank-deposit target | Credit-union deposits | Thrift deposits | Nonbank depository bridge | Large-time deposits | Other deposits | Tier 0 | Tier 2 | Tier 3 | Depository gap vs Tier 3 | Bank-deposit gap vs Tier 3 | Bank-credit change |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows: list[str] = []
    for date, row in diagnostics.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    _format_millions(row.get("delta_partial_m2_less_currency_level_mil")),
                    _format_millions(row.get("delta_depository_target_level_mil")),
                    _format_millions(row.get("delta_liquid_deposit_target_level_mil")),
                    _format_millions(row.get("delta_commercial_bank_deposits_level_mil")),
                    _format_millions(row.get("delta_credit_union_deposits_level_mil")),
                    _format_millions(row.get("delta_thrift_deposits_level_mil")),
                    _format_millions(row.get("delta_nonbank_depository_bridge_level_mil")),
                    _format_millions(row.get("delta_large_time_deposits_all_commercial_banks_level_mil")),
                    _format_millions(row.get("delta_other_deposits_all_commercial_banks_level_mil")),
                    _format_millions(row.get("tier0_bank_only_flow_mil")),
                    _format_millions(row.get("tier2_bank_only_flow_mil")),
                    _format_millions(row.get("tier3_bank_only_flow_mil")),
                    _format_millions(row.get("depository_target_minus_tier3_bank_only_flow_mil")),
                    _format_millions(row.get("commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil")),
                    _format_millions(row.get("delta_bank_credit_level_mil")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `Partial target` = `M2 - currency`.",
        "- `Depository target` = `M2 - currency - retail money market funds` when the retail MMF series is loaded.",
        "- `Liquid target` = `M2 - currency - retail money market funds - small time deposits` when both component series are loaded.",
        "- `Bank-deposit target` uses all commercial bank deposits when that series is loaded.",
        "- `Credit-union deposits` is a bridge-side context term from NCUA Call Report `Acct_018` totals for federally insured credit unions when that series is loaded.",
        "- `Thrift deposits` is the bridge-side context term from the FDIC banks financial API for BKCLASS `SB`, `SI`, and `SL` when that series is loaded.",
        "- `Nonbank depository bridge` is the simple sum of the loaded credit-union and thrift bridge sides.",
        "- `Large-time deposits` is shown as a loaded H.8 bank-liability context term when available; it is not yet a headline target.",
        "- `Other deposits` is the loaded seasonally adjusted H.8 other-deposits bank-liability context term. It is broader than a clean bank-only liquid subcomponent and is shown as context only.",
        "- Use this as a sign and magnitude check on the ladder, not as a replacement estimator.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_stage0_diagnostics(
    *,
    quarterly: pd.DataFrame,
    estimates: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = DEFAULT_START,
) -> tuple[Path, Path, pd.DataFrame]:
    diagnostics = build_monetary_stage0_diagnostics(quarterly, estimates, start=start)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = diagnostics.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_stage0_diagnostics_markdown(diagnostics), encoding="utf-8")

    return csv_path, markdown_path, diagnostics
