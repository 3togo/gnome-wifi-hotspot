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
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk

try:
    from startup import get_auto_start, set_auto_start, is_gnome, launch_tray, desktop_integration_available
except ModuleNotFoundError:
    from settings.startup import get_auto_start, set_auto_start, is_gnome, launch_tray, desktop_integration_available

try:
    from service_client import ServiceClient, ConfigurationWriter
except ModuleNotFoundError:
    from settings.service_client import ServiceClient, ConfigurationWriter

try:
    from wifi_qr import wifi_payload, qr_rgb
except ModuleNotFoundError:
    from settings.wifi_qr import wifi_payload, qr_rgb

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

        self._closed = False
        self._loaded = False
        self._status_pending = False
        self._clients_pending = False
        self._status_revision = 0
        self._save_timer = 0
        self._pending_config = None
        self._closing_after_save = False
        self._build_ui()
        self._set_form_sensitive(False)
        self.switch_hotspot.set_sensitive(False)
        self.client = ServiceClient(self._on_client_ready)
        self.writer = ConfigurationWriter(self.client)
        self._status_timer = GLib.timeout_add_seconds(3, self._refresh_status)
        self.connect("close-request", self._on_close)

    def _on_client_ready(self, error):
        if self._closed:
            return
        self.dbus_proxy = self.client.proxy
        if error:
            self._load_fallback_config()
            self._loading_fields = False
            return
        if not self._loaded:
            self._load_data()
        else:
            self._refresh_status()

    def _on_close(self, *_args):
        if self._closed:
            return False
        if self._closing_after_save:
            return True
        if self._pending_config is not None or self.writer.inflight:
            config = self._collect_config()
            if config is not None:
                self._closing_after_save = True
                self._set_form_sensitive(False)
                if self._save_timer:
                    GLib.source_remove(self._save_timer)
                    self._save_timer = 0
                self._pending_config = None
                def saved(config, error):
                    self._closing_after_save = False
                    if error:
                        self._pending_config = dict(config)
                        self._set_form_sensitive(True)
                        self.add_toast(Adw.Toast.new(str(error)))
                        return
                    self._close_resources()
                    self.destroy()
                self.writer.submit(config, saved)
                return True
        self._close_resources()
        return False

    def _close_resources(self):
        self._closed = True
        for source in (self._status_timer, self._save_timer):
            if source:
                GLib.source_remove(source)
        self._status_timer = self._save_timer = 0
        self.client.close()

    def _set_form_sensitive(self, enabled):
        for name in ('combo_backend', 'combo_wifi_iface', 'combo_inet_iface', 'combo_band',
                     'entry_ssid', 'entry_pass', 'entry_gateway', 'entry_channel',
                     'switch_hidden', 'switch_isolate', 'switch_80211n', 'switch_80211ac', 'switch_80211ax'):
            getattr(self, name).set_sensitive(enabled)
        if enabled and self.config_data.get('BACKEND') == 'networkmanager':
            self.combo_inet_iface.set_sensitive(False)

    def _build_ui(self):
        # Header bar controls
        header = self.get_titlebar()

        # ---------------- Page 1: General & Network Settings ---------------- #
        page_general = Adw.PreferencesPage(title="General", icon_name="network-wireless-hotspot-symbolic")
        self.add(page_general)

        grp_startup = Adw.PreferencesGroup(title="Startup")
        page_general.add(grp_startup)
        controls_available = desktop_integration_available()
        self.switch_startup = Adw.SwitchRow(
            title="Start desktop controls at login",
            subtitle=("Show desktop controls when you log in. Disabling also hides them now."
                      if controls_available else "Install the optional GNOME or tray integration for your desktop."),
            active=get_auto_start() if controls_available else False,
            sensitive=controls_available,
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

        self.combo_backend = Adw.ComboRow(title="Hotspot Backend",
            subtitle="NetworkManager runs until switched off and follows host routing; experimental")
        self.combo_backend.set_model(Gtk.StringList.new(["create_ap", "NetworkManager (Experimental)"]))
        self.combo_backend.connect("notify::selected", self._on_field_changed)
        grp_net.add(self.combo_backend)

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
            if not desktop_integration_available():
                raise RuntimeError("Desktop controls are not installed for this session")
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
        def interfaces_loaded(data, error):
            if not error:
                self.interfaces = data
                self.combo_wifi_iface.set_model(Gtk.StringList.new(data["wifi_interfaces"] or ["wlan0"]))
                self.combo_inet_iface.set_model(Gtk.StringList.new(data["all_interfaces"] or ["wlan0"]))
            else:
                self._load_fallback_config()
            self.client.call("GetCapabilities", capabilities_loaded)

        def capabilities_loaded(data, error):
            if not error:
                self.capabilities = data
                ap_5g = "Yes" if data.get("ap_5ghz") else "No"
                band = data.get("current_sta_band", "Unknown")
                self.row_caps.set_subtitle(f"5GHz AP Support: {ap_5g} | Current Wi-Fi Band: {band} GHz")
            self.client.call("GetConfig", config_loaded, timeout=60000)

        def config_loaded(data, error):
            if error:
                self._load_fallback_config()
            else:
                self._populate_fields(data)
            self._loading_fields = False
            self._loaded = error is None
            self._set_form_sensitive(error is None)
            self._refresh_status()

        self.client.call("GetInterfaces", interfaces_loaded)

    def _populate_fields(self, conf):
        was_loading = self._loading_fields
        self._loading_fields = True
        try:
            self.config_data = dict(conf)
            self.combo_backend.set_selected(1 if conf.get("BACKEND") == "networkmanager" else 0)
            use_nm = conf.get("BACKEND") == "networkmanager"
            self.combo_inet_iface.set_sensitive(not use_nm)
            self.combo_inet_iface.set_subtitle("Uses the host default route, including Ethernet or VPN"
                if use_nm else "Choose the same Wi-Fi adapter for simultaneous Wi-Fi + hotspot")
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
        self.row_caps.set_subtitle("Hotspot service unavailable. Check that Wi-Fi Relay is installed and running.")
        self._populate_fields(conf)

    def _refresh_status(self):
        if self._closed:
            return GLib.SOURCE_REMOVE
        if not self.dbus_proxy or self._hotspot_busy or self._status_pending:
            return GLib.SOURCE_CONTINUE
        self._status_pending = True
        revision = self._status_revision
        def status_loaded(status, error):
            self._status_pending = False
            if revision != self._status_revision or self._hotspot_busy:
                return
            if error:
                self.switch_hotspot.set_sensitive(False)
                self.row_status.set_subtitle("Hotspot service unavailable")
                return
            self._status_revision += 1
            active = status["active"]
            requested = active or status.get("desired_active", False)
            self.combo_backend.set_sensitive(self._loaded and not requested)
            self.switch_hotspot.set_sensitive(self._loaded or requested)
            self.switch_hotspot.handler_block_by_func(self._on_switch_toggled)
            self.switch_hotspot.set_active(requested)
            self.switch_hotspot.handler_unblock_by_func(self._on_switch_toggled)
            if active:
                self.row_status.set_subtitle(f"On — SSID: {status.get('ssid')} ({status.get('iface')})")
            else:
                self.row_status.set_subtitle(status.get("error") or ("Waiting for Wi-Fi" if requested else "Off"))
                self._update_clients_list([])
            if active and not self._clients_pending:
                self._clients_pending = True
                client_revision = self._status_revision
                def clients_loaded(clients, error):
                    self._clients_pending = False
                    if not error and client_revision == self._status_revision and not self._hotspot_busy:
                        self._update_clients_list(clients)
                self.client.call("GetClients", clients_loaded)
        self.client.call("GetStatus", status_loaded)
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
        if not self.dbus_proxy or self._hotspot_busy or self._loading_fields or (state and not self._loaded):
            return True
        config = self._collect_config() if state else None
        if state and config is None:
            return True
        if state:
            if self._save_timer:
                GLib.source_remove(self._save_timer)
                self._save_timer = 0
            self._pending_config = None
        self._hotspot_busy = True
        self._status_revision += 1
        self._set_form_sensitive(False)
        switch.set_sensitive(False)
        self.row_status.set_subtitle("Starting hotspot…" if state else "Stopping hotspot…")
        def operate(saved=None, error=None):
            if error:
                self._pending_config = dict(saved) if saved is not None else None
                self._on_hotspot_finished(None, error, state)
                return
            if saved is not None:
                self.config_data = saved
            self.client.call("Start" if state else "Stop",
                             lambda data, failure: self._on_hotspot_finished(data, failure, state),
                             timeout=60000)
        if state:
            self.writer.submit(config, operate)
        else:
            operate()
        return True

    def _on_hotspot_finished(self, data, error, starting):
        if not error and ((starting and not data.get("success")) or (not starting and not data)):
            error = RuntimeError(data.get("error") or "Failed to start hotspot" if starting
                                 else "Failed to stop hotspot")
        if error:
            self.add_toast(Adw.Toast.new(str(error)))
        self._hotspot_busy = False
        self._set_form_sensitive(self._loaded)
        self.switch_hotspot.set_sensitive(self._loaded)
        self._refresh_status()

    def _on_field_changed(self, *args):
        if self._loading_fields or self._hotspot_busy or self._closed or self._closing_after_save:
            return False
        config = self._collect_config()
        if config is None:
            return False
        self._pending_config = config
        if self._save_timer:
            GLib.source_remove(self._save_timer)
        self._save_timer = GLib.timeout_add(500, self._flush_config)
        return True

    def _flush_config(self):
        self._save_timer = 0
        config, self._pending_config = self._pending_config, None
        if config is not None and not self._closed:
            self.writer.submit(config, self._on_config_saved)
        return GLib.SOURCE_REMOVE

    def _on_config_saved(self, config, error):
        if error:
            if self._pending_config is None:
                self._pending_config = dict(config)
            self.row_status.set_title("Settings were not saved")
            self.row_status.set_subtitle(str(error))
            return
        self.config_data = config
        if self._hotspot_busy:
            return
        use_nm = config["BACKEND"] == "networkmanager"
        self.combo_inet_iface.set_sensitive(not use_nm)
        self.combo_inet_iface.set_subtitle("Uses the host default route, including Ethernet or VPN"
            if use_nm else "Choose the same Wi-Fi adapter for simultaneous Wi-Fi + hotspot")
        self.row_status.set_title("Service Status")

    def _collect_config(self):
        wifi_item = self.combo_wifi_iface.get_selected_item()
        inet_item = self.combo_inet_iface.get_selected_item()
        if wifi_item is None or inet_item is None:
            self.row_status.set_title("Settings were not saved")
            self.row_status.set_subtitle("Select a Wi-Fi adapter and sharing interface first.")
            return None
        # Auto-save the selected interfaces without discarding other options.
        band_idx = self.combo_band.get_selected()
        band_str = "auto" if band_idx == 0 else ("2.4" if band_idx == 1 else "5")

        conf = {
            **self.config_data,
            "BACKEND": "networkmanager" if self.combo_backend.get_selected() == 1 else "create_ap",
            "SSID": self.entry_ssid.get_text() or get_default_ssid(),
            "PASSPHRASE": self.entry_pass.get_text(),
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

        return conf

    def _on_show_qr(self, button):
        if not self._loaded:
            self.add_toast(Adw.Toast.new("Wait for the hotspot settings to load before sharing."))
            return
        ssid = self.entry_ssid.get_text()
        pwd = self.entry_pass.get_text()
        try:
            payload = wifi_payload(ssid, pwd, self.switch_hidden.get_active())
            width, pixels = qr_rgb(payload)
        except ValueError as error:
            self.add_toast(Adw.Toast.new(str(error)))
            return
        texture = Gdk.MemoryTexture.new(width, width, Gdk.MemoryFormat.R8G8B8,
                                        GLib.Bytes.new(pixels), width * 3)
        picture = Gtk.Picture.new_for_paintable(texture)
        picture.set_alternative_text("Wi-Fi connection QR code for " + ssid)
        picture.set_can_shrink(True)
        picture.set_size_request(width, width)
        picture.set_halign(Gtk.Align.CENTER)
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Wi-Fi Connection Code",
            body=f"Network Name: {ssid}\nPassword: {pwd}\n\nScan the QR code with your phone’s camera to connect.",
        )
        dialog.set_extra_child(picture)
        dialog.add_response("ok", "Close")
        dialog.present()
        return dialog


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
