# rebalanced-fsm

A small, data-first finite state machine for Python 3.14+. Typed, immutable, and fluent.

## Install

```bash
pip install rebalanced-fsm
```

## Basics

```python
from dataclasses import dataclass
from rebalanced_fsm import Machine, State, Transition, Event

@dataclass
class Account:
    balance: float = 0

m = Machine[Account](
    initial="empty",
    context=Account(),
    states={
        "empty": State(on={"deposit": Transition("funded").then(
            lambda ctx, ev: Account(ctx.balance + ev.payload["amount"])
        )}),
        "funded": State(on={"withdraw": Transition("empty").when(
            lambda ctx, ev: ctx.balance >= ev.payload["amount"]
        ).then(
            lambda ctx, ev: Account(ctx.balance - ev.payload["amount"])
        )}, final=True),
    },
)

m.send(Event("deposit", {"amount": 100}))
print(m.state, m.context.balance)  # funded 100
```

## Concepts

**Type-safe context**
```python
Machine[Portfolio](...)  # mypy/pyright knows context is Portfolio
```

**Guards**
```python
from rebalanced_fsm import where

has_cash = where(lambda ctx, ev: ctx.cash >= ev.payload["cost"])
many_shares = where(lambda ctx, ev: ctx.shares > 100)

# Compose with &, |, ~
Transition("buy").when(has_cash & ~many_shares)
```

**Fluent transitions**
```python
Transition("armed") \
    .when(rsi_low) \
    .then(deploy_cash)

# Internal transitions skip enter/leave hooks
Transition("self").internal_only()
```

**Final states**
```python
"done": State(final=True)  # accepts no events
```

**Error handling**
```python
from rebalanced_fsm import UnhandledPolicy

m = Machine(..., on_unhandled=UnhandledPolicy.RAISE)
# m.send(Event("unknown"))  # UnhandledEventError
```

## License

Apache 2.0 - see [root LICENSE](../../LICENSE)
