import socket
from typing import List


def get_ip_address() -> List[str]:
    # Step 1: Get the local hostname.
    hostname = socket.gethostname()
    hostname = hostname if hostname.endswith(".local") else hostname + ".local"

    # Step 2: Get a list of IP addresses associated with the hostname.
    ip_addresses = socket.gethostbyname_ex(hostname)[2]

    filtered_ips = [ip for ip in ip_addresses if not ip.startswith("127.")]
    return filtered_ips
