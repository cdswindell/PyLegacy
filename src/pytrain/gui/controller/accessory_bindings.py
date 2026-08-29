#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
"""What a gamepad control does when the panel it points at is not showing an engine.

A *context* is a name for a situation a pane can be in -- a track switch on display, a route,
an accessory -- together with a table saying what each control does there. The input router
asks the pane which contexts it is in, walks the answer most-specific-first, and takes the
first entry it finds. Anything a context claims is handled here and goes no further; anything
it does not claim falls through to the ordinary engine handling.

The point of stating it as data is that the alternative does not scale. Before this module the
switch and route remaps were two module constants apiece and a hand-written handler each, and
the two handlers were the same forty lines with three differences between them. A third panel
type would have been a third copy. Here the differences are fields:

* ``axis_signed`` -- a route fires only when the stick goes up or right, because a route has no
  un-fire for the other two deflections to mean. A switch ignores the sign, having two things
  it can be asked to do and a pair of axes to ask them with.
* ``axis_held`` -- an ASC2's momentary output stays energised for as long as the stick is away
  from center, because that is what the on-screen key does while a finger rests on it. A
  latched axis has no release to give it, and an analog one sends a value rather than a phase.
* ``yields_to_catalog`` -- the face buttons are how an entry in the scope catalog is confirmed,
  so a context lets go of them while that list is up.
* ``claim`` -- the verb for a control a context takes and does nothing with. A route claims the
  horn button rather than passing it on, because the pane has no engine in it and the horn
  would otherwise sound at whichever engine the pane held before the route was picked.

This module is deliberately free of ``tkinter`` and ``guizero``, as ``control_labels`` is, so
the whole map can be read and tested without a display.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Collection, Mapping

log = logging.getLogger(__name__)

# A context name has to be a plain identifier: the names are written into a profile by hand and
# read back as dictionary keys, so anything else is a typo rather than an intention. New names
# are allowed -- a profile may add a context of its own -- which is why this is a shape check
# and not a membership test against the defaults.
_CONTEXT_NAME = re.compile(r"^[a-z][a-z0-9_]*$")

# The runtime action names a trigger bound to startup/shutdown emits once it can tell a short
# press from a held one. Spelled out rather than imported from ``steam_deck_input``, which
# imports this module; ``test_accessory_bindings`` asserts the two agree.
STARTUP_IMMEDIATE = "startup_immediate"
STARTUP_DELAYED = "startup_delayed"
SHUTDOWN_IMMEDIATE = "shutdown_immediate"
SHUTDOWN_DELAYED = "shutdown_delayed"

# The dispatch verbs a binding may name. Each is the *way* a command is sent, as against the
# command itself: the router holds the small amount of code each one needs and the table says
# only which of them applies.
VERB_SWITCH_THRU = "switch_thru"
VERB_SWITCH_OUT = "switch_out"
VERB_ROUTE_FIRE = "route_fire"
VERB_ACC_COMMAND = "acc_command"
VERB_ENGINE_COMMAND = "engine_command"
VERB_LCS_ON = "lcs_on"
VERB_LCS_OFF = "lcs_off"
VERB_ASC2_MOMENTARY = "asc2_momentary"
VERB_ACC_THROTTLE = "acc_throttle"
VERB_CLAIM = "claim"

# The verbs that act on a stick position rather than on a press. An action bound to one of
# these arrives every time the stick moves, and is sent for as long as it is held away from
# center -- as against the latched axis bindings, which fire once per deflection.
ANALOG_VERBS = frozenset({VERB_ACC_THROTTLE})

# Axis actions may provide a dispatch for each sign before falling back to the plain action.
# The positive member is deliberately second: the router uses the first entry for a negative
# value and the second for a positive value. Keeping this mapping here makes the sign convention
# part of the data-driven binding mechanism rather than a special case in the input router.
AXIS_DIRECTION_NAMES: Mapping[str, tuple[str, str]] = {
    "direction": ("direction_left", "direction_right"),
    "throttle": ("throttle_down", "throttle_up"),
}
AXIS_VARIANT_ACTIONS = frozenset(name for pair in AXIS_DIRECTION_NAMES.values() for name in pair)

KNOWN_VERBS = frozenset(
    {
        VERB_SWITCH_THRU,
        VERB_SWITCH_OUT,
        VERB_ROUTE_FIRE,
        VERB_ACC_COMMAND,
        VERB_ENGINE_COMMAND,
        VERB_LCS_ON,
        VERB_LCS_OFF,
        VERB_ASC2_MOMENTARY,
        VERB_ACC_THROTTLE,
        VERB_CLAIM,
    }
)


@dataclass(frozen=True)
class Dispatch:
    """What one control does in one context.

    ``verb`` says how to send and ``command`` what to send, where the verb needs telling. The
    remaining fields are the handful of behaviours that cannot be expressed as a command name.
    """

    verb: str
    command: str | tuple[str, ...] | None = None
    # The action arrives as a stick position rather than as a press, and fires once per
    # deflection: the stick has to come back near center before it can fire again. Without
    # this a stick held over would send a command every poll for as long as a thumb rested
    # on it.
    axis_latched: bool = False
    # Only a positive deflection acts (up, the sticks being inverted in the profile, or
    # right). False means the sign is ignored and how far the stick moved is all that
    # matters. The latch is taken either way, so returning from a pull is a movement through
    # the firing range rather than a fire.
    axis_signed: bool = False
    # The action arrives as a stick position and holds something on while it is deflected: the
    # press when the value first crosses the profile's direction threshold, the release when it
    # falls back inside the hysteresis band. The third of the three axis modes, and the only one
    # with a release: a momentary output has to be let go of, and a stick's letting go is a
    # value rather than an event.
    axis_held: bool = False
    data: int | None = None
    # Re-send while the control is held, on the profile's repeat interval.
    repeat: bool = False
    # Deliver the release as well as the press. Only a momentary output needs this; every
    # other binding acts on the press and has its release swallowed.
    both_phases: bool = False

    @property
    def is_claim_only(self) -> bool:
        return self.verb == VERB_CLAIM

    @property
    def is_analog(self) -> bool:
        """True when the value matters rather than the press: a stick driving a speed."""
        return self.verb in ANALOG_VERBS

    @property
    def is_axis(self) -> bool:
        """True for a binding driven by a stick position rather than by a press.

        Latched and held alike, which is what the derived ``*_AXIS_ACTIONS`` name sets want:
        either way the action arrives as a value and none of the button handling applies.
        """
        return self.axis_latched or self.axis_held

    @property
    def axis_modes(self) -> int:
        """How many of the three axis modes this binding claims; more than one is invalid.

        Nothing in the dataclass can stop a table entry asking for two, so the count is stated
        here and checked where the verbs are checked. The three are mutually exclusive in
        practice -- one fire per deflection, a press held for as long as the deflection lasts,
        or a value sent every time it changes -- and there is no sensible reading of a pair.
        """
        return sum((self.axis_latched, self.axis_held, self.is_analog))


@dataclass(frozen=True)
class ContextSpec:
    """A named situation and the bindings that apply in it."""

    name: str
    # The next link in the chain. A context states only its differences from the one it
    # inherits, which is how a more specific panel type reuses a more general one's bindings
    # without restating them.
    inherits: str | None = None
    bindings: Mapping[str, Dispatch | None] = field(default_factory=dict)
    # Swallow every action that reaches this context unbound, rather than letting it fall
    # through to the engine handling. What a pane with no engine in it wants: a stick or a
    # trigger passed on would address whichever engine the pane held before its scope changed.
    claims_unbound: bool = False
    # Actions this context lets go of while the scope catalog is open. The catalog is where
    # the thing this pane is showing gets picked, and the face buttons are how an entry in it
    # is confirmed.
    yields_to_catalog: frozenset[str] = frozenset()
    # Actions whose claim must also drop whatever the control had left running: a repeating
    # button command and a sequence-control burst. Either may have been under way when the
    # pane changed scope, and the release is swallowed, so nothing else would stop the router
    # re-sending at a pane with no engine in it.
    clears_held: frozenset[str] = frozenset()


# The controls a pane showing a track switch takes. There is no engine in it to drive, so the
# controls that would drive one throw the switch instead: the face button that runs an engine's
# sequence control (A in the bundled profile) and the trigger that shuts one down (L2) throw it
# through, the button that sounds the horn (Y) and the trigger that starts one up (R2) throw it
# out, and each stick throws its own pane's switch -- pushed left or right (the direction axis)
# through, up or down (the throttle axis) out.
#
# Keyed on the action rather than on the physical axis or button, so a custom profile that puts
# these bindings elsewhere keeps working. This is the same indirection the open catalog uses to
# claim the D-pad and the admin panel to claim L1.
_SWITCH_BINDINGS: Mapping[str, Dispatch | None] = {
    "direction": Dispatch(VERB_SWITCH_THRU, axis_latched=True),
    "throttle": Dispatch(VERB_SWITCH_OUT, axis_latched=True),
    "sequence_control": Dispatch(VERB_SWITCH_THRU),
    "horn": Dispatch(VERB_SWITCH_OUT),
    "shutdown": Dispatch(VERB_SWITCH_THRU),
    SHUTDOWN_IMMEDIATE: Dispatch(VERB_SWITCH_THRU),
    SHUTDOWN_DELAYED: Dispatch(VERB_SWITCH_THRU),
    "startup": Dispatch(VERB_SWITCH_OUT),
    STARTUP_IMMEDIATE: Dispatch(VERB_SWITCH_OUT),
    STARTUP_DELAYED: Dispatch(VERB_SWITCH_OUT),
}

# The same repurposing for a pane showing a route, which has no engine to drive either. A route
# has one thing to do rather than two, so both triggers fire it and there is nothing for the
# thru/out split to distinguish.
#
# Of the two face buttons only the one that throws a switch through fires -- A in the bundled
# profile, the button that confirms an entry in the catalog and so already reads as "do it". Y
# is not made a second way to say the one thing, a route having no un-fire for it to mean; it is
# claimed all the same and does nothing, which is the swallow the down and left stick
# deflections get and is taken for their reason.
_ROUTE_BINDINGS: Mapping[str, Dispatch | None] = {
    "direction": Dispatch(VERB_ROUTE_FIRE, axis_latched=True, axis_signed=True),
    "throttle": Dispatch(VERB_ROUTE_FIRE, axis_latched=True, axis_signed=True),
    "sequence_control": Dispatch(VERB_ROUTE_FIRE),
    "horn": Dispatch(VERB_CLAIM),
    "shutdown": Dispatch(VERB_ROUTE_FIRE),
    SHUTDOWN_IMMEDIATE: Dispatch(VERB_ROUTE_FIRE),
    SHUTDOWN_DELAYED: Dispatch(VERB_ROUTE_FIRE),
    "startup": Dispatch(VERB_ROUTE_FIRE),
    STARTUP_IMMEDIATE: Dispatch(VERB_ROUTE_FIRE),
    STARTUP_DELAYED: Dispatch(VERB_ROUTE_FIRE),
}

# The face buttons, for both pane types. They are named apart from the rest because they are
# the two the catalog takes back and the two that can leave something running behind them.
_FACE_BUTTON_ACTIONS = frozenset({"sequence_control", "horn"})

SWITCH_CONTEXT = "switch"
ROUTE_CONTEXT = "route"

# The accessory contexts. ``acc`` is the base every accessory panel is in, whichever panel that
# is; the three that follow name the panel actually on screen and are chained over it. Their
# bindings arrive with the panels they belong to; the base binds nothing and exists for the
# swallow, so an accessory panel cannot pass a stick or a trigger on to whatever engine the pane
# held before its scope changed.
ACC_CONTEXT = "acc"
ACC_GENERIC_CONTEXT = "acc_generic"
ACC_BPC2_CONTEXT = "acc_bpc2"
ACC_ASC2_CONTEXT = "acc_asc2"

# The panel kinds ``KeypadView.accessory_panel_kind`` reports, named here rather than in the
# view so that the table, the view and the input layer all spell them the same way -- and so
# that the mapping below, which is the whole of the correspondence between what is drawn and
# what claims the pad, can be read without a display.
PANEL_SENSOR_TRACK = "sensor_track"
PANEL_AMC2 = "amc2"
PANEL_BPC2 = "bpc2"
PANEL_ASC2 = "asc2"
PANEL_GENERIC = "generic"

# Panel on screen -> the context chain that claims the pad for it, most specific first.
#
# Sensor Track and AMC2 are absent deliberately: neither panel's controls have been given
# gamepad bindings, and a chain of nothing but the base would claim every control and send
# none of them, which is worse than leaving the pad alone.
PANEL_CONTEXT_CHAINS: Mapping[str, tuple[str, ...]] = {
    PANEL_GENERIC: (ACC_GENERIC_CONTEXT, ACC_CONTEXT),
    PANEL_BPC2: (ACC_BPC2_CONTEXT, ACC_CONTEXT),
    PANEL_ASC2: (ACC_ASC2_CONTEXT, ACC_BPC2_CONTEXT, ACC_CONTEXT),
}

# The controls a pane showing the generic accessory panel takes. Every one of them is a key
# that panel already offers on screen, so nothing here is invented for the pad: the vertical
# stick works the speed slider, the shoulder buttons the two coupler keys, and the D-pad the
# Boost and Brake pair.
#
# The horizontal stick is bound to TOGGLE_DIRECTION rather than to a forward/reverse pair,
# there being no left-hand or right-hand form of a toggle. It is latched and *not* signed, so
# a push either way toggles exactly once and a thumb resting on the stick does not flip a
# crane back and forth for as long as it rests there.
#
# SET_ADDRESS and AUX1_OPT_ONE are left unbound deliberately. Both are keys on this panel, and
# re-addressing an accessory is not something a button somebody can brush should do.
_ACC_GENERIC_BINDINGS: Mapping[str, Dispatch | None] = {
    "throttle": Dispatch(VERB_ACC_THROTTLE),
    "direction": Dispatch(VERB_ACC_COMMAND, command="TOGGLE_DIRECTION", axis_latched=True),
    "rear_coupler": Dispatch(VERB_ACC_COMMAND, command="REAR_COUPLER"),
    "front_coupler": Dispatch(VERB_ACC_COMMAND, command="FRONT_COUPLER"),
    "dpad_up": Dispatch(VERB_ACC_COMMAND, command="BOOST", repeat=True),
    "dpad_down": Dispatch(VERB_ACC_COMMAND, command="BRAKE", repeat=True),
}

# The two shoulder buttons are the catalog-jump and admin-chord modifiers as well as the
# coupler keys, so this context lets go of them while either of those panels is up -- the same
# carve-out the face buttons get, and for the same reason: a reader picking an accessory out of
# the catalog is not asking for a coupler.
_ACC_GENERIC_MODIFIER_ACTIONS = frozenset({"front_coupler", "rear_coupler"})

# The controls a pane showing a power district takes. The panel has two keys on it, On and
# Off, and this gives each of them two ways to be reached: the trigger a pane would otherwise
# start or shut an engine down with, and the D-pad pointed the way the key sits on screen.
#
# Keyed on ``startup`` / ``shutdown`` rather than on the triggers themselves, so a profile that
# moves them keeps the power district behaviour with them. The delayed and immediate forms a
# trigger emits once it can tell a short press from a held one are bound alongside: a power
# district has no held variant to wait for, so either form means the same thing here.
_ACC_BPC2_BINDINGS: Mapping[str, Dispatch | None] = {
    "startup": Dispatch(VERB_LCS_ON),
    STARTUP_IMMEDIATE: Dispatch(VERB_LCS_ON),
    STARTUP_DELAYED: Dispatch(VERB_LCS_ON),
    "shutdown": Dispatch(VERB_LCS_OFF),
    SHUTDOWN_IMMEDIATE: Dispatch(VERB_LCS_OFF),
    SHUTDOWN_DELAYED: Dispatch(VERB_LCS_OFF),
    "dpad_right": Dispatch(VERB_LCS_ON),
    "dpad_left": Dispatch(VERB_LCS_OFF),
    "direction_right": Dispatch(VERB_LCS_ON, axis_latched=True),
    "direction_left": Dispatch(VERB_LCS_OFF, axis_latched=True),
}

# An ASC2 is a power district plus one key more, so this context states only that key and
# inherits the On/Off pair rather than restating it.
#
# The momentary output is the only binding in the whole table that needs the release as well
# as the press: the on-screen key energises the output while it is held and drops it when it
# is let go, and a button that did only the first half would leave it on.
#
# The vertical stick reaches that same output, and is bound as the plain ``throttle`` action
# rather than as the up/down pair: the variant lookup finds neither and falls back here, so a
# push either way energises it. There is no second output for one of them to mean instead.
_ACC_ASC2_BINDINGS: Mapping[str, Dispatch | None] = {
    "sequence_control": Dispatch(VERB_ASC2_MOMENTARY, both_phases=True),
    "dpad_up": Dispatch(VERB_ASC2_MOMENTARY, both_phases=True),
    "throttle": Dispatch(VERB_ASC2_MOMENTARY, axis_held=True, both_phases=True),
}

DEFAULT_CONTEXTS: Mapping[str, ContextSpec] = {
    SWITCH_CONTEXT: ContextSpec(
        name=SWITCH_CONTEXT,
        bindings=_SWITCH_BINDINGS,
        yields_to_catalog=_FACE_BUTTON_ACTIONS,
        clears_held=_FACE_BUTTON_ACTIONS,
    ),
    ROUTE_CONTEXT: ContextSpec(
        name=ROUTE_CONTEXT,
        bindings=_ROUTE_BINDINGS,
        yields_to_catalog=_FACE_BUTTON_ACTIONS,
        clears_held=_FACE_BUTTON_ACTIONS,
    ),
    ACC_CONTEXT: ContextSpec(
        name=ACC_CONTEXT,
        claims_unbound=True,
        yields_to_catalog=_FACE_BUTTON_ACTIONS,
        clears_held=_FACE_BUTTON_ACTIONS,
    ),
    ACC_GENERIC_CONTEXT: ContextSpec(
        name=ACC_GENERIC_CONTEXT,
        inherits=ACC_CONTEXT,
        bindings=_ACC_GENERIC_BINDINGS,
        yields_to_catalog=_FACE_BUTTON_ACTIONS | _ACC_GENERIC_MODIFIER_ACTIONS,
        clears_held=_FACE_BUTTON_ACTIONS,
    ),
    # Neither of the two below inherits ``acc_generic``, deliberately: there is no coupler and
    # no Boost key on a power district or an ASC2 panel, so a control bound to one of those in
    # the generic context has nothing to act on here. It is claimed by the ``acc`` base and
    # sent nowhere, which is the whole point of keeping the aux keys out of that base.
    ACC_BPC2_CONTEXT: ContextSpec(
        name=ACC_BPC2_CONTEXT,
        inherits=ACC_CONTEXT,
        bindings=_ACC_BPC2_BINDINGS,
        yields_to_catalog=_FACE_BUTTON_ACTIONS,
        clears_held=_FACE_BUTTON_ACTIONS,
    ),
    ACC_ASC2_CONTEXT: ContextSpec(
        name=ACC_ASC2_CONTEXT,
        inherits=ACC_BPC2_CONTEXT,
        bindings=_ACC_ASC2_BINDINGS,
        yields_to_catalog=_FACE_BUTTON_ACTIONS,
        clears_held=_FACE_BUTTON_ACTIONS,
    ),
}


def merge_contexts(
    raw: Any,
    *,
    base: Mapping[str, ContextSpec] = DEFAULT_CONTEXTS,
    known_actions: Collection[str] | None = None,
    known_verbs: Collection[str] = KNOWN_VERBS,
    protected_actions: Collection[str] = (),
) -> Mapping[str, ContextSpec]:
    """``base`` with a profile's ``contexts`` section laid over it.

    A profile may override an entry, add one, add a whole context, or remove a binding by
    naming it ``null`` -- the last being why "unbind this" is expressible rather than merely
    omitted. Anything malformed is logged and skipped, never raised: the discipline
    ``ControlProfile.load`` already keeps, on the grounds that one bad table entry must not
    take the gamepad out altogether.

    ``protected_actions`` are refused outright. They are the global-target safety actions --
    HALT above all -- which no context has any business rebinding or swallowing, in the same
    spirit as ``_validate_action_target`` refusing a HALT that is not global.
    """
    if raw is None:
        return base
    if not isinstance(raw, Mapping):
        log.warning("contexts must be an object; ignoring")
        return base
    merged = dict(base)
    for name, entry in raw.items():
        if not isinstance(name, str) or not _CONTEXT_NAME.match(name):
            log.warning(f"Ignoring context with invalid name: {name!r}")
            continue
        if entry is None:
            # A whole context removed. Dropped rather than emptied so nothing in the chain
            # claims for it either.
            merged.pop(name, None)
            continue
        if not isinstance(entry, Mapping):
            log.warning(f"Ignoring context {name!r}: must be an object")
            continue
        current = merged.get(name)
        spec = _merge_one(
            name,
            entry,
            current,
            known_actions=known_actions,
            known_verbs=known_verbs,
            protected_actions=frozenset(protected_actions),
        )
        if spec is not None:
            merged[name] = spec
    return merged


def _merge_one(
    name: str,
    entry: Mapping[str, Any],
    current: ContextSpec | None,
    *,
    known_actions: Collection[str] | None,
    known_verbs: Collection[str],
    protected_actions: frozenset[str],
) -> ContextSpec | None:
    inherits = current.inherits if current is not None else None
    if "inherits" in entry:
        raw_inherits = entry["inherits"]
        if raw_inherits is None or (isinstance(raw_inherits, str) and _CONTEXT_NAME.match(raw_inherits)):
            inherits = raw_inherits
        else:
            log.warning(f"Ignoring inherits for context {name!r}: {raw_inherits!r}")

    bindings: dict[str, Dispatch | None] = dict(current.bindings) if current is not None else {}
    raw_bindings = entry.get("bindings", {})
    if not isinstance(raw_bindings, Mapping):
        log.warning(f"Ignoring bindings for context {name!r}: must be an object")
        raw_bindings = {}
    for action, raw_dispatch in raw_bindings.items():
        if not isinstance(action, str):
            log.warning(f"Ignoring binding in context {name!r}: action must be a string")
            continue
        if action in protected_actions:
            log.warning(f"Refusing to rebind protected action {action!r} in context {name!r}")
            continue
        if known_actions is not None and action not in known_actions:
            log.warning(f"Ignoring unknown action {action!r} in context {name!r}")
            continue
        if raw_dispatch is None:
            # An explicit unbind, which ``resolve`` honours by stopping the walk. Kept as a
            # None entry rather than deleted, so it also masks anything inherited.
            bindings[action] = None
            continue
        dispatch = _parse_dispatch(name, action, raw_dispatch, known_verbs)
        if dispatch is not None:
            bindings[action] = dispatch

    return ContextSpec(
        name=name,
        inherits=inherits,
        bindings=bindings,
        claims_unbound=_flag(entry, "claims_unbound", current.claims_unbound if current else False, name),
        yields_to_catalog=_names(
            entry, "yields_to_catalog", current.yields_to_catalog if current else frozenset(), name
        ),
        clears_held=_names(entry, "clears_held", current.clears_held if current else frozenset(), name),
    )


def _parse_dispatch(
    context: str,
    action: str,
    raw: Any,
    known_verbs: Collection[str],
) -> Dispatch | None:
    if not isinstance(raw, Mapping):
        log.warning(f"Ignoring binding {action!r} in context {context!r}: must be an object")
        return None
    verb = raw.get("verb")
    if verb not in known_verbs:
        log.warning(f"Ignoring binding {action!r} in context {context!r}: unknown verb {verb!r}")
        return None
    command = raw.get("command")
    if command is not None and not isinstance(command, (str, list)):
        log.warning(f"Ignoring binding {action!r} in context {context!r}: invalid command {command!r}")
        return None
    if isinstance(command, list):
        command = tuple(command)
    data = raw.get("data")
    if data is not None and (isinstance(data, bool) or not isinstance(data, int)):
        log.warning(f"Ignoring binding {action!r} in context {context!r}: invalid data {data!r}")
        return None
    dispatch = Dispatch(
        verb=verb,
        command=command,
        axis_latched=bool(raw.get("axis_latched", False)),
        axis_signed=bool(raw.get("axis_signed", False)),
        axis_held=bool(raw.get("axis_held", False)),
        data=data,
        repeat=bool(raw.get("repeat", False)),
        both_phases=bool(raw.get("both_phases", False)),
    )
    if dispatch.axis_modes > 1:
        # Two axis modes at once has no reading: the router would have to pick one, and which
        # one it picked would be an accident of the order of its branches. Logged and dropped,
        # the discipline the rest of this loader keeps.
        log.warning(f"Ignoring binding {action!r} in context {context!r}: claims more than one axis mode")
        return None
    return dispatch


def _flag(entry: Mapping[str, Any], key: str, default: bool, context: str) -> bool:
    if key not in entry:
        return default
    value = entry[key]
    if not isinstance(value, bool):
        log.warning(f"Ignoring {key} for context {context!r}: must be true or false")
        return default
    return value


def _names(entry: Mapping[str, Any], key: str, default: frozenset[str], context: str) -> frozenset[str]:
    if key not in entry:
        return default
    value = entry[key]
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        log.warning(f"Ignoring {key} for context {context!r}: must be a list of action names")
        return default
    return frozenset(value)


@dataclass(frozen=True)
class Resolution:
    """The outcome of asking the table what a control does in a pane's contexts."""

    context: ContextSpec
    dispatch: Dispatch | None

    @property
    def claimed_only(self) -> bool:
        """True when the action is taken and nothing is sent."""
        return self.dispatch is None or self.dispatch.is_claim_only


