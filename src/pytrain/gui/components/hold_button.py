#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
import time
import tkinter as tk
from threading import Condition, RLock
from tkinter import TclError
from typing import Any, Callable

from guizero import PushButton

log = logging.getLogger(__name__)

# A crossing this far outside the widget still counts as inside. Touch contact centroids
# wander by a few pixels over a long hold as finger pressure changes.
LEAVE_SLOP_PX = 16
# How long a <Leave> must persist, with no intervening <Enter>, before it cancels a hold.
# Long enough to swallow jitter, short enough that a deliberate drag-off feels immediate.
LEAVE_CONFIRM_MS = 150
# A fresh press this soon after a hold was abandoned is almost certainly the same gesture
# continuing -- i.e. a jitter cost the user their progress. Logged, not acted on: by then
# the hold is already gone, and this exists to make the loss visible in a trace.
RESTART_WINDOW_MS = 1500
# A press this soon after a hold was abandoned inherits the progress that hold had made.
# Much tighter than RESTART_WINDOW_MS, which only logs: this one changes behaviour, and a
# deliberate second press does not follow a deliberate release within a third of a second.
RESTART_RESUME_MS = 300

# Every diagnostic in this module starts with this, so a session log can be filtered to
# just the hold lifecycle: grep "holdbtn" pytrain.log
DIAG = "holdbtn"
# Per-event tracing on top of that: every crossing, motion, deferral step and overlay
# placement. Off by default -- it ran to about a dozen lines per press and buried the rest
# of a -debug session. What stays on is the hold's story (press, resume, threshold, fire,
# cancel); this is the finer detail that identified the Steam Deck's dropped-contact
# jitter. Kept rather than deleted because that root cause is still unknown and this is the
# only way to see the touch stream after the fact. Set True to get it back.
DIAG_VERBOSE = False

# X11 button-1 bit in an event's state mask. Crossing and motion events carry the button
# state at the time they were generated, so this answers "is the finger still down?"
# without waiting for a ButtonPress that may never arrive.
B1_MASK = 0x0100


