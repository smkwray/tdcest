from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_fdic_savings_institution_deposit_bridge(
    raw_bridge: pd.DataFrame | None,
    quarterly: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if raw_bridge is None or raw_bridge.empty:
        return pd.DataFrame()

    frame = raw_bridge.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    numeric_cols = [col for col in frame.columns if col not in {"source_api_url", "source_cache_file"}]
    for col in numeric_cols:
        if col == "date":
            continue
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    if quarterly is not None and not quarterly.empty:
        joined = frame.set_index("date")
        if "commercial_bank_deposits" in quarterly.columns:
            bank_levels = pd.to_numeric(quarterly["commercial_bank_deposits"], errors="coerce").rename("commercial_bank_deposits")
            joined = joined.join(bank_levels, how="left")
            joined["commercial_bank_deposits_level_mil"] = joined["commercial_bank_deposits"] * 1000.0
            joined["savings_institution_to_bank_deposit_ratio"] = (
                joined["total_savings_institution_deposits_mil"] / joined["commercial_bank_deposits_level_mil"]
            )
            joined = joined.drop(columns=["commercial_bank_deposits"])
        else:
            joined["commercial_bank_deposits_level_mil"] = pd.NA
            joined["savings_institution_to_bank_deposit_ratio"] = pd.NA
        if "credit_union_deposits" in quarterly.columns:
            cu_levels = pd.to_numeric(quarterly["credit_union_deposits"], errors="coerce").rename("credit_union_deposits")
            joined = joined.join(cu_levels, how="left")
            joined["credit_union_deposits_level_mil"] = joined["credit_union_deposits"]
            joined["nonbank_depository_bridge_level_mil"] = (
                joined["total_savings_institution_deposits_mil"] + joined["credit_union_deposits_level_mil"]
            )
            if "commercial_bank_deposits_level_mil" in joined.columns:
                joined["nonbank_depository_bridge_to_bank_deposit_ratio"] = (
                    joined["nonbank_depository_bridge_level_mil"] / joined["commercial_bank_deposits_level_mil"]
                )
            joined = joined.drop(columns=["credit_union_deposits"])
        else:
            joined["credit_union_deposits_level_mil"] = pd.NA
            joined["nonbank_depository_bridge_level_mil"] = pd.NA
            joined["nonbank_depository_bridge_to_bank_deposit_ratio"] = pd.NA
        frame = joined.reset_index()
    else:
        frame["commercial_bank_deposits_level_mil"] = pd.NA
        frame["savings_institution_to_bank_deposit_ratio"] = pd.NA
        frame["credit_union_deposits_level_mil"] = pd.NA
        frame["nonbank_depository_bridge_level_mil"] = pd.NA
        frame["nonbank_depository_bridge_to_bank_deposit_ratio"] = pd.NA

    return frame.sort_values("date").reset_index(drop=True)


def render_fdic_savings_institution_deposit_bridge_markdown(bridge: pd.DataFrame) -> str:
    title = "# FDIC Savings Institution Deposit Bridge"
    intro = (
        "Quarterly savings-institution bridge built from the public FDIC banks financial API. "
        "This is the thrift or savings-institution side of the broader bank-versus-broad-depository bridge."
    )
    if bridge.empty:
        return "\n".join([title, "", intro, "", "No FDIC savings-institution bridge is available."])

    latest = bridge.iloc[-1]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Total savings-institution deposits {_format_millions(latest.get('total_savings_institution_deposits_mil'))}; "
        f"federal savings banks {_format_millions(latest.get('federal_savings_bank_deposits_mil'))}; "
        f"state savings banks {_format_millions(latest.get('state_savings_bank_deposits_mil'))}; "
        f"state savings and loans {_format_millions(latest.get('state_savings_and_loan_deposits_mil'))}; "
        f"savings-institution-to-bank-deposit ratio {_format_millions(pd.to_numeric(latest.get('savings_institution_to_bank_deposit_ratio'), errors='coerce') * 100 if pd.notna(latest.get('savings_institution_to_bank_deposit_ratio')) else pd.NA)}%; "
        f"nonbank-depository-bridge-to-bank-deposit ratio {_format_millions(pd.to_numeric(latest.get('nonbank_depository_bridge_to_bank_deposit_ratio'), errors='coerce') * 100 if pd.notna(latest.get('nonbank_depository_bridge_to_bank_deposit_ratio')) else pd.NA)}%."
    )
    header = [
        "| Quarter | Total savings-institution deposits | Federal savings banks | State savings banks | State savings and loans | Savings-institution count | Commercial-bank deposits | Credit-union deposits | Nonbank depository bridge | Savings-to-bank ratio | Nonbank bridge to bank ratio | Source cache |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    rows: list[str] = []
    for _, row in bridge.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    _format_millions(row.get("total_savings_institution_deposits_mil")),
                    _format_millions(row.get("federal_savings_bank_deposits_mil")),
                    _format_millions(row.get("state_savings_bank_deposits_mil")),
                    _format_millions(row.get("state_savings_and_loan_deposits_mil")),
                    f"{int(pd.to_numeric(row.get('total_savings_institution_count'), errors='coerce') or 0):,}",
                    _format_millions(row.get("commercial_bank_deposits_level_mil")),
                    _format_millions(row.get("credit_union_deposits_level_mil")),
                    _format_millions(row.get("nonbank_depository_bridge_level_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("savings_institution_to_bank_deposit_ratio"), errors="coerce") * 100
                        if pd.notna(row.get("savings_institution_to_bank_deposit_ratio"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("nonbank_depository_bridge_to_bank_deposit_ratio"), errors="coerce") * 100
                        if pd.notna(row.get("nonbank_depository_bridge_to_bank_deposit_ratio"))
                        else pd.NA
                    ),
                    str(row.get("source_cache_file")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- Support series `thrift_deposits` is sourced from FDIC `DEP` totals for BKCLASS `SB`, `SI`, and `SL`.",
        "- `DEP` is treated as thousands of dollars in the FDIC API and converted here to millions of dollars.",
        "- With both the FDIC thrift bridge and the NCUA credit-union bridge present, the repo can make the nonbank depository side explicit in the perimeter diagnostics.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_fdic_savings_institution_deposit_bridge(
    *,
    raw_bridge_path: Path | str,
    quarterly: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    raw_bridge = pd.read_csv(raw_bridge_path)
    bridge = build_fdic_savings_institution_deposit_bridge(raw_bridge=raw_bridge, quarterly=quarterly)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    bridge.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_fdic_savings_institution_deposit_bridge_markdown(bridge), encoding="utf-8")
    return csv_path, markdown_path, bridge
