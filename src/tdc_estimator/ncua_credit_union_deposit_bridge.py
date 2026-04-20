from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_ncua_credit_union_deposit_bridge(
    raw_bridge: pd.DataFrame | None,
    quarterly: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if raw_bridge is None or raw_bridge.empty:
        return pd.DataFrame()

    frame = raw_bridge.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    numeric_cols = [col for col in frame.columns if col != "source_zip_url" and col != "source_zip_file"]
    for col in numeric_cols:
        if col == "date":
            continue
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    if quarterly is not None and not quarterly.empty and "commercial_bank_deposits" in quarterly.columns:
        bank_levels = pd.to_numeric(quarterly["commercial_bank_deposits"], errors="coerce").rename("commercial_bank_deposits")
        joined = frame.set_index("date").join(bank_levels, how="left")
        joined["commercial_bank_deposits_level_mil"] = joined["commercial_bank_deposits"] * 1000.0
        joined["federally_insured_credit_union_to_bank_deposit_ratio"] = (
            joined["federally_insured_credit_union_shares_and_deposits_mil"]
            / joined["commercial_bank_deposits_level_mil"]
        )
        frame = joined.reset_index().drop(columns=["commercial_bank_deposits"])
    else:
        frame["commercial_bank_deposits_level_mil"] = pd.NA
        frame["federally_insured_credit_union_to_bank_deposit_ratio"] = pd.NA

    return frame.sort_values("date").reset_index(drop=True)


def render_ncua_credit_union_deposit_bridge_markdown(bridge: pd.DataFrame) -> str:
    title = "# NCUA Credit Union Deposit Bridge"
    intro = (
        "Quarterly credit-union bridge built from NCUA final Call Report ZIP files. "
        "This is the credit-union side of the broader bank-versus-broad-depository bridge. "
        "It does not by itself close the thrift or savings-institution gap."
    )
    if bridge.empty:
        return "\n".join([title, "", intro, "", "No NCUA credit-union bridge is available."])

    latest = bridge.iloc[-1]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Federally insured credit-union shares and deposits {_format_millions(latest.get('federally_insured_credit_union_shares_and_deposits_mil'))}; "
        f"all credit-union shares and deposits {_format_millions(latest.get('total_credit_union_shares_and_deposits_mil'))}; "
        f"implied federally insured nonmember deposits {_format_millions(latest.get('federally_insured_credit_union_implied_nonmember_deposits_mil'))}; "
        f"federally insured credit unions {int(latest.get('federally_insured_credit_union_count') or 0):,}; "
        f"credit-union-to-bank-deposit ratio {_format_millions(pd.to_numeric(latest.get('federally_insured_credit_union_to_bank_deposit_ratio'), errors='coerce') * 100 if pd.notna(latest.get('federally_insured_credit_union_to_bank_deposit_ratio')) else pd.NA)}%."
    )
    header = [
        "| Quarter | Federally insured CU shares and deposits | All CU shares and deposits | Federally insured member shares | Federally insured implied nonmember deposits | Federally insured CU count | Nonfederally insured CU count | Commercial-bank deposits | CU to bank ratio | Source ZIP |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    rows: list[str] = []
    for _, row in bridge.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    _format_millions(row.get("federally_insured_credit_union_shares_and_deposits_mil")),
                    _format_millions(row.get("total_credit_union_shares_and_deposits_mil")),
                    _format_millions(row.get("federally_insured_credit_union_member_shares_mil")),
                    _format_millions(row.get("federally_insured_credit_union_implied_nonmember_deposits_mil")),
                    f"{int(pd.to_numeric(row.get('federally_insured_credit_union_count'), errors='coerce') or 0):,}",
                    f"{int(pd.to_numeric(row.get('nonfederally_insured_credit_union_count'), errors='coerce') or 0):,}",
                    _format_millions(row.get("commercial_bank_deposits_level_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("federally_insured_credit_union_to_bank_deposit_ratio"), errors="coerce") * 100
                        if pd.notna(row.get("federally_insured_credit_union_to_bank_deposit_ratio"))
                        else pd.NA
                    ),
                    str(row.get("source_zip_file")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- Support series `credit_union_deposits` is sourced from federally insured credit-union `Acct_018` totals in the NCUA ZIPs.",
        "- `Acct_013` is total member shares; implied nonmember deposits are calculated as `Acct_018 - Acct_013`.",
        "- This is a partial bridge. FDIC-insured savings institutions are still required to complete the bank-versus-broad-depository side.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_ncua_credit_union_deposit_bridge(
    *,
    raw_bridge_path: Path | str,
    quarterly: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    raw_bridge = pd.read_csv(raw_bridge_path)
    bridge = build_ncua_credit_union_deposit_bridge(raw_bridge=raw_bridge, quarterly=quarterly)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    bridge.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_ncua_credit_union_deposit_bridge_markdown(bridge), encoding="utf-8")
    return csv_path, markdown_path, bridge
