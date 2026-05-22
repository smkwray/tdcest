from __future__ import annotations

import json
from pathlib import Path
import urllib.parse
import urllib.request

import pandas as pd

from .config import USER_AGENT

NYFED_REVERSE_REPO_PROPOSITIONS_URL = "https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json"


def _positive(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(lower=0.0)


def nyfed_reverse_repo_propositions_url(*, start: str, end: str) -> str:
    params = urllib.parse.urlencode({"startDate": str(start), "endDate": str(end)})
    return f"{NYFED_REVERSE_REPO_PROPOSITIONS_URL}?{params}"


def load_nyfed_reverse_repo_propositions(*, start: str, end: str, timeout: int = 120) -> dict:
    url = nyfed_reverse_repo_propositions_url(start=start, end=end)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_nyfed_reverse_repo_propositions(payload: dict) -> pd.DataFrame:
    operations = payload.get("repo", {}).get("operations", [])
    rows: list[dict[str, object]] = []
    for operation in operations:
        date = pd.to_datetime(operation.get("operationDate"), errors="coerce")
        if pd.isna(date):
            continue
        row: dict[str, object] = {
            "date": date,
            "total_on_rrp": float(operation.get("totalAmtAccepted") or 0.0) / 1_000_000.0,
        }
        for proposition in operation.get("propositions", []) or []:
            counterparty_type = str(proposition.get("counterpartyType") or "").lower().strip()
            if counterparty_type:
                row[f"{counterparty_type}_on_rrp"] = float(proposition.get("amtAccepted") or 0.0) / 1_000_000.0
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["date", "value", "gse_on_rrp", "mmf_on_rrp", "bank_on_rrp", "pd_on_rrp", "total_on_rrp"])

    frame = pd.DataFrame(rows).sort_values("date")
    for col in ("gse_on_rrp", "mmf_on_rrp", "bank_on_rrp", "pd_on_rrp", "total_on_rrp"):
        if col not in frame.columns:
            frame[col] = 0.0
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    frame["value"] = frame["gse_on_rrp"]
    return frame[["date", "value", "gse_on_rrp", "mmf_on_rrp", "bank_on_rrp", "pd_on_rrp", "total_on_rrp"]].reset_index(drop=True)


def write_gse_on_rrp_support(
    *,
    out_path: Path | str,
    start: str,
    end: str,
    raw_json_path: Path | str | None = None,
    timeout: int = 120,
) -> Path:
    payload = load_nyfed_reverse_repo_propositions(start=start, end=end, timeout=timeout)
    if raw_json_path is not None:
        raw_target = Path(raw_json_path)
        raw_target.parent.mkdir(parents=True, exist_ok=True)
        raw_target.write_text(json.dumps(payload), encoding="utf-8")
    support = normalize_nyfed_reverse_repo_propositions(payload)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    support.to_csv(target, index=False)
    return target


