#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from unittest.mock import Mock, call

import pytest

from pytrain.gui.components import touch_scrollbar as mod


@pytest.mark.parametrize("width,length", [(38, 64), (48, 80)])
def test_touch_scrollbar_keeps_native_behavior_and_sets_minimum_image_size(monkeypatch, width, length):
    initialize = Mock(return_value=None)
    configure = Mock()
    style = Mock()
    images = [Mock(), Mock()]
    photo = Mock(side_effect=images)
    monkeypatch.setattr(mod.ttk.Scrollbar, "__init__", initialize)
    monkeypatch.setattr(mod.TouchScrollbar, "__str__", lambda _self: "test_scrollbar")
    monkeypatch.setattr(mod.TouchScrollbar, "configure", configure)
    monkeypatch.setattr(mod.ttk, "Style", Mock(return_value=style))
    monkeypatch.setattr(mod.tk, "PhotoImage", photo)
    master, command = object(), Mock()
    bar = mod.TouchScrollbar(master, command=command, width=width, min_thumb_length=length)

    initialize.assert_called_once_with(master, orient="vertical", command=command, takefocus=0)
    assert photo.call_args_list == [call(master=bar, width=width, height=length)] * 2
    assert bar._thumb_images == images
    for image, color in zip(images, (mod.BAR_COLOR, mod.BAR_ACTIVE_COLOR)):
        assert image.put.call_args_list == [
            call(mod.BAR_EDGE_COLOR, to=(0, 0, width, length)),
            call(color, to=(mod.BAR_EDGE_PX, mod.BAR_EDGE_PX, width - mod.BAR_EDGE_PX, length - mod.BAR_EDGE_PX)),
        ]
    name = configure.call_args.kwargs["style"]
    style.element_create.assert_any_call(
        f"{name}.thumb",
        "image",
        images[0],
        ("pressed", images[1]),
        ("active", images[1]),
        border=mod.BAR_EDGE_PX,
        sticky="nsew",
    )
    for part in ("trough", "uparrow", "downarrow"):
        style.element_create.assert_any_call(f"{name}.{part}", "from", "clam", f"Scrollbar.{part}")
    assert style.layout.call_args.args[1][0][1]["children"] == [
        (f"{name}.uparrow", {"side": "top", "sticky": "ew"}),
        (f"{name}.downarrow", {"side": "bottom", "sticky": "ew"}),
        (f"{name}.thumb", {"sticky": "nswe"}),
    ]
    colors = style.configure.call_args.kwargs
    assert colors["background"] == mod.BAR_COLOR
    assert colors["troughcolor"] == mod.BAR_TROUGH_COLOR
    assert colors["bordercolor"] == mod.BAR_EDGE_COLOR
    style.map.assert_called_once_with(
        name, background=[("pressed", mod.BAR_ACTIVE_COLOR), ("active", mod.BAR_ACTIVE_COLOR)]
    )
