"""DS^T_DU expense/control-layer complement panel (identity note section 2).

Builds, per quarter and marketable interest component, the deposit-user
debt-service complement on the official expense pools:

    complement (DS + U) = official pool - Fed exact - certified RU allocations

Conventions are binding per the DS^T_DU identity note (2026-07-13): this is the
expense-equivalent holder-incidence control, NOT cash received (no cash-labeled
columns here); the complement embeds the not-yet-separated unallocated term U
until the direct-side mapping isolates it; a negative complement is a failed
identity and fails the build closed; the output is never additive to Tier 2 rows.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ESTIMAND_LAYER = "expense_control"
CERTIFIED_TIER = "certified_modern_component_identity"
ANALYSIS_TIER = "analysis_component_identity"
TOTAL_COMPONENT_KEY = "total_core"

REQUIRED_CANDIDATE_COLUMNS = [
    "date",
    "sector_group",
    "component_key",
    "official_component_pool_mil",
    "fed_exact_component_mil",
    "component_anchored_interest_mil",
]


def load_certified_dates_from_manifest(manifest_path: Path | str) -> list[pd.Timestamp]:
    path = Path(manifest_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [pd.Timestamp(value) for value in payload.get("expected_dates", [])]


def build_dst_du_expense_panel(
    candidate: pd.DataFrame,
    *,
    certified_dates: list[pd.Timestamp] | None = None,
) -> pd.DataFrame:
    missing = [column for column in REQUIRED_CANDIDATE_COLUMNS if column not in candidate.columns]
    if missing:
        raise ValueError(f"Candidate frame is missing required columns: {missing}")

    frame = candidate.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"])
    certified = {pd.Timestamp(value).normalize() for value in (certified_dates or [])}

    rows: list[dict[str, object]] = []
    failures: list[str] = []
    for (date, component_key), group in frame.groupby(["date", "component_key"]):
        pool_values = pd.to_numeric(group["official_component_pool_mil"], errors="coerce").dropna()
        if pool_values.empty:
            continue
        pool = float(pool_values.iloc[0])
        fed_raw = pd.to_numeric(group["fed_exact_component_mil"], errors="coerce").dropna()
        fed_exact = float(fed_raw.iloc[0]) if not fed_raw.empty else 0.0
        fed_exact_missing = fed_raw.empty
        allocations = pd.to_numeric(group["component_anchored_interest_mil"], errors="coerce")
        if allocations.isna().any():
            sectors = group.loc[allocations.isna(), "sector_group"].tolist()
            failures.append(
                f"{component_key} at {date.date()}: NaN RU allocation for {sectors}"
            )
            continue
        ru_by_sector = {
            str(sector): float(value)
            for sector, value in zip(group["sector_group"], allocations)
        }
        ru_total = float(allocations.sum())
        complement = pool - fed_exact - ru_total
        if complement < 0.0:
            failures.append(
                f"{component_key} at {date.date()}: negative complement "
                f"{complement:,.3f}M — failed identity (never clip)"
            )
            continue
        rows.append(
            {
                "date": date,
                "component_key": str(component_key),
                "estimand_layer": ESTIMAND_LAYER,
                "official_component_pool_mil": pool,
                "fed_exact_component_mil": fed_exact,
                "fed_exact_missing": fed_exact_missing,
                "ru_bank_mil": ru_by_sector.get("bank"),
                "ru_credit_union_mil": ru_by_sector.get("credit_union"),
                "ru_row_mil": ru_by_sector.get("row"),
                "ru_allocated_total_mil": ru_total,
                "dst_du_expense_complement_mil": complement,
                "complement_share_of_pool": complement / pool if pool > 0 else pd.NA,
                "method_tier": CERTIFIED_TIER if date in certified else ANALYSIS_TIER,
            }
        )
    if failures:
        raise ValueError(
            "DS^T_DU expense complement failed closed on "
            f"{len(failures)} quarter/component cells: " + " | ".join(failures[:8])
        )
    panel = pd.DataFrame(rows).sort_values(["date", "component_key"]).reset_index(drop=True)
    if panel.empty:
        raise ValueError("Candidate frame produced no complement rows.")

    totals = (
        panel.groupby("date", as_index=False)
        .agg(
            official_component_pool_mil=("official_component_pool_mil", "sum"),
            fed_exact_component_mil=("fed_exact_component_mil", "sum"),
            ru_bank_mil=("ru_bank_mil", "sum"),
            ru_credit_union_mil=("ru_credit_union_mil", "sum"),
            ru_row_mil=("ru_row_mil", "sum"),
            ru_allocated_total_mil=("ru_allocated_total_mil", "sum"),
            dst_du_expense_complement_mil=("dst_du_expense_complement_mil", "sum"),
            fed_exact_missing=("fed_exact_missing", "any"),
        )
    )
    totals["component_key"] = TOTAL_COMPONENT_KEY
    totals["estimand_layer"] = ESTIMAND_LAYER
    totals["complement_share_of_pool"] = (
        totals["dst_du_expense_complement_mil"] / totals["official_component_pool_mil"]
    )
    totals["method_tier"] = totals["date"].map(
        lambda value: CERTIFIED_TIER if value in certified else ANALYSIS_TIER
    )
    combined = pd.concat([panel, totals[panel.columns]], ignore_index=True)
    return combined.sort_values(["date", "component_key"]).reset_index(drop=True)


def render_dst_du_expense_summary(panel: pd.DataFrame) -> str:
    totals = panel[panel["component_key"] == TOTAL_COMPONENT_KEY].sort_values("date")
    latest = totals.iloc[-1]
    certified_count = int((totals["method_tier"] == CERTIFIED_TIER).sum())
    lines = [
        "# DS^T_DU expense/control complement panel",
        "",
        "Estimand: expense-equivalent holder-incidence control on the official",
        "marketable component pools (modified accrual). NOT cash received — the",
        "cash layer is a separate future row family. The complement embeds the",
        "unallocated term U until the direct-side mapping isolates it, so it is",
        "an upper bound for DS proper. Never additive to Tier 2 rows.",
        "Conventions: DS^T_DU identity note (approved 2026-07-13).",
        "",
        f"Quarters: {totals['date'].dt.date.min()} to {totals['date'].dt.date.max()} "
        f"({len(totals)} total, {certified_count} certified).",
        f"Latest ({latest['date'].date()}): pool "
        f"${latest['official_component_pool_mil']:,.1f}M, complement (DS+U) "
        f"${latest['dst_du_expense_complement_mil']:,.1f}M "
        f"({latest['complement_share_of_pool']:.1%} of pool), tier {latest['method_tier']}.",
    ]
    return "\n".join(lines) + "\n"


def write_dst_du_expense_panel(
    *,
    candidate_path: Path | str,
    manifest_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    candidate = pd.read_csv(candidate_path)
    certified_dates = load_certified_dates_from_manifest(manifest_path)
    panel = build_dst_du_expense_panel(candidate, certified_dates=certified_dates)
    out_csv = Path(out_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write = panel.copy()
    write["date"] = pd.to_datetime(write["date"], errors="coerce").dt.date.astype(str)
    write.to_csv(out_csv, index=False)
    out_md = Path(out_markdown_path)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_dst_du_expense_summary(panel), encoding="utf-8")
    return out_csv, out_md, panel
