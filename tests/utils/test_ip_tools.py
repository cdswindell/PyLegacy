#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# tests/utils/test_ip_tools.py
import socket
import subprocess

import pytest

from src.pytrain.utils import ip_tools
from src.pytrain.utils.ip_tools import find_base_address, get_ip_address, is_base_address, get_ip_from_command


class DummyCompleted:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


@pytest.fixture(autouse=True)
def mock_network_wait(monkeypatch):
    monkeypatch.setattr("src.pytrain.utils.ip_tools.wait_for_network", lambda timeout_s=60.0: True)


def test_find_hostname_script_prefers_path(monkeypatch, tmp_path):
    path_script = tmp_path / "bin" / "hostname.sh"
    path_script.parent.mkdir()
    path_script.touch()
    scripts_dir = tmp_path / "python-scripts"
    scripts_dir.mkdir()
    (scripts_dir / "hostname.sh").touch()

    monkeypatch.setattr(ip_tools.shutil, "which", lambda name: str(path_script))
    monkeypatch.setattr(ip_tools.sysconfig, "get_path", lambda name: str(scripts_dir))

    assert ip_tools._find_hostname_script() == path_script


def test_find_hostname_script_uses_python_scripts_directory(monkeypatch, tmp_path):
    scripts_dir = tmp_path / "python-scripts"
    scripts_dir.mkdir()
    scripts_script = scripts_dir / "hostname.sh"
    scripts_script.touch()

    monkeypatch.setattr(ip_tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(ip_tools.sysconfig, "get_path", lambda name: str(scripts_dir))

    assert ip_tools._find_hostname_script() == scripts_script


def test_find_hostname_script_uses_source_tree_path(monkeypatch, tmp_path):
    source_root = tmp_path / "source tree with spaces"
    source_file = source_root / "src" / "pytrain" / "utils" / "ip_tools.py"
    source_file.parent.mkdir(parents=True)
    source_file.touch()
    source_script = source_root / "src" / "pytrain" / "installation" / "hostname.sh"
    source_script.parent.mkdir()
    source_script.touch()

    monkeypatch.setattr(ip_tools, "__file__", str(source_file))
    monkeypatch.setattr(ip_tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(ip_tools.sysconfig, "get_path", lambda name: str(tmp_path / "missing-scripts"))

    assert ip_tools._find_hostname_script() == source_script


def test_find_hostname_script_returns_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(ip_tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(ip_tools.sysconfig, "get_path", lambda name: str(tmp_path / "missing-scripts"))
    monkeypatch.setattr(ip_tools, "__file__", str(tmp_path / "missing" / "ip_tools.py"))

    assert ip_tools._find_hostname_script() is None


def test_get_ip_address_linux_hostname_success(monkeypatch):
    # Force is_linux() to return True
    monkeypatch.setattr("src.pytrain.is_linux", lambda: True, raising=False)
    monkeypatch.setattr(ip_tools, "_find_hostname_script", lambda: pytest.fail("Native hostname is preferred"))

    # Mock subprocess.run to simulate `hostname -I` output
    # noinspection PyUnusedLocal
    def fake_run(cmd, capture_output=True, text=True):
        assert cmd == ["hostname", "-I"]
        return DummyCompleted(returncode=0, stdout="192.168.1.10 10.0.0.5\n")

    monkeypatch.setattr("subprocess.run", fake_run)

    ips = get_ip_address()
    assert ips == ["192.168.1.10"]


@pytest.mark.parametrize("location", ["path", "python-scripts", "source"])
def test_get_ip_address_missing_hostname_uses_script(monkeypatch, tmp_path, location):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: True)
    source_file = tmp_path / "source tree with spaces" / "pytrain" / "utils" / "ip_tools.py"
    source_file.parent.mkdir(parents=True)
    source_file.touch()
    scripts_dir = tmp_path / "python scripts"
    script = {
        "path": tmp_path / "path bin" / "hostname.sh",
        "python-scripts": scripts_dir / "hostname.sh",
        "source": source_file.parents[1] / "installation" / "hostname.sh",
    }[location]
    script.parent.mkdir(parents=True)
    script.touch()
    script.chmod(0o644)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    monkeypatch.setattr(ip_tools, "__file__", str(source_file))
    monkeypatch.setattr(ip_tools.shutil, "which", lambda name: str(script) if location == "path" else None)
    monkeypatch.setattr(ip_tools.sysconfig, "get_path", lambda name: str(scripts_dir))
    calls = []
    monkeypatch.setattr(ip_tools, "wait_for_network", lambda: calls.append("wait"))

    def fake_run(cmd, *, capture_output, text):
        assert capture_output is True
        assert text is True
        calls.append(cmd)
        if cmd == ["hostname", "-I"]:
            raise FileNotFoundError("hostname")
        assert cmd == ["/bin/bash", str(script), "-I"]
        return DummyCompleted(stdout=" 192.168.1.10 10.0.0.5\n")

    monkeypatch.setattr(ip_tools.subprocess, "run", fake_run)
    assert get_ip_address() == ["192.168.1.10"]
    assert calls == ["wait", ["hostname", "-I"], ["/bin/bash", str(script), "-I"]]


@pytest.mark.parametrize("failure", ["missing", "oserror", "nonzero", "blank"])
def test_get_ip_address_script_failure_uses_socket(monkeypatch, tmp_path, failure):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: True)
    script = tmp_path / "hostname.sh"
    monkeypatch.setattr(ip_tools, "_find_hostname_script", lambda: None if failure == "missing" else script)
    monkeypatch.setattr(ip_tools.socket, "gethostname", lambda: "myhost.local")

    def fake_resolve(hostname):
        assert hostname == "myhost.local"
        return hostname, [], ["127.0.0.1", "192.168.0.42"]

    monkeypatch.setattr(ip_tools.socket, "gethostbyname_ex", fake_resolve)
    calls = []

    def fake_run(cmd, *, capture_output, text):
        calls.append(cmd)
        if cmd == ["hostname", "-I"]:
            raise FileNotFoundError("hostname")
        assert cmd == ["/bin/bash", str(script), "-I"]
        if failure == "oserror":
            raise OSError("Cannot launch script")
        return (
            DummyCompleted(returncode=1, stdout="192.168.1.10")
            if failure == "nonzero"
            else DummyCompleted(stdout=" \n\t")
        )

    monkeypatch.setattr(ip_tools.subprocess, "run", fake_run)
    assert get_ip_address() == ["192.168.0.42"]
    assert len(calls) == (1 if failure == "missing" else 2)


@pytest.mark.parametrize("returncode, stdout", [(1, "192.168.1.10"), (0, " \n\t")])
def test_get_ip_address_native_failure_does_not_use_script(monkeypatch, returncode, stdout):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: True)
    monkeypatch.setattr(ip_tools, "_find_hostname_script", lambda: pytest.fail("Must not search for script"))
    monkeypatch.setattr(ip_tools.socket, "gethostname", lambda: "myhost")
    monkeypatch.setattr(ip_tools.socket, "gethostbyname_ex", lambda name: (name, [], ["192.168.0.42"]))

    def fake_run(cmd, *, capture_output, text):
        assert cmd == ["hostname", "-I"]
        return DummyCompleted(returncode, stdout)

    monkeypatch.setattr(ip_tools.subprocess, "run", fake_run)
    assert get_ip_address() == ["192.168.0.42"]


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("missing_native", [False, True])
def test_get_ip_address_command_cancellation_propagates(monkeypatch, tmp_path, exception, missing_native):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: True)
    monkeypatch.setattr(ip_tools, "_find_hostname_script", lambda: tmp_path / "hostname.sh")

    def fake_run(cmd, *, capture_output, text):
        if missing_native and cmd == ["hostname", "-I"]:
            raise FileNotFoundError("hostname")
        raise exception()

    monkeypatch.setattr(ip_tools.subprocess, "run", fake_run)
    with pytest.raises(exception):
        get_ip_address()


