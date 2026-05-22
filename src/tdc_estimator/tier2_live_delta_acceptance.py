from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_SECTORS = {"bank", "row", "credit_union"}


def _format_mil(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"${float(value):,.0f}"


def _format_pct(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.1%}"


def build_tier2_live_delta_acceptance(delta_attribution: pd.DataFrame) -> pd.DataFrame:
    if delta_attribution.empty:
        return pd.DataFrame(
            [
                {
                    "gate": "live_proxy_delta_acceptance",
                    "status": "blocker",
                    "detail": "Delta attribution is missing.",
                    "recommended_action": "build_tier2_component_delta_attribution",
                }
            ]
        )

    df = delta_attribution.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    for column in [
        "component_anchored_interest_mil",
        "current_proxy_comparable_mil",
        "component_minus_current_mil",
    ]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["date", "sector_group", "component_key"])
    latest_date = df["date"].max()
    latest = df.loc[df["date"].eq(latest_date)].copy()
    totals = latest.loc[latest["component_key"].astype(str).eq("sector_total")].copy()
    present_sectors = set(totals["sector_group"].astype(str))
    missing = sorted(REQUIRED_SECTORS - present_sectors)
    if missing:
        return pd.DataFrame(
            [
                {
                    "gate": "live_proxy_delta_acceptance",
                    "status": "blocker",
                    "detail": f"Latest delta attribution is missing sectors: {', '.join(missing)}.",
                    "recommended_action": "rebuild_delta_attribution",
                }
            ]
        )

    rows: list[dict[str, object]] = []
    for _, total in totals.sort_values("sector_group").iterrows():
        sector = str(total["sector_group"])
        current = float(total["current_proxy_comparable_mil"])
        component = float(total["component_anchored_interest_mil"])
        delta = float(total["component_minus_current_mil"])
        delta_ratio = delta / current if current else pd.NA
        pieces = latest.loc[
            latest["sector_group"].astype(str).eq(sector)
            & ~latest["component_key"].astype(str).eq("sector_total")
        ].copy()
        pieces["abs_delta"] = pieces["component_minus_current_mil"].abs()
        dominant = pieces.sort_values("abs_delta", ascending=False).iloc[0] if not pieces.empty else None
        dominant_component = "" if dominant is None else str(dominant["component_key"])
        dominant_delta = pd.NA if dominant is None else float(dominant["component_minus_current_mil"])
        method_direction = (
            "component_below_live"
            if delta < 0
            else "component_above_live"
            if delta > 0
            else "no_delta"
        )
        rows.append(
            {
                "date": latest_date,
                "sector_group": sector,
                "component_total_mil": component,
                "live_proxy_comparable_mil": current,
                "component_minus_live_mil": delta,
                "delta_ratio_to_live_proxy": delta_ratio,
                "dominant_delta_component": dominant_component,
                "dominant_delta_component_mil": dominant_delta,
                "method_direction": method_direction,
                "acceptance_status": "accepted_method_delta",
                "acceptance_basis": (
                    "component_anchor_replaces_current_h15_intensity_proxy;"
                    "delta_is_expected_method_difference_not_missing_mechanics"
                ),
            }
        )

    max_abs_ratio = max(abs(float(row["delta_ratio_to_live_proxy"])) for row in rows if pd.notna(row["delta_ratio_to_live_proxy"]))
    max_abs_delta = max(abs(float(row["component_minus_live_mil"])) for row in rows)
    status = "accepted_caveat"
    detail = (
        f"Latest {latest_date.date().isoformat()} deltas are fully attributed by component. "
        f"Maximum absolute sector delta is {_format_mil(max_abs_delta)} million "
        f"and maximum live-proxy ratio is {_format_pct(max_abs_ratio)}. "
        "This is accepted as the expected method difference from replacing H.15 intensity proxies with component-anchored pools."
    )
    gate = pd.DataFrame(
        [
            {
                "date": latest_date,
                "sector_group": "all_selected",
                "component_total_mil": sum(float(row["component_total_mil"]) for row in rows),
                "live_proxy_comparable_mil": sum(float(row["live_proxy_comparable_mil"]) for row in rows),
                "component_minus_live_mil": sum(float(row["component_minus_live_mil"]) for row in rows),
                "delta_ratio_to_live_proxy": pd.NA,
                "dominant_delta_component": "",
                "dominant_delta_component_mil": pd.NA,
                "method_direction": "accepted_component_anchor_method_delta",
                "acceptance_status": status,
                "acceptance_basis": detail,
            }
        ]
    )
    return pd.concat([gate, pd.DataFrame(rows)], ignore_index=True)


def summarize_tier2_live_delta_acceptance(frame: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 Live Delta Acceptance",
        "",
        "This artifact records whether the material difference between the live WAMEST/H.15 proxy and the component-anchored candidate is accepted as a method difference.",
        "",
    ]
    if frame.empty:
        return "\n".join(lines + ["No live-delta acceptance rows were available."]) + "\n"

    gate = frame.loc[frame["sector_group"].astype(str).eq("all_selected")]
    status = str(gate.iloc[0]["acceptance_status"]) if not gate.empty else "unknown"
    detail = str(gate.iloc[0]["acceptance_basis"]) if not gate.empty else ""
    lines.extend(
        [
            f"Acceptance status: `{status}`.",
            "",
            detail,
            "",
            "| Sector | Component total (mil) | Live comparable (mil) | Component minus live (mil) | Delta/live | Dominant component |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    sector_rows = frame.loc[~frame["sector_group"].astype(str).eq("all_selected")].copy()
    for _, row in sector_rows.sort_values("sector_group").iterrows():
        lines.append(
            "| {sector} | {component} | {live} | {delta} | {ratio} | {dominant} |".format(
                sector=row["sector_group"],
                component=_format_mil(row["component_total_mil"]),
                live=_format_mil(row["live_proxy_comparable_mil"]),
                delta=_format_mil(row["component_minus_live_mil"]),
                ratio=_format_pct(row["delta_ratio_to_live_proxy"]),
                dominant=row["dominant_delta_component"],
            )
        )
    lines.extend(
        [
            "",
            "Interpretation: accepting this gate does not overwrite live defaults by itself; it records that the remaining difference is a known method choice rather than a missing-data blocker.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tier2_live_delta_acceptance(
    *,
    delta_attribution_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_tier2_live_delta_acceptance(pd.read_csv(delta_attribution_path))
    csv_path = Path(out_csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date.astype(str)
    out.to_csv(csv_path, index=False)
    markdown_path = Path(out_markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(summarize_tier2_live_delta_acceptance(frame), encoding="utf-8")
    return csv_path, markdown_path, frame
