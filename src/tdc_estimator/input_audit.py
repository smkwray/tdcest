from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


AUDIT_SERIES_CONFIG: dict[str, dict[str, str]] = {
    "fed_tsy_tx": {
        "native_frequency": "Quarterly",
        "source_unit": "Millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly transaction flow.",
        "series_group": "tier0_base",
    },
    "us_chartered_tsy_tx": {
        "native_frequency": "Quarterly",
        "source_unit": "Millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly transaction flow.",
        "series_group": "tier0_base",
    },
    "foreign_offices_tsy_tx": {
        "native_frequency": "Quarterly",
        "source_unit": "Millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly transaction flow.",
        "series_group": "tier0_base",
    },
    "affiliated_areas_tsy_tx": {
        "native_frequency": "Quarterly",
        "source_unit": "Millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly transaction flow.",
        "series_group": "tier0_base",
    },
    "row_tsy_tx": {
        "native_frequency": "Quarterly",
        "source_unit": "Millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly transaction flow.",
        "series_group": "tier0_base",
    },
    "treasury_operating_cash_tx": {
        "native_frequency": "Quarterly",
        "source_unit": "Millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly transaction flow and enters with a negative sign in the estimator.",
        "series_group": "tier0_base",
    },
    "fed_remit_or_deferred": {
        "native_frequency": "Weekly level",
        "source_unit": "Millions of U.S. dollars",
        "estimator_conversion": "Negative values are clipped to zero, then weekly positives are summed to quarterly flow equivalents.",
        "series_group": "tier0_base",
    },
    "fed_tsy_coupon_interest_proxy": {
        "native_frequency": "Quarterly support file",
        "source_unit": "Intended to be millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly flow support series after SOMA par values are normalized to millions.",
        "series_group": "tier1_coupon",
    },
    "bank_tsy_coupon_interest_proxy": {
        "native_frequency": "Quarterly support file",
        "source_unit": "Intended to be millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly flow support series. Builder assumes holdings levels and curve yields are already scaled to estimator units.",
        "series_group": "tier2_coupon",
    },
    "row_tsy_coupon_interest_proxy": {
        "native_frequency": "Quarterly support file",
        "source_unit": "Intended to be millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly flow support series. Benchmark against BEA/FRED ROW federal interest after converting SAAR to quarterly flow.",
        "series_group": "tier2_coupon",
    },
    "bank_noninterest_outlay_proxy": {
        "native_frequency": "Quarterly support file",
        "source_unit": "Intended to be millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly flow support series and subtracted in Tier 3.",
        "series_group": "tier3_fiscal",
    },
    "row_noninterest_outlay_proxy": {
        "native_frequency": "Quarterly support file",
        "source_unit": "Intended to be millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly flow support series and subtracted in Tier 3.",
        "series_group": "tier3_fiscal",
    },
    "bank_nonborrow_receipt_proxy": {
        "native_frequency": "Quarterly support file",
        "source_unit": "Intended to be millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly flow support series and added in Tier 3.",
        "series_group": "tier3_fiscal",
    },
    "row_nonborrow_receipt_proxy": {
        "native_frequency": "Quarterly support file",
        "source_unit": "Intended to be millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly flow support series and added in Tier 3.",
        "series_group": "tier3_fiscal",
    },
    "mint_cb_cash_factor_proxy": {
        "native_frequency": "Quarterly support file",
        "source_unit": "Intended to be millions of U.S. dollars",
        "estimator_conversion": "Used directly as a quarterly flow support series and added in Tier 3.",
        "series_group": "tier3_fiscal",
    },
    "bea_row_fed_interest_paid_saar": {
        "native_frequency": "Quarterly SAAR",
        "source_unit": "Billions of U.S. dollars SAAR",
        "estimator_conversion": "Benchmark only. Divide SAAR by 4 to get quarterly billions, then multiply by 1,000 to compare with estimator-scale millions.",
        "series_group": "benchmark",
    },
}

