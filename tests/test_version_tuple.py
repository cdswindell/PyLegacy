"""Version tuple validation for client/server registration."""

import pytest

import pytrain


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("v2.12.4", (2, 12, 4)),
        ("v2.12.4+", (2, 12, 4)),
        ("v2.12.4-2", (2, 12, 4)),
    ],
)
def test_version_tuple_valid(monkeypatch, version, expected):
    monkeypatch.setattr(pytrain, "get_version", lambda: version)
    assert pytrain.get_version_tuple() == expected


@pytest.mark.parametrize("version", ["v0.0+", "v2.12", "v2.x.4"])
def test_version_tuple_rejects_invalid_versions(monkeypatch, version):
    monkeypatch.setattr(pytrain, "get_version", lambda: version)
    with pytest.raises(ValueError, match="Invalid PyTrain version"):
        pytrain.get_version_tuple()