def test_get_ip_address_non_linux_socket_success_filters_localhost(monkeypatch):
    # Force is_linux() to return False so socket path is used
    monkeypatch.setattr("src.pytrain.is_linux", lambda: False, raising=False)
    monkeypatch.setattr(ip_tools.subprocess, "run", lambda *args, **kwargs: pytest.fail("Linux command on non-Linux"))
    monkeypatch.setattr(ip_tools, "_find_hostname_script", lambda: pytest.fail("Script discovery on non-Linux"))

    # Mock networking calls
    monkeypatch.setattr("socket.gethostname", lambda: "myhost", raising=True)

    def fake_gethostbyname_ex(hostname):
        # Should append .local when missing
        assert hostname == "myhost.local"
        return "myhost.local", [], ["127.0.1.1", "192.168.0.42", "127.0.0.1"]

    monkeypatch.setattr("socket.gethostbyname_ex", fake_gethostbyname_ex, raising=True)

    ips = get_ip_address()
    # Should filter loopback (127.*)
    assert ips == ["192.168.0.42"]


def test_get_ip_address_non_linux_retries_until_success(monkeypatch):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: False, raising=False)
    monkeypatch.setattr("socket.gethostname", lambda: "retryhost", raising=True)

    calls = {"count": 0}

    try:
        get_ip_from_command()
    except subprocess.CalledProcessError:
        pass

    def noop_get_ip_from_command():
        raise subprocess.CalledProcessError(1, "ipconfig")

    def flaky_gethostbyname_ex(hostname):
        calls["count"] += 1
        if calls["count"] < 3:
            raise socket.gaierror("temporary failure in name resolution")
        return hostname, [], ["10.1.2.3"]

    monkeypatch.setattr("src.pytrain.utils.ip_tools.get_ip_from_command", noop_get_ip_from_command, raising=True)
    monkeypatch.setattr("socket.gethostbyname_ex", flaky_gethostbyname_ex, raising=True)

    ips = get_ip_address(max_attempts=5)
    assert ips == ["10.1.2.3"]
    assert calls["count"] == 3  # failed twice, succeeded on third attempt


