"""Tax maths: inclusive and exclusive prices, compound taxes, rounding."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.modules.sales.tax import Rate, cash_round, line

VAT = Rate("vat", "VAT", Decimal("15"))
SD = Rate("sd", "Supplementary duty", Decimal("10"))
ON_TOP = Rate("city", "City tax", Decimal("2"), compound=True)


def test_exclusive_prices_add_tax() -> None:
    result = line(10000, [VAT], inclusive=False)
    assert (result.net, result.gross) == (10000, 11500)
    assert [t.amount for t in result.taxes] == [1500]


def test_inclusive_prices_work_the_net_back() -> None:
    result = line(11500, [VAT], inclusive=True)
    assert (result.net, result.gross) == (10000, 11500)
    assert [t.amount for t in result.taxes] == [1500]


def test_compound_taxes_apply_to_the_price_plus_earlier_taxes() -> None:
    result = line(10000, [SD, VAT, ON_TOP], inclusive=False)
    # SD 1000 and VAT 1500 on the net; the city tax 2% of 12500.
    assert [t.amount for t in result.taxes] == [1000, 1500, 250]
    assert result.gross == 12750
    back = line(12750, [SD, VAT, ON_TOP], inclusive=True)
    assert back.net == 10000
    assert [t.amount for t in back.taxes] == [1000, 1500, 250]


def test_no_taxes_and_zero_rates() -> None:
    assert line(999, [], inclusive=True).gross == 999
    zero = line(999, [Rate("z", "Exempt", Decimal(0))], inclusive=False)
    assert (zero.net, zero.gross, zero.taxes[0].amount) == (999, 999, 0)


def test_cash_rounding() -> None:
    assert cash_round(12345, 1) == 12345
    assert cash_round(12345, 100) == 12300
    assert cash_round(12350, 100) == 12400
    assert cash_round(12345, 50) == 12350


@given(
    amount=st.integers(min_value=0, max_value=10**9),
    percents=st.lists(st.decimals(min_value=0, max_value=50, places=2), max_size=3),
    compound=st.lists(st.booleans(), min_size=3, max_size=3),
)
def test_inclusive_lines_always_add_up_to_the_price(
    amount: int, percents: list[Decimal], compound: list[bool]
) -> None:
    rates = [Rate(str(i), f"T{i}", p, compound[i]) for i, p in enumerate(percents)]
    result = line(amount, rates, inclusive=True)
    assert result.gross == amount
    assert result.net + sum(t.amount for t in result.taxes) == amount
    assert result.net >= 0
