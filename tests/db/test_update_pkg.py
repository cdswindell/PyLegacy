"""Preserve update-package metadata behavior after removing query packages."""

import pytest

from src.pytrain.db.comp_data import UpdatePkg


@pytest.mark.parametrize(
    "field, offset, length, payload, equal",
    [
        ("speed", 0x07, 1, b"\x2a", True),
        ("speed", 0x07, 1, b"\x00", True),
        ("target_speed", 0x07, 1, b"\x2a", False),
        ("speed", 0x08, 1, b"\x2a", False),
        ("speed", 0x07, 2, b"\x2a\x00", False),
    ],
)
def test_update_packages_compare_and_hash_by_field_location(field, offset, length, payload, equal):
    package = UpdatePkg("speed", 0x07, 1, b"\x2a")
    other = UpdatePkg(field, offset, length, payload)

    assert (package == other) is equal
    assert (package != other) is not equal
    assert len({package, other}) == (1 if equal else 2)


def test_update_package_does_not_equal_unrelated_metadata():
    package = UpdatePkg("speed", 0x07, 1, b"\x2a")

    assert package != ("speed", 0x07, 1)
