from __future__ import annotations

import unicodedata as ud
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.bell_horn_panel as mod
from src.pytrain.gui.controller.engine_gui_conf import (
    CYCLE_KEY,
    FONT_SIZE_EXCEPTIONS,
    PAUSE_KEY,
    PLAY_KEY,
    PLAY_PAUSE_KEY,
    PLAY_PAUSE_KEY_COMPACT,
)

# The codepoint that renders as a blue-and-white emoji wherever a color emoji font is installed.
EMOJI_PAUSE = "⏸"


class _Box:
    def __init__(self, _parent=None, **kwargs) -> None:
        self.kwargs = kwargs
        self.tk = SimpleNamespace(
            grid_rowconfigure=lambda *_a, **_kw: None,
            grid_columnconfigure=lambda *_a, **_kw: None,
        )


class _Text:
    def __init__(self, _parent=None, **kwargs) -> None:
        self.kwargs = kwargs
        self.text_size = None
        self.text_bold = None


# Whatever the panel asks a button for: its label and the font size it named (None = take the
# shared default that _build_keypad_button picks from FONT_SIZE_EXCEPTIONS).
S_24 = 24


def _keys(compact: bool, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int | None]]:
    labels: list[tuple[str, int | None]] = []
    monkeypatch.setattr(mod, "Box", _Box)
    monkeypatch.setattr(mod, "Text", _Text)
    monkeypatch.setattr(mod, "find_file", lambda name: name)
    host = SimpleNamespace(
        button_size=90,
        s_20=20,
        s_24=S_24,
        compact=compact,
        cache=lambda *_args: None,
        on_engine_command=lambda *_args: None,
    )
    host.make_keypad_button = lambda *args, **kwargs: (
        labels.append((args[1], kwargs.get("size"))),
        (object(), object()),
    )[1]

    panel = mod.BellHornPanel.__new__(mod.BellHornPanel)
    panel._gui = host
    panel.build(_Box())
    return labels


def _build(compact: bool, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Build the panel and return the labels it asked for, in order."""
    return [label for label, _size in _keys(compact, monkeypatch)]


def test_the_deck_avoids_the_emoji_pause_codepoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """U+23F8's default Unicode presentation is emoji, and SteamOS ships Noto Color Emoji.

    Its glyph is a blue rounded square with white bars, and being a bitmap it ignores the button's
    foreground color -- so half of "play slash pause" came out wrong on the Deck while the same
    string rendered correctly on the Pi, which has no color emoji font ahead of its text fonts.
    A U+FE0E text-presentation selector does not help: it was probed on the Deck and the emoji
    glyph still won, so the codepoint has to be avoided outright.
    """
    labels = _build(compact=True, monkeypatch=monkeypatch)

    assert PLAY_PAUSE_KEY_COMPACT in labels
    assert PLAY_PAUSE_KEY not in labels
    assert EMOJI_PAUSE not in "".join(labels), "no label may carry a codepoint an emoji font claims"


def test_the_pi_keeps_the_glyph_it_already_renders_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    labels = _build(compact=False, monkeypatch=monkeypatch)

    assert PLAY_PAUSE_KEY in labels
    assert PLAY_PAUSE_KEY_COMPACT not in labels


def test_both_rows_keep_their_other_keys_in_either_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # The swap must touch the Bell play/pause button and nothing else: the Horn row's plain Play
    # triangle is unaffected, since U+25B6 defaults to text presentation.
    for compact in (True, False):
        labels = _build(compact=compact, monkeypatch=monkeypatch)

        assert labels.count(CYCLE_KEY) == 2, f"compact={compact}: one cycle key per row"
        assert PLAY_KEY in labels
        assert labels.count("On") == 1 and labels.count("Off") == 1


def test_the_replacement_is_monochrome_by_construction() -> None:
    # U+25AE has no emoji form at all, and sits in the same Geometric Shapes block as the play
    # triangle, so one font serves the whole label rather than two.
    bars = PLAY_PAUSE_KEY_COMPACT.split("/")[1]

    assert set(bars) == {"▮"}
    assert ud.name(bars[0]) == "BLACK VERTICAL RECTANGLE"
    assert ud.name(PLAY_PAUSE_KEY_COMPACT[0]) == "BLACK RIGHT-POINTING TRIANGLE"


def test_the_replacement_is_no_wider_than_what_it_replaces() -> None:
    # A keypad cell is a fixed square with pack_propagate(False), so an over-wide label is clipped
    # rather than given room. Character count is the only proxy available headless; the measured
    # widths on the Deck were ~140px against ~155px for the emoji form.
    assert len(PLAY_PAUSE_KEY_COMPACT) <= len(PLAY_PAUSE_KEY) + 1


def test_every_glyph_label_still_gets_the_large_font() -> None:
    # FONT_SIZE_EXCEPTIONS is matched by value (guizero_base: `label in FONT_SIZE_EXCEPTIONS`), so
    # a new glyph string that is not in the set would silently render at body-text size.
    for key in (CYCLE_KEY, PLAY_KEY, PLAY_PAUSE_KEY, PLAY_PAUSE_KEY_COMPACT, PAUSE_KEY):
        assert key in FONT_SIZE_EXCEPTIONS, key


def test_the_deck_names_a_smaller_size_for_the_play_pause_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Four characters against one for every other key on the row. At the shared s_30 that
    # _build_keypad_button picks for anything in FONT_SIZE_EXCEPTIONS it filled its cell edge to
    # edge, and a cell is a fixed square with pack_propagate off, so there was no margin left.
    sizes = dict(_keys(compact=True, monkeypatch=monkeypatch))

    assert sizes[PLAY_PAUSE_KEY_COMPACT] == S_24


def test_the_pi_names_no_size_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    # Passing None is what leaves portrait's path untouched: _build_keypad_button then takes the
    # shared s_30 from FONT_SIZE_EXCEPTIONS exactly as it did before.
    sizes = dict(_keys(compact=False, monkeypatch=monkeypatch))

    assert sizes[PLAY_PAUSE_KEY] is None


def test_no_other_key_gets_its_size_named_in_either_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # The whole point of naming one: every other key still resolves its own size from the shared
    # rule, so this stays a single exception rather than the start of a table.
    for compact in (True, False):
        named = [label for label, size in _keys(compact, monkeypatch) if size is not None]

        assert named in ([PLAY_PAUSE_KEY_COMPACT], []), f"compact={compact}: {named}"
