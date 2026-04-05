from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Never, Self, overload

from .machine import Event


@dataclass(frozen=True, slots=True)
class Condition:
    fn: Callable[[Any, Event], bool]
    desc: str = "?"

    def __call__(self, context: Any, event: Event) -> bool:
        return self.fn(context, event)

    def __and__(self, other: Self) -> Condition:
        return Condition(
            lambda ctx, ev: self(ctx, ev) and other(ctx, ev),
            f"({self.desc} & {other.desc})",
        )

    def __or__(self, other: Self) -> Condition:
        return Condition(
            lambda ctx, ev: self(ctx, ev) or other(ctx, ev),
            f"({self.desc} | {other.desc})",
        )

    def __invert__(self) -> Condition:
        return Condition(
            lambda ctx, ev: not self(ctx, ev),
            f"~{self.desc}",
        )

    def __bool__(self) -> Never:
        raise TypeError(
            f"Condition({self.desc!r}) used in boolean context; "
            f"call it: condition(ctx, event)"
        )

    def __repr__(self) -> str:
        return f"Condition({self.desc})"


@overload
def where(fn: Callable[[Any, Event], bool], /) -> Condition: ...


@overload
def where(*, desc: str) -> Callable[[Callable[[Any, Event], bool]], Condition]: ...


def where(
    fn: Callable[[Any, Event], bool] | None = None,
    /,
    *,
    desc: str = "",
) -> Condition | Callable[[Callable[[Any, Event], bool]], Condition]:
    def _wrap(f: Callable[[Any, Event], bool]) -> Condition:
        return Condition(fn=f, desc=desc or getattr(f, "__name__", "?"))

    if fn is not None:
        return _wrap(fn)
    return _wrap