def resolve(
    chain: tuple[str, ...],
    action: str,
    contexts: Mapping[str, ContextSpec] = DEFAULT_CONTEXTS,
) -> Resolution | None:
    """What ``action`` does for a pane reporting ``chain``, or None if nothing claims it.

    The chain arrives most specific first, so the walk takes the first context that has an
    opinion. An explicit ``None`` binding is an opinion: it says this context unbinds the
    action, which is how a profile expresses "leave this control alone here" as against merely
    not mentioning it. Either way the walk stops, and the action is still claimed if any
    context in the chain claims what it has not bound.
    """
    seen: set[str] = set()
    claimer: ContextSpec | None = None
    unbound = False
    for name in _expand(chain, contexts, seen):
        spec = contexts.get(name)
        if spec is None:
            continue
        if claimer is None and spec.claims_unbound:
            claimer = spec
        if unbound or action not in spec.bindings:
            # Either nothing here has an opinion, or a nearer link has already said "unbound"
            # and the walk goes on only to find whichever context does the swallowing.
            continue
        dispatch = spec.bindings[action]
        if dispatch is not None:
            return Resolution(spec, dispatch)
        # Explicitly unbound here: no further binding is looked at, so an override cannot fall
        # through to the entry it was written to remove. A claiming context still swallows it.
        unbound = True
    return Resolution(claimer, None) if claimer is not None else None