def test_is_base_address_success_and_failure(monkeypatch):
    # Build a fake socket that can simulate connect success/failure
    class DummySocket:
        def __init__(self, should_fail=False):
            self.should_fail = should_fail
            self.timeout = None

        def settimeout(self, t):
            self.timeout = t

        # noinspection PyUnusedLocal
        def connect(self, addr):
            if self.should_fail:
                raise socket.error("connection refused")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    # Patch socket.socket to return success instance
    def socket_factory_success(fam, typ):
        assert fam == socket.AF_INET and typ == socket.SOCK_STREAM
        return DummySocket(should_fail=False)

    # Patch socket.socket to return failure instance
    # noinspection PyUnusedLocal
    def socket_factory_fail(fam, typ):
        return DummySocket(should_fail=True)

    # Success case
    monkeypatch.setattr("socket.socket", socket_factory_success, raising=True)
    assert is_base_address("192.168.0.50") == "192.168.0.50"

    # Failure case
    monkeypatch.setattr("socket.socket", socket_factory_fail, raising=True)
    assert is_base_address("192.168.0.51") is None


def test_find_base_address_returns_first_found(monkeypatch):
    # Limit CPU count to keep Pool size consistent in tests
    monkeypatch.setattr("src.pytrain.utils.ip_tools.cpu_count", lambda: 4, raising=True)

    # Pretend local machine IP is 192.168.1.42
    monkeypatch.setattr("src.pytrain.utils.ip_tools.get_ip_address", lambda: ["192.168.1.42"], raising=True)

    # Fake Pool that yields results where one address is found
    class DummyPool:
        def __init__(self, n):
            self.n = n
            self.terminated = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        # Ignore the function, just yield some None results then one match
        # noinspection PyUnusedLocal,PyMethodMayBeStatic
        def imap_unordered(self, func, iterable):
            iterable = list(iterable)
            assert "192.168.1.42" not in iterable
            yield None
            yield None
            yield "192.168.1.99"

        def terminate(self):
            self.terminated = True

    # Patch Pool constructor at the module where it's used
    monkeypatch.setattr("src.pytrain.utils.ip_tools.Pool", lambda n: DummyPool(n), raising=True)

    # Run and verify we got the discovered address
    found = find_base_address()
    assert found == "192.168.1.99"
