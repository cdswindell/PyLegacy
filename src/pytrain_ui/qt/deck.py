"""Steam Deck profile routing for two independent Qt cab workspaces.

Only the toolkit-neutral profile/provider/router is shared with the older frontend.
No Tk application or accessory GUI classes are constructed here.
"""

from __future__ import annotations

import json
import logging
import time

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Property, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QMouseEvent
from PySide6.QtQml import QQmlEngine, QQmlExpression

from pytrain.gui.controller.steam_deck_input import ControlProfile, DeckInputRouter, SteamDeckInputProvider
from pytrain.protocol.command_req import CommandReq

log = logging.getLogger(__name__)


class QtDeckPane:
    """Translate the existing semantic Deck bindings into Qt controllers."""

    def __init__(self, controllers: dict) -> None:
        self.controllers = controllers
        self.workspace = None
        self._pending_speed = None
        self._sensor_choice = None
        self._held_relay = None
        self.host = None
        self._admin_press = None

    @property
    def cab(self):
        return self.controllers["cabController"]

    def evaluate(self, source):
        if self.workspace is None:
            return None
        # The first visual child belongs to CabWorkspace's component context,
        # which contains its private IDs; the instance itself has the host context.
        context = QQmlEngine.contextForObject(self.workspace.childItems()[0])
        expression = QQmlExpression(context, self.workspace, source)
        result = expression.evaluate()
        if expression.hasError():
            log.warning("Steam Deck workspace action failed: %s", expression.error().toString())
            return None
        return result[0] if isinstance(result, tuple) else result

    @property
    def input_state(self):
        value = self.evaluate("JSON.stringify(window.controllerInputState)")
        return json.loads(value) if value else {}

    @property
    def popup_visible(self):
        return self.input_state.get("blocked", False)

    def close_popup(self):
        self.evaluate("window.requestEditorExit(function() { window.closeOpenPanels(); cabMenu.close(); })")

    @property
    def admin_visible(self):
        return self.input_state.get("manage", False)

    def on_admin_command(self, command, pressed):
        if not pressed:
            self._release_admin_press()
            return
        if not self.admin_visible or self.workspace is None or self._admin_press is not None:
            return
        button = self.workspace.findChild(QObject, "adminCommand-" + command)
        if button is None or not button.isVisible() or not button.isEnabled():
            return
        ancestor = button.parentItem()
        while ancestor is not None:
            if ancestor.property("contentY") is not None:
                center = button.mapToItem(ancestor, button.boundingRect().center()).y()
                maximum = max(0, ancestor.property("contentHeight") - ancestor.height())
                ancestor.setProperty(
                    "contentY", max(0, min(maximum, ancestor.property("contentY") + center - ancestor.height() / 2))
                )
            ancestor = ancestor.parentItem()
        point = button.mapToScene(button.boundingRect().center())
        self._admin_press = (self.workspace.window(), point)
        self._send_admin_press(QEvent.Type.MouseButtonPress)

    def _send_admin_press(self, event_type):
        window, point = self._admin_press
        buttons = Qt.MouseButton.LeftButton if event_type == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton
        event = QMouseEvent(
            event_type, point, point, Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier
        )
        QCoreApplication.sendEvent(window, event)

    def _release_admin_press(self):
        if self._admin_press is not None:
            self._send_admin_press(QEvent.Type.MouseButtonRelease)
            self._admin_press = None

    @property
    def controls_visible(self):
        return self.host is not None and self.host.controlsVisible

    def close_controls(self):
        self.host.closeControls()

    def page_controls(self, forward):
        self.host.helpPageRequested.emit(1 if forward else -1)

    @property
    def catalog_visible(self):
        return self.input_state.get("catalog", False)

    @property
    def input_contexts(self):
        state = self.input_state
        if state.get("blocked"):
            return ("acc",)  # Claim command bindings while an editor/menu is active.
        scope = state.get("scope")
        if scope == "SWITCH":
            return ("switch",)
        if scope == "ROUTE":
            return ("route",)
        if scope == "ACCESSORY":
            accessory = state.get("accessory", {})
            kind = "TMCC" if accessory.get("sharedCommandAddress") else accessory.get("kind", "")
            return {
                "TMCC": ("acc_generic", "acc"),
                "ASC2": ("acc_asc2", "acc_bpc2", "acc"),
                "BPC2": ("acc_bpc2", "acc"),
                "SENSOR": ("acc_sensor_track", "acc"),
            }.get(kind, ("acc",))
        return ()

    @property
    def switch_active(self):
        return self.input_state.get("scope") == "SWITCH"

    @property
    def route_active(self):
        return self.input_state.get("scope") == "ROUTE"

    @property
    def throttle_state(self):
        # Read-only state is the existing router's throttle input contract.
        return self.cab._state_port.state if self.cab._state_port is not None else None

    @property
    def throttle_generation(self):
        return self.cab._target_generation

    def nudge_throttle(self, delta):
        if self.input_state.get("blocked") or self.catalog_visible:
            return None
        current = self.cab.targetSpeed if self._pending_speed is None else self._pending_speed
        self._pending_speed = max(0, min(self.cab.speedMax, current + delta))
        return self._pending_speed

    def commit_throttle(self, target=None):
        if not self.input_state.get("blocked") and not self.catalog_visible:
            value = self._pending_speed if target is None else target
            if value is not None:
                self.cab.setSpeed(round(value))

    def clear_throttle(self):
        self._pending_speed = None

    def on_speed_command(self, value):
        if not self.input_contexts and not self.catalog_visible:
            self.cab.setSpeed(value)

    def on_engine_command(self, commands, data=0):
        if self.input_contexts or self.catalog_visible:
            return
        adapter = self.cab._command_port
        if adapter is None:
            return
        for name in [commands] if isinstance(commands, str) else commands:
            command = adapter._command_enum_for(name).by_name(name)
            if command is not None:
                CommandReq.build(command, self.cab.tmccId, data=data, scope=adapter.state.scope).send()
                return
            if adapter.send_panel_command(name):
                return

    def show_scope_catalog(self):
        self.evaluate("window.controllerShowRoster()")

    def hide_scope_catalog(self):
        self.evaluate("window.controllerHideRoster()")

    def scroll_catalog(self, delta):
        self.evaluate(f"window.controllerNavigate({int(delta)})")

    def scroll_catalog_to_end(self, to_top):
        self.evaluate(f"window.controllerNavigate(0, {-1 if to_top else 1})")

    def select_catalog_entry(self):
        self.evaluate("window.controllerSelect()")

    def on_switch_command(self, thru):
        state = self.input_state
        address = state.get("row", {}).get("tmccId", 0)
        if not state.get("blocked") and address:
            self.controllers["switchOpsController"].operateSwitch(address, "THRU" if thru else "OUT")

    def on_route_command(self):
        state = self.input_state
        address = state.get("row", {}).get("tmccId", 0)
        if not state.get("blocked") and address:
            self.controllers["routeOpsController"].fireRoute(address)

    @property
    def accessory(self):
        return self.input_state.get("accessory", {})

    def on_acc_command(self, command, data=0):
        state = self.input_state
        if state.get("blocked"):
            return
        accessory = state.get("accessory", {})
        aliases = {
            "AUX1_OPTION_ONE": "AUX1_OPT_ONE",
            "AUX2_OPTION_ONE": "AUX2_OPT_ONE",
            "BOOST_SPEED": "BOOST",
            "BRAKE_SPEED": "BRAKE",
        }
        self.controllers["accessoryCatalogController"].tmccCommand(
            accessory.get("key", ""),
            accessory.get("tmccId", accessory.get("primaryTmccId", 0)),
            aliases.get(command, command),
            data or 0,
        )

    def on_acc_speed_command(self, value):
        self.on_acc_command("RELATIVE_SPEED", value)

    def on_lcs_command(self, on):
        state = self.input_state
        accessory = state.get("accessory", {})
        if not state.get("blocked"):
            self.controllers["accessoryCatalogController"].quickAction(
                "ON" if on else "OFF",
                accessory.get("tmccId", accessory.get("primaryTmccId", 0)),
                accessory.get("kind", ""),
            )

    def on_asc2_momentary(self, pressed):
        controller = self.controllers["accessoryCatalogController"]
        if not pressed:
            if self._held_relay is not None:
                controller.holdQuickAction(self._held_relay, False)
                self._held_relay = None
        elif not self.input_state.get("blocked"):
            address = self.accessory.get("tmccId", self.accessory.get("primaryTmccId", 0))
            if address:
                self._held_relay = address
                controller.holdQuickAction(address, True)

    def on_sensor_track_step(self, delta):
        current = self.accessory.get("sequence", 0) if self._sensor_choice is None else self._sensor_choice
        self._sensor_choice = max(0, min(9, current + delta))

    def on_sensor_track_select(self):
        if self._sensor_choice is not None and not self.input_state.get("blocked"):
            self.controllers["accessoryCatalogController"].setSensorSequence(
                self.accessory.get("key", ""), self._sensor_choice
            )

    def on_sensor_track_revert(self):
        self._sensor_choice = None

    def release(self):
        self._release_admin_press()
        self.on_asc2_momentary(False)
        self.controllers["accessoryCatalogController"].releaseConfiguredHolds(self.accessory.get("key", ""))
        self.cab.cancelRelativeThrottle()
        self.clear_throttle()


