from __future__ import annotations

from pathlib import Path

import pandas as pd


OCC_PATTERNS = [
    r"comptroller of currency",
    r"comptroller of the currency",
]

OFR_PATTERNS = [
    r"financial research fund",
]

FDIC_PATTERNS = [
    r"federal deposit insurance corporation",
    r"\bfdic\b",
]


def _match_bucket(title: str) -> str | None:
    title = title or ""
    checks = [
        ("occ_candidate", OCC_PATTERNS),
        ("ofr_candidate", OFR_PATTERNS),
        ("fdic_or_other_bank_regulatory_candidate", FDIC_PATTERNS),
    ]
    for bucket, patterns in checks:
        for pattern in patterns:
            if pd.Series([title]).str.contains(pattern, case=False, regex=True, na=False).iloc[0]:
                return bucket
    return None


def _bucket_note(bucket: str) -> str:
    notes = {
        "occ_candidate": (
            "OCC-specific bank-regulatory receipt line. Strong bank-sector linkage, but still annual account-level evidence without public quarterly cash timing."
        ),
        "ofr_candidate": (
            "Financial Research Fund line. Useful for large-BHC sensitivity work, but not broad bank-sector default coverage."
        ),
        "fdic_or_other_bank_regulatory_candidate": (
            "Depository-regulatory or resolution-linked line. Worth keeping visible as a bank non-tax sensitivity, but still mixed and annual at the public account-title level."
        ),
    }
    return notes[bucket]


def build_bank_nontax_regulatory_pilot(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates is None or candidates.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    sub = candidates.loc[candidates["counterparty_group"].eq("bank")].copy()
    for _, row in sub.iterrows():
        title = str(row["receipt_line_item_nm"])
        bucket = _match_bucket(title)
        if bucket is None:
            continue
        rows.append(
            {
                "date": pd.Timestamp(row["date"]),
                "fiscal_year": int(row["fiscal_year"]),
                "receipt_line_item_nm": title,
                "receipt_amt_mil": float(row["receipt_amt_mil"]),
                "pilot_bucket": bucket,
                "default_eligible": False,
                "note": _bucket_note(bucket),
            }
        )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out = (
        out.groupby(
            ["date", "fiscal_year", "receipt_line_item_nm", "pilot_bucket", "default_eligible", "note"],
            dropna=False,
            as_index=False,
        )["receipt_amt_mil"]
        .sum()
        .sort_values(["date", "pilot_bucket", "receipt_amt_mil", "receipt_line_item_nm"], ascending=[False, True, False, True])
        .reset_index(drop=True)
    )
    return out


def render_bank_nontax_regulatory_pilot_markdown(pilot: pd.DataFrame) -> str:
    title = "# Bank Non-Tax Regulatory Pilot"
    intro = (
        "Annual bank non-tax pilot intake from the public `Receipts by Department` account surface. "
        "Amounts are in millions. This artifact is for bank non-tax sensitivity scoping only and does not promote any line into the default Tier 3 correction."
    )
    if pilot.empty:
        return "\n".join([title, "", intro, "", "No OCC, OFR, or other bank-regulatory pilot lines matched the current rules."])

    latest_date = pd.Timestamp(pilot["date"].max())
    latest = pilot.loc[pilot["date"].eq(latest_date)].copy()
    occ_total = latest.loc[latest["pilot_bucket"].eq("occ_candidate"), "receipt_amt_mil"].sum()
    ofr_total = latest.loc[latest["pilot_bucket"].eq("ofr_candidate"), "receipt_amt_mil"].sum()
    other_total = latest.loc[
        latest["pilot_bucket"].eq("fdic_or_other_bank_regulatory_candidate"), "receipt_amt_mil"
    ].sum()
    summary = (
        f"Latest fiscal year-end in view: {latest_date.date().isoformat()}. "
        f"OCC-linked pilot lines total {occ_total:,.3f} million; "
        f"OFR-linked pilot lines total {ofr_total:,.3f} million; "
        f"other bank-regulatory pilot lines total {other_total:,.3f} million."
    )

    header = [
        "| Fiscal year-end | Receipt line item | Amount (mil) | Pilot bucket | Default eligible |",
        "| --- | --- | ---: | --- | --- |",
    ]
    rows = []
    for _, row in latest.sort_values(["pilot_bucket", "receipt_amt_mil"], ascending=[True, False]).iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    str(row["receipt_line_item_nm"]),
                    f"{float(row['receipt_amt_mil']):,.3f}",
                    str(row["pilot_bucket"]),
                    "yes" if bool(row["default_eligible"]) else "no",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `occ_candidate` is the strongest current public bank non-tax line family, but it still needs quarterly timing and budget-treatment work before any default use.",
        "- `ofr_candidate` is best treated as a large-BHC sensitivity rather than broad bank coverage.",
        "- Other bank-regulatory lines remain visible so the project can decide later whether to keep them as sensitivities or reject them entirely.",
    ]

    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_bank_nontax_regulatory_pilot(
    candidates: pd.DataFrame,
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    pilot = build_bank_nontax_regulatory_pilot(candidates)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pilot.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bank_nontax_regulatory_pilot_markdown(pilot), encoding="utf-8")

    return csv_path, markdown_path, pilot
