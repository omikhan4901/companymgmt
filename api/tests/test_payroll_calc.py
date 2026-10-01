"""Pay calculation: worked examples for each rule, the tax maths, and invariants that must
hold for any input (Hypothesis)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.modules.payroll import calc, defaults

TK = 100  # paisa per taka
RULES = calc.Rules()
STAFF = calc.Structure(basic=20_000 * TK, house_rent=10_000 * TK, medical=2_000 * TK, conveyance=1_000 * TK)


def lines(result: calc.Result) -> dict[str, int]:
    return {line.code: line.amount for line in result.lines}


def test_full_month() -> None:
    r = calc.calculate(calc.Inputs(period="2026-06", structure=STAFF), RULES)
    assert lines(r) == {
        "basic": 2_000_000,
        "house_rent": 1_000_000,
        "medical": 200_000,
        "conveyance": 100_000,
    }
    assert (r.gross, r.deductions, r.net, r.carried_forward) == (3_300_000, 0, 3_300_000, 0)
    assert (r.days_in_period, r.payable_days) == (30, 30)


def test_joining_mid_month_pays_the_days_employed() -> None:
    r = calc.calculate(calc.Inputs(period="2026-06", structure=STAFF, joined_on=date(2026, 6, 16)), RULES)
    assert r.gross == 1_650_000
    left = calc.calculate(calc.Inputs(period="2026-06", structure=STAFF, left_on=date(2026, 6, 10)), RULES)
    assert left.gross == 1_100_000
    assert left.payable_days == 10


def test_february_in_leap_and_normal_years() -> None:
    leap = calc.calculate(calc.Inputs(period="2028-02", structure=STAFF, joined_on=date(2028, 2, 15)), RULES)
    assert (leap.days_in_period, leap.payable_days) == (29, 15)
    assert lines(leap)["basic"] == calc.money(Decimal(2_000_000) * 15 / 29)
    normal = calc.calculate(
        calc.Inputs(period="2027-02", structure=STAFF, joined_on=date(2027, 2, 15)), RULES
    )
    assert (normal.days_in_period, normal.payable_days) == (28, 14)
    assert lines(normal)["basic"] == 1_000_000


def test_thirty_day_basis() -> None:
    thirty = calc.Rules(day_basis="thirty")
    full = calc.calculate(calc.Inputs(period="2026-07", structure=STAFF), thirty)
    assert (full.days_in_period, full.gross) == (30, 3_300_000)
    part = calc.calculate(calc.Inputs(period="2026-07", structure=STAFF, joined_on=date(2026, 7, 17)), thirty)
    assert part.payable_days == 15
    assert part.gross == 1_650_000


def test_unpaid_leave_is_deducted_per_day() -> None:
    r = calc.calculate(calc.Inputs(period="2026-06", structure=STAFF, unpaid_leave_days=Decimal(2)), RULES)
    assert lines(r)["unpaid_leave"] == 220_000
    assert r.net == 3_080_000
    half = calc.calculate(
        calc.Inputs(period="2026-06", structure=STAFF, unpaid_leave_days=Decimal("0.5")), RULES
    )
    assert lines(half)["unpaid_leave"] == 55_000


def test_overtime_at_twice_the_hourly_basic() -> None:
    worker = calc.Structure(basic=20_800 * TK, overtime=True)
    worked = {date(2026, 6, 1): 600, date(2026, 6, 2): 480, date(2026, 6, 3): 450}
    r = calc.calculate(calc.Inputs(period="2026-06", structure=worker, worked=worked), RULES)
    # basic / 208 = 100 tk an hour, times 2, for 2 hours.
    assert lines(r)["overtime"] == 400 * TK
    assert (r.worked_minutes, r.overtime_minutes) == (1530, 120)
    no_ot = calc.calculate(
        calc.Inputs(period="2026-06", structure=calc.Structure(basic=20_800 * TK), worked=worked), RULES
    )
    assert "overtime" not in lines(no_ot)


def test_hourly_and_daily_pay() -> None:
    worked = {date(2026, 6, 1): 9 * 60, date(2026, 6, 2): 9 * 60, date(2026, 6, 3): 0}
    hourly = calc.calculate(
        calc.Inputs(
            period="2026-06",
            structure=calc.Structure(pay_rule="hourly", rate=150 * TK, overtime=True),
            worked=worked,
        ),
        RULES,
    )
    # 18 hours at 150, plus the overtime premium (the extra 1x) on 2 hours.
    assert lines(hourly) == {"hours": 2_700 * TK, "overtime": 300 * TK}
    daily = calc.calculate(
        calc.Inputs(
            period="2026-06", structure=calc.Structure(pay_rule="daily", rate=800 * TK), worked=worked
        ),
        RULES,
    )
    assert lines(daily) == {"days": 1_600 * TK}


def test_festival_bonus_after_a_year() -> None:
    long_served = calc.Inputs(
        period="2026-06", structure=STAFF, joined_on=date(2024, 1, 10), bonus_label="Eid-ul-Adha bonus"
    )
    r = calc.calculate(long_served, RULES)
    assert lines(r)["bonus"] == 2_000_000
    assert r.lines[-1].label == "Eid-ul-Adha bonus"
    new = calc.calculate(
        calc.Inputs(
            period="2026-06", structure=STAFF, joined_on=date(2026, 1, 10), bonus_label="Eid-ul-Adha bonus"
        ),
        RULES,
    )
    assert "bonus" not in lines(new)
    assert calc.months_of_service(date(2025, 6, 30), date(2026, 6, 29)) == 11
    assert calc.months_of_service(date(2025, 6, 30), date(2026, 6, 30)) == 12


def test_deductions_larger_than_pay_carry_forward() -> None:
    intern = calc.Structure(basic=5_000 * TK)
    r = calc.calculate(
        calc.Inputs(
            period="2026-06",
            structure=intern,
            loans=[calc.LoanDue("a", "Advance", 8_000 * TK, 10_000 * TK)],
        ),
        RULES,
    )
    assert (r.gross, r.deductions, r.net, r.carried_forward) == (500_000, 800_000, 0, 300_000)
    # An installment never takes more than what's left of the loan.
    small = calc.calculate(
        calc.Inputs(
            period="2026-06", structure=STAFF, loans=[calc.LoanDue("b", "Loan", 5_000 * TK, 1_200 * TK)]
        ),
        RULES,
    )
    assert lines(small)["loan"] == 1_200 * TK


def test_net_is_rounded_to_whole_taka() -> None:
    odd = calc.Structure(basic=3_333_350)
    r = calc.calculate(calc.Inputs(period="2026-06", structure=odd), RULES)
    assert lines(r)["rounding"] == 50
    assert r.net == 3_333_400
    exact = calc.calculate(calc.Inputs(period="2026-06", structure=odd), calc.Rules(round_net=False))
    assert exact.net == 3_333_350


def test_bangladesh_salary_tax() -> None:
    table = defaults.BANGLADESH_TAX
    assert calc.annual_tax(300_000 * TK, table) == 0
    # 600,000: a third is exempt, 400,000 taxable, 25,000 over the tax-free amount at 10%
    # is 2,500, raised to the minimum of 5,000.
    assert calc.annual_tax(600_000 * TK, table) == 5_000 * TK
    # 1,200,000: 400,000 exempt, 800,000 - 375,000 = 425,000: 30,000 + 18,750.
    assert calc.annual_tax(1_200_000 * TK, table) == 48_750 * TK
    # 3,000,000: exemption capped at 500,000; 2,125,000 over the tax-free amount.
    assert calc.annual_tax(3_000_000 * TK, table) == (30_000 + 60_000 + 100_000 + 231_250) * TK
    # A higher tax-free amount (e.g. women and people over 65).
    assert calc.annual_tax(800_000 * TK, table, tax_free_override=600_000 * TK) == 0


def test_tax_is_deducted_monthly_when_switched_on() -> None:
    taxed = calc.Rules(tax=defaults.BANGLADESH_TAX)
    manager = calc.Structure(
        basic=60_000 * TK, house_rent=30_000 * TK, medical=6_000 * TK, conveyance=4_000 * TK
    )
    r = calc.calculate(calc.Inputs(period="2026-06", structure=manager), taxed)
    yearly = 100_000 * 12 + 60_000 * 2
    assert lines(r)["tax"] == calc.money(Decimal(calc.annual_tax(yearly * TK, defaults.BANGLADESH_TAX)) / 12)
    exempt = calc.calculate(
        calc.Inputs(period="2026-06", structure=calc.Structure(basic=60_000 * TK, deduct_tax=False)), taxed
    )
    assert "tax" not in lines(exempt)


def test_zero_salary_is_a_zero_payslip() -> None:
    r = calc.calculate(calc.Inputs(period="2026-06", structure=calc.Structure()), RULES)
    assert (r.lines, r.gross, r.net) == ([], 0, 0)


# ---- Invariants ----------------------------------------------------------------------------

amounts = st.integers(min_value=0, max_value=50_000_000)


@st.composite
def payroll_inputs(draw: st.DrawFn) -> tuple[calc.Inputs, calc.Rules]:
    year = draw(st.integers(2024, 2030))
    month = draw(st.integers(1, 12))
    start, end = calc.period_bounds(f"{year:04d}-{month:02d}")
    days = (end - start).days + 1
    structure = calc.Structure(
        pay_rule=draw(st.sampled_from(["monthly", "hourly", "daily"])),
        basic=draw(amounts),
        house_rent=draw(amounts),
        medical=draw(amounts),
        conveyance=draw(amounts),
        other=draw(amounts),
        rate=draw(st.integers(0, 500_000)),
        overtime=draw(st.booleans()),
        deduct_tax=draw(st.booleans()),
    )
    worked = draw(
        st.dictionaries(
            st.integers(0, days - 1).map(lambda i: start + timedelta(days=i)),
            st.integers(0, 16 * 60),
            max_size=31,
        )
    )
    joined = draw(st.none() | st.integers(-400, days - 1).map(lambda i: start + timedelta(days=i)))
    left = draw(st.none() | st.integers(0, days + 30).map(lambda i: start + timedelta(days=i)))
    if joined and left and left < joined:
        left = None
    loans = [
        calc.LoanDue(str(i), "Loan", draw(st.integers(1, 9_000_000)), draw(st.integers(1, 9_000_000)))
        for i in range(draw(st.integers(0, 3)))
    ]
    items = [
        calc.Item(draw(st.sampled_from(["earning", "deduction"])), "Item", draw(st.integers(1, 5_000_000)))
        for _ in range(draw(st.integers(0, 3)))
    ]
    inputs = calc.Inputs(
        period=f"{year:04d}-{month:02d}",
        structure=structure,
        joined_on=joined,
        left_on=left,
        unpaid_leave_days=Decimal(draw(st.integers(0, 62))) / 2,
        worked=worked,
        bonus_label=draw(st.none() | st.just("Bonus")),
        loans=loans,
        items=items,
    )
    rules = calc.Rules(
        day_basis=draw(st.sampled_from(["calendar", "thirty"])),
        round_net=draw(st.booleans()),
        unit=draw(st.sampled_from([1, 100])),
        tax=draw(st.none() | st.just(defaults.BANGLADESH_TAX)),
    )
    return inputs, rules


@settings(max_examples=400, deadline=None)
@given(payroll_inputs())
def test_payslip_invariants(case: tuple[calc.Inputs, calc.Rules]) -> None:
    inputs, rules = case
    r = calc.calculate(inputs, rules)
    earnings = sum(line.amount for line in r.lines if line.kind == "earning")
    deductions = sum(line.amount for line in r.lines if line.kind == "deduction")
    assert r.gross == earnings
    assert r.deductions == deductions
    assert r.net == max(r.gross - r.deductions, 0)
    assert r.carried_forward == max(r.deductions - r.gross, 0)
    assert r.gross >= 0
    assert all(line.amount > 0 for line in r.lines if line.code != "rounding")
    assert sum(1 for line in r.lines if line.code == "rounding") <= 1
    if rules.round_net and r.net > 0:
        assert r.net % rules.unit == 0
    assert 0 <= r.payable_days <= r.days_in_period
    for loan, line in zip(inputs.loans, [x for x in r.lines if x.code == "loan"], strict=False):
        assert line.amount <= min(loan.installment, loan.outstanding)
