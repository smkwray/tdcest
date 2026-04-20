from __future__ import annotations

from pathlib import Path

import pandas as pd


CHECK_COLUMNS = [
    "check_key",
    "check_group",
    "status",
    "metric_value",
    "binding_boundary",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    subset = frame.loc[frame[key_col].eq(key)]
    if subset.empty:
        return pd.Series(dtype="object")
    return subset.iloc[0]


def build_backend_release_check(
    *,
    downstream_consistency_review: pd.DataFrame | None,
    backend_closeout_review: pd.DataFrame | None,
) -> pd.DataFrame:
    consistency = downstream_consistency_review.copy() if downstream_consistency_review is not None else pd.DataFrame()
    closeout = backend_closeout_review.copy() if backend_closeout_review is not None else pd.DataFrame()

    all_consistency_pass = (
        not consistency.empty
        and "status" in consistency.columns
        and consistency["status"].eq("pass").all()
    )
    contract_layer = _get_row(closeout, "review_key", "downstream_contract_layer")
    bank_branch = _get_row(closeout, "review_key", "bank_receipt_branch")
    row_branch = _get_row(closeout, "review_key", "row_mrv_branch")
    fiscal_shell = _get_row(closeout, "review_key", "fiscal_shell")
    monetary_crosscheck = _get_row(closeout, "review_key", "monetary_crosscheck")

    checks = [
        {
            "check_key": "downstream_consistency_all_pass",
            "check_group": "contract_layer",
            "status": "pass" if all_consistency_pass else "fail",
            "metric_value": (
                str(int(consistency["status"].eq("pass").sum())) + "/" + str(len(consistency))
                if not consistency.empty and "status" in consistency.columns
                else "0/0"
            ),
            "binding_boundary": "all downstream contract invariants must stay green",
            "summary_note": "The downstream contract layer should not be treated as closed out unless the consistency review is fully green.",
        },
        {
            "check_key": "distribution_scope_explicit",
            "check_group": "distribution",
            "status": "pass",
            "metric_value": "full_repo_required_for_regeneration",
            "binding_boundary": "partial packs must be treated as snapshots unless explicitly labeled full_repo",
            "summary_note": "Release posture assumes the full repo is the regenerable unit. Partial audit packs are snapshot-only unless explicitly labeled as full repo exports.",
        },
        {
            "check_key": "closeout_contract_layer_ready",
            "check_group": "closeout_state",
            "status": "pass" if str(contract_layer.get("release_readiness")) == "closeout_ready" else "fail",
            "metric_value": contract_layer.get("release_readiness", "n/a"),
            "binding_boundary": contract_layer.get("binding_boundary", "n/a"),
            "summary_note": "Closeout review should classify the contract layer as closeout-ready before the backend is considered stable.",
        },
        {
            "check_key": "bank_branch_bounded_ready",
            "check_group": "receipt_branches",
            "status": "pass" if str(bank_branch.get("release_readiness")) == "bounded_historical_ready" else "fail",
            "metric_value": bank_branch.get("release_readiness", "n/a"),
            "binding_boundary": bank_branch.get("binding_boundary", "n/a"),
            "summary_note": "Bank receipts should remain historical-default-only and explicitly bounded by the stale-share rule.",
        },
        {
            "check_key": "row_branch_bounded_ready",
            "check_group": "receipt_branches",
            "status": "pass" if str(row_branch.get("release_readiness")) == "bounded_nondefault_ready" else "fail",
            "metric_value": row_branch.get("release_readiness", "n/a"),
            "binding_boundary": row_branch.get("binding_boundary", "n/a"),
            "summary_note": "MRV should remain the only bounded ROW pilot and explicitly nondefault.",
        },
        {
            "check_key": "fiscal_shell_bounded_ready",
            "check_group": "diagnostic_systems",
            "status": "pass" if str(fiscal_shell.get("release_readiness")) == "bounded_diagnostic_ready" else "fail",
            "metric_value": fiscal_shell.get("release_readiness", "n/a"),
            "binding_boundary": fiscal_shell.get("binding_boundary", "n/a"),
            "summary_note": "Fiscal shell should stay explicit as a bounded reconciliation system rather than a receipt-complete estimator.",
        },
        {
            "check_key": "monetary_branch_stable",
            "check_group": "diagnostic_systems",
            "status": "pass" if str(monetary_crosscheck.get("release_readiness")) == "diagnostic_only_stable" else "fail",
            "metric_value": monetary_crosscheck.get("release_readiness", "n/a"),
            "binding_boundary": monetary_crosscheck.get("binding_boundary", "n/a"),
            "summary_note": "Monetary branch should remain diagnostic-only and not reopen as a headline-estimator buildout.",
        },
    ]

    all_pass = all(check["status"] == "pass" for check in checks)
    checks.append(
        {
            "check_key": "overall_release_recommendation",
            "check_group": "summary",
            "status": "pass" if all_pass else "fail",
            "metric_value": "backend_bounded_closeout_ready" if all_pass else "needs_more_backend_closeout",
            "binding_boundary": "A new branch should open only if one of the explicit bounded stop rules is cleared by genuinely new evidence or a failing invariant.",
            "summary_note": "Overall backend release recommendation.",
        }
    )

    return pd.DataFrame(checks).reindex(columns=CHECK_COLUMNS)


def render_backend_release_check_markdown(frame: pd.DataFrame) -> str:
    title = "# Backend Release Check"
    intro = (
        "Final backend release-style checklist. It converts the closeout state into explicit pass/fail checks and one overall recommendation."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No backend release checks are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Check | Group | Status | Metric | Binding boundary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for _, row in frame.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["check_key"]),
                    str(row["check_group"]),
                    str(row["status"]),
                    str(row["metric_value"]),
                    str(row["binding_boundary"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Notes", ""])
    for _, row in frame.iterrows():
        lines.append(f"- `{row['check_key']}`: {row['summary_note']}")

    return "\n".join(lines + [""])


def write_backend_release_check(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    downstream_consistency_review: pd.DataFrame | None,
    backend_closeout_review: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_backend_release_check(
        downstream_consistency_review=downstream_consistency_review,
        backend_closeout_review=backend_closeout_review,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_backend_release_check_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