AUDIT_SERIES_ORDER = [
    "fed_tsy_tx",
    "us_chartered_tsy_tx",
    "foreign_offices_tsy_tx",
    "affiliated_areas_tsy_tx",
    "row_tsy_tx",
    "treasury_operating_cash_tx",
    "fed_remit_or_deferred",
    "fed_tsy_coupon_interest_proxy",
    "bank_tsy_coupon_interest_proxy",
    "row_tsy_coupon_interest_proxy",
    "bank_noninterest_outlay_proxy",
    "row_noninterest_outlay_proxy",
    "bank_nonborrow_receipt_proxy",
    "row_nonborrow_receipt_proxy",
    "mint_cb_cash_factor_proxy",
    "bea_row_fed_interest_paid_saar",
]


def _maybe(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(index=df.index, dtype="float64")


def _format_number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _latest_non_null(series: pd.Series) -> tuple[pd.Timestamp | None, float | None]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None, None
    return pd.Timestamp(clean.index.max()), float(clean.loc[clean.index.max()])


def _build_row_coupon_benchmark_check(quarterly: pd.DataFrame) -> dict[str, Any]:
    if "row_tsy_coupon_interest_proxy" not in quarterly.columns or "bea_row_fed_interest_paid_saar" not in quarterly.columns:
        return {
            "benchmark_available": False,
            "audit_status": "benchmark_unavailable",
            "audit_note": "BEA/FRED ROW federal-interest benchmark is not loaded, so the ROW coupon unit check cannot run.",
        }

    proxy = _maybe(quarterly, "row_tsy_coupon_interest_proxy")
    benchmark_saar = _maybe(quarterly, "bea_row_fed_interest_paid_saar")
    benchmark_quarterly_millions = benchmark_saar * 250.0
    overlap = pd.DataFrame(
        {
            "proxy": pd.to_numeric(proxy, errors="coerce"),
            "benchmark_quarterly_millions": pd.to_numeric(benchmark_quarterly_millions, errors="coerce"),
        }
    ).dropna()
    overlap = overlap[overlap["benchmark_quarterly_millions"] > 0]
    if overlap.empty:
        return {
            "benchmark_available": True,
            "audit_status": "benchmark_empty",
            "audit_note": "BEA/FRED ROW benchmark is loaded, but there is no positive quarterly overlap with the ROW coupon proxy.",
        }

    latest_date = pd.Timestamp(overlap.index.max())
    latest = overlap.loc[latest_date]
    ratio = float(latest["proxy"] / latest["benchmark_quarterly_millions"])
    ratio_x1000 = ratio * 1000.0
    status = "ok"
    note = "ROW coupon proxy is broadly aligned with the BEA/FRED benchmark on the current estimator scale."
    if ratio <= 0.01 and 0.5 <= ratio_x1000 <= 1.5:
        status = "possible_x1000_mismatch"
        note = (
            "ROW coupon proxy is about 1/1000 of the BEA/FRED benchmark on the current estimator scale, "
            "while multiplying by 1,000 would bring it close to the benchmark. This suggests a possible billions-versus-millions mismatch."
        )
    elif ratio < 0.5 or ratio > 1.5:
        status = "benchmark_gap"
        note = "ROW coupon proxy differs materially from the BEA/FRED benchmark even after ordinary quarterly conversion assumptions."

    return {
        "benchmark_available": True,
        "benchmark_key": "bea_row_fed_interest_paid_saar",
        "benchmark_date": latest_date,
        "benchmark_quarterly_millions": float(latest["benchmark_quarterly_millions"]),
        "ratio_to_benchmark": ratio,
        "ratio_if_x1000": ratio_x1000,
        "audit_status": status,
        "audit_note": note,
    }


def build_input_audit(quarterly: pd.DataFrame, series_meta: dict[str, Any]) -> pd.DataFrame:
    row_coupon_check = _build_row_coupon_benchmark_check(quarterly)
    rows: list[dict[str, Any]] = []

    for key in AUDIT_SERIES_ORDER:
        if key not in quarterly.columns:
            continue
        config = AUDIT_SERIES_CONFIG.get(key, {})
        meta = series_meta.get(key, {})
        latest_date, latest_value = _latest_non_null(_maybe(quarterly, key))
        row: dict[str, Any] = {
            "series_key": key,
            "series_group": config.get("series_group"),
            "source_kind": meta.get("source_kind"),
            "raw_filename": meta.get("raw_filename"),
            "native_frequency": config.get("native_frequency"),
            "source_unit": config.get("source_unit"),
            "estimator_target_unit": "Millions of U.S. dollars",
            "estimator_target_frequency": "Quarterly flow",
            "estimator_conversion": config.get("estimator_conversion"),
            "latest_date": latest_date.date().isoformat() if latest_date is not None else None,
            "latest_value": latest_value,
            "max_abs_value": float(pd.to_numeric(_maybe(quarterly, key), errors="coerce").abs().max()),
            "audit_status": "ok",
            "audit_note": "",
            "benchmark_key": None,
            "benchmark_date": None,
            "benchmark_quarterly_millions": None,
            "ratio_to_benchmark": None,
            "ratio_if_x1000": None,
        }
        if key == "row_tsy_coupon_interest_proxy":
            row.update(row_coupon_check)
            if row.get("benchmark_date") is not None:
                row["benchmark_date"] = pd.Timestamp(row["benchmark_date"]).date().isoformat()
        elif key == "bank_tsy_coupon_interest_proxy" and row_coupon_check.get("audit_status") == "possible_x1000_mismatch":
            row["audit_status"] = "coupled_scale_risk"
            row["audit_note"] = (
                "Bank and ROW coupon proxies are built from the same sector-coupon engine family. "
                "The flagged ROW scale mismatch raises a coupled unit-risk warning for the bank coupon proxy as well."
            )
        rows.append(row)

    return pd.DataFrame(rows)


def render_input_audit_markdown(audit: pd.DataFrame) -> str:
    title = "# Input Unit And Frequency Audit"
    intro = (
        "Audit of the currently loaded Tier 0 through Tier 3 input series. "
        "The target estimator contract is quarterly flow in millions of U.S. dollars. "
        "This artifact records the assumed native frequency, unit treatment, and any benchmark-based warnings."
    )
    if audit.empty:
        return "\n".join([title, "", intro, "", "No loaded series were available for the audit."])

    flagged = audit[audit["audit_status"].isin(["possible_x1000_mismatch", "benchmark_gap", "coupled_scale_risk"])]
    latest_row_coupon = audit.loc[audit["series_key"].eq("row_tsy_coupon_interest_proxy")]
    summary_lines = []
    if not latest_row_coupon.empty:
        row = latest_row_coupon.iloc[0]
        summary_lines.append(
            "ROW coupon check: "
            f"status `{row['audit_status']}`; "
            f"latest proxy {_format_number(row.get('latest_value'))}; "
            f"benchmark quarterly millions {_format_number(row.get('benchmark_quarterly_millions'))}; "
            f"ratio {_format_number(row.get('ratio_to_benchmark'))}; "
            f"ratio if x1000 {_format_number(row.get('ratio_if_x1000'))}."
        )
        if row.get("audit_note"):
            summary_lines.append(str(row["audit_note"]))

    header = (
        "| Series | Group | Native frequency | Source unit | Latest value | Audit status | Benchmark ratio | Benchmark ratio if x1000 |\n"
        "| --- | --- | --- | --- | ---: | --- | ---: | ---: |"
    )
    rows: list[str] = []
    for _, row in audit.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row.get("series_key", "")),
                    str(row.get("series_group", "")),
                    str(row.get("native_frequency", "")),
                    str(row.get("source_unit", "")),
                    _format_number(row.get("latest_value")),
                    str(row.get("audit_status", "")),
                    _format_number(row.get("ratio_to_benchmark")),
                    _format_number(row.get("ratio_if_x1000")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `benchmark_unavailable` means the audit logic exists, but the relevant benchmark series is not loaded in the current raw bundle.",
        "- `possible_x1000_mismatch` means the live scale is close to 1/1000 of the benchmark while a simple x1000 adjustment would bring it near the benchmark.",
        "- `coupled_scale_risk` means there is no direct benchmark in this artifact, but the series is produced by the same builder family and unit assumptions as a flagged benchmarked series.",
        "- This audit is a contract check, not a proof that any proxy is conceptually complete.",
    ]
    if not flagged.empty:
        notes.append(
            "- Flagged series currently make Tier 2 and Tier 3 numerical magnitudes provisional until the scale issue is resolved."
        )

    return "\n".join([title, "", intro, "", *summary_lines, "", header, *rows, "", *notes, ""])


def write_input_audit(
    quarterly: pd.DataFrame,
    series_meta: dict[str, Any],
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    audit = build_input_audit(quarterly, series_meta)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_input_audit_markdown(audit), encoding="utf-8")

    return csv_path, markdown_path, audit