def build_gse_rrp_boundary_check(quarterly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    required = {"gse_tsy_tx", "gse_on_rrp"}
    missing = sorted(required - set(quarterly.columns))
    if missing:
        return pd.DataFrame(
            [
                {
                    "date": pd.NaT,
                    "status": "missing_inputs",
                    "gse_tsy_tx": pd.NA,
                    "gse_on_rrp": pd.NA,
                    "gse_on_rrp_runoff": pd.NA,
                    "gse_treasury_increase": pd.NA,
                    "gse_rrp_boundary_adjustment": pd.NA,
                    "detail": f"Missing required columns: {', '.join(missing)}.",
                }
            ]
        )

    frame = quarterly[["gse_tsy_tx", "gse_on_rrp"]].copy()
    if "gse_tsy_level" in quarterly.columns:
        frame["gse_tsy_level"] = quarterly["gse_tsy_level"]
    frame = frame.dropna(subset=["gse_tsy_tx", "gse_on_rrp"], how="all").sort_index()
    if frame.empty:
        return pd.DataFrame(
            [
                {
                    "date": pd.NaT,
                    "status": "no_rows",
                    "gse_tsy_tx": pd.NA,
                    "gse_on_rrp": pd.NA,
                    "gse_on_rrp_runoff": pd.NA,
                    "gse_treasury_increase": pd.NA,
                    "gse_rrp_boundary_adjustment": pd.NA,
                    "detail": "GSE Treasury and GSE ON RRP inputs were present but empty.",
                }
            ]
        )

    gse_on_rrp = pd.to_numeric(frame["gse_on_rrp"], errors="coerce")
    gse_tsy_tx = pd.to_numeric(frame["gse_tsy_tx"], errors="coerce")
    if "gse_tsy_level" in frame.columns:
        gse_treasury_increase = _positive(pd.to_numeric(frame["gse_tsy_level"], errors="coerce").diff())
        source = "level_diff"
    else:
        gse_treasury_increase = _positive(gse_tsy_tx)
        source = "transactions_positive_part"
    gse_on_rrp_runoff = _positive(-gse_on_rrp.diff()).fillna(0.0)
    adjustment = pd.concat([gse_treasury_increase, gse_on_rrp_runoff], axis=1).min(axis=1)

    for date, row in frame.iterrows():
        adj = adjustment.loc[date]
        rows.append(
            {
                "date": date,
                "status": "diagnostic_only",
                "gse_tsy_tx": gse_tsy_tx.loc[date],
                "gse_on_rrp": gse_on_rrp.loc[date],
                "gse_on_rrp_runoff": gse_on_rrp_runoff.loc[date],
                "gse_treasury_increase": gse_treasury_increase.loc[date],
                "gse_rrp_boundary_adjustment": adj,
                "detail": (
                    "Boundary diagnostic only: min(positive GSE Treasury acquisition, GSE ON RRP runoff). "
                    f"Treasury acquisition source: {source}."
                ),
            }
        )
    return pd.DataFrame(rows)


def write_gse_rrp_boundary_check(
    *,
    quarterly: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> pd.DataFrame:
    diagnostic = build_gse_rrp_boundary_check(quarterly)
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    diagnostic.to_csv(target, index=False)

    if markdown_path is not None:
        md_target = Path(markdown_path)
        md_target.parent.mkdir(parents=True, exist_ok=True)
        valid = diagnostic.loc[diagnostic["status"].eq("diagnostic_only")].copy()
        lines = [
            "# GSE/RRP boundary diagnostic",
            "",
            "This is a boundary check only. It is not part of the canonical TDC estimator.",
            "",
            "Construction: `min(max(0, GSE Treasury acquisition), max(0, -Delta GSE ON RRP))`.",
        ]
        if valid.empty:
            detail = diagnostic["detail"].iloc[0] if "detail" in diagnostic.columns and not diagnostic.empty else "No diagnostic rows."
            lines.extend(["", f"Status: {detail}"])
        else:
            latest = valid.dropna(subset=["gse_rrp_boundary_adjustment"]).tail(1)
            material = valid.loc[pd.to_numeric(valid["gse_rrp_boundary_adjustment"], errors="coerce").fillna(0.0).gt(0.0)]
            lines.extend(
                [
                    "",
                    f"Rows: {len(valid)}",
                    f"Rows with positive diagnostic adjustment: {len(material)}",
                ]
            )
            if not latest.empty:
                row = latest.iloc[0]
                lines.extend(
                    [
                        "",
                        (
                            f"Latest row: {pd.Timestamp(row['date']).date().isoformat()}, "
                            f"GSE ON RRP {row['gse_on_rrp']:.3f}, "
                            f"runoff {row['gse_on_rrp_runoff']:.3f}, "
                            f"Treasury increase {row['gse_treasury_increase']:.3f}, "
                            f"diagnostic adjustment {row['gse_rrp_boundary_adjustment']:.3f}."
                        ),
                    ]
                )
        md_target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return diagnostic
