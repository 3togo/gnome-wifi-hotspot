#!/usr/bin/env python3
"""
Wi-Fi Relay Settings App (Libadwaita / GTK4)
Native GNOME interface for configuring Wi-Fi Hotspot, managing AP settings,
viewing connected devices and generating QR connection codes.
"""

import sys
import os
import json
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, Adw, Gio, GLib

try:
    from startup import get_auto_start, set_auto_start, is_gnome, launch_tray
except ModuleNotFoundError:
    from settings.startup import get_auto_start, set_auto_start, is_gnome, launch_tray

BUS_NAME = "io.github.erhanzeyrek.WifiHotspot"
OBJECT_PATH = "/io/github/erhanzeyrek/WifiHotspot"
INTERFACE_NAME = "io.github.erhanzeyrek.WifiHotspot"


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


class HotspotSettingsWindow(Adw.PreferencesWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Wi-Fi Relay Settings")
        self.set_default_size(680, 580)
        self.app = app
        self.dbus_proxy = None
        self.config_data = {}
        self.interfaces = {"wifi_interfaces": ["wlan0"], "all_interfaces": ["wlan0", "eth0"]}
        self.capabilities = {}
        self._hotspot_busy = False
        self._loading_fields = True

        self._init_dbus()
        self._build_ui()
        self._load_data()
        self._loading_fields = False

        # Periodic status refresh
        GLib.timeout_add_seconds(3, self._refresh_status)

    def _init_dbus(self):
        try:
            self.dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                BUS_NAME,
                OBJECT_PATH,
                INTERFACE_NAME,
                None,
            )
        except Exception as e:
            print(f"[!] Warning: Could not connect to system D-Bus: {e}")

    def _build_ui(self):
        # Header bar controls
        header = self.get_titlebar()

        # ---------------- Page 1: General & Network Settings ---------------- #
        page_general = Adw.PreferencesPage(title="General", icon_name="network-wireless-hotspot-symbolic")
        self.add(page_general)

        grp_startup = Adw.PreferencesGroup(title="Startup")
        page_general.add(grp_startup)
        self.switch_startup = Adw.SwitchRow(
            title="Start tray at login",
            subtitle="Show the tray automatically when you log in. Disabling also hides it now.",
            active=get_auto_start(),
        )
        self.switch_startup.connect("notify::active", self._on_startup_changed)
        grp_startup.add(self.switch_startup)

        # Status Group
        grp_status = Adw.PreferencesGroup(title="Hotspot Status")
        page_general.add(grp_status)

        self.row_status = Adw.ActionRow(title="Service Status", subtitle="Checking connection...")
        self.switch_hotspot = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.switch_hotspot.connect("state-set", self._on_switch_toggled)
        self.row_status.add_suffix(self.switch_hotspot)
        grp_status.add(self.row_status)

        # Basic Settings Group
        grp_basic = Adw.PreferencesGroup(title="Wireless Network Configuration", description="Hotspot broadcast name and security credentials")
        page_general.add(grp_basic)

        self.entry_ssid = Adw.EntryRow(title="Hotspot Name (SSID)")
        self.entry_ssid.connect("changed", self._on_field_changed)
        grp_basic.add(self.entry_ssid)

        self.entry_pass = Adw.PasswordEntryRow(title="Password (WPA2/WPA3)")
        self.entry_pass.connect("changed", self._on_field_changed)
        grp_basic.add(self.entry_pass)

        # Network Interfaces Group
        grp_net = Adw.PreferencesGroup(title="Network Interfaces and Frequency Band")
        page_general.add(grp_net)

        self.combo_wifi_iface = Adw.ComboRow(title="Wi-Fi Adapter", subtitle="A virtual hotspot interface is created on this adapter")
        self.combo_wifi_iface.connect("notify::selected", self._on_field_changed)
        grp_net.add(self.combo_wifi_iface)

        self.combo_inet_iface = Adw.ComboRow(title="Internet Sharing Interface", subtitle="Choose the same Wi-Fi adapter for simultaneous Wi-Fi + hotspot")
        self.combo_inet_iface.connect("notify::selected", self._on_field_changed)
        grp_net.add(self.combo_inet_iface)

        self.combo_band = Adw.ComboRow(title="Frequency Band")
        band_model = Gtk.StringList.new(["Automatic (Recommended)", "2.4 GHz", "5 GHz"])
        self.combo_band.set_model(band_model)
        self.combo_band.connect("notify::selected", self._on_field_changed)
        grp_net.add(self.combo_band)

        self.row_caps = Adw.ActionRow(title="Hardware Capabilities", subtitle="Detecting...")
        grp_net.add(self.row_caps)

        # ---------------- Page 2: Advanced Settings ---------------- #
        page_adv = Adw.PreferencesPage(title="Advanced", icon_name="emblem-system-symbolic")
        self.add(page_adv)

        grp_adv_sec = Adw.PreferencesGroup(title="Broadcast and Security Options")
        page_adv.add(grp_adv_sec)

        self.switch_hidden = Adw.SwitchRow(title="Hidden SSID", subtitle="Hide network name from broadcast")
        self.switch_hidden.connect("notify::active", self._on_field_changed)
        grp_adv_sec.add(self.switch_hidden)

        self.switch_isolate = Adw.SwitchRow(title="Client Isolation", subtitle="Prevent connected devices from communicating with each other")
        self.switch_isolate.connect("notify::active", self._on_field_changed)
        grp_adv_sec.add(self.switch_isolate)

        self.switch_80211n = Adw.SwitchRow(title="IEEE 802.11n (Wi-Fi 4)", subtitle="High-throughput rate support")
        self.switch_80211n.connect("notify::active", self._on_field_changed)
        grp_adv_sec.add(self.switch_80211n)

        self.switch_80211ac = Adw.SwitchRow(title="IEEE 802.11ac (Wi-Fi 5)", subtitle="5 GHz multi-stream support")
        self.switch_80211ac.connect("notify::active", self._on_field_changed)
        grp_adv_sec.add(self.switch_80211ac)

        self.switch_80211ax = Adw.SwitchRow(title="IEEE 802.11ax (Wi-Fi 6)", subtitle="Wi-Fi 6 high-efficiency mode")
        self.switch_80211ax.connect("notify::active", self._on_field_changed)
        grp_adv_sec.add(self.switch_80211ax)

        grp_ip = Adw.PreferencesGroup(title="Gateway and Channel")
        page_adv.add(grp_ip)

        self.entry_gateway = Adw.EntryRow(title="Gateway IP")
        self.entry_gateway.connect("changed", self._on_field_changed)
        grp_ip.add(self.entry_gateway)

        self.entry_channel = Adw.EntryRow(title="Channel Number")
        self.entry_channel.connect("changed", self._on_field_changed)
        grp_ip.add(self.entry_channel)

        # ---------------- Page 3: Connected Devices & Sharing ---------------- #
        page_clients = Adw.PreferencesPage(title="Devices & Sharing", icon_name="network-workgroup-symbolic")
        self.add(page_clients)

        grp_share = Adw.PreferencesGroup(title="Quick Share")
        page_clients.add(grp_share)

        row_qr = Adw.ActionRow(title="Connect via QR Code", subtitle="Scan with phone or tablet camera to connect instantly")
        btn_qr = Gtk.Button(label="Show QR", valign=Gtk.Align.CENTER)
        btn_qr.add_css_class("suggested-action")
        btn_qr.connect("clicked", self._on_show_qr)
        row_qr.add_suffix(btn_qr)
        grp_share.add(row_qr)

        self.grp_clients_list = Adw.PreferencesGroup(title="Connected Devices", description="Devices currently connected to this hotspot")
        page_clients.add(self.grp_clients_list)

        self.row_no_clients = Adw.ActionRow(title="No devices connected", subtitle="Connected devices will be listed here")
        self.grp_clients_list.add(self.row_no_clients)

    # ---------------- D-Bus & Data Operations ---------------- #

    def _on_startup_changed(self, row, _param):
        enabled = row.get_active()
        try:
            set_auto_start(enabled, Gio.Settings.new("org.gnome.shell") if is_gnome() else None, Gio.Settings.sync)
            if enabled and not is_gnome():
                launch_tray()
        except Exception as error:
            row.handler_block_by_func(self._on_startup_changed)
            row.set_active(get_auto_start())
            row.handler_unblock_by_func(self._on_startup_changed)
            dialog = Adw.MessageDialog(transient_for=self, heading="Could not save startup setting", body=str(error))
            dialog.add_response("ok", "Close")
            dialog.present()

    def _load_data(self):
        if not self.dbus_proxy:
            self._load_fallback_config()
            return

        try:
            # 1. Interfaces
            res = self.dbus_proxy.GetInterfaces()
            self.interfaces = json.loads(res)

            wifi_model = Gtk.StringList.new(self.interfaces.get("wifi_interfaces", ["wlan0"]))
            self.combo_wifi_iface.set_model(wifi_model)

            all_model = Gtk.StringList.new(self.interfaces.get("all_interfaces", ["wlan0", "eth0"]))
            self.combo_inet_iface.set_model(all_model)

            # 2. Capabilities
            res_caps = self.dbus_proxy.GetCapabilities()
            self.capabilities = json.loads(res_caps)
            ap_5g = "Yes" if self.capabilities.get("ap_5ghz") else "No"
            sta_b = self.capabilities.get("current_sta_band", "Unknown")
            self.row_caps.set_subtitle(f"5GHz AP Support: {ap_5g} | Current Wi-Fi Band: {sta_b} GHz")

            # 3. Config
            res_conf = self.dbus_proxy.GetConfig()
            self.config_data = json.loads(res_conf)
            self._populate_fields(self.config_data)

            # 4. Status
            self._refresh_status()

        except Exception as e:
            print(f"[!] Error loading data over D-Bus: {e}")
            self._load_fallback_config()

    def _populate_fields(self, conf):
        was_loading = self._loading_fields
        self._loading_fields = True
        try:
            self.config_data = dict(conf)
            for row, key in ((self.combo_wifi_iface, "WIFI_IFACE"),
                             (self.combo_inet_iface, "INTERNET_IFACE")):
                model = row.get_model()
                if model:
                    for index in range(model.get_n_items()):
                        if model.get_string(index) == conf.get(key):
                            row.set_selected(index)
                            break
            self.entry_ssid.set_text(conf.get("SSID", get_default_ssid()))
            self.entry_pass.set_text(conf.get("PASSPHRASE", "12345678"))
            self.entry_gateway.set_text(conf.get("GATEWAY", "192.168.12.1"))
            self.entry_channel.set_text(conf.get("CHANNEL", "default"))

            self.switch_hidden.set_active(conf.get("HIDDEN", "0") == "1")
            self.switch_isolate.set_active(conf.get("ISOLATE_CLIENTS", "0") == "1")
            self.switch_80211n.set_active(conf.get("IEEE80211N", "0") == "1")
            self.switch_80211ac.set_active(conf.get("IEEE80211AC", "0") == "1")
            self.switch_80211ax.set_active(conf.get("IEEE80211AX", "0") == "1")

            band = conf.get("FREQ_BAND", "auto")
            if band == "2.4":
                self.combo_band.set_selected(1)
            elif band == "5":
                self.combo_band.set_selected(2)
            else:
                self.combo_band.set_selected(0)
        finally:
            self._loading_fields = was_loading

    def _load_fallback_config(self):
        conf_path = "/etc/wifi-hotspot.conf"
        if not os.path.exists(conf_path):
            conf_path = os.path.expanduser("~/.config/wifi-hotspot.conf")
        conf = {}
        try:
            if os.path.exists(conf_path):
                with open(conf_path, "r") as f:
                    for line in f:
                        if "=" in line and not line.startswith("#"):
                            k, v = line.rstrip("\r\n").split("=", 1)
                            conf[k] = v
        except OSError:
            # Credentials are owner-only; keep settings usable if authorization failed.
            conf = {}

        # Local interface scan
        wifi = []
        all_ifaces = []
        try:
            for iface in os.listdir("/sys/class/net"):
                if iface == "lo":
                    continue
                all_ifaces.append(iface)
                if os.path.exists(f"/sys/class/net/{iface}/wireless") or os.path.exists(f"/sys/class/net/{iface}/phy80211"):
                    wifi.append(iface)
        except Exception:
            pass

        self.combo_wifi_iface.set_model(Gtk.StringList.new(wifi or ["wlp2s0"]))
        self.combo_inet_iface.set_model(Gtk.StringList.new(all_ifaces or ["wlp2s0", "enp1s0"]))
        self.row_caps.set_subtitle("⚠️ Background service is not running — run 'make dev-run-daemon' in terminal")
        self._populate_fields(conf)

    def _refresh_status(self):
        if not self.dbus_proxy or self._hotspot_busy:
            return GLib.SOURCE_CONTINUE
        try:
            res = self.dbus_proxy.GetStatus()
            status = json.loads(res)
            active = bool(status.get("active"))

            # Update switch state silently
            self.switch_hotspot.handler_block_by_func(self._on_switch_toggled)
            self.switch_hotspot.set_active(active)
            self.switch_hotspot.handler_unblock_by_func(self._on_switch_toggled)

            if active:
                self.row_status.set_subtitle(f"On — SSID: {status.get('ssid')} ({status.get('iface')})")
            else:
                self.row_status.set_subtitle("Off")

            # Update clients
            res_clients = self.dbus_proxy.GetClients()
            clients = json.loads(res_clients)
            self._update_clients_list(clients)

        except Exception as e:
            pass
        return GLib.SOURCE_CONTINUE

    def _update_clients_list(self, clients):
        if clients:
            self.row_no_clients.set_title(f"{len(clients)} Device(s) Connected")
            client_texts = []
            for c in clients:
                host = c.get('hostname')
                ip = c.get('ip')
                if host and ip:
                    client_texts.append(f"• {host} ({ip})")
                elif host:
                    client_texts.append(f"• {host}")
                elif ip:
                    client_texts.append(f"• Device ({ip})")
                else:
                    client_texts.append(f"• Device (Connecting...)")
            self.row_no_clients.set_subtitle("\n".join(client_texts))
        else:
            self.row_no_clients.set_title("No devices connected")
            self.row_no_clients.set_subtitle("Connected devices will be listed here")

    def _on_switch_toggled(self, switch, state):
        if not self.dbus_proxy or self._hotspot_busy:
            return True
        self._hotspot_busy = True
        switch.set_sensitive(False)
        self.row_status.set_subtitle("Starting (Wi-Fi may switch to 2.4 GHz)..." if state else "Stopping...")
        self.dbus_proxy.call(
            "Start" if state else "Stop", None, Gio.DBusCallFlags.NONE,
            60000, None, self._on_hotspot_finished, state,
        )
        return False

    def _on_hotspot_finished(self, proxy, result, starting):
        try:
            value = proxy.call_finish(result).unpack()[0]
            if starting:
                response = json.loads(value)
                if not response.get("success"):
                    raise RuntimeError(response.get("error") or "Failed to start hotspot.")
            elif not value:
                raise RuntimeError("Failed to stop hotspot.")
        except Exception as error:
            self.add_toast(Adw.Toast.new(str(error)))
        finally:
            self._hotspot_busy = False
            self.switch_hotspot.set_sensitive(True)
            self._refresh_status()

    def _on_field_changed(self, *args):
        if self._loading_fields or self._hotspot_busy:
            return
        wifi_item = self.combo_wifi_iface.get_selected_item()
        inet_item = self.combo_inet_iface.get_selected_item()
        if wifi_item is None or inet_item is None:
            return
        # Auto-save the selected interfaces without discarding other options.
        band_idx = self.combo_band.get_selected()
        band_str = "auto" if band_idx == 0 else ("2.4" if band_idx == 1 else "5")

        conf = {
            **self.config_data,
            "SSID": self.entry_ssid.get_text() or get_default_ssid(),
            "PASSPHRASE": self.entry_pass.get_text() or "12345678",
            "GATEWAY": self.entry_gateway.get_text() or "192.168.12.1",
            "CHANNEL": self.entry_channel.get_text() or "default",
            "FREQ_BAND": band_str,
            "HIDDEN": "1" if self.switch_hidden.get_active() else "0",
            "ISOLATE_CLIENTS": "1" if self.switch_isolate.get_active() else "0",
            "IEEE80211N": "1" if self.switch_80211n.get_active() else "0",
            "IEEE80211AC": "1" if self.switch_80211ac.get_active() else "0",
            "IEEE80211AX": "1" if self.switch_80211ax.get_active() else "0",
            "WIFI_IFACE": wifi_item.get_string(),
            "INTERNET_IFACE": inet_item.get_string(),
        }

        if self.dbus_proxy:
            try:
                self.dbus_proxy.SetConfig(json.dumps(conf))
                self.config_data = conf
                self.row_status.set_title("Service Status")
            except Exception as e:
                self.row_status.set_title("Settings were not saved")
                self.row_status.set_subtitle(str(e))

    def _on_show_qr(self, button):
        ssid = self.entry_ssid.get_text() or get_default_ssid()
        pwd = self.entry_pass.get_text() or "12345678"
        qr_text = f"WIFI:T:WPA;S:{ssid};P:{pwd};;"

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Wi-Fi Connection Code",
            body=f"Network Name: {ssid}\nPassword: {pwd}\n\nYou can scan or share the text below with your camera:\n{qr_text}",
        )
        dialog.add_response("ok", "Close")
        dialog.present()


class HotspotSettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.erhanzeyrek.WifiHotspot",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = HotspotSettingsWindow(self)
        win.present()


if __name__ == "__main__":
    app = HotspotSettingsApp()
    sys.exit(app.run(sys.argv))
