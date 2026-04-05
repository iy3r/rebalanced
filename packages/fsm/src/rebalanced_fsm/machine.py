from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, TypeAlias, TypeVar

ContextT = TypeVar("ContextT")
Guard: TypeAlias = Callable[[Any, "Event"], bool]
Action: TypeAlias = Callable[[Any, "Event"], Any]


class FSMError(Exception):
    """Base for all FSM errors."""


class InvalidMachineError(FSMError, ValueError):
    """Machine definition is structurally invalid."""

    def __init__(self, message: str, *, state: Hashable | None = None) -> None:
        super().__init__(message)
        self.state = state


class TransitionRejected(FSMError):
    """Raised when a specific transition condition fails."""

    def __init__(
        self,
        message: str,
        *,
        state: Hashable,
        event: "Event",
        reason: str,
        guard: Guard | None = None,
    ) -> None:
        super().__init__(message)
        self.state = state
        self.event = event
        self.reason = reason  # "no_transition", "guard_failed", "final_state"
        self.guard = guard


class UnhandledEventError(FSMError, LookupError):
    """No transition matched and policy is RAISE."""

    def __init__(
        self,
        message: str,
        *,
        state: Hashable,
        event: "Event",
    ) -> None:
        super().__init__(message)
        self.state = state
        self.event = event


def _always(_ctx: Any, _ev: "Event") -> bool:
    return True


def _identity(ctx: Any, _ev: "Event") -> Any:
    return ctx


@dataclass(frozen=True, slots=True, match_args=True)
class Event:
    kind: Hashable
    payload: Any = None

    def __repr__(self) -> str:
        if self.payload is None:
            return f"Event({self.kind!r})"
        return f"Event({self.kind!r}, {self.payload!r})"


@dataclass(frozen=True, slots=True, match_args=True)
class Transition:
    target: Hashable
    guard: Guard = field(default=_always, compare=False)
    action: Action = field(default=_identity, compare=False)
    internal: bool = False

    def when(self, guard: Guard) -> "Transition":
        return Transition(
            target=self.target,
            guard=guard,
            action=self.action,
            internal=self.internal,
        )

    def then(self, action: Action) -> "Transition":
        return Transition(
            target=self.target,
            guard=self.guard,
            action=action,
            internal=self.internal,
        )

    def internal_only(self) -> "Transition":
        return Transition(
            target=self.target,
            guard=self.guard,
            action=self.action,
            internal=True,
        )


_TransitionMap: TypeAlias = Mapping[Hashable, tuple[Transition, ...]]


@dataclass(frozen=True, slots=True, match_args=True)
class State:
    on: Mapping[Hashable, Transition | Sequence[Transition]] = field(
        default_factory=dict,
    )
    enter: Action = field(default=_identity, compare=False)
    leave: Action = field(default=_identity, compare=False)
    final: bool = False


@dataclass(frozen=True, slots=True, match_args=True)
class _CompiledState:
    on: _TransitionMap
    enter: Action = field(default=_identity, compare=False)
    leave: Action = field(default=_identity, compare=False)
    final: bool = False


def _normalize(
    on: Mapping[Hashable, Transition | Sequence[Transition]],
) -> _TransitionMap:
    return {k: (v,) if isinstance(v, Transition) else tuple(v) for k, v in on.items()}


def _compile(
    raw: Mapping[str, State] | Mapping[Hashable, State],
    initial: Hashable,
) -> MappingProxyType[Hashable, _CompiledState]:
    if initial not in raw:
        raise InvalidMachineError(
            f"Unknown initial state: {initial!r}",
            state=initial,
        )

    compiled: dict[Hashable, _CompiledState] = {}
    for name, s in raw.items():
        if not isinstance(s, State):
            raise TypeError(f"{name!r}: expected State, got {type(s).__name__}")
        if s.final and s.on:
            raise InvalidMachineError(
                f"Final state {name!r} must not have transitions",
                state=name,
            )
        if not s.final and not s.on:
            raise InvalidMachineError(
                f"Non-final state {name!r} has no transitions (trap)",
                state=name,
            )
        compiled[name] = _CompiledState(
            on=_normalize(s.on),
            enter=s.enter,
            leave=s.leave,
            final=s.final,
        )

    for src, s in compiled.items():
        for kind, transitions in s.on.items():
            for t in transitions:
                if t.target not in compiled:
                    raise InvalidMachineError(
                        f"{src!r} on {kind!r}: unknown target {t.target!r}",
                        state=src,
                    )
                if t.internal and t.target != src:
                    raise InvalidMachineError(
                        f"{src!r} on {kind!r}: internal must self-target, "
                        f"got {t.target!r}",
                        state=src,
                    )

    seen: set[Hashable] = {initial}
    queue = [initial]
    while queue:
        for ts in compiled[queue.pop()].on.values():
            for t in ts:
                if t.target not in seen:
                    seen.add(t.target)
                    queue.append(t.target)

    unreachable = set(compiled) - seen
    if unreachable:
        names = ", ".join(sorted(map(repr, unreachable)))
        raise InvalidMachineError(
            f"Unreachable from {initial!r}: {names}",
            state=initial,
        )

    return MappingProxyType(compiled)


class UnhandledPolicy(StrEnum):
    IGNORE = "ignore"
    RAISE = "raise"


class Machine[ContextT]:
    __slots__ = ("_states", "_state", "_context", "_on_unhandled", "_prepare")

    def __init__(
        self,
        *,
        initial: Hashable,
        context: ContextT,
        states: Mapping[str, State] | Mapping[Hashable, State],
        on_unhandled: UnhandledPolicy = UnhandledPolicy.IGNORE,
        prepare: Action | None = None,
    ) -> None:
        self._states = _compile(states, initial)
        self._state = initial
        self._context = context
        self._on_unhandled = on_unhandled
        self._prepare = prepare

    @property
    def state(self) -> Hashable:
        return self._state

    @property
    def context(self) -> ContextT:
        return self._context

    @property
    def is_done(self) -> bool:
        return self._states[self._state].final

    def can(self, event: Event) -> bool:
        for t in self._states[self._state].on.get(event.kind, ()):
            if t.guard(self._context, event):
                return True
        return False

    def send(self, event: Event) -> bool:
        ctx = self._prepare(self._context, event) if self._prepare else self._context
        state_def = self._states[self._state]

        if state_def.final:
            self._context = ctx  # type: ignore[assignment]
            return False

        for t in state_def.on.get(event.kind, ()):
            if not t.guard(ctx, event):
                continue

            if not t.internal:
                ctx = state_def.leave(ctx, event)
            ctx = t.action(ctx, event)
            if not t.internal:
                ctx = self._states[t.target].enter(ctx, event)

            self._state = t.target
            self._context = ctx  # type: ignore[assignment]
            return True

        if self._on_unhandled is UnhandledPolicy.RAISE:
            raise UnhandledEventError(
                f"No transition for {event.kind!r} in state {self._state!r}",
                state=self._state,
                event=event,
            )
        self._context = ctx  # type: ignore[assignment]
        return False

    def __repr__(self) -> str:
        return f"Machine(state={self._state!r})"
