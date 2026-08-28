#!/usr/bin/env python3
"""
GNOME Wi-Fi Hotspot D-Bus Daemon
Exposes io.github.erhanzeyrek.WifiHotspot on the system D-Bus.
Manages create_ap, automatic 2.4/5GHz band checking, and firewalld DHCP/DNS fixes.
"""

import sys
import os
import json
import subprocess
import shutil
import re
import gi

gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")
from gi.repository import GLib, Gio

BUS_NAME = "io.github.erhanzeyrek.WifiHotspot"
OBJECT_PATH = "/io/github/erhanzeyrek/WifiHotspot"
INTERFACE_NAME = "io.github.erhanzeyrek.WifiHotspot"

# Config file paths
SYSTEM_CONFIG = "/etc/wifi-hotspot.conf"
LOCAL_CONFIG = os.path.expanduser("~/.config/wifi-hotspot.conf")
DEV_CONFIG = os.path.join(os.path.dirname(__file__), "..", "data", "wifi-hotspot.conf")

INTROSPECTION_XML = f"""
<node>
  <interface name="{INTERFACE_NAME}">
    <method name="Start">
      <arg type="s" name="result" direction="out"/>
    </method>
    <method name="Stop">
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="GetStatus">
      <arg type="s" name="status_json" direction="out"/>
    </method>
    <method name="GetClients">
      <arg type="s" name="clients_json" direction="out"/>
    </method>
    <method name="GetConfig">
      <arg type="s" name="config_json" direction="out"/>
    </method>
    <method name="SetConfig">
      <arg type="s" name="config_json" direction="in"/>
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="GetInterfaces">
      <arg type="s" name="ifaces_json" direction="out"/>
    </method>
    <method name="GetCapabilities">
      <arg type="s" name="caps_json" direction="out"/>
    </method>
    <method name="SwitchBandAndReconnect">
      <arg type="s" name="target_band" direction="in"/>
      <arg type="s" name="result_json" direction="out"/>
    </method>
    <method name="PrepareFirewall">
      <arg type="b" name="success" direction="out"/>
    </method>
    <signal name="StatusChanged">
      <arg type="s" name="status_json"/>
    </signal>
    <signal name="ClientsChanged">
      <arg type="s" name="clients_json"/>
    </signal>
    <signal name="UserActionRequired">
      <arg type="s" name="action_json"/>
    </signal>
  </interface>
</node>
"""


def find_create_ap():
    """Locate create_ap executable."""
    local_path = os.path.join(os.path.dirname(__file__), "create_ap")
    if os.path.exists(local_path) and os.access(local_path, os.X_OK):
        return local_path
    usr_libexec = "/usr/libexec/wifi-hotspot-daemon/create_ap"
    if os.path.exists(usr_libexec) and os.access(usr_libexec, os.X_OK):
        return usr_libexec
    which_path = shutil.which("create_ap")
    if which_path:
        return which_path
    return "create_ap"


def get_default_ssid():
    """Generate default SSID from machine hostname."""
    try:
        import socket
        name = socket.gethostname().strip()
        if name and name.lower() not in ("localhost", "localhost.localdomain", "(none)"):
            return f"{name}-Hotspot"
    except Exception:
        pass
    return "Hotspot"


def get_config_path(for_write=False):
    """Determine appropriate config path."""
    if os.path.exists(SYSTEM_CONFIG) or (for_write and os.access("/etc", os.W_OK)):
        return SYSTEM_CONFIG
    if os.path.exists(LOCAL_CONFIG) or for_write:
        os.makedirs(os.path.dirname(LOCAL_CONFIG), exist_ok=True)
        return LOCAL_CONFIG
    if os.path.exists(DEV_CONFIG):
        return DEV_CONFIG
    return SYSTEM_CONFIG


