from pathlib import Path


ROOT = Path(__file__).parents[3]


def test_runtime_dependencies_and_profile_are_packaged() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-nogpio.txt").read_text(encoding="utf-8")

    assert '"pygame-ce >=' in pyproject
    assert "pygame-ce>=" in requirements
    assert '"*.json"' in pyproject


def test_launch_artifacts_preserve_gamescope_display_and_describe_kde_entry() -> None:
    launch = (ROOT / "src/pytrain/installation/launch_pytrain.bash.template").read_text(encoding="utf-8")
    desktop = (ROOT / "src/pytrain/installation/pytrain_desktop.template").read_text(encoding="utf-8")

    assert 'if [ -z "$DISPLAY" ]' in launch
    assert "export DISPLAY" in launch
    assert "Terminal=false" in desktop
    assert "Categories=Game;Utility;" in desktop
