import threading
import time

from src.pytrain.db.accessory_state import AccessoryState
from src.pytrain.db.state_watcher import StateWatcher
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum as Aux


class TestStateWatcher:
    @staticmethod
    def _new_accessory(addr: int = 42) -> AccessoryState:
        st = AccessoryState(CommandScope.ACC)
        # Ensure component data is initialized so synchronizer/condition exists and address is set
        st.initialize(CommandScope.ACC, addr)
        # Keep address deterministic for any address-dependent paths
        st._address = addr  # type: ignore[attr-defined]

        return st

    def test_watched_property_and_action_delegate(self):
        acc = self._new_accessory(9)
        called = {"n": 0}

        def action():
            called["n"] += 1

        watcher = StateWatcher(acc, action)
        try:
            # watched property returns the same state
            assert watcher.watched is acc

            # action method should call our handler
            watcher.action()
            assert called["n"] == 1
        finally:
            watcher.shutdown()
            watcher.join(timeout=1)

    def test_triggers_action_on_accessory_update(self):
        acc = self._new_accessory(12)
        evt = threading.Event()
        calls = {"n": 0}

        def action():
            calls["n"] += 1
            evt.set()

        watcher = StateWatcher(acc, action)
        try:
            # Cause a state update that should notify the watcher threads
            acc.update(CommandReq.build(Aux.AUX1_ON, acc.address))

            # Wait for action to be called
            assert evt.wait(timeout=2.0), "Watcher action did not trigger after state update"
            assert calls["n"] >= 1

            # Also validate that AccessoryState actually updated aux state
            assert acc.aux1_state in {Aux.AUX1_ON, Aux.AUX1_OPT_ONE}
            assert acc.aux_state in {Aux.AUX1_OPT_ONE, Aux.AUX2_OPT_ONE, None}  # impl detail may toggle/set

        finally:
            watcher.shutdown()
            watcher.join(timeout=1)

    def test_multiple_updates_collapse_to_calls_and_shutdown_stops_processing(self):
        acc = self._new_accessory(21)
        calls = {"n": 0}
        lock = threading.Lock()
        evt = threading.Event()

        def action():
            with lock:
                calls["n"] += 1
            evt.set()

        watcher = StateWatcher(acc, action)
        try:
            # Burst of updates; notifier should coalesce queue entries per processing cycle.
            for _ in range(5):
                req = CommandReq.build(Aux.AUX2_OFF, acc.address)
                acc.update(req)
            # Wait for at least one action call
            assert evt.wait(timeout=2.0), "Watcher did not trigger on burst updates"
            evt.clear()

            with lock:
                call_count_after_burst = calls["n"]
            assert call_count_after_burst >= 1

            # Now stop the watcher
            watcher.shutdown()
            watcher.join(timeout=2)

            # Further updates should not trigger action anymore
            before = calls["n"]
            acc.update(CommandReq.build(Aux.NUMERIC, acc.address, data=3))
            time.sleep(0.2)
            assert calls["n"] == before, "Action should not be called after watcher shutdown"
        finally:
            # Ensure shutdown even on assertion errors without broad exception catching
            if watcher.is_alive():
                watcher.shutdown()
                watcher.join(timeout=1)

    def test_shutdown_is_idempotent_and_notifier_unblocks(self):
        acc = self._new_accessory(7)
        evt = threading.Event()

        def action():
            # Just mark that the thread was active at least once.
            evt.set()

        watcher = StateWatcher(acc, action)
        try:
            # Trigger one update so threads are active
            acc.update(CommandReq.build(Aux.AUX1_OPT_ONE, acc.address))
            evt.wait(timeout=2.0)

            # Call shutdown twice; should not raise and should not hang
            watcher.shutdown()
            watcher.shutdown()
            watcher.join(timeout=2)
            assert not watcher.is_alive()
        finally:
            if watcher.is_alive():
                watcher.shutdown()
                watcher.join(timeout=1)
