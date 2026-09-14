import pytest

from pytrain_ui.launcher import select_backend


def test_qt_is_preferred_when_available() -> None:
    backend, args = select_backend(["12", "-train"], qt_installed=True, legacy_env="")

    assert backend == "qt"
    assert args == ["12", "-train"]


def test_legacy_is_fallback_when_qt_is_unavailable() -> None:
    backend, args = select_backend(["12"], qt_installed=False, legacy_env="")

    assert backend == "legacy"
    assert args == ["12"]


def test_legacy_flag_overrides_qt_and_is_not_forwarded() -> None:
    backend, args = select_backend(["--legacy", "12"], qt_installed=True, legacy_env="")

    assert backend == "legacy"
    assert args == ["12"]


def test_qt_flag_overrides_legacy_environment() -> None:
    backend, args = select_backend(["--qt", "12"], qt_installed=True, legacy_env="1")

    assert backend == "qt"
    assert args == ["12"]


def test_legacy_environment_opts_out_of_qt() -> None:
    backend, args = select_backend(["12"], qt_installed=True, legacy_env="true")

    assert backend == "legacy"
    assert args == ["12"]


def test_explicit_qt_requires_optional_dependency() -> None:
    with pytest.raises(RuntimeError, match="PySide6 is not installed"):
        select_backend(["--qt"], qt_installed=False, legacy_env="")


def test_backend_flags_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="either --qt or --legacy"):
        select_backend(["--qt", "--legacy"], qt_installed=True, legacy_env="")
