#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Absorbing spurious releases from a touch panel that drops a contact mid-hold.

Established by experiment on 2026-08-22, after several sessions of chasing it as a software
bug: the Steam Deck's touch panel misreports contact position while the unit is charging
from an ungrounded (two-prong) USB-C supply. The chassis floats and rings against earth, the
noise corrupts the panel's sense axis, and the pointer teleports hundreds of pixels along Y
while X still tracks the finger correctly. X11 renders each teleport as a ``<Leave>`` plus a
spurious ``<ButtonRelease>``, then an ``<Enter>`` plus a press when it snaps back -- which
resets a three-second hold. It reproduces only with the Deck on a flat surface, charging,
pressed with a bare finger; holding the unit couples the chassis to your body and it stops,
as does unplugging it, as does a capacitive stylus. A combo box on the same screen showed the
same symptom and the same cure, which is what confirmed the cause was electrical.

So none of this is a defect in PyTrain, and none of it can be properly fixed in a widget. It
is damage limitation, and it lives in its own module so that ``hold_button`` reads as a
button rather than as a workaround.

**It is dormant unless a caller passes a non-zero ``press_recovery_ms``**, which today is
nobody -- ``PRESS_RECOVERY_MS`` in ``admin_panel`` is 0, because the Deck is used on battery.
Raise that one constant to re-arm everything here. For calibration, over the worst logged
session (17 flips in 16 seconds, charging): 100ms caught 11 of 18, 350ms caught all 18 at a
release latency you could see.
"""

from __future__ import annotations

import logging
import time
from tkinter import TclError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hold_button import HoldButton

log = logging.getLogger(__name__)

# X11 button-1 bit in an event's state mask. Crossing and motion events carry the button
# state at the time they were generated, so this answers "is the finger still down?"
# without waiting for a ButtonPress that may never arrive.
B1_MASK = 0x0100

# A fresh press this soon after a hold was abandoned is almost certainly the same gesture
# continuing -- i.e. a flip cost the user their progress. Logged, not acted on: by then the
# hold is already gone, and this exists to make the loss visible in a trace.
RESTART_WINDOW_MS = 1500
# A press this soon after a hold was abandoned inherits the progress that hold had made.
# Much tighter than RESTART_WINDOW_MS, which only logs: this one changes behaviour, and a
# deliberate second press does not follow a deliberate release within a third of a second.
RESTART_RESUME_MS = 300


def unwrap_event(event):
    """The underlying tkinter event, unwrapping guizero's EventData if present.

    Two bindings deliver events to a HoldButton: guizero's ``when_left_button_released``,
    which wraps the real event in an EventData exposing only x/y/widget/keycode, and raw
    ``tk.bind()``, which passes the tkinter event straight through. Reading ``.state`` off the
    wrapper silently fails, which made every button-delivered release look stateless
    regardless of where it came from -- and costs a wrong theory about which releases were
    genuine.
    """
    if event is None:
        return None
    return getattr(event, "tk_event", event)


def contact_is_down(event) -> bool:
    """Whether the event's state mask says button 1 was still held when it was generated."""
    try:
        return bool(int(unwrap_event(event).state) & B1_MASK)
    except (AttributeError, TypeError, ValueError):
        # Some drivers do not populate state; absence is not evidence of a lift, but it is
        # not evidence of a hold either, so do not resume on it.
        return False


def describe_state(event) -> str:
    """The event's button mask, rendered for a trace -- including whether it was wrapped."""
    unwrapped = unwrap_event(event)
    wrapped = " (guizero wrapper)" if unwrapped is not event else ""
    try:
        state = int(unwrapped.state)
    except (AttributeError, TypeError, ValueError):
        return f"state=<unavailable>{wrapped} raw={getattr(unwrapped, 'state', '<missing>')!r}"
    return f"state=0x{state:04x} b1={bool(state & B1_MASK)}{wrapped}"