def resolve_axis(
    chain: tuple[str, ...],
    action: str,
    value: float,
    contexts: Mapping[str, ContextSpec] = DEFAULT_CONTEXTS,
) -> Resolution | None:
    """Resolve an axis variant before its plain action, based on the value's sign.

    A context that claims unbound actions must not prevent the plain-action fallback: ``acc``
    claims every unmatched action, but its claim is not a directional variant binding. An
    explicit ``None`` *is* a binding, however, and therefore masks the plain action for that
    sign, allowing a profile to unbind one side independently.
    """
    variants = AXIS_DIRECTION_NAMES.get(action)
    if variants is not None:
        variant = variants[1] if value > 0 else variants[0]
        if _has_binding(chain, variant, contexts):
            return resolve(chain, variant, contexts)
    return resolve(chain, action, contexts)


def _has_binding(chain: tuple[str, ...], action: str, contexts: Mapping[str, ContextSpec]) -> bool:
    """Whether an action is explicitly listed in any context in the expanded chain."""
    seen: set[str] = set()
    return any(action in contexts[name].bindings for name in _expand(chain, contexts, seen) if name in contexts)


def _expand(
    chain: tuple[str, ...],
    contexts: Mapping[str, ContextSpec],
    seen: set[str],
):
    """The chain with each link's ``inherits`` followed, in order and without repeats."""
    for name in chain:
        current: str | None = name
        while current is not None and current not in seen:
            seen.add(current)
            yield current
            spec = contexts.get(current)
            current = spec.inherits if spec is not None else None


def actions_with_verb(spec: ContextSpec, *verbs: str) -> frozenset[str]:
    """The actions ``spec`` binds to any of ``verbs``. Used to derive the legacy name sets."""
    wanted = frozenset(verbs)
    return frozenset(
        action for action, dispatch in spec.bindings.items() if dispatch is not None and dispatch.verb in wanted
    )


def bound_actions(spec: ContextSpec) -> frozenset[str]:
    """Every action ``spec`` has an entry for, claim-only ones included."""
    return frozenset(action for action, dispatch in spec.bindings.items() if dispatch is not None)


def axis_actions(spec: ContextSpec) -> frozenset[str]:
    """The actions ``spec`` binds that arrive as a stick position rather than as a press.

    Every axis mode counts, not the latched one alone: a held binding is as much a stick as a
    latched one, and leaving it out would give the derived name sets a second, narrower idea of
    what an axis is.
    """
    return frozenset(action for action, dispatch in spec.bindings.items() if dispatch is not None and dispatch.is_axis)
