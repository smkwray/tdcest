"""Settlement-route incidence: each test fails if a route posts to the wrong ledger.

Incidence follows the claim debited or credited at settlement, so these tests
route the same legal holder through different claims and expect different
reserve postings.
"""

from __future__ import annotations

import pytest

from tdc_estimator.settlement_routes import (
    REQUIRED_ROUTE_IDS,
    ROUTE_REGISTRY_FIELDS,
    SettlementEvent,
    event_incidence,
    load_settlement_routes,
    route_for_claim,
    route_registry_frame,
)

P = 100.0


def post(debit: str, credit: str, *, security: bool = False) -> tuple[float, float]:
    return event_incidence(SettlementEvent(debit, credit, P, treasury_security=security))


def test_registry_has_required_routes_and_one_route_per_claim():
    routes = load_settlement_routes()
    assert set(REQUIRED_ROUTE_IDS) <= set(routes)
    claims = [route.settlement_claim for route in routes.values()]
    assert len(claims) == len(set(claims))
    for route in routes.values():
        assert route_for_claim(route.settlement_claim) is route
    frame = route_registry_frame()
    assert list(frame.columns) == ROUTE_REGISTRY_FIELDS
    assert set(frame["route_id"]) == set(routes)


def test_reserve_incidence_cannot_be_inferred_from_holder_sector():
    routes = load_settlement_routes()
    by_holder: dict[str, set[int]] = {}
    for route in routes.values():
        for holder in route.holder_sector:
            by_holder.setdefault(holder, set()).add(route.trc_incidence)
    assert by_holder["foreign_official"] == {0, 1}
    assert by_holder["money_market_fund"] == {0, 1}
    # Same legal holder, two settlement claims, two reserve incidences.
    official = [r for r in routes.values() if "foreign_official" in r.holder_sector]
    assert {r.route_id: r.trc_incidence for r in official}["foreign_official_deposit"] == 0
    assert {r.route_id: r.trc_incidence for r in official}["foreign_bank_settled"] == 1
    assert post("foreign_official_deposit", "treasury_general_account") != post(
        "foreign_bank_settled", "treasury_general_account")


def test_tga_spending_and_tax():
    assert post("treasury_general_account", "covered_deposit") == (P, P)
    assert post("covered_deposit", "treasury_general_account") == (-P, -P)


def test_tt_and_l_receipt_then_call():
    assert post("covered_deposit", "tt_and_l") == (-P, 0.0)
    assert post("tt_and_l", "treasury_general_account") == (0.0, -P)
    receipt, call = post("covered_deposit", "tt_and_l"), post("tt_and_l", "treasury_general_account")
    # Over the full chain the tax lands once on each ledger.
    assert (receipt[0] + call[0], receipt[1] + call[1]) == post("covered_deposit", "treasury_general_account")


def test_bank_versus_deposit_funded_auction_purchase():
    assert post("bank_reserve_own_account", "treasury_general_account") == (0.0, -P)
    assert post("covered_deposit", "treasury_general_account") == (-P, -P)


def test_on_rrp_funded_mmf_and_gse_purchases_move_neither_ledger():
    assert post("mmf_on_rrp", "treasury_general_account") == (0.0, 0.0)
    assert post("gse_on_rrp", "treasury_general_account") == (0.0, 0.0)
    # The same fund paying from a bank deposit drains both.
    assert post("covered_deposit", "treasury_general_account") == (-P, -P)


def test_foreign_official_direct_fed_versus_bank_settled_purchase():
    assert post("foreign_official_deposit", "treasury_general_account") == (0.0, 0.0)
    assert post("foreign_official_rrp", "treasury_general_account") == (0.0, 0.0)
    assert post("foreign_bank_settled", "treasury_general_account") == (0.0, -P)
    assert post("covered_deposit", "treasury_general_account") == (-P, -P)


def test_debt_service_by_route():
    assert post("treasury_general_account", "covered_deposit") == (P, P)
    assert post("treasury_general_account", "bank_reserve_own_account") == (0.0, P)
    assert post("treasury_general_account", "foreign_official_deposit") == (0.0, 0.0)
    assert post("treasury_general_account", "mmf_on_rrp") == (0.0, 0.0)


def test_soma_secondary_purchases_and_sales_by_counterparty():
    assert post("fed_soma", "covered_deposit", security=True) == (P, P)
    assert post("fed_soma", "bank_reserve_own_account", security=True) == (0.0, P)
    assert post("covered_deposit", "fed_soma", security=True) == (-P, -P)
    assert post("bank_reserve_own_account", "fed_soma", security=True) == (0.0, -P)
    # Bank and covered nonbank trading with each other move deposits, not reserves.
    assert post("bank_reserve_own_account", "covered_deposit", security=True) == (P, 0.0)
    assert post("covered_deposit", "bank_reserve_own_account", security=True) == (-P, 0.0)


@pytest.mark.parametrize("debit,credit", [
    ("treasury_general_account", "fed_soma"),  # coupon paid to SOMA
    ("fed_soma", "treasury_general_account"),  # cash remittance, SOMA add-on or rollover
    ("other_treasury_fed_account", "treasury_general_account"),  # matched special-account entry
    ("intragovernmental", "treasury_general_account"),
])
def test_coupon_remittance_rollover_and_redemption_have_zero_direct_effect(debit, credit):
    assert post(debit, credit) == (0.0, 0.0)
    assert post(credit, debit) == (0.0, 0.0)


@pytest.mark.parametrize("debit,credit", [
    ("fed_soma", "bank_reserve_own_account"),  # interest on reserve balances
    ("fed_soma", "foreign_official_deposit"),  # FIMA repo cash
])
def test_iorb_and_fima_rejected_without_treasury_event_link(debit, credit):
    with pytest.raises(ValueError, match="not a Treasury event"):
        post(debit, credit)


def test_events_fail_closed_on_bad_input():
    with pytest.raises(ValueError, match="unknown route"):
        post("covered_deposit", "tga")
    with pytest.raises(ValueError, match="distinct"):
        post("covered_deposit", "covered_deposit", security=True)
    with pytest.raises(ValueError, match="finite"):
        event_incidence(SettlementEvent("covered_deposit", "treasury_general_account", float("nan")))
    with pytest.raises(ValueError, match="exactly one route"):
        route_for_claim("reserve_balances")