# noinspection protected-member
class TouchContactFilter:
    """Decides whether a mid-hold ButtonRelease should be believed yet.

    Owns the two pieces of state a plain button has no use for:

    * the **recovery window** -- a release is held in suspense for ``recovery_ms``, and
      withdrawn entirely if the contact proves to be still down before it expires;
    * the **abandon ledger** -- when a hold was lost anyway, the press that immediately
      follows can inherit its progress instead of starting from zero.

    Deliberately does not touch the hold clock. The button banks and restores its own
    elapsed time; this object answers only "is that release real yet?" and "does this new
    press deserve credit?". Keeping the clock on one side of the seam is what stopped the
    two copies of elapsed time from drifting apart, which was its own bug.
    """

    def __init__(self, host: "HoldButton", recovery_ms: int) -> None:
        self._host = host
        self._recovery_ms = max(0, int(recovery_ms))
        self._release_pending = False
        self._after_id: str | None = None
        self._abandoned_at: float | None = None
        self._abandoned_banked = 0.0

    @property
    def enabled(self) -> bool:
        """False disables every behavior here and is the Raspberry Pi's configuration."""
        return self._recovery_ms > 0

    @property
    def recovery_ms(self) -> int:
        return self._recovery_ms

    @property
    def release_pending(self) -> bool:
        """A release is being held in suspense, waiting to see if the contact returns."""
        return self._release_pending

    @property
    def has_abandoned_hold(self) -> bool:
        """A hold ended without firing recently enough for its progress to be inherited."""
        return self._abandoned_at is not None

    def arm(self, banked: float) -> None:
        """Suspend a release for the recovery window. ``banked`` is logged, not stored."""
        self._release_pending = True
        self._host._vdiag("release-deferred", f"banked={banked:.3f}s window={self._recovery_ms}ms")
        self._cancel_timer()
        try:
            self._after_id = self._host.tk.after(self._recovery_ms, self._expire)
        except (AttributeError, TclError, RuntimeError):
            # No event loop to defer with: decide immediately rather than hang the hold.
            self._expire()

    def disarm(self) -> None:
        """Withdraw a suspended release -- the contact came back, or the hold ended."""
        self._cancel_timer()
        self._release_pending = False

    def contact_returned(self, event, source: str) -> bool:
        """Whether this event proves a suspended release was spurious.

        The Deck does not always follow a spurious release with a fresh press: the pointer
        gets warped off the button and back within one continuous press, so waiting for a
        ButtonPress leaves the hold to expire. A crossing or motion event carries the button
        state at the time it was generated, which settles it directly.
        """
        if not self._release_pending:
            return False
        if not contact_is_down(event):
            self._host._vdiag(f"{source}-no-contact", lambda: describe_state(event))
            return False
        self._host._vdiag(f"{source}-contact-held", lambda: describe_state(event))
        return True

    def note_abandoned(self, banked: float) -> None:
        """Record that a hold ended without firing, so the next press can inherit it."""
        if not self.enabled:
            return
        self._abandoned_at = time.monotonic()
        self._abandoned_banked = banked

    def inherited_progress(self, press_time: float) -> float:
        """Hold time a press starting at ``press_time`` should be credited with.

        Zero in the ordinary case. A non-zero result means a flip costs the user their
        progress and this press is the same gesture continuing -- which needs no theory
        about which releases were genuine, because, to reach the threshold from here, the
        finger must still be pressing.
        """
        if self._abandoned_at is None:
            return 0.0
        gap_ms = int((press_time - self._abandoned_at) * 1000)
        lost = self._abandoned_banked
        self._abandoned_at = None
        self._abandoned_banked = 0.0
        if gap_ms <= RESTART_RESUME_MS and lost > 0:
            self._host._diag("restart-resumed", f"inherited={lost:.3f}s gap={gap_ms}ms")
            return lost
        if gap_ms <= RESTART_WINDOW_MS:
            # The symptom users actually report -- "it keeps resetting" -- and otherwise
            # invisible in a trace, because a fresh press looks identical whether or not it
            # is really the same finger continuing.
            self._host._diag("restart-after-abandon", f"lost={lost:.3f}s gap={gap_ms}ms")
        return 0.0

    def _expire(self) -> None:
        """The window closed with no returning contact: the finger really did lift."""
        self._after_id = None
        if not self._release_pending:
            return
        self._release_pending = False
        self._host._confirm_release()

    def _cancel_timer(self) -> None:
        if self._after_id is None:
            return
        try:
            self._host.tk.after_cancel(self._after_id)
        except (AttributeError, TclError, RuntimeError):
            pass
        self._after_id = None
