"""Scope-filtered, coalescing mailboxes for completed component state changes.

Mailboxes contain invalidation keys, not state snapshots or an event history.
Subscribers read the current state after draining their mailbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Condition, RLock
from typing import TYPE_CHECKING, Iterable
from weakref import WeakSet, ref

from ..protocol.constants import CommandScope

if TYPE_CHECKING:
    from .component_state import ComponentState


@dataclass(frozen=True)
class StateChange:
    scope: CommandScope
    address: int


class StateChangeSubscription:
    """One consumer's mailbox; repeated changes occupy one pending entry per entity.

    ``wait`` claims one wakeup until ``drain`` consumes it. This allows event-loop
    bridges to queue a single delivery while additional changes accumulate.
    """

    def __init__(self, hub: StateChangeHub, scopes: frozenset[CommandScope]) -> None:
        self.scopes = scopes
        self._hub = hub
        self._condition = Condition()
        self._pending: set[StateChange] = set()
        self._closed = False
        self._wakeup_pending = False

    @property
    def pending_count(self) -> int:
        with self._condition:
            return len(self._pending)

    @property
    def closed(self) -> bool:
        with self._condition:
            return self._closed

    def wait(self, timeout: float | None = None) -> bool:
        """Block for one delivery opportunity; return false on close or timeout."""
        with self._condition:
            ready = self._condition.wait_for(
                lambda: self._closed or (bool(self._pending) and not self._wakeup_pending), timeout
            )
            if not ready or self._closed:
                return False
            self._wakeup_pending = True
            return True

    def drain(self) -> frozenset[StateChange]:
        """Take the pending identifiers and permit the next wakeup."""
        with self._condition:
            changes = frozenset(self._pending)
            self._pending.clear()
            self._wakeup_pending = False
            self._condition.notify_all()
            return changes

    def close(self) -> None:
        self._hub.unsubscribe(self)

    def _enqueue(self, change: StateChange) -> None:
        with self._condition:
            if not self._closed:
                self._pending.add(change)
                self._condition.notify_all()

    def _close(self) -> None:
        with self._condition:
            self._closed = True
            self._pending.clear()
            self._condition.notify_all()


class StateChangeHub:
    """Fan out invalidations only to live subscribers; retain no global backlog."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._subscriptions: WeakSet[StateChangeSubscription] = WeakSet()

    def subscribe(self, scopes: Iterable[CommandScope]) -> StateChangeSubscription:
        subscription = StateChangeSubscription(self, frozenset(scopes))
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: StateChangeSubscription) -> None:
        with self._lock:
            self._subscriptions.discard(subscription)
            subscription._close()

    def publish(self, scope: CommandScope, address: int | None) -> None:
        """Enqueue identifiers without callbacks, state references, or consumer waits."""
        if address is None:
            return
        with self._lock:
            for subscription in tuple(self._subscriptions):
                if scope in subscription.scopes:
                    subscription._enqueue(StateChange(scope, address))


state_changes = StateChangeHub()


class StateChangeCondition(Condition):
    """Preserve Condition wakeups and additionally invalidate scope subscribers.

    Route dependency propagation and existing StateWatchers continue to use their
    original notify_all calls. Notifications are invalidations, so a wakeup that
    does not mutate state (such as watcher shutdown) is harmless to consumers.
    """

    def __init__(self, state: ComponentState) -> None:
        super().__init__(RLock())
        self._state_ref = ref(state)

    def notify_all(self) -> None:
        super().notify_all()
        state = self._state_ref()
        if state is not None:
            state_changes.publish(state.scope, state.address)
