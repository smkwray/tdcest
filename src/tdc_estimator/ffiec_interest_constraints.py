from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


RCB_FIELD_MAP = {
    "treasury_htm_amortized_cost": ["RCFD0211", "RCON0211"],
    "treasury_htm_fair_value": ["RCFD0213", "RCON0213"],
    "treasury_afs_amortized_cost": ["RCFD1286", "RCON1286"],
    "treasury_afs_fair_value": ["RCFD1287", "RCON1287"],
    "treasury_bucket_3m_or_less": ["RCFDA549", "RCONA549"],
    "treasury_bucket_3_12m": ["RCFDA550", "RCONA550"],
    "treasury_bucket_1_3y": ["RCFDA551", "RCONA551"],
    "treasury_bucket_3_5y": ["RCFDA552", "RCONA552"],
    "treasury_bucket_5_15y": ["RCFDA553", "RCONA553"],
    "treasury_bucket_over_15y": ["RCFDA554", "RCONA554"],
}
DATE_TOKEN = re.compile(r"(\d{8})")


def _report_date(path: Path) -> pd.Timestamp:
    for token in DATE_TOKEN.findall(str(path)):
        try:
            return pd.to_datetime(token, format="%m%d%Y").normalize()
        except ValueError:
            continue
    raise ValueError(f"Could not infer report date from {path}")


def _read_rcb(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype=str, low_memory=False)
    df.columns = [str(col).strip().strip('"') for col in df.columns]
    if "IDRSSD" not in df.columns:
        raise ValueError(f"RCB file is missing IDRSSD: {path}")
    df = df.loc[df["IDRSSD"].astype(str).str.fullmatch(r"\d+", na=False)].copy()
    return df.drop_duplicates(subset=["IDRSSD"], keep="first")


def _merge_rcb_files(paths: list[Path]) -> pd.DataFrame:
    merged: pd.DataFrame | None = None
    for path in paths:
        current = _read_rcb(path)
        if merged is None:
            merged = current
            continue
        keep = ["IDRSSD", *[col for col in current.columns if col not in merged.columns]]
        merged = merged.merge(current[keep], on="IDRSSD", how="outer")
    return merged if merged is not None else pd.DataFrame()


def _coalesce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    out = pd.Series(pd.NA, index=df.index, dtype="object")
    for column in columns:
        if column not in df.columns:
            continue
        values = df[column].replace({"": pd.NA})
        out = out.where(out.notna(), values)
    return pd.to_numeric(out, errors="coerce").fillna(0.0)


def normalize_ffiec_interest_constraints_from_extracted_root(root: Path | str) -> pd.DataFrame:
    root = Path(root)
    rows: list[pd.DataFrame] = []
    for extracted in sorted(root.glob("*/extracted")):
        rcb_files = sorted(extracted.glob("*Schedule RCB*.txt"))
        if not rcb_files:
            continue
        report_date = _report_date(rcb_files[0])
        merged = _merge_rcb_files(rcb_files)
        if merged.empty:
            continue
        out = pd.DataFrame(
            {
                "date": report_date,
                "reporter_id": merged["IDRSSD"].astype(str),
                "bank_class": "all_commercial_banks",
                "provider": "ffiec",
                "dataset": "ffiec_call_reports",
                "raw_file": ";".join(path.name for path in rcb_files),
            }
        )
        for output, candidates in RCB_FIELD_MAP.items():
            out[output] = _coalesce_numeric(merged, candidates)
        out["total_treasuries_amortized_cost"] = out[
            ["treasury_htm_amortized_cost", "treasury_afs_amortized_cost"]
        ].sum(axis=1)
        out["total_treasuries_fair_value"] = out[["treasury_htm_fair_value", "treasury_afs_fair_value"]].sum(axis=1)
        bucket_cols = [
            "treasury_bucket_3m_or_less",
            "treasury_bucket_3_12m",
            "treasury_bucket_1_3y",
            "treasury_bucket_3_5y",
            "treasury_bucket_5_15y",
            "treasury_bucket_over_15y",
        ]
        out["treasury_ladder_total"] = out[bucket_cols].sum(axis=1)
        out["treasury_short_share_le_1y"] = (
            out[["treasury_bucket_3m_or_less", "treasury_bucket_3_12m"]].sum(axis=1) / out["treasury_ladder_total"]
        ).where(out["treasury_ladder_total"].ne(0))
        out["treasury_bill_share_proxy_3m_or_less"] = (
            out["treasury_bucket_3m_or_less"] / out["treasury_ladder_total"]
        ).where(out["treasury_ladder_total"].ne(0))
        rows.append(out)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(["date", "reporter_id"]).reset_index(drop=True)


def write_ffiec_interest_constraints_from_extracted_root(
    *,
    extracted_root: Path | str,
    out_path: Path | str,
) -> tuple[Path, pd.DataFrame]:
    out = normalize_ffiec_interest_constraints_from_extracted_root(extracted_root)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return path, out
