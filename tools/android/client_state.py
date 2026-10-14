"""Read Android shell snapshots without accepting a previous hotspot association."""
import ipaddress
import re


def hotspot_ipv4(wifi_status, addresses, ssid, bssid, subnet):
    """Return one current hotspot IPv4 address, or None while the client rejoins.

    A repeated SSID and an old lease are insufficient: match the AP's current
    BSSID and require the connected state before using the interface address.
    """
    if not re.search(r'^Wifi is connected to', wifi_status, re.M | re.I):
        return None
    association = re.search(r'SSID: (.*?), BSSID: ([0-9a-f:]{17})(?:,|\s)', wifi_status, re.I)
    if (not association or association[1].strip('"') != ssid
            or association[2].lower() != bssid.lower()):
        return None
    network = ipaddress.ip_network(subnet, strict=False)
    try:
        candidates = {ipaddress.ip_address(value) for value in re.findall(r'\binet ([0-9.]+)/', addresses)}
    except ValueError:
        return None
    candidates = {value for value in candidates if value in network
                  and value not in (network.network_address, network.broadcast_address)}
    return str(next(iter(candidates))) if len(candidates) == 1 else None
