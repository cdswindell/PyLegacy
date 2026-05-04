from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.image_presenter as mod
from src.pytrain.protocol.constants import CommandScope


class _NullContext:
    def __enter__(self):
        return self

    @staticmethod
    def __exit__(exc_type, exc, tb):
        return False


class _DummyImageBox:
    def __init__(self) -> None:
        self.visible = False
        self.show_calls = 0
        self.hide_calls = 0
        self.config_calls: list[dict] = []
        self.tk = SimpleNamespace(config=self._config)

    def _config(self, **kwargs) -> None:
        self.config_calls.append(kwargs)

    def show(self) -> None:
        self.visible = True
        self.show_calls += 1

    def hide(self) -> None:
        self.visible = False
        self.hide_calls += 1


class _DummyImage:
    def __init__(self) -> None:
        self.image = None
        self.config_calls: list[dict] = []
        self.tk = SimpleNamespace(config=self._config)

    def _config(self, **kwargs) -> None:
        self.config_calls.append(kwargs)


def _build_host(scope: CommandScope, ids: dict[CommandScope, int], image_cache: dict | None = None):
    scoped_ids = dict(ids)
    return SimpleNamespace(
        scope=scope,
        _scope_tmcc_ids=scoped_ids,
        scope_tmcc_id=lambda the_scope=None: scoped_ids.get(the_scope or scope, 0),
        _image_cache=dict(image_cache or {}),
        image_box=_DummyImageBox(),
        image=_DummyImage(),
        active_state=None,
        avail_image_height=96,
        avail_image_width=192,
        locked=lambda: _NullContext(),
        _state_store=SimpleNamespace(get_state=lambda *_args, **_kwargs: None),
        state_store=SimpleNamespace(get_state=lambda *_args, **_kwargs: None),
        get_prod_info=lambda *_args, **_kwargs: pytest.fail("Unexpected product lookup"),
        get_scaled_image=lambda *_args, **_kwargs: object(),
        get_image=lambda *_args, **_kwargs: object(),
        get_configured_accessory=lambda *_args, **_kwargs: None,
        is_accessory_view=lambda *_args, **_kwargs: False,
        get_accessory_view=lambda *_args, **_kwargs: None,
        _image_presenter=None,
    )


def test_update_ignores_stale_engine_callback_for_other_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _build_host(
        scope=CommandScope.ACC,
        ids={CommandScope.ACC: 12, CommandScope.ENGINE: 7, CommandScope.TRAIN: 0},
        image_cache={(CommandScope.ENGINE, 7): object()},
    )
    presenter = mod.ImagePresenter(host)
    host._image_presenter = presenter

    calc_calls: list[int] = []
    monkeypatch.setattr(presenter, "calc_box_size", lambda: calc_calls.append(1) or (96, 192), raising=True)

    presenter.update(key=(CommandScope.ENGINE, 7))

    assert calc_calls == []
    assert host.image_box.show_calls == 0
    assert host.image_box.hide_calls == 0
    assert host.image.config_calls == []


def test_update_uses_cached_engine_image_without_recalculating_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    img = object()
    host = _build_host(
        scope=CommandScope.ENGINE,
        ids={CommandScope.ENGINE: 5, CommandScope.TRAIN: 0},
        image_cache={(CommandScope.ENGINE, 5): img},
    )
    presenter = mod.ImagePresenter(host)
    host._image_presenter = presenter

    calc_calls: list[int] = []
    monkeypatch.setattr(presenter, "calc_box_size", lambda: calc_calls.append(1) or (96, 192), raising=True)

    presenter.update(tmcc_id=5)

    assert calc_calls == []
    assert host.image_box.config_calls[-1] == {"width": 192, "height": 96}
    assert host.image.config_calls[-1] == {"image": img}
    assert host.image_box.show_calls == 1


def test_update_accepts_relevant_engine_callback_for_active_train(monkeypatch: pytest.MonkeyPatch) -> None:
    img = object()
    host = _build_host(
        scope=CommandScope.TRAIN,
        ids={CommandScope.TRAIN: 40, CommandScope.ENGINE: 7},
        image_cache={(CommandScope.ENGINE, 7): img},
    )
    presenter = mod.ImagePresenter(host)
    host._image_presenter = presenter

    calc_calls: list[int] = []
    monkeypatch.setattr(presenter, "calc_box_size", lambda: calc_calls.append(1) or (96, 192), raising=True)

    presenter.update(key=(CommandScope.ENGINE, 7, 40))

    assert calc_calls == []
    assert host._image_cache[(CommandScope.TRAIN, 40)] is img
    assert host.image.config_calls[-1] == {"image": img}
    assert host.image_box.show_calls == 1
