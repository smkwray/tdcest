"""Typed settlement-route registry shared by TDC and TRC incidence.

Each route names the cash claim debited or credited at settlement. Its
incidences are the effect of one dollar on covered domestic nonbank deposits
(TDC) and on aggregate reserve balances (TRC) when that claim settles against a
Treasury account at the Federal Reserve. The incidence of an event that moves
cash from claim A to claim B is ``incidence(B) - incidence(A)``. Incidence
follows the claim, never the legal holder: one holder sector can appear on
several routes with different reserve incidence.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import math

import pandas as pd

from .catalog import DEFAULT_VINTAGE, MeasurementVintage

HOLDER_SECTORS = (
    "domestic_nonbank",
    "money_market_fund",
    "gse",
    "depository_institution",
    "foreign_official",
    "foreign_private",
    "federal_reserve",
    "treasury",
)
DIRECTION_POLICIES = (
    "symmetric",
    "one_sided_runoff_funded_purchases",
    "opposite_sign_overlap_bound",
)
EVIDENCE_TIERS = (
    "source_exact",
    "proxy",
    "implied_by_treasury_fed_deposit_closure",
    "partial_bound",
    "heuristic_bound",
    "definitional_zero",
)
ROUTE_STATUSES = (
    "default_measured",
    "default_proxy",
    "default_implied",
    "default_partial_one_sided",
    "wedge_leg_measured",
    "nondefault_bound",
    "definitional_zero",
)
REQUIRED_ROUTE_IDS = (
    "covered_deposit",
    "bank_reserve_own_account",
    "mmf_on_rrp",
    "gse_on_rrp",
    "foreign_bank_settled",
    "foreign_official_deposit",
    "foreign_official_rrp",
    "tt_and_l",
    "fed_soma",
    "intragovernmental",
    "other_treasury_fed_account",
)


@dataclass(frozen=True)
class SettlementRoute:
    route_id: str
    holder_sector: tuple[str, ...]
    settlement_claim: str
    fed_account: str
    tdc_incidence: int
    trc_incidence: int
    direction_policy: str
    evidence_tier: str
    default_eligible: bool
    coverage_start: str
    coverage_end: str
    status: str
    treasury_account: bool = False


SETTLEMENT_ROUTES: tuple[SettlementRoute, ...] = (
    SettlementRoute(
        "treasury_general_account", ("treasury",), "treasury_general_account",
        "treasury_general_account", 0, 0, "symmetric", "source_exact", True,
        "2003Q1", "2025Q4", "default_measured", treasury_account=True,
    ),
    SettlementRoute(
        "covered_deposit",
        ("domestic_nonbank", "money_market_fund", "gse", "foreign_official", "foreign_private"),
        "covered_bank_deposit", "reserve_balances", 1, 1, "symmetric",
        "implied_by_treasury_fed_deposit_closure", True, "2003Q1", "2025Q4", "default_implied",
    ),
    SettlementRoute(
        "bank_reserve_own_account", ("depository_institution",), "reserve_balance",
        "reserve_balances", 0, 1, "symmetric", "implied_by_treasury_fed_deposit_closure", True,
        "2003Q1", "2025Q4", "default_implied",
    ),
    SettlementRoute(
        "mmf_on_rrp", ("money_market_fund",), "on_rrp_claim_mmf", "reverse_repo_others", 0, 0,
        "one_sided_runoff_funded_purchases", "partial_bound", True, "2013Q3", "2025Q4",
        "default_partial_one_sided",
    ),
    SettlementRoute(
        "gse_on_rrp", ("gse",), "on_rrp_claim_gse", "reverse_repo_others", 0, 0,
        "one_sided_runoff_funded_purchases", "partial_bound", False, "2013Q3", "2025Q4",
        "nondefault_bound",
    ),
    SettlementRoute(
        "foreign_bank_settled", ("foreign_official", "foreign_private"), "noncovered_bank_deposit",
        "reserve_balances", 0, 1, "symmetric", "implied_by_treasury_fed_deposit_closure", True,
        "2003Q1", "2025Q4", "default_implied",
    ),
    SettlementRoute(
        "foreign_official_deposit", ("foreign_official",), "foreign_official_fed_deposit",
        "foreign_official_deposits", 0, 0, "opposite_sign_overlap_bound", "heuristic_bound", False,
        "2007Q4", "2025Q4", "nondefault_bound",
    ),
    SettlementRoute(
        "foreign_official_rrp", ("foreign_official",), "foreign_official_reverse_repo",
        "reverse_repo_foreign_official", 0, 0, "opposite_sign_overlap_bound", "heuristic_bound", False,
        "2007Q4", "2025Q4", "nondefault_bound",
    ),
    SettlementRoute(
        "tt_and_l", ("treasury",), "treasury_tax_and_loan_bank_deposit", "reserve_balances", 0, 1,
        "symmetric", "source_exact", True, "2006Q1", "2025Q4", "wedge_leg_measured",
        treasury_account=True,
    ),
    SettlementRoute(
        "fed_soma", ("federal_reserve",), "fed_own_balance_sheet", "soma_and_fed_earnings", 0, 0,
        "symmetric", "proxy", True, "2002Q1", "2025Q4", "default_proxy",
    ),
    SettlementRoute(
        "intragovernmental", ("treasury",), "intragovernmental_book_entry", "none", 0, 0,
        "symmetric", "definitional_zero", True, "2002Q1", "2025Q4", "definitional_zero",
        treasury_account=True,
    ),
    SettlementRoute(
        "other_treasury_fed_account", ("treasury",), "treasury_special_fed_account",
        "supplementary_financing_account", 0, 0, "symmetric", "source_exact", True,
        "2003Q1", "2025Q4", "default_measured", treasury_account=True,
    ),
)

ROUTE_REGISTRY_FIELDS = [field.name for field in fields(SettlementRoute)]


def load_settlement_routes() -> dict[str, SettlementRoute]:
    """Validate the registry once and return it keyed by route id."""
    routes: dict[str, SettlementRoute] = {}
    claims: set[str] = set()
    for route in SETTLEMENT_ROUTES:
        if route.route_id in routes:
            raise ValueError(f"duplicate route_id {route.route_id}")
        if route.settlement_claim in claims:
            raise ValueError(f"settlement claim {route.settlement_claim} is not mutually exclusive")
        unknown = set(route.holder_sector) - set(HOLDER_SECTORS)
        if not route.holder_sector or unknown:
            raise ValueError(f"{route.route_id}: invalid holder sectors {sorted(unknown)}")
        if route.tdc_incidence not in (0, 1) or route.trc_incidence not in (0, 1):
            raise ValueError(f"{route.route_id}: incidences must be 0 or 1")
        for value, allowed, label in [
            (route.direction_policy, DIRECTION_POLICIES, "direction_policy"),
            (route.evidence_tier, EVIDENCE_TIERS, "evidence_tier"),
            (route.status, ROUTE_STATUSES, "status"),
        ]:
            if value not in allowed:
                raise ValueError(f"{route.route_id}: unknown {label} {value}")
        if pd.Period(route.coverage_start, freq="Q") > pd.Period(route.coverage_end, freq="Q"):
            raise ValueError(f"{route.route_id}: coverage_start after coverage_end")
        routes[route.route_id] = route
        claims.add(route.settlement_claim)
    missing = set(REQUIRED_ROUTE_IDS) - set(routes)
    if missing:
        raise ValueError(f"registry is missing required routes {sorted(missing)}")
    return routes


def route_for_claim(settlement_claim: str) -> SettlementRoute:
    """Resolve the unique route for the claim debited or credited at settlement."""
    matches = [route for route in load_settlement_routes().values() if route.settlement_claim == settlement_claim]
    if len(matches) != 1:
        raise ValueError(f"settlement claim {settlement_claim!r} does not resolve to exactly one route")
    return matches[0]


def route_registry_frame(vintage: MeasurementVintage = DEFAULT_VINTAGE) -> pd.DataFrame:
    """Registry rows; routes measured through the admitted endpoint run to the vintage endpoint."""
    rows = []
    for route in load_settlement_routes().values():
        row = {name: getattr(route, name) for name in ROUTE_REGISTRY_FIELDS}
        row["holder_sector"] = "|".join(route.holder_sector)
        if route.coverage_end == DEFAULT_VINTAGE.quarter_end:
            row["coverage_end"] = vintage.quarter_end
        rows.append(row)
    return pd.DataFrame(rows, columns=ROUTE_REGISTRY_FIELDS)


@dataclass(frozen=True)
class SettlementEvent:
    """Cash of ``amount`` moves from the debited claim's route to the credited claim's route.

    ``treasury_security`` marks a Treasury-security settlement. An event with no
    Treasury account on either side and no Treasury-security link is not a
    Treasury event and belongs in the non-Treasury reserve remainder.
    """

    debit_route: str
    credit_route: str
    amount: float
    treasury_security: bool = False


def event_incidence(event: SettlementEvent) -> tuple[float, float]:
    """Return the (TDC, TRC) postings of one Treasury settlement event."""
    routes = load_settlement_routes()
    if event.debit_route not in routes or event.credit_route not in routes:
        raise ValueError(f"unknown route in {event}")
    if event.debit_route == event.credit_route:
        raise ValueError("an event must move cash between two distinct claims")
    if not math.isfinite(event.amount) or event.amount < 0:
        raise ValueError("event amount must be finite and nonnegative")
    debit, credit = routes[event.debit_route], routes[event.credit_route]
    if not (debit.treasury_account or credit.treasury_account or event.treasury_security):
        raise ValueError("not a Treasury event: no Treasury account or Treasury-security link")
    return (
        event.amount * (credit.tdc_incidence - debit.tdc_incidence),
        event.amount * (credit.trc_incidence - debit.trc_incidence),
    )
