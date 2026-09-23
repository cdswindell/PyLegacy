"""Opt-in tests; API imports and lifecycle state live exclusively in children."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif("PYTRAIN_API_CHECKOUT" not in os.environ, reason="Set PYTRAIN_API_CHECKOUT to a local API checkout")
@pytest.mark.parametrize("role", ["server", "client"])
@pytest.mark.parametrize("route", ["callback", "queued"])
@pytest.mark.parametrize("action", ["QUIT", "UPDATE", "RESTART", "REBOOT", "SHUTDOWN", "UPGRADE"])
def test_api_exit_receiver(role, route, action):
    run_child(role, route, action)


@pytest.mark.skipif("PYTRAIN_API_CHECKOUT" not in os.environ, reason="Set PYTRAIN_API_CHECKOUT to a local API checkout")
@pytest.mark.parametrize("role", ["server", "client"])
def test_api_callback_cache_failure(role):
    """A warning permits UPDATE/relaunch; retained ownership remains retryable."""
    run_child(role, "callback", "UPDATE", "cache-failure")


@pytest.mark.skipif("PYTRAIN_API_CHECKOUT" not in os.environ, reason="Set PYTRAIN_API_CHECKOUT to a local API checkout")
@pytest.mark.skipif(os.name != "posix", reason="Real SIGINT handoff requires POSIX")
@pytest.mark.parametrize("role", ["server", "client"])
@pytest.mark.parametrize(
    "route,action", [("endpoint", "UPDATE"), ("queued", "UPDATE"), ("queued", "RESTART"), ("queued", "QUIT")]
)
def test_api_real_signal_handoff(role, route, action):
    run_child(role, route, action, "signal")


def run_child(role, route, action, scenario="success"):
    configured = os.environ["PYTRAIN_API_CHECKOUT"]
    checkout = Path(configured).expanduser().resolve()
    if not configured or not (checkout / "src/pytrain_api/pytrain_api.py").is_file():
        pytest.fail(f"Invalid PYTRAIN_API_CHECKOUT: {configured!r}; expected an existing source checkout")
    interpreter = os.environ.get("PYTRAIN_API_PYTHON", sys.executable)
    helper = Path(__file__).with_name("_pytrain_api_exit_child.py")
    command = [interpreter, "-I", "-B", str(helper), str(checkout), role, route, action, scenario]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.fail(f"API integration child failed: {command!r}\n{exc}")
    diagnostics = f"{command!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.returncode == 0, diagnostics
    assert "API_EXIT_OK" in result.stdout, diagnostics
    print(result.stdout)
