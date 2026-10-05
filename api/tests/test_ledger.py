"""Property tests: every automatic posting balances, and stock always reconciles, across
thousands of random operations (the M9 "done when")."""

from __future__ import annotations

import uuid
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.modules.accounting import postings
from app.modules.inventory import costing

RATES = [uuid.uuid4() for _ in range(3)]
money = st.integers(min_value=-(10**9), max_value=10**9)
positive = st.integers(min_value=0, max_value=10**9)


@st.composite
def sale_lines(draw: st.DrawFn) -> list[postings.SaleLineFacts]:
    lines = []
    for _ in range(draw(st.integers(min_value=0, max_value=6))):
        taxes = draw(st.lists(st.tuples(st.sampled_from(RATES), money), max_size=3))
        lines.append(postings.SaleLineFacts(net=draw(money), taxes=taxes))
    return lines


@settings(max_examples=2000)
@given(
    lines=sale_lines(),
    cash=money,
    on_account=money,
    rounding=st.integers(min_value=-500, max_value=500),
    kind=st.sampled_from(["sale", "return"]),
)
def test_sale_postings_always_balance(
    lines: list[postings.SaleLineFacts], cash: int, on_account: int, rounding: int, kind: str
) -> None:
    posting = postings.sale(1, kind, cash, on_account, rounding, lines, {RATES[0]: uuid.uuid4()})
    assert postings.balanced(posting.legs)
    assert postings.balanced(postings.reverse(posting.legs))


@settings(max_examples=1000)
@given(
    net=positive,
    taxes=st.lists(st.tuples(st.sampled_from(RATES), positive, positive), max_size=3),
    paid=positive,
    owed=positive,
    paid_from=st.sampled_from(["drawer", "petty_cash", "bank", "other"]),
)
def test_purchase_postings_balance_when_paid_and_owed_add_up(
    net: int, taxes: list[tuple[uuid.UUID, int, int]], paid: int, owed: int, paid_from: str
) -> None:
    total = net + sum(t[1] for t in taxes)
    paid = min(paid, total)
    posting = postings.purchase("PO", net, taxes, paid, paid_from, total - paid, {})
    assert postings.balanced(posting.legs)


@settings(max_examples=1000)
@given(
    kind=st.sampled_from(
        ["opening", "purchase", "sale", "return", "void", "adjustment", "count", "transfer_in"]
    ),
    value=money,
    amount=positive,
    gross=positive,
    net=positive,
    deductions=positive,
)
def test_every_other_posting_balances(
    kind: str, value: int, amount: int, gross: int, net: int, deductions: int
) -> None:
    stock = postings.stock(kind, value, "Tea")
    for posting in [
        stock,
        postings.supplier_payment("S", amount, "bank"),
        postings.customer_payment("C", amount),
        postings.customer_adjustment("C", value, None),
        postings.expense("E", amount, "drawer", None),
        postings.petty_top_up(amount),
        postings.payroll("2026-09", gross, net, deductions),
    ]:
        if posting is not None:
            assert postings.balanced(posting.legs)


operation = st.one_of(
    st.tuples(
        st.just("in"),
        st.decimals(min_value=Decimal("0.001"), max_value=Decimal(1000), places=3),
        st.decimals(min_value=0, max_value=Decimal(10000), places=2),
    ),
    st.tuples(
        st.just("out"),
        st.decimals(min_value=Decimal("0.001"), max_value=Decimal(1000), places=3),
        st.just(Decimal(0)),
    ),
    st.tuples(
        st.just("back"),
        st.decimals(min_value=Decimal("0.001"), max_value=Decimal(1000), places=3),
        st.just(Decimal(0)),
    ),
)


@settings(max_examples=300)
@given(ops=st.lists(operation, min_size=1, max_size=40))
def test_stock_always_reconciles(ops: list[tuple[str, Decimal, Decimal]]) -> None:
    """Quantity on hand is the sum of movements, and value is the sum of values moved."""
    p = costing.EMPTY
    quantity = value = Decimal(0)
    for kind, q, cost in ops:
        if kind == "in":
            p, moved = costing.receive(p, q, cost)
            quantity += q
        else:
            signed = -q if kind == "out" else q
            p, moved = costing.move(p, signed)
            quantity += signed
        value += moved
        assert p.quantity == quantity
        assert p.average >= 0
        if p.quantity == 0:
            assert p.value == 0
            value = Decimal(0)
        else:
            assert abs(p.value - value) < Decimal("0.0001")


def test_stock_sold_before_its_delivery_is_recosted() -> None:
    """Sold 2 ahead at the old average (10); the delivery costs 12: those 2 cost 4 more."""
    p, _ = costing.receive(costing.EMPTY, Decimal(1), Decimal(10))
    p, sold = costing.move(p, Decimal(-3))
    assert (p.quantity, sold) == (Decimal(-2), Decimal(-30))
    p, change = costing.receive(p, Decimal(5), Decimal(12))
    assert (p.quantity, p.average, p.value) == (Decimal(3), Decimal(12), Decimal(36))
    assert costing.correction(Decimal(5), Decimal(12), change) == Decimal(-4)
