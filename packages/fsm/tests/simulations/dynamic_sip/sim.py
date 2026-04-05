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
    """Prepare context at start of each day: accrue interest, add SIP."""
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
    """Check if we have enough cash to buy at least one unit."""
    nav = ev.payload.nav
    return nav > 0 and floor(ctx.cash / nav) >= 1


def cooldown_elapsed(ctx: Portfolio, ev: Event) -> bool:
    """21-day cooldown between deployments."""
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


# -----------
# State Chart
# -----------

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
    return Machine[Portfolio](
        initial="accumulating",
        context=ctx,
        states=STATES,
        on_unhandled=UnhandledPolicy.RAISE,
        prepare=daily_bookkeeping,
    )