# noinspection unused-parameter
class HoldButton(PushButton):
    """
    A PushButton subclass that adds:
      - on_press → single short tap, or fired when held if no hold/repeat defined
      - on_hold → single fire after hold_threshold seconds
      - on_repeat → continuous fire while held

    Each callback can be:
        func
        or (func, args)
        or (func, args, kwargs)

    Optional: full-height left-to-right progress fill while holding.
      - Implemented as a Canvas overlay placed in the *toplevel* window, so it does not perturb
        button geometry.
      - Because the overlay sits above the button, it also draws the label text; the underlying
        button text is temporarily hidden while holding.

    Hover behavior:
      - We implement hover via <Enter>/<Leave> bindings that explicitly set the tk Button background
        to its activebackground and then restore to normal backgrounds.
      - This keeps hover working even after the overlay is shown/hidden.
    """

    def __init__(
        self,
        master,
        text: str = "",
        on_press=None,
        on_hold=None,
        on_repeat=None,
        hold_threshold: float = 1.0,
        repeat_interval: float = 0.2,
        debounce_ms: int = 80,
        bg: str = "white",
        text_color: str = "black",
        text_size: int | None = None,
        text_bold: bool | None = None,
        flash: bool = True,
        command: Callable | None = None,
        args: list[Any] | None = None,
        # ── Progress fill options ──
        show_hold_progress: bool = False,
        progress_update_ms: int = 40,
        progress_fill_color: str = "darkgrey",
        critical_fill_color: str = "darkgrey",
        progress_empty_color: str | None = None,  # None => uses current button bg
        progress_keep_full_until_release: bool = True,
        cancel_on_leave: bool = False,
        press_recovery_ms: int = 0,
        **kwargs,
    ):
        # semaphore to protect critical code
        self._cv = Condition(RLock())

        # canonical colors/images for restore
        self._normal_bg: str | None = None
        self._normal_fg: str | None = None
        self._normal_text_bg: str | None = None
        self._normal_text_fg: str | None = None

        self._normal_img = None
        self._inverted_img = None

        # hover bookkeeping
        self._hover_normal_bg: str | None = None
        self._hover_active_bg: str | None = None

        # timing/state
        self.hold_threshold = float(hold_threshold)
        self.repeat_interval = float(repeat_interval)
        self.debounce_ms = int(debounce_ms)

        self._press_time: float | None = None
        self._pressed: bool = False
        self._held: bool = False
        self._repeating: bool = False
        self._after_id: str | None = None
        self._handled_hold: bool = False
        self._handled_flash: bool = False

        # progress config/state
        self._show_hold_progress = bool(show_hold_progress)
        self._progress_update_ms = int(progress_update_ms)
        self._progress_fill_color = str(progress_fill_color)
        self._critical_fill_color = str(critical_fill_color)
        self._progress_empty_color = progress_empty_color
        self._progress_keep_full_until_release = bool(progress_keep_full_until_release)

        self._progress_start: float | None = None
        self._progress_after_id: str | None = None
        self._cancel_on_leave = bool(cancel_on_leave)
        # Window in which a <ButtonRelease> followed by a fresh <ButtonPress> is treated
        # as one continuing hold rather than two. 0 disables it. See _defer_release.
        self._press_recovery_ms = int(press_recovery_ms)
        self._release_pending: bool = False
        self._release_after_id: str | None = None
        # Hold time banked across release/press gaps, so a recovered hold resumes where
        # it left off instead of starting the countdown again.
        self._held_elapsed: float = 0.0
        # When a hold was last abandoned without firing, and how much progress went with
        # it. Only used for diagnostics -- see the restart check in _on_press_event.
        self._abandoned_at: float | None = None
        self._abandoned_banked: float = 0.0
        # Captured now: the underlying label is blanked while the progress overlay is up,
        # so reading it during a hold yields "".
        self._diag_label = str(text) or "?"
        # Pending-leave state, see _on_leave_candidate.
        self._leave_pending: bool = False
        self._leave_after_id: str | None = None
        # Last geometry the overlay was placed at, so _on_configure_event can skip a
        # re-place that would change nothing (see _position_overlay).
        self._overlay_geometry: tuple[int, int, int, int] | None = None

        # overlay canvas (toplevel)
        self._progress_canvas: tk.Canvas | None = None
        self._progress_rect = None
        self._progress_bg_rect = None
        self._progress_text_item = None
        self._overlay_visible: bool = False

        # stash/restore label while overlay is visible
        self._saved_button_text: str | None = None

        # flash requested?
        self._flash_requested = bool(flash)

        # initialize parent
        super().__init__(master, text=text, **kwargs)

        # apply base properties (guizero-level)
        if bg:
            self._normal_bg = self._normal_text_bg = self.bg = bg
        if text_color:
            self._normal_fg = self.text_color = self._normal_text_fg = text_color
        if text_size is not None:
            self.text_size = text_size
        if text_bold is not None:
            self.text_bold = text_bold

        # resolve command vs. on_press
        if command and on_press:
            raise ValueError("Cannot specify both command and on_press")
        elif command:
            on_press = (command, args) if args else command

        # callbacks
        self._on_press = on_press
        self._on_hold = on_hold
        self._on_repeat = on_repeat

        # bind events (mouse and touchscreen compatible)
        self.when_left_button_pressed = self._on_press_event
        self.when_left_button_released = self._on_release_event
        if self._cancel_on_leave:
            self.tk.bind("<Leave>", self._on_leave_candidate, add="+")
            self.tk.bind("<Enter>", self._on_enter_candidate, add="+")
        if press_recovery_ms > 0:
            # Motion is what proves a contact is still down when no press follows a
            # spurious release. Bound only where recovery is wanted, to keep the event
            # traffic off buttons that do not need it.
            self.tk.bind("<Motion>", self._on_motion_candidate, add="+")

        # hover bindings (robust, independent of Tk "active" internals)
        if show_hold_progress:
            self.tk.bind("<Enter>", self._on_hover_enter, add="+")
            self.tk.bind("<Leave>", self._on_hover_leave, add="+")

        # keep overlay aligned when widget moves/resizes
        self.tk.bind("<Configure>", self._on_configure_event, add="+")

        # flash behavior
        if self._flash_requested and text:
            self.do_flash()

        # capture initial "real" tk background/foreground (your helper often sets these after creation)
        self._snapshot_tk_normals()

    # ───────────────────────────────
    # Parent setter overrides
    # ───────────────────────────────
    @PushButton.text.setter
    def text(self, value):
        with self._cv:
            PushButton.text.fset(self, value)
            if self._flash_requested and value:
                self.do_flash()

    @PushButton.text_color.setter
    def text_color(self, value):
        with self._cv:
            PushButton.text_color.fset(self, value)
            self._normal_fg = self._normal_text_fg = value

    @PushButton.bg.setter
    def bg(self, value):
        with self._cv:
            PushButton.bg.fset(self, value)
            self._normal_bg = self._normal_text_bg = value

    # ───────────────────────────────
    # Properties for dynamic callbacks
    # ───────────────────────────────
    @property
    def images(self) -> tuple:
        return self._normal_img, self._inverted_img

    @images.setter
    def images(self, value: tuple) -> None:
        self._normal_img, self._inverted_img = value
        self.tk.config(image=self._normal_img, compound="center")
        if self._flash_requested and self._normal_img and self._inverted_img:
            self.do_flash()

    @property
    def on_press(self):
        return self._on_press

    @on_press.setter
    def on_press(self, func):
        self._on_press = func

    @property
    def on_hold(self):
        return self._on_hold

    @on_hold.setter
    def on_hold(self, func):
        self._on_hold = func

    @property
    def on_repeat(self):
        return self._on_repeat

    @on_repeat.setter
    def on_repeat(self, func):
        self._on_repeat = func

    @property
    def progress_fill_color(self) -> str:
        return self._progress_fill_color

    @progress_fill_color.setter
    def progress_fill_color(self, value: str) -> None:
        self._progress_fill_color = str(value)
        if self._progress_canvas is not None and self._progress_rect is not None:
            try:
                self._progress_canvas.itemconfig(self._progress_rect, fill=self._progress_fill_color)
            except TclError:
                pass

    @property
    def critical_fill_color(self) -> str:
        return self._critical_fill_color

    @critical_fill_color.setter
    def critical_fill_color(self, value: str) -> None:
        self._critical_fill_color = str(value)

    @property
    def progress_empty_color(self) -> str | None:
        return self._progress_empty_color

    @progress_empty_color.setter
    def progress_empty_color(self, value: str | None) -> None:
        self._progress_empty_color = None if value is None else str(value)
        if self._progress_canvas is not None and self._progress_bg_rect is not None:
            canvas_bg = self._progress_empty_color or self._normal_bg or self._safe_tk_bg() or "white"
            try:
                self._progress_canvas.config(background=canvas_bg)
                self._progress_canvas.itemconfig(self._progress_bg_rect, fill=canvas_bg)
            except TclError:
                pass

    # ───────────────────────────────
    # Internal event handlers
    # ───────────────────────────────
    # noinspection PyUnusedLocal
    def begin_hold(self) -> None:
        """Start a hold as though the button had been pressed with a finger.

        For synthetic input (e.g., a controller chord standing in for a press): the
        hold progress bar animates and ``on_hold`` fires after ``hold_threshold``
        exactly as it would for a real press, so the timing and the visual feedback
        have a single implementation.
        """
        self._on_press_event()

    def _diag(self, event: str, detail: str = "") -> None:
        """Trace one step of the hold lifecycle.

        Enabled by PyTrain's -debug flag. Holds are cancelled by pointer events that are
        invisible after the fact, so every decision point logs what it saw and what it
        concluded -- the elapsed time is what says how far into the three seconds a hold
        died.
        """
        if not log.isEnabledFor(logging.DEBUG):
            return
        elapsed = f"{time.monotonic() - self._press_time:.3f}s" if self._press_time else "-"
        log.debug(
            "%s[%s] %s t=%s pressed=%s leave_pending=%s %s",
            DIAG,
            self._diag_name(),
            event,
            elapsed,
            self._pressed,
            self._leave_pending,
            detail,
        )

    def _vdiag(self, event: str, detail: Callable[[], str] | str = "") -> None:
        """Trace one pointer event -- only when DIAG_VERBOSE is set. See _diag.

        ``detail`` may be a callable, so a description that costs Tk round-trips (pointer
        position, widget geometry) is not built when nothing will read it. Motion arrives
        often enough during a three-second hold for that to be worth the indirection.
        """
        if not DIAG_VERBOSE or not log.isEnabledFor(logging.DEBUG):
            return
        self._diag(event, detail() if callable(detail) else detail)

    def _diag_name(self) -> str:
        return getattr(self, "_diag_label", "?")

    @property
    def is_holding(self) -> bool:
        """True between the press and the hold firing (or being cancelled).

        Public so a host can avoid disturbing the widget mid-hold: anything that repacks
        the layout generates pointer crossings, which cancel the hold.
        """
        return bool(self._pressed)

    def cancel_hold(self, reason: str = "cancel_hold()") -> None:
        """Abandon a hold started by :meth:`begin_hold` before it completes.

        Stops the progress animation and the pending ``on_hold`` without firing the
        short-press callback -- the same treatment as a finger sliding off the button.
        Harmless if the hold has already completed.
        """
        self._on_leave_event(reason=reason)

    def _on_press_event(self, event=None):
        if not self._is_enabled():
            self._pressed = False
            self._repeating = False
            self._cancel_after()
            self._stop_progress()
            return

        if self._release_pending:
            self._resume_hold()
            return
        self._pressed = True
        self._leave_pending = False
        self._cancel_leave_timer()
        self._held_elapsed = 0.0
        self._press_time = time.monotonic()
        self._diag("press", f"threshold={self.hold_threshold}s")
        self._note_restart_after_abandon()
        self._held = False
        self._repeating = False
        self._handled_hold = False

        # snapshot current tk normals (important: your helper sets tk background/activebackground directly)
        self._snapshot_tk_normals()

        # start progress feedback
        self._start_progress()

        # schedule hold trigger
        self._cancel_after()
        self._after_id = self.tk.after(int(self.hold_threshold * 1000), self._trigger_hold_or_repeat)

    # noinspection PyUnusedLocal
    def _on_release_event(self, event=None):
        self._vdiag(
            "release",
            lambda: (
                f"{self._describe_event(event)} {self._describe_state(event)}" if event is not None else "synthetic"
            ),
        )
        # Every mid-hold release is deferred, whatever it looks like. Branching on the
        # state mask was tried and withdrawn: guizero's EventData hid the field, so the
        # mask only ever revealed which binding delivered the event, not whether the
        # finger really lifted. The mask is still logged, for evidence.
        if self._should_defer_release():
            self._defer_release()
            return
        self._do_release(event)

    @staticmethod
    def _tk_event(event):
        """The underlying tkinter event, unwrapping guizero's EventData if present.

        Two bindings deliver events here: guizero's when_left_button_released, which
        wraps the real event in an EventData exposing only x/y/widget/keycode, and raw
        tk.bind() on the progress overlay, which passes the tkinter event straight
        through. Reading `.state` off the wrapper silently fails, which made every
        button-delivered release look stateless regardless of where it came from.
        """
        if event is None:
            return None
        return getattr(event, "tk_event", event)

    def _should_defer_release(self) -> bool:
        """Whether this release might be the touchscreen dropping a still-held contact.

        Observed on the Steam Deck: during a long hold the touch stream emits a release
        and a fresh press milliseconds apart while the finger never moves. Taken at face
        value that restarts the countdown, so a three-second hold can never complete.
        Only deferred for holds still short of their threshold -- a completed hold has
        already fired, and a button with no on_hold has nothing to protect.
        """
        return bool(
            self._press_recovery_ms > 0
            and self._pressed
            and self._on_hold
            and not self._handled_hold
            and self._elapsed_held() < self.hold_threshold
        )

    def _note_restart_after_abandon(self) -> None:
        """Flag a countdown that restarted from zero right after one was abandoned.

        This is the symptom users actually report -- "it keeps resetting" -- and it is
        otherwise invisible in a trace, because a fresh press looks identical whether or
        not it is really the same finger continuing.
        """
        if self._abandoned_at is None:
            return
        gap_ms = int((self._press_time - self._abandoned_at) * 1000)
        lost = self._abandoned_banked
        self._abandoned_at = None
        self._abandoned_banked = 0.0
        if gap_ms <= RESTART_RESUME_MS and lost > 0:
            # Inherit the abandoned progress rather than starting the countdown again.
            # This is the fix for the reported symptom, and it needs no theory about which
            # releases were real: to reach the threshold the finger must still be pressing.
            self._held_elapsed = lost
            self._diag("restart-resumed", f"inherited={lost:.3f}s gap={gap_ms}ms")
            return
        if gap_ms <= RESTART_WINDOW_MS:
            self._diag("restart-after-abandon", f"lost={lost:.3f}s gap={gap_ms}ms")

    def _note_abandoned(self, banked: float) -> None:
        """Remember that a hold ended without firing, for the restart check above."""
        if self._on_hold and not self._handled_hold:
            self._abandoned_at = time.monotonic()
            self._abandoned_banked = banked

    def _elapsed_held(self) -> float:
        running = (time.monotonic() - self._press_time) if self._press_time else 0.0
        return self._held_elapsed + running

    def _defer_release(self) -> None:
        """Bank the time held so far and wait to see whether the contact comes back."""
        self._held_elapsed = self._elapsed_held()
        # Stop the running clock, or _elapsed_held() adds it to the banked total again on
        # the next call -- which pushed a second release past the threshold and let it
        # end the hold outright.
        self._press_time = None
        self._release_pending = True
        # Pause the countdown. Left running, a contact genuinely lifted at 2.9s would
        # still fire at 3.0s -- an unwanted reboot is a bad way to learn that.
        self._cancel_after()
        self._vdiag("release-deferred", f"banked={self._held_elapsed:.3f}s window={self._press_recovery_ms}ms")
        self._cancel_release_timer()
        try:
            self._release_after_id = self.tk.after(self._press_recovery_ms, self._confirm_release)
        except (AttributeError, TclError, RuntimeError):
            self._confirm_release()

    def _resume_hold(self) -> None:
        """A press arrived inside the recovery window: carry on the same hold."""
        self._cancel_release_timer()
        self._release_pending = False
        self._pressed = True
        self._leave_pending = False
        self._cancel_leave_timer()
        self._press_time = time.monotonic()
        remaining = max(0.0, self.hold_threshold - self._held_elapsed)
        self._diag("press-resumed", f"banked={self._held_elapsed:.3f}s remaining={remaining:.3f}s")
        # No progress-bar bookkeeping here: _progress_fraction reads _elapsed_held(), which
        # the two lines above have already brought up to date.
        try:
            self._after_id = self.tk.after(max(1, int(remaining * 1000)), self._trigger_hold_or_repeat)
        except (AttributeError, TclError, RuntimeError):
            self._after_id = None

    def _confirm_release(self) -> None:
        """No press followed: the finger really did come up."""
        self._release_after_id = None
        if not self._release_pending:
            return
        self._release_pending = False
        self._diag("release-confirmed", f"banked={self._held_elapsed:.3f}s")
        self._do_release(None)

    def _cancel_release_timer(self) -> None:
        if self._release_after_id is None:
            return
        try:
            self.tk.after_cancel(self._release_after_id)
        except (AttributeError, TclError, RuntimeError):
            pass
        self._release_after_id = None

    def _do_release(self, event=None):
        self._note_abandoned(self._elapsed_held())
        enabled = self._is_enabled()
        self._pressed = False

        # stop progress + timers
        self._stop_progress()
        self._cancel_after()

        if not enabled:
            self._repeating = False
            return

        elapsed = self._elapsed_held()
        self._held_elapsed = 0.0
        if elapsed < (self.debounce_ms / 1000.0):
            return

        # stop repeating
        if self._repeating:
            self._repeating = False
            return

        # Case 1: standard short press
        if not self._held:
            self._invoke_callback(self._on_press)
            return

        # Case 2: held long enough, but no hold/repeat defined
        if self._held and not self._handled_hold:
            self._invoke_callback(self._on_press)

    # noinspection PyUnusedLocal
    # noinspection PyUnusedLocal
    def _on_leave_candidate(self, event=None):
        """Start a *provisional* cancel on <Leave>; confirm it only if it persists.

        A bare <Leave> is not trustworthy on a touchscreen. The progress overlay is
        placed over the button, so a crossing can be synthesized, and jitter in the touch
        stream produces Leave/Enter pairs milliseconds apart. Cancelling on the Leave
        itself therefore aborted roughly half of all 3-second holds.

        Two filters, because either alone has been shown insufficient:

        * The event's own ``x``/``y`` are relative to this widget, so a Leave reporting a
          position still inside the button (plus ``LEAVE_SLOP_PX``) is jitter and is
          discarded outright. This is trusted ahead of ``winfo_pointerxy()``, which
          queries the *mouse* pointer -- not reliably warped to the finger under
          gamescope, which is why a pointer-only check still let jitter through.
        * Anything that survives that is confirmed after ``LEAVE_CONFIRM_MS``. A genuine
          drag-off stays outside and cancels; jitter is followed immediately by an Enter,
          which clears the pending cancel.
        """
        if not self._pressed:
            self._vdiag("leave-ignored", "no hold in flight")
            return
        if self._event_inside(event):
            self._vdiag("leave-discarded", lambda: f"inside widget {self._describe_event(event)}")
            return
        self._vdiag("leave-provisional", lambda: f"{self._describe_event(event)} confirm_in={LEAVE_CONFIRM_MS}ms")
        self._leave_pending = True
        self._cancel_leave_timer()
        try:
            self._leave_after_id = self.tk.after(LEAVE_CONFIRM_MS, self._confirm_leave)
        except (AttributeError, TclError, RuntimeError):
            # No event loop to defer with: fall back to deciding immediately.
            self._confirm_leave()

    # noinspection PyUnusedLocal
    def _on_enter_candidate(self, event=None):
        """An Enter means the finger never really left: drop the provisional cancel."""
        if self._leave_pending:
            self._vdiag("leave-rescinded", "enter arrived before the confirm deadline")
        self._leave_pending = False
        self._cancel_leave_timer()
        self._maybe_resume_from_contact(event, "enter")

    # noinspection PyUnusedLocal
    def _on_motion_candidate(self, event=None):
        """Motion over the button while a release is deferred: is the contact still down?"""
        self._maybe_resume_from_contact(event, "motion")

    def _maybe_resume_from_contact(self, event, source: str) -> None:
        """Resume a deferred hold when an event proves the contact is still down.

        The Deck does not always follow a spurious release with a fresh press: the
        pointer gets warped off the button and back inside one continuous press, so
        waiting for a ButtonPress leaves the hold to expire. A crossing or motion event
        carries the button state at the time it was generated, which settles it directly.
        """
        if not self._release_pending:
            return
        if not self._event_button1_down(event):
            self._vdiag(f"{source}-no-contact", lambda: self._describe_state(event))
            return
        self._vdiag(f"{source}-contact-held", lambda: self._describe_state(event))
        self._resume_hold()

    @staticmethod
    def _event_button1_down(event) -> bool:
        try:
            return bool(int(HoldButton._tk_event(event).state) & B1_MASK)
        except (AttributeError, TypeError, ValueError):
            # Some drivers do not populate state; absence is not evidence of a lift, but
            # it is not evidence of a hold either, so do not resume on it.
            return False

    @staticmethod
    def _describe_state(event) -> str:
        unwrapped = HoldButton._tk_event(event)
        wrapped = " (guizero wrapper)" if unwrapped is not event else ""
        try:
            state = int(unwrapped.state)
        except (AttributeError, TypeError, ValueError):
            return f"state=<unavailable>{wrapped} raw={getattr(unwrapped, 'state', '<missing>')!r}"
        return f"state=0x{state:04x} b1={bool(state & B1_MASK)}{wrapped}"

    def _confirm_leave(self) -> None:
        self._leave_after_id = None
        if not self._leave_pending or not self._pressed:
            self._vdiag("confirm-moot", "already rescinded or released")
            return
        self._leave_pending = False
        if self._pointer_outside():
            self._diag("confirm-cancel", self._describe_pointer())
            self._on_leave_event(reason="pointer left the button")
            return
        self._vdiag("confirm-declined", lambda: f"pointer back inside {self._describe_pointer()}")

    def _cancel_leave_timer(self) -> None:
        if self._leave_after_id is None:
            return
        try:
            self.tk.after_cancel(self._leave_after_id)
        except (AttributeError, TclError, RuntimeError):
            pass
        self._leave_after_id = None

    @staticmethod
    def _event_inside(event) -> bool:
        """True when a crossing event reports a position still within the widget.

        Uses the event's own coordinates, which describe where the crossing actually
        happened rather than where the mouse pointer currently is.
        """
        unwrapped = HoldButton._tk_event(event)
        try:
            x = int(unwrapped.x)
            y = int(unwrapped.y)
            width = int(unwrapped.widget.winfo_width())
            height = int(unwrapped.widget.winfo_height())
        except (AttributeError, TclError, RuntimeError, TypeError, ValueError):
            return False
        slop = LEAVE_SLOP_PX
        return -slop <= x < width + slop and -slop <= y < height + slop

    def _pointer_outside(self) -> bool:
        """True when the mouse pointer is outside this button's rectangle, plus slop.

        Returns False if the geometry cannot be read: an unknown position must not cancel
        a hold, since a spurious cancel is the failure this whole path exists to avoid.
        """
        try:
            px, py = self.tk.winfo_pointerxy()
            x = int(self.tk.winfo_rootx())
            y = int(self.tk.winfo_rooty())
            width = int(self.tk.winfo_width())
            height = int(self.tk.winfo_height())
        except (AttributeError, TclError, RuntimeError, TypeError, ValueError):
            return False
        slop = LEAVE_SLOP_PX
        return not (x - slop <= px < x + width + slop and y - slop <= py < y + height + slop)

    def _describe_event(self, event) -> str:
        unwrapped = self._tk_event(event)
        try:
            width, height = int(self.tk.winfo_width()), int(self.tk.winfo_height())
            return f"event=({int(unwrapped.x)},{int(unwrapped.y)}) size=({width}x{height})"
        except (AttributeError, TclError, RuntimeError, TypeError, ValueError):
            return "event=<unreadable>"

    def _describe_pointer(self) -> str:
        try:
            px, py = self.tk.winfo_pointerxy()
            x, y = int(self.tk.winfo_rootx()), int(self.tk.winfo_rooty())
            w, h = int(self.tk.winfo_width()), int(self.tk.winfo_height())
            return f"pointer=({px},{py}) rect=({x},{y})-({x + w},{y + h}) slop={LEAVE_SLOP_PX}"
        except (AttributeError, TclError, RuntimeError, TypeError, ValueError):
            return "pointer=<unreadable>"

    def _on_leave_event(self, event=None, reason: str = "leave"):
        # Treat leaving the button as a cancel (common on touch drags). Called directly
        # by cancel_hold(), which must always cancel, and via _confirm_leave for pointer
        # events, which must not cancel on jitter.
        self._diag("cancel", f"reason={reason}")
        self._note_abandoned(self._elapsed_held())
        self._leave_pending = False
        self._cancel_leave_timer()
        self._release_pending = False
        self._cancel_release_timer()
        self._held_elapsed = 0.0
        self._pressed = False
        self._repeating = False
        self._stop_progress()
        self._cancel_after()

    # noinspection PyUnusedLocal
    def _on_configure_event(self, event=None):
        if self._pressed:
            self._vdiag("configure", "geometry event during a hold")
        # _position_overlay is a no-op when the geometry is unchanged, so a <Configure>
        # that does not actually move the button cannot synthesise a pointer crossing
        # over the overlay mid-hold.
        if self._overlay_visible:
            self._position_overlay()

    def _trigger_hold_or_repeat(self):
        self._diag("threshold-reached")
        if not self._is_enabled():
            self._diag("cancel", "reason=disabled at threshold")
            self._pressed = False
            self._repeating = False
            self._stop_progress()
            self._cancel_after()
            return

        self._held = True
        handled = False

        if self._on_repeat:
            self._repeating = True
            if self._progress_keep_full_until_release:
                self._set_progress_full()
            else:
                self._stop_progress()
            self._repeat_fire()
            handled = True

        elif self._on_hold:
            self._diag("fired", "on_hold")
            if self._progress_keep_full_until_release:
                self._set_progress_full()
            else:
                self._stop_progress()
            self._invoke_callback(self._on_hold)
            handled = True
            self.restore_color_state()

        elif self._on_press and not self._on_hold and not self._on_repeat:
            if self._progress_keep_full_until_release:
                self._set_progress_full()
            else:
                self._stop_progress()
            self._invoke_callback(self._on_press)
            handled = True
            self.restore_color_state()

        self._handled_hold = handled

    def _repeat_fire(self):
        if not self._repeating:
            return
        if not self._is_enabled():
            self._pressed = False
            self._repeating = False
            self._stop_progress()
            self._cancel_after()
            return
        self._invoke_callback(self._on_repeat)
        self._after_id = self.tk.after(int(self.repeat_interval * 1000), self._repeat_fire)

    # ───────────────────────────────
    # Hover behavior (explicit, robust)
    # ───────────────────────────────
    # noinspection PyUnusedLocal
    def _on_hover_enter(self, event=None) -> None:
        # while pressed or overlay visible, don't fight pressed visuals
        if not self._is_enabled() or self._pressed or self._overlay_visible:
            return
        try:
            self._hover_normal_bg = str(self.tk.cget("background"))
            self._hover_active_bg = str(self.tk.cget("activebackground"))
            if self._hover_active_bg:
                self.tk.config(background=self._hover_active_bg)
        except TclError:
            pass

    # noinspection PyUnusedLocal
    def _on_hover_leave(self, event=None) -> None:
        if self._pressed or self._overlay_visible:
            return
        try:
            # restore to current "normal" (prefer snapshot from enter)
            bg = self._hover_normal_bg or str(self.tk.cget("background"))
            self.tk.config(background=bg)
        except TclError:
            pass

    # ───────────────────────────────
    # Helper: invoke callback flexibly
    # ───────────────────────────────
    @staticmethod
    def _invoke_callback(cb):
        """Invoke callback allowing func, (func,args), or (func,args,kwargs)."""
        if not cb:
            return
        if callable(cb):
            cb()
        elif isinstance(cb, (tuple, list)) and len(cb) > 0:
            func = cb[0]
            args = cb[1] if len(cb) > 1 else []
            kwargs = cb[2] if len(cb) > 2 else {}
            func(*args, **kwargs)

    # ───────────────────────────────
    # Helper: snapshot tk "normal" colors (matches hb.tk.config usage)
    # ───────────────────────────────
    def _snapshot_tk_normals(self) -> None:
        if self.text:
            self._normal_text_bg = self.bg
            self._normal_text_fg = self.text_color

        try:
            self._normal_bg = str(self.tk.cget("background"))
        except TclError:
            pass
        try:
            # Tk uses "foreground" (guizero uses text_color)
            self._normal_fg = str(self.tk.cget("foreground"))
        except TclError:
            pass

    def _is_enabled(self) -> bool:
        try:
            return bool(self.enabled)
        except (AttributeError, TclError, RuntimeError):
            pass

        try:
            return str(self.tk.cget("state")) in {"normal", "active"}
        except (TclError, RuntimeError):
            return False

    # ───────────────────────────────
    # Helper: Flash button when pressed
    # ───────────────────────────────
    def do_flash(self) -> None:
        if self._handled_flash:
            return
        self._handled_flash = True

        def on_press(_event):
            if not self._is_enabled():
                return

            with self._cv:
                # snapshot from tk so it respects hb.tk.config(background=...)
                self._snapshot_tk_normals()

                # Apply pressed colors at tk-level to match your helper usage
                pressed_bg = "dark_grey"
                try:
                    if self.text:
                        PushButton.bg.fset(self, self._normal_text_fg if self._normal_text_fg else "black")
                        PushButton.text_color.fset(self, self._normal_text_bg if self._normal_text_bg else "white")
                    else:
                        # even if text is blanked, keep bg feedback if desired
                        self.tk.config(background=pressed_bg)
                except TclError:
                    pass

                if self._inverted_img:
                    try:
                        self.tk.config(image=self._inverted_img, compound="center")
                    except TclError:
                        pass

        def on_release(_event):
            self.restore_color_state()

        self.tk.bind("<ButtonPress-1>", on_press, add="+")
        self.tk.bind("<ButtonRelease-1>", on_release, add="+")

    def restore_color_state(self) -> None:
        with self._cv:
            # restore colors using tk-configured "normals" to match hb.tk.config(...)
            try:
                if self.text:
                    PushButton.bg.fset(self, self._normal_text_bg if self._normal_text_bg else "black")
                    PushButton.text_color.fset(self, self._normal_text_fg if self._normal_text_fg else "white")

                if self._normal_bg is not None:
                    self.tk.config(background=self._normal_bg)

                if self._normal_fg is not None:
                    self.tk.config(foreground=self._normal_fg)
            except TclError:
                pass

            # restore canonical image state
            if self._normal_img:
                try:
                    if str(self.tk.cget("image")) != str(self._normal_img):
                        self.tk.config(image=self._normal_img, compound="center")
                except TclError:
                    pass

    # ───────────────────────────────
    # Progress overlay (Canvas) — no button geometry changes
    # ───────────────────────────────
    def cancel_interaction(self) -> None:
        """Cancel an active press/hold/repeat without invoking callbacks."""
        with self._cv:
            self._pressed = False
            self._repeating = False
            self._held = True
            self._handled_hold = True
            self._press_time = None
            self._cancel_after()
            self._stop_progress()
            self.restore_color_state()

    def _progress_fraction(self) -> float:
        """How full the bar should be, read off the same clock the countdown runs on.

        Deliberately *not* wall-clock since _progress_start. That clock keeps running while
        a release is deferred, so the bar crept on for the whole recovery window after the
        finger came up. It could never fire -- _defer_release cancels the countdown -- but
        the bar said otherwise, which is worse than useless on a button that reboots the
        machine. Sharing _elapsed_held() means the bar freezes when the countdown pauses
        and resumes when it resumes, with no second copy of the elapsed time to keep in
        step. _progress_start survives only as the "progress is running" flag.
        """
        if not self._progress_start or self.hold_threshold <= 0:
            return 0.0
        return max(0.0, min(1.0, self._elapsed_held() / self.hold_threshold))

    def _ensure_overlay(self) -> None:
        if self._progress_canvas is not None:
            return

        top = self.tk.winfo_toplevel()

        canvas_bg = self._progress_empty_color or self._normal_bg or self._safe_tk_bg() or "white"
        self._progress_canvas = tk.Canvas(
            top,
            highlightthickness=0,
            bd=0,
            background=canvas_bg,
        )

        self._progress_bg_rect = self._progress_canvas.create_rectangle(
            0,
            0,
            0,
            0,
            outline="",
            fill=canvas_bg,
        )

        self._progress_rect = self._progress_canvas.create_rectangle(
            0,
            0,
            0,
            0,
            outline="",
            fill=self._progress_fill_color,
        )

        self._progress_text_item = self._progress_canvas.create_text(
            0,
            0,
            text="",
            anchor="center",
            fill=self._normal_fg or self._safe_tk_fg() or "black",
            font=self.tk.cget("font"),
        )

        # If overlay is visible and user releases on it, we still want release behavior.
        self._progress_canvas.bind("<ButtonRelease-1>", lambda e: self._on_release_event(e), add="+")
        if self._cancel_on_leave:
            # Only when asked. The overlay covers the button for all but the first
            # instant of a hold, so an unconditional cancel here overrode
            # cancel_on_leave=False and killed holds on the slightest touch drift.
            self._progress_canvas.bind("<Leave>", self._on_leave_candidate, add="+")
            self._progress_canvas.bind("<Enter>", self._on_enter_candidate, add="+")
        if self._press_recovery_ms > 0:
            self._progress_canvas.bind("<Motion>", self._on_motion_candidate, add="+")
        self._progress_canvas.place_forget()
        self._overlay_geometry = None

    def _safe_tk_bg(self) -> str | None:
        try:
            return str(self.tk.cget("background"))
        except TclError:
            return None

    def _safe_tk_fg(self) -> str | None:
        try:
            return str(self.tk.cget("foreground"))
        except TclError:
            return None

    def _position_overlay(self) -> None:
        if not self._progress_canvas:
            return

        top = self._progress_canvas.master  # toplevel

        try:
            bx = int(self.tk.winfo_rootx())
            by = int(self.tk.winfo_rooty())
            bw = int(self.tk.winfo_width())
            bh = int(self.tk.winfo_height())
            if bw <= 1 or bh <= 1:
                # Tk reports 1x1 for a widget it has not laid out yet. Accepting that
                # places a 1x1 overlay -- an invisible progress bar -- so force a
                # geometry pass and re-read before believing it.
                self.tk.update_idletasks()
                bw = int(self.tk.winfo_width())
                bh = int(self.tk.winfo_height())
            bw, bh = max(1, bw), max(1, bh)

            tx = int(top.winfo_rootx())
            ty = int(top.winfo_rooty())
        except TclError:
            return

        x = bx - tx
        y = by - ty

        geometry = (x, y, bw, bh)
        degenerate = bw <= 1 or bh <= 1
        if geometry != self._overlay_geometry:
            # Re-placing the window under the pointer can synthesise a crossing, which
            # used to cancel the hold. Only place when something actually moved; the
            # fill and label below still refresh on every call.
            #
            # A degenerate size is never cached: the widget is not laid out yet, so the
            # next call must place again rather than conclude nothing changed and leave
            # an invisible overlay in place for the rest of the hold.
            self._overlay_geometry = None if degenerate else geometry
            self._progress_canvas.place(x=x, y=y, width=bw, height=bh)
            self._vdiag("overlay-placed", f"geometry={geometry}{' DEGENERATE' if degenerate else ''}")

        canvas_bg = self._progress_empty_color or self._normal_bg or self._safe_tk_bg() or "white"
        try:
            self._progress_canvas.config(background=canvas_bg)
            self._progress_canvas.itemconfig(self._progress_bg_rect, fill=canvas_bg)
            self._progress_canvas.itemconfig(self._progress_rect, fill=self._progress_fill_color)
            self._progress_canvas.coords(self._progress_bg_rect, 0, 0, bw, bh)
        except TclError:
            return

        frac = self._progress_fraction() if self._pressed else 0.0
        fill_w = int(bw * frac)
        try:
            self._progress_canvas.coords(self._progress_rect, 0, 0, fill_w, bh)
        except TclError:
            return

        # label text on overlay
        if self._progress_text_item is not None:
            label = self._saved_button_text if self._saved_button_text is not None else self.text
            try:
                self._progress_canvas.itemconfig(
                    self._progress_text_item,
                    text=label,
                    fill=self._normal_fg or self._safe_tk_fg() or "black",
                    font=self.tk.cget("font"),
                )
                self._progress_canvas.coords(self._progress_text_item, bw // 2, bh // 2)
            except TclError:
                return

        # Raise the overlay widget safely (type-checker friendly; avoids Canvas item APIs)
        try:
            self._progress_canvas.tk.call("raise", str(self._progress_canvas))
        except TclError:
            pass

    def _set_overlay_fraction(self, frac: float) -> None:
        if not self._progress_canvas:
            return
        try:
            w = max(1, int(self._progress_canvas.winfo_width()))
            h = max(1, int(self._progress_canvas.winfo_height()))
        except TclError:
            return

        fill_w = int(w * max(0.0, min(1.0, frac)))
        fill_color = self._progress_fill_color
        if self._critical_fill_color and self._critical_fill_color != self._progress_fill_color:
            fill_color = self._progress_fill_color if frac < 0.70 else self._critical_fill_color
        try:
            if fill_color != self._progress_fill_color:
                self._progress_canvas.itemconfig(self._progress_rect, fill=fill_color)
            self._progress_canvas.coords(self._progress_rect, 0, 0, fill_w, h)
        except TclError:
            pass

    def _schedule_progress_tick(self) -> None:
        self._progress_after_id = self.tk.after(self._progress_update_ms, self._progress_tick)

    def _progress_tick(self) -> None:
        if not self._is_enabled():
            self._pressed = False
            self._repeating = False
            self._stop_progress()
            self._cancel_after()
            return
        if not self._pressed or not self._progress_start:
            return

        frac = self._progress_fraction()
        self._set_overlay_fraction(frac)

        if frac < 1.0:
            self._schedule_progress_tick()

    def _start_progress(self) -> None:
        if not self._show_hold_progress or self.hold_threshold <= 0 or not self._is_enabled():
            return

        self._progress_start = time.monotonic()
        self._cancel_progress_after()

        self._ensure_overlay()

        # Hide underlying label while overlay is visible (overlay draws the label)
        if self._saved_button_text is None:
            self._saved_button_text = self.text
            self.text = ""

        self._overlay_visible = True
        self._position_overlay()
        self._set_overlay_fraction(0.0)
        self._schedule_progress_tick()

    def _set_progress_full(self) -> None:
        if not self._overlay_visible:
            return
        self._set_overlay_fraction(1.0)

    def _stop_progress(self) -> None:
        self._cancel_progress_after()
        self._progress_start = None

        if self._progress_canvas:
            try:
                self._progress_canvas.place_forget()
            except TclError:
                pass
        self._overlay_geometry = None
        if self._overlay_visible:
            self._vdiag("overlay-hidden")
        self._overlay_visible = False

        # Restore underlying label
        if self._saved_button_text is not None:
            self.text = self._saved_button_text
            self._saved_button_text = None

        # Clear hover unconditionally (prevents "stuck hover" after touch release)
        self._on_hover_leave()

    # ───────────────────────────────
    # Timer cancellation helpers (narrow exceptions)
    # ───────────────────────────────
    def _cancel_after(self) -> None:
        after_id = self._after_id
        if not after_id:
            return
        self._after_id = None
        try:
            self.tk.after_cancel(after_id)
        except TclError:
            pass
        except RuntimeError:
            pass

    def _cancel_progress_after(self) -> None:
        after_id = self._progress_after_id
        if not after_id:
            return
        self._progress_after_id = None
        try:
            self.tk.after_cancel(after_id)
        except TclError:
            pass
        except RuntimeError:
            pass
