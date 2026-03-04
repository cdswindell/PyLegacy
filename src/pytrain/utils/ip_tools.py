#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import ipaddress
import logging
import socket
import subprocess
import time
from multiprocessing import Pool, cpu_count
from typing import List

from ..protocol.constants import DEFAULT_BASE_PORT

log = logging.getLogger(__name__)


TEST_NET_IP = ("192.0.2.1", 80)  # RFC 5737 TEST-NET-1 (non-routable on the public Internet)


def wait_for_ipv4(timeout_s: float = 30.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(TEST_NET_IP)
                ip = s.getsockname()[0]
            finally:
                s.close()

            # Exclude loopback, link-local, and "0.0.0.0"
            ip_obj = ipaddress.ip_address(ip)
            if not (ip_obj.is_loopback or ip_obj.is_link_local or ip == "0.0.0.0"):
                return True
        except OSError:
            pass

        if timeout_s > 1:
            log.debug("Waiting for IPv4 Network...")
        time.sleep(0.5)

    return False


def wait_for_network(timeout_s: float = 30.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if wait_for_ipv4(timeout_s=1.0):
            return True
        log.debug("Waiting for network...")
        time.sleep(0.5)
    return False


def get_ip_from_command():
    try:
        # The specific interface might vary (e.g., en0, en1, etc.)
        # en0 is often the default Ethernet or Wi-Fi interface
        command = "ipconfig getifaddr en0"
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        # Decode the bytes to a string and strip whitespace
        ip_address = result.decode("utf-8").strip()
        return ip_address
    except subprocess.CalledProcessError as e:
        raise e


def get_ip_address(max_attempts: int = 32) -> List[str]:
    from .. import is_linux

    wait_for_network()

    # if on linux, use hostname to get IP addr
    if is_linux():
        result = subprocess.run("hostname -I".split(), capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout.strip().split()
            if output and output[0]:
                return [output[0]]

    # Otherwise, use socket technique
    hostname = socket.gethostname()
    hostname = hostname if hostname.endswith(".local") else hostname + ".local"

    # Step 3: Get a list of IP addresses associated with the hostname
    ip_addresses = []
    attempts = 0
    while len(ip_addresses) == 0 and attempts <= max_attempts:
        try:
            ip_addresses = socket.gethostbyname_ex(hostname)[2]
        except socket.gaierror as ge:
            attempts += 1
            if attempts > max_attempts:
                raise ge
        except socket.herror as he:
            attempts += 1
            if attempts > max_attempts:
                raise he
        # try another approach
        if len(ip_addresses) == 0:
            try:
                ip_addresses = [get_ip_from_command()]
            except subprocess.CalledProcessError:
                pass

    filtered_ips = {ip for ip in ip_addresses if not ip.startswith("127.")}
    return list(filtered_ips)


def is_base_address(address, base3_port: int = DEFAULT_BASE_PORT) -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.15)
            s.connect((address, base3_port))
            return address
    except socket.error:
        return None


def find_base_address() -> str | None:
    num_cpus = cpu_count() - 1
    possible_ips = list()
    local_ips = get_ip_address()
    for ip in local_ips:
        parts = ip.split(".")
        me = int(parts[-1])
        network = ".".join(parts[:-1]) + "."
        for i in range(2, 255):
            if i == me:
                continue
            possible_ips.append(network + str(i))
    with Pool(num_cpus) as p:
        for result in p.imap_unordered(is_base_address, possible_ips):
            if result is not None:
                p.terminate()
                return result
    return None
