"""Regression tests for GitHub-based PyCab Flatpak update discovery."""

import io
import json

import pytest

from pytrain.utils import flatpak_updates


def test_version_key_includes_packaging_revision():
    assert flatpak_updates.version_key("v2.12.4-3") > flatpak_updates.version_key("2.12.4-2")
    assert flatpak_updates.version_key("v2.12.5") > flatpak_updates.version_key("v2.12.4-99")
    assert flatpak_updates.version_key("v2.12.4") == flatpak_updates.version_key("2.12.4-0")


@pytest.mark.parametrize("tag", ["", "main", "v2.12", "v2.12.4-rc1", "v2.12.4-1-extra"])
def test_rejects_invalid_tags(tag):
    with pytest.raises(ValueError):
        flatpak_updates.version_key(tag)


def test_release_check_requires_complete_assets(monkeypatch):
    payload = {
        "tag_name": "v2.12.4-4",
        "html_url": "https://github.com/cdswindell/PyCab-Flatpak/releases/tag/v2.12.4-4",
        "assets": [{"name": "PyCab.flatpak"}, {"name": "PyCab.flatpak.sha256"}],
    }

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    def fake_open(request, timeout):
        assert request.full_url == flatpak_updates.RELEASE_URL
        assert timeout == 5.0
        return Response(json.dumps(payload).encode())

    monkeypatch.setattr(flatpak_updates, "urlopen", fake_open)
    result = flatpak_updates.check_flatpak_update("v2.12.4-3")
    assert result.available
    assert result.available_tag == "v2.12.4-4"
    assert not flatpak_updates.check_flatpak_update("v2.12.4-4").available

    payload["assets"].pop()
    with pytest.raises(ValueError, match="missing"):
        flatpak_updates.check_flatpak_update("v2.12.4-3")


def test_release_check_does_not_mutate_other_update_paths(monkeypatch):
    monkeypatch.setenv("PYTRAIN_DISABLE_SELF_UPDATE", "1")
    from pytrain.utils.update_policy import self_update_disabled

    assert self_update_disabled()
    assert flatpak_updates.version_key("v2.12.4-3") == (2, 12, 4, 3)
