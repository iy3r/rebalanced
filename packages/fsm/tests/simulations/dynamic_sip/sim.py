"""Dynamic SIP Simulation: Buy when market is oversold (RSI < 33).

WHAT IT DOES
------------
This simulates a systematic investment strategy that accumulates cash in a liquid
fund and deploys into NIFTYBEES only when the RSI indicates oversold conditions
(< 33), with a 21-day cooldown between deployments.

THE FOUR STATES
---------------
1. ACCUMULATING: Cash builds up in liquid fund (earning ~6% annually). 
   Wait for RSI < 33 to transition to ARMED.

2. ARMED: RSI < 33 and we can buy at least one unit. Deploy all cash into
   equity immediately, then move to COOLDOWN.

3. COOLDOWN: 21-day mandatory wait. If RSI still < 33 after 21 days → ARMED.
   Otherwise → ACCUMULATING.

4. DONE: Simulation complete. Calculate XIRR for performance measurement.

KEY PARAMETERS
--------------
- MONTHLY_SIP: ₹10,000 fresh inflow at each month start
- LIQUID_ANNUAL: ~6% interest earned on uninvested cash
- RSI_THRESHOLD: < 33 triggers deployment opportunity
- COOLDOWN_DAYS: 21 days minimum between deployments

The simulation runs April 2006 - March 2026 (20 years) and computes annualized
returns (XIRR) for performance analysis.
"""

from dataclasses import dataclass, replace
from math import floor
from typing import NamedTuple

from rebalanced_fsm import Event, Machine, State, Transition, UnhandledPolicy, where

MONTHLY_SIP = 10_000.0
LIQUID_ANNUAL = 0.06
LIQUID_DAILY = (1 + LIQUID_ANNUAL) ** (1 / 365) - 1
RSI_THRESHOLD = 33
COOLDOWN_DAYS = 21


class DeployEntry(NamedTuple):
    day_idx: int
    nav: float
    units: int
    amount: float


@dataclass(frozen=True, slots=True)
class Portfolio:
    cash: float = 0.0
    units: int = 0
    last_deploy_day_idx: int | None = None
    deploy_log: tuple[DeployEntry, ...] = ()

    def market_value(self, nav: float) -> float:
        return self.cash + (self.units * nav)


# ---------
# Lifecycle
# ---------


def daily_bookkeeping(ctx: Portfolio, ev: Event) -> Portfolio:
    """Accrue daily interest on cash, add monthly SIP inflows."""
    if ev.kind != "next_day":
        return ctx
    cash = ctx.cash * (1 + LIQUID_DAILY)
    if ev.payload.is_month_start:
        cash += MONTHLY_SIP
    return replace(ctx, cash=cash)


# ------
# Guards
# ------


def rsi_below_threshold(ctx: Portfolio, ev: Event) -> bool:
    """RSI < 33 indicates oversold condition."""
    rsi = ev.payload.rsi
    return rsi is not None and rsi < RSI_THRESHOLD


def can_buy_at_least_one_unit(ctx: Portfolio, ev: Event) -> bool:
    """Check sufficient cash to buy minimum one unit at current NAV."""
    nav = ev.payload.nav
    return nav > 0 and floor(ctx.cash / nav) >= 1


def cooldown_elapsed(ctx: Portfolio, ev: Event) -> bool:
    """21-day minimum between deployments."""
    if ctx.last_deploy_day_idx is None:
        return True
    return ev.payload.day_idx - ctx.last_deploy_day_idx >= COOLDOWN_DAYS


# --------
# Actions
# --------


def deploy_cash(ctx: Portfolio, ev: Event) -> Portfolio:
    """Deploy all available cash to buy units at current NAV."""
    nav = ev.payload.nav
    units_to_buy = floor(ctx.cash / nav)
    deploy_amount = units_to_buy * nav

    entry = DeployEntry(
        day_idx=ev.payload.day_idx,
        nav=nav,
        units=units_to_buy,
        amount=deploy_amount,
    )
    return replace(
        ctx,
        cash=ctx.cash - deploy_amount,
        units=ctx.units + units_to_buy,
        last_deploy_day_idx=ev.payload.day_idx,
        deploy_log=ctx.deploy_log + (entry,),
    )


# -------------------------------
# State Chart (Fluent Style)
# -------------------------------

# Reusable guard combinations
rsi_and_cash = where(rsi_below_threshold) & where(can_buy_at_least_one_unit)
cooldown_and_rsi_and_cash = where(cooldown_elapsed) & rsi_and_cash


STATES = {
    "accumulating": State(
        on={
            "next_day": [
                Transition("armed").when(rsi_and_cash),
                Transition("accumulating").internal_only(),
            ],
            "end": Transition("done"),
        },
    ),
    "armed": State(
        on={
            "next_day": [
                Transition("cooldown")
                    .when(where(can_buy_at_least_one_unit))
                    .then(deploy_cash),
                Transition("armed").internal_only(),
            ],
            "end": Transition("done"),
        },
    ),
    "cooldown": State(
        on={
            "next_day": [
                Transition("armed").when(cooldown_and_rsi_and_cash),
                Transition("accumulating").when(where(cooldown_elapsed)),
                Transition("cooldown").internal_only(),
            ],
            "end": Transition("done"),
        },
    ),
    "done": State(final=True),
}


def build_machine(ctx: Portfolio) -> Machine[Portfolio]:
    """Build a type-safe FSM for the dynamic SIP strategy."""
    return Machine[Portfolio](
        initial="accumulating",
        context=ctx,
        states=STATES,
        on_unhandled=UnhandledPolicy.RAISE,
        prepare=daily_bookkeeping,
    )
