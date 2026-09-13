"""Small pygame/SDL gamepad bridge for the Qt cab."""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, QTimer

log = logging.getLogger(__name__)


class QtGamepadInput(QObject):
    """Poll a single SDL gamepad and translate it into semantic cab actions.

    The left stick is intentionally a *rate* throttle: deflecting it upward repeatedly
    increases the current target rather than treating the spring-centered stick as an
    absolute speed position.
    """

    POLL_MS = 20
    DEAD_ZONE = 0.25
    THROTTLE_REPEAT_SECONDS = 0.11
    HORN_REPEAT_SECONDS = 0.10
    DPAD_REPEAT_SECONDS = 0.22

    def __init__(self, cab, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cab = cab
        self._pygame = None
        self._joystick = None
        self._horn_down = False
        self._hat = (0, 0)
        self._next_throttle = 0.0
        self._next_horn = 0.0
        self._next_dpad = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)

        self._initialize()

    @property
    def connected(self) -> bool:
        return self._joystick is not None

    @property
    def name(self) -> str:
        return self._joystick.get_name() if self._joystick is not None else ""

    def close(self) -> None:
        self._timer.stop()
        if self._joystick is not None:
            try:
                self._joystick.quit()
            except Exception:
                pass
            self._joystick = None

    def _initialize(self) -> None:
        try:
            import pygame

            self._pygame = pygame
            pygame.joystick.init()
            pygame.event.set_allowed(None)
            pygame.event.set_allowed(
                [
                    pygame.JOYDEVICEADDED,
                    pygame.JOYDEVICEREMOVED,
                    pygame.JOYBUTTONDOWN,
                    pygame.JOYBUTTONUP,
                    pygame.JOYHATMOTION,
                ]
            )
            self._attach_first_controller()
            self._timer.start()
        except Exception as exc:
            log.info("Gamepad input unavailable: %s", exc)
            self._pygame = None

    def _attach_first_controller(self) -> None:
        pygame = self._pygame
        if pygame is None or self._joystick is not None or pygame.joystick.get_count() == 0:
            return
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        self._joystick = joystick
        log.info("Qt cab controller connected: %s", joystick.get_name())

    def _poll(self) -> None:
        pygame = self._pygame
        if pygame is None:
            return

        try:
            pygame.event.pump()
            for event in pygame.event.get():
                if event.type == pygame.JOYDEVICEADDED:
                    self._attach_first_controller()
                elif event.type == pygame.JOYDEVICEREMOVED:
                    if self._joystick is not None and event.instance_id == self._joystick.get_instance_id():
                        log.info("Qt cab controller disconnected")
                        self._joystick.quit()
                        self._joystick = None
                        self._horn_down = False
                        self._hat = (0, 0)
                elif event.type == pygame.JOYBUTTONDOWN:
                    self._button_down(event.button)
                elif event.type == pygame.JOYBUTTONUP:
                    self._button_up(event.button)
                elif event.type == pygame.JOYHATMOTION:
                    self._hat = tuple(event.value)

            if self._joystick is None:
                self._attach_first_controller()
                return

            now = time.monotonic()
            self._poll_throttle(now)
            self._poll_horn(now)
            self._poll_dpad(now)
        except Exception as exc:
            log.debug("Gamepad poll failed: %s", exc)

    def _button_down(self, button: int) -> None:
        # SDL B = 1 in the existing Steam Deck profile.
        if button == 1:
            self._cab.bell()
        # SDL Y = 3; horn repeats while held.
        elif button == 3:
            self._horn_down = True
            self._next_horn = 0.0

    def _button_up(self, button: int) -> None:
        if button == 3:
            self._horn_down = False
            self._cab.horn(False)

    def _poll_throttle(self, now: float) -> None:
        joystick = self._joystick
        if joystick is None or joystick.get_numaxes() < 2 or now < self._next_throttle:
            return

        # SDL left-stick Y is negative upward. Convert upward to positive rate.
        lever = -float(joystick.get_axis(1))
        magnitude = abs(lever)
        if magnitude <= self.DEAD_ZONE:
            return

        scaled = (magnitude - self.DEAD_ZONE) / (1.0 - self.DEAD_ZONE)
        step = max(1, min(5, round(1 + scaled * 4)))
        self._cab.changeSpeed(step if lever > 0 else -step)
        self._next_throttle = now + self.THROTTLE_REPEAT_SECONDS

    def _poll_horn(self, now: float) -> None:
        if self._horn_down and now >= self._next_horn:
            self._cab.horn(True)
            self._next_horn = now + self.HORN_REPEAT_SECONDS

    def _poll_dpad(self, now: float) -> None:
        if now < self._next_dpad:
            return
        _x, y = self._hat
        if y > 0:
            self._cab.boost(True)
            self._next_dpad = now + self.DPAD_REPEAT_SECONDS
        elif y < 0:
            self._cab.brake(True)
            self._next_dpad = now + self.DPAD_REPEAT_SECONDS