class WifiHotspotDaemon:
    def __init__(self, connection):
        self.connection = connection
        self.create_ap_bin = find_create_ap()
        self.cached_clients = []
        self.cached_status_active = False
        self.is_starting = False
        print(f"[*] WifiHotspotDaemon initialized. Using create_ap: {self.create_ap_bin}")

        # Subscribe to NetworkManager WirelessEnabled property changes
        try:
            self.connection.signal_subscribe(
                "org.freedesktop.NetworkManager",
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                "/org/freedesktop/NetworkManager",
                "org.freedesktop.NetworkManager",
                Gio.DBusSignalFlags.NONE,
                self._on_nm_properties_changed,
                None,
            )
            print("[*] Subscribed to NetworkManager property changes.")
        except Exception as e:
            print(f"[!] Warning: Could not subscribe to NM signals: {e}")

        # Periodic check for status, Wi-Fi radio & connected clients (every 2s)
        GLib.timeout_add_seconds(2, self._periodic_poll)

    def _on_nm_properties_changed(self, connection, sender_name, object_path, interface_name, signal_name, parameters, user_data):
        if self.is_starting:
            return
        try:
            interface, changed_props, _ = parameters.unpack()
            if "WirelessEnabled" in changed_props:
                wireless_enabled = bool(changed_props["WirelessEnabled"])
                print(f"[*] NetworkManager WirelessEnabled changed: {wireless_enabled}")
                if not wireless_enabled:
                    status = self._get_status_dict()
                    if status["active"]:
                        print("[*] Wi-Fi turned off. Automatically stopping hotspot...")
                        self.method_stop()
        except Exception as e:
            print(f"[!] Error handling NM property change: {e}")

    def _emit_signal(self, signal_name, json_str):
        try:
            self.connection.emit_signal(
                None,
                OBJECT_PATH,
                INTERFACE_NAME,
                signal_name,
                GLib.Variant("(s)", (json_str,)),
            )
        except Exception as e:
            print(f"[!] Error emitting signal {signal_name}: {e}")

    def _periodic_poll(self):
        try:
            status = self._get_status_dict()

            # 1. If hotspot is active, check if Wi-Fi radio was turned off
            if status["active"]:
                code, out, _ = self._run_cmd(["nmcli", "radio", "wifi"])
                if code == 0 and out.strip().lower() == "disabled":
                    print("[*] Wi-Fi disabled detected via poll. Stopping hotspot...")
                    self.method_stop()
                    return GLib.SOURCE_CONTINUE

            # 2. Check if active status changed (e.g. process died or interface removed)
            if status["active"] != self.cached_status_active:
                self.cached_status_active = status["active"]
                self._emit_signal("StatusChanged", json.dumps(status))

            # 3. Check connected clients
            if status["active"]:
                clients = self._get_clients_list(status.get("iface", "wlp2s0"))
                if clients != self.cached_clients:
                    self.cached_clients = clients
                    self._emit_signal("ClientsChanged", json.dumps(clients))
            else:
                if self.cached_clients:
                    self.cached_clients = []
                    self._emit_signal("ClientsChanged", json.dumps([]))
        except Exception as e:
            pass
        return GLib.SOURCE_CONTINUE

    # ------------------ Wi-Fi & System Helpers ------------------ #

    def _run_cmd(self, args):
        try:
            res = subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except Exception as e:
            return -1, "", str(e)

    def _get_status_dict(self):
        code, out, _ = self._run_cmd([self.create_ap_bin, "--list-running"])
        if code == 0 and out.strip():
            # Output format: <PID> <PHYSICAL_IFACE> [(<VIRTUAL_IFACE>)]
            lines = out.strip().split("\n")
            first = lines[0].split()
            pid = int(first[0]) if first[0].isdigit() else 0
            phy_iface = first[1] if len(first) > 1 else "wlan0"
            virt_iface = phy_iface
            if "(" in out and ")" in out:
                m = re.search(r"\(([^)]+)\)", out)
                if m:
                    virt_iface = m.group(1)

            config = self._read_config_dict()
            actual_band = config.get("FREQ_BAND", "2.4")
            if actual_band == "auto" or not actual_band:
                code_i, out_i, _ = self._run_cmd(["iw", "dev", virt_iface, "info"])
                if "MHz" in out_i:
                    m_freq = re.search(r"\((\d+)\s*MHz\)", out_i)
                    if m_freq:
                        freq_val = int(m_freq.group(1))
                        actual_band = "5" if freq_val > 3000 else "2.4"
                    else:
                        actual_band = "2.4"
                else:
                    actual_band = "2.4"

            return {
                "active": True,
                "pid": pid,
                "iface": virt_iface,
                "phy_iface": phy_iface,
                "ssid": config.get("SSID", get_default_ssid()),
                "band": actual_band,
                "client_count": len(self.cached_clients),
            }
        return {
            "active": False,
            "pid": 0,
            "iface": "",
            "phy_iface": "",
            "ssid": "",
            "band": "",
            "client_count": 0,
        }

    def _get_clients_list(self, iface):
        # 1. Get stations from iw
        code, out, _ = self._run_cmd(["iw", "dev", iface, "station", "dump"])
        macs = []
        if code == 0:
            for line in out.splitlines():
                if line.startswith("Station "):
                    parts = line.split()
                    if len(parts) >= 2:
                        macs.append(parts[1].lower())

        # Fallback to create_ap if iw fails
        if not macs:
            code, out, _ = self._run_cmd([self.create_ap_bin, "--list-clients", iface])
            if code == 0 and out.strip() and "No clients connected" not in out:
                for line in out.strip().split("\n"):
                    if line.startswith("MAC") or not line.strip():
                        continue
                    p = line.split()
                    if len(p) >= 1:
                        macs.append(p[0].lower())

        if not macs:
            return []

        # 2. Read dnsmasq leases for IP and Hostname
        leases = {}
        try:
            import glob
            for lease_file in glob.glob("/tmp/create_ap.*/dnsmasq.leases"):
                with open(lease_file, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        # format: <timestamp> <mac> <ip> <hostname> <client_id>
                        if len(parts) >= 4:
                            l_mac = parts[1].lower()
                            l_ip = parts[2]
                            l_host = parts[3] if parts[3] != "*" else ""
                            leases[l_mac] = {"ip": l_ip, "hostname": l_host}
        except Exception:
            pass

        # 3. Read ARP table (/proc/net/arp) as fallback for IP
        arp_table = {}
        try:
            with open("/proc/net/arp", "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 6:
                        a_ip = parts[0]
                        a_mac = parts[3].lower()
                        arp_table[a_mac] = a_ip
        except Exception:
            pass

        # 4. Construct enriched client list
        clients = []
        for mac in macs:
            ip = leases.get(mac, {}).get("ip") or arp_table.get(mac, "")
            hostname = leases.get(mac, {}).get("hostname", "")

            # If hostname is not in lease, try reverse DNS
            if not hostname and ip:
                try:
                    import socket
                    host = socket.gethostbyaddr(ip)[0]
                    if host and host != ip:
                        hostname = host.split(".")[0]
                except Exception:
                    pass

            clients.append({
                "mac": mac,
                "ip": ip,
                "hostname": hostname
            })

        return clients

    def _read_config_dict(self):
        path = get_config_path(for_write=False)
        conf = {}
        if os.path.exists(path):
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        conf[k.strip()] = v.strip().strip("\"'")
        return conf

    def _write_config_dict(self, conf):
        path = get_config_path(for_write=True)
        lines = ["# Wi-Fi Hotspot Configuration\n"]
        for k, v in conf.items():
            lines.append(f"{k}={v}\n")
        with open(path, "w") as f:
            f.writelines(lines)
        return True

    def prepare_firewall(self):
        """Auto-configure firewalld for DHCP/DNS and kill leftover dnsmasq instances."""
        print("[*] Preparing firewall rules and cleaning dnsmasq...")
        # Check if firewalld is running
        code, out, _ = self._run_cmd(["firewall-cmd", "--state"])
        if code == 0 and "running" in out:
            self._run_cmd(["firewall-cmd", "--add-service=dhcp", "--permanent"])
            self._run_cmd(["firewall-cmd", "--add-service=dns", "--permanent"])
            self._run_cmd(["firewall-cmd", "--reload"])

        # Kill conflicting orphaned dnsmasq instances
        self._run_cmd(["killall", "-q", "dnsmasq"])
        return True

    def get_capabilities(self):
        """Analyze Wi-Fi adapter capabilities (2.4GHz / 5GHz AP support and current STA band)."""
        config = self._read_config_dict()
        wifi_iface = config.get("WIFI_IFACE", "wlan0")

        ap_2ghz = True
        ap_5ghz = False
        ap_sta_concurrent = True
        current_sta_band = ""
        current_sta_ssid = ""

        # Check iw list for AP mode on 5GHz frequencies (band 2)
        code, out, _ = self._run_cmd(["iw", "list"])
        if code == 0:
            if "Band 2:" in out and "AP" in out:
                # Basic check: if Band 2 exists and Supported interface modes has AP
                if "Supported interface modes:" in out and "* AP" in out:
                    ap_5ghz = True

        # 1. Direct kernel nl80211 check via `iw dev <wifi_iface> link`
        code, out, _ = self._run_cmd(["iw", "dev", wifi_iface, "link"])
        if code == 0 and "Connected to" in out:
            for line in out.split("\n"):
                line = line.strip()
                if line.startswith("SSID:"):
                    current_sta_ssid = line.split("SSID:", 1)[1].strip()
                elif line.startswith("freq:"):
                    freq_part = line.split("freq:", 1)[1].strip().split()[0]
                    if freq_part.isdigit():
                        freq = int(freq_part)
                        current_sta_band = "5" if freq >= 4900 else "2.4"

        # 2. Fallback via nmcli
        if not current_sta_band or not current_sta_ssid:
            code, out, _ = self._run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID,FREQ,DEVICE", "dev", "wifi"])
            if code == 0 and out:
                for line in out.split("\n"):
                    if line.startswith("yes:"):
                        parts = line.split(":")
                        if len(parts) >= 3:
                            if not current_sta_ssid:
                                current_sta_ssid = parts[1].strip()
                            freq_match = re.search(r"(\d+)", parts[2])
                            if freq_match:
                                freq = int(freq_match.group(1))
                                current_sta_band = "5" if freq >= 4900 else "2.4"
                        break

        return {
            "ap_2ghz": ap_2ghz,
            "ap_5ghz": ap_5ghz,
            "current_sta_band": current_sta_band,
            "current_sta_ssid": current_sta_ssid,
            "ap_sta_concurrent": ap_sta_concurrent,
            "wifi_iface": wifi_iface,
        }

    def switch_band_and_reconnect(self, target_band):
        """Switch current Wi-Fi connection to specified band (2.4GHz or 5GHz) for the active SSID."""
        caps = self.get_capabilities()
        ssid = caps.get("current_sta_ssid")
        wifi_iface = caps.get("wifi_iface", "wlan0")

        if not ssid:
            return json.dumps({"success": False, "error": "No active Wi-Fi connection to switch."})

        # Scan for BSSIDs of the same SSID matching target band
        code, out, _ = self._run_cmd(["nmcli", "-t", "-f", "SSID,BSSID,FREQ,DEVICE", "dev", "wifi", "list"])
        target_bssid = None
        if code == 0 and out:
            for line in out.split("\n"):
                parts = line.split(":")
                if len(parts) >= 3 and parts[0] == ssid:
                    bssid = ":".join(parts[1:7]) if len(parts) >= 7 else parts[1]
                    freq_str = parts[-2]
                    if freq_str.isdigit():
                        freq = int(freq_str)
                        is_5g = freq >= 4900
                        if (target_band == "5" and is_5g) or (target_band == "2.4" and not is_5g):
                            target_bssid = bssid
                            break

        print(f"[*] Reconnecting to {ssid} on {target_band}GHz (BSSID: {target_bssid})...")
        if target_bssid:
            self._run_cmd(["nmcli", "dev", "wifi", "connect", target_bssid, "ifname", wifi_iface])
        else:
            # Reconnect by SSID
            self._run_cmd(["nmcli", "dev", "wifi", "connect", ssid, "ifname", wifi_iface])

        return json.dumps({"success": True, "target_band": target_band, "ssid": ssid})

    # ------------------ D-Bus Methods ------------------ #

    def handle_method_call(self, connection, sender, object_path, interface_name, method_name, parameters, invocation):
        try:
            if method_name == "Start":
                res = self.method_start()
                invocation.return_value(GLib.Variant("(s)", (res,)))
            elif method_name == "Stop":
                res = self.method_stop()
                invocation.return_value(GLib.Variant("(b)", (res,)))
            elif method_name == "GetStatus":
                res = json.dumps(self._get_status_dict())
                invocation.return_value(GLib.Variant("(s)", (res,)))
            elif method_name == "GetClients":
                status = self._get_status_dict()
                clients = self._get_clients_list(status.get("iface", "wlan0"))
                invocation.return_value(GLib.Variant("(s)", (json.dumps(clients),)))
            elif method_name == "GetConfig":
                conf = self._read_config_dict()
                invocation.return_value(GLib.Variant("(s)", (json.dumps(conf),)))
            elif method_name == "SetConfig":
                json_str = parameters.unpack()[0]
                conf = json.loads(json_str)
                res = self._write_config_dict(conf)
                invocation.return_value(GLib.Variant("(b)", (res,)))
            elif method_name == "GetInterfaces":
                res = self.method_get_interfaces()
                invocation.return_value(GLib.Variant("(s)", (res,)))
            elif method_name == "GetCapabilities":
                res = json.dumps(self.get_capabilities())
                invocation.return_value(GLib.Variant("(s)", (res,)))
            elif method_name == "SwitchBandAndReconnect":
                band = parameters.unpack()[0]
                res = self.switch_band_and_reconnect(band)
                invocation.return_value(GLib.Variant("(s)", (res,)))
            elif method_name == "PrepareFirewall":
                res = self.prepare_firewall()
                invocation.return_value(GLib.Variant("(b)", (res,)))
            else:
                invocation.return_error_literal(
                    Gio.DBusError.quark(),
                    Gio.DBusError.UNKNOWN_METHOD,
                    f"Unknown method {method_name}",
                )
        except Exception as e:
            print(f"[!] Error in {method_name}: {e}")
            invocation.return_error_literal(
                Gio.DBusError.quark(),
                Gio.DBusError.FAILED,
                str(e),
            )

    def method_start(self):
        self.is_starting = True
        try:
            status = self._get_status_dict()
            if status["active"]:
                return json.dumps({"success": True, "message": "Already running", "active": True})

            # 1. Check Hardware Capabilities & Band Mismatch
            caps = self.get_capabilities()
            config = self._read_config_dict()
            req_band = config.get("FREQ_BAND", "auto")

            # If currently connected via 5GHz but Wi-Fi card does NOT support 5GHz AP mode:
            if caps["current_sta_band"] == "5" and not caps["ap_5ghz"]:
                msg = (
                    "Your Wi-Fi adapter does not support 5GHz Hotspot mode. "
                    "Would you like to switch your internet connection to the 2.4GHz band and start the Hotspot?"
                )
                action_payload = {
                    "type": "band_switch",
                    "message": msg,
                    "target_band": "2.4",
                    "action": "SwitchBandAndReconnect",
                }
                self._emit_signal("UserActionRequired", json.dumps(action_payload))
                return json.dumps({
                    "success": False,
                    "action_required": "band_switch",
                    "target_band": "2.4",
                    "message": msg,
                })

            # 2. Automatically Prepare Firewall & Clear dnsmasq
            self.prepare_firewall()

            # 3. Ensure Channel Compatibility in AP+STA Repeater Mode
            wifi_iface = config.get("WIFI_IFACE", "wlp2s0")
            inet_iface = config.get("INTERNET_IFACE", "wlp2s0")
            if wifi_iface == inet_iface or caps.get("current_sta_ssid"):
                # In concurrent AP+STA mode, channel MUST follow connected channel (default)
                if config.get("CHANNEL") != "default":
                    print("[*] Normalizing CHANNEL=default for AP+STA concurrent mode.")
                    config["CHANNEL"] = "default"
                    self._write_config_dict(config)

            # Resolve auto band based on capabilities
            resolved_band = req_band
            if req_band == "auto":
                if caps.get("current_sta_band"):
                    resolved_band = caps["current_sta_band"]
                elif caps.get("ap_5ghz"):
                    resolved_band = "5"
                else:
                    resolved_band = "2.4"
                print(f"[*] Auto frequency band resolved to: {resolved_band}")

            # 4. Start create_ap process with logfile
            config_path = get_config_path(for_write=False)
            log_path = "/tmp/create_ap.log"
            cmd = [self.create_ap_bin, "--config", config_path, "--logfile", log_path, "--daemon", "--freq-band", resolved_band]
            print(f"[*] Starting hotspot with: {' '.join(cmd)}")
            code, out, err = self._run_cmd(cmd)

            # Wait up to 8 seconds for status to become active
            for _ in range(16):
                GLib.usleep(500000) # 0.5s
                status = self._get_status_dict()
                if status["active"]:
                    break
            
            self.cached_status_active = status["active"]
            self._emit_signal("StatusChanged", json.dumps(status))

            if status["active"]:
                return json.dumps({"success": True, "status": status})
            else:
                err_msg = ""
                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r") as f:
                            lines = [line.strip() for line in f if line.strip()]
                            err_msg = " \n".join(lines[-4:])
                    except Exception:
                        pass
                if not err_msg:
                    err_msg = err or out or "Failed to start AP"
                print(f"[!] Hotspot start failed: {err_msg}")
                return json.dumps({"success": False, "error": err_msg})
        finally:
            self.is_starting = False

    def method_stop(self):
        status = self._get_status_dict()
        if not status["active"]:
            return True

        iface_to_stop = status.get("phy_iface") or status.get("iface") or str(status.get("pid"))
        print(f"[*] Stopping hotspot for: {iface_to_stop}")
        code, out, err = self._run_cmd([self.create_ap_bin, "--stop", iface_to_stop])

        # Wait up to 4 seconds for status to become inactive
        for _ in range(8):
            GLib.usleep(500000)
            new_status = self._get_status_dict()
            if not new_status["active"]:
                break
        self.cached_clients = []
        self._emit_signal("StatusChanged", json.dumps(new_status))
        self._emit_signal("ClientsChanged", json.dumps([]))
        return not new_status["active"]

    def method_get_interfaces(self):
        wifi_ifaces = []
        all_ifaces = []

        code, out, _ = self._run_cmd(["iw", "dev"])
        if code == 0 and out:
            for line in out.split("\n"):
                line = line.strip()
                if line.startswith("Interface "):
                    wifi_ifaces.append(line.split()[1])

        code, out, _ = self._run_cmd(["ip", "-o", "link", "show"])
        if code == 0 and out:
            for line in out.split("\n"):
                if line.strip():
                    parts = line.split(":")
                    if len(parts) >= 2:
                        ifname = parts[1].strip()
                        if "@" in ifname:
                            ifname = ifname.split("@")[0]
                        if ifname != "lo":
                            all_ifaces.append(ifname)

        return json.dumps({
            "wifi_interfaces": wifi_ifaces or ["wlan0"],
            "all_interfaces": list(set(all_ifaces)) or ["wlan0", "eth0"],
        })


def on_bus_acquired(connection, name):
    print(f"[*] D-Bus system bus acquired: {name}")
    node_info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
    interface_info = node_info.interfaces[0]

    daemon = WifiHotspotDaemon(connection)

    connection.register_object(
        OBJECT_PATH,
        interface_info,
        daemon.handle_method_call,
        None,
        None,
    )


def on_name_acquired(connection, name):
    print(f"[*] Name successfully acquired on D-Bus: {name}")


def on_name_lost(connection, name):
    print(f"[!] Name lost on D-Bus: {name}. Exiting.")
    sys.exit(1)


def main():
    Gio.bus_own_name(
        Gio.BusType.SYSTEM,
        BUS_NAME,
        Gio.BusNameOwnerFlags.REPLACE,
        on_bus_acquired,
        on_name_acquired,
        on_name_lost,
    )

    loop = GLib.MainLoop()
    try:
        print("[*] WifiHotspot D-Bus service loop running...")
        loop.run()
    except KeyboardInterrupt:
        print("\n[*] Exiting daemon...")
        loop.quit()


if __name__ == "__main__":
    main()