class QtDeckController(QObject):
    """Poll one physical Deck and route actions to left, right, or focused pane."""

    focusChanged = Signal()
    controlsChanged = Signal()
    helpPageRequested = Signal(int)

    def __init__(self, left, right, profile_path=None, parent=None, *, provider_factory=SteamDeckInputProvider):
        super().__init__(parent)
        self.left = QtDeckPane(left)
        self.right = QtDeckPane(right)
        self.left.host = self.right.host = self
        self._controls_visible = False
        self._focused = "right"
        self._profile = ControlProfile.load(profile_path)
        self._router = DeckInputRouter(
            self._profile,
            left=lambda: self.left,
            right=lambda: self.right,
            focused=lambda: self.left if self._focused == "left" else self.right,
            global_actions={
                "halt": self.right.cab.halt,
                "focus_left": lambda: self.focusPane("left"),
                "focus_right": lambda: self.focusPane("right"),
                "focus_toggle": self.toggleFocus,
                "show_controls": self.showControls,
            },
        )
        self._provider = provider_factory(self._profile, fires_on_press=self._router.fires_on_press)
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self.poll)
        self._tokens = None

    @Property(str, notify=focusChanged)
    def focusedPane(self):
        return self._focused

    def attach(self, window):
        self.left.workspace = window.property("leftPane")
        self.right.workspace = window.property("rightPane")
        try:
            self._provider.start()
            self._timer.start()
        except Exception as exc:
            log.warning("Steam Deck controller unavailable; touchscreen remains active: %s", exc)

    @Slot(str)
    def focusPane(self, pane):
        if pane not in ("left", "right") or pane == self._focused:
            return
        self.release()
        self._focused = pane
        self.focusChanged.emit()

    @Slot()
    def toggleFocus(self):
        self.focusPane("left" if self._focused == "right" else "right")

    @Property(bool, notify=controlsChanged)
    def controlsVisible(self):
        return self._controls_visible

    @Property(str, constant=True)
    def controlsText(self):
        rows = ["Steam Deck controls", "Touch either pane to focus it. HALT always affects the layout."]
        for index, binding in self._profile.axes.items():
            rows.append(f"Axis {index}: {binding.action.replace('_', ' ')} ({binding.target})")
        for index, binding in self._profile.buttons.items():
            rows.append(f"Button {index}: {binding.action.replace('_', ' ')} ({binding.target})")
        rows.extend(
            [
                "D-pad: roster navigation or the active panel's operations.",
                "X closes this help. Both stick clicks open it.",
            ]
        )
        return "\n".join(rows)

    @Slot()
    def showControls(self):
        self.release()
        self._controls_visible = not self._controls_visible
        self.controlsChanged.emit()

    @Slot()
    def closeControls(self):
        self._controls_visible = False
        self.controlsChanged.emit()

    @Slot()
    def release(self):
        self._router.clear()
        self.left.release()
        self.right.release()

    @Slot()
    def poll(self):
        try:
            tokens = tuple(
                (
                    pane.throttle_generation,
                    pane.input_state.get("scope"),
                    pane.input_state.get("blocked"),
                    pane.input_state.get("catalog"),
                    pane.accessory.get("key"),
                )
                for pane in (self.left, self.right)
            )
            if self._tokens is not None and tokens != self._tokens:
                self.release()
            self._tokens = tokens
            for action in self._provider.poll():
                if action.name == "disconnect":
                    self.release()
                else:
                    self._router.handle(action)
            self._router.tick(time.monotonic())
        except Exception as exc:
            self.release()
            log.warning("Steam Deck input poll failed: %s", exc)

    def close(self):
        self._timer.stop()
        self.release()
        self._provider.stop()
