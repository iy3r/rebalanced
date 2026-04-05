from datetime import date

from rebalanced_fsm import Event

from .conftest import SIM_END, SIM_START, MarketDay
from .sim import MONTHLY_SIP, Portfolio, build_machine


def _days_since_epoch(d: date) -> int:
    return (d - date(1970, 1, 1)).days


def _xirr_rate(
    cashflows: list[tuple[int, float]], guess: float = 0.1, max_iter: int = 100
) -> float | None:
    rate = guess
    for _ in range(max_iter):
        npv = 0.0
        dnpv = 0.0
        for days, cf in cashflows:
            t = days / 365.0
            discount = (1 + rate) ** t
            npv += cf / discount
            dnpv += -t * cf / (discount * (1 + rate))
        if abs(npv) < 1e-10:
            return rate
        if abs(dnpv) < 1e-15:
            return None
        rate = rate - npv / dnpv
        if rate <= -1:
            return None
    return None


def _calculate_xirr(
    portfolio: Portfolio,
    start_date: date,
    end_date: date,
    final_nav: float,
) -> tuple[float | None, dict]:
    cashflows: list[tuple[int, float]] = []

    current = start_date
    total_sip = 0.0
    while current <= end_date:
        days = _days_since_epoch(current)
        cashflows.append((days, -MONTHLY_SIP))
        total_sip += MONTHLY_SIP
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    final_days = _days_since_epoch(end_date)
    final_value = portfolio.market_value(final_nav)
    cashflows.append((final_days, final_value))

    xirr = _xirr_rate(cashflows)

    metrics = {
        "xirr": xirr,
        "total_sip": total_sip,
        "final_value": final_value,
        "units": portfolio.units,
        "residual_cash": portfolio.cash,
        "deploy_count": len(portfolio.deploy_log),
    }

    return xirr, metrics


def test_dynamic_sip_xirr(market_days: list[MarketDay]) -> None:
    ctx = Portfolio()
    machine = build_machine(ctx)

    final_nav = 0.0
    for day in market_days:
        final_nav = day.nav
        machine.send(Event("next_day", day))

    machine.send(Event("end", None))

    final_portfolio: Portfolio = machine.context
    xirr, metrics = _calculate_xirr(final_portfolio, SIM_START, SIM_END, final_nav)

    # Print metrics for debugging/verification
    print(f"\nDynamic SIP Results ({SIM_START} to {SIM_END}):")
    if metrics["xirr"] is not None:
        print(f"  XIRR: {metrics['xirr'] * 100:.2f}%")
    else:
        print("  XIRR: None")
    print(f"  Total SIP: ₹{metrics['total_sip']:,.0f}")
    print(f"  Final Value: ₹{metrics['final_value']:,.0f}")
    print(f"  Units Held: {metrics['units']:,}")
    print(f"  Residual Cash: ₹{metrics['residual_cash']:,.0f}")
    print(f"  Deploy Events: {metrics['deploy_count']}")

    # Assertions
    assert xirr is not None, "XIRR should converge"
    assert xirr > 0, "Strategy should have positive return"
    assert metrics["units"] > 0, "Should have purchased units"
    assert metrics["final_value"] > metrics["total_sip"] * 0.5, (
        "Should retain significant value"
    )

    assert round(xirr, 4) == 0.1099, f"XIRR {xirr * 100:.2f}% expected was 10.99%"
