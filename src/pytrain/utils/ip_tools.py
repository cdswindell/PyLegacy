#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import socket
import subprocess
from multiprocessing import Pool, cpu_count
from typing import List


from ..protocol.constants import DEFAULT_BASE_PORT


def get_ip_address(max_attempts: int = 32) -> List[str]:
    from .. import is_linux

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

    # Step 2: Get a list of IP addresses associated with the hostname
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
