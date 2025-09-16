#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# test/utils/test_ip_tools.py
import socket

from src.pytrain.utils.ip_tools import find_base_address, get_ip_address, is_base_address


class DummyCompleted:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_get_ip_address_linux_hostname_success(monkeypatch):
    # Force is_linux() to return True
    monkeypatch.setattr("src.pytrain.is_linux", lambda: True, raising=False)

    # Mock subprocess.run to simulate `hostname -I` output
    # noinspection PyUnusedLocal
    def fake_run(cmd, capture_output=True, text=True):
        assert cmd == ["hostname", "-I"]
        return DummyCompleted(returncode=0, stdout="192.168.1.10 10.0.0.5\n")

    monkeypatch.setattr("subprocess.run", fake_run)

    ips = get_ip_address()
    assert ips == ["192.168.1.10"]


def test_get_ip_address_non_linux_socket_success_filters_localhost(monkeypatch):
    # Force is_linux() to return False so socket path is used
    monkeypatch.setattr("src.pytrain.is_linux", lambda: False, raising=False)

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

    def flaky_gethostbyname_ex(hostname):
        calls["count"] += 1
        if calls["count"] < 3:
            raise socket.gaierror("temporary failure in name resolution")
        return hostname, [], ["10.1.2.3"]

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
    # Limit CPU count to keep Pool size consistent in test
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
