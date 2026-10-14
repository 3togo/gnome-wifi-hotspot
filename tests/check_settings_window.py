"""GTK4 smoke check. Run with a display (or Xvfb) in a separate process."""
from pathlib import Path
import sys
import os
import time


def drain_events():
    deadline = time.monotonic() + 5
    context = GLib.MainContext.default()
    while context.pending():
        if time.monotonic() >= deadline:
            raise AssertionError("Settings event queue did not settle")
        context.iteration(False)


sys.path.insert(0, os.environ.get('WIFI_RELAY_TEST_SETTINGS_DIR') or
                str(Path(__file__).resolve().parents[1] / 'settings'))
import main
from main import Adw, Gio, GLib, HotspotSettingsWindow

# Build real widgets without contacting or changing the host network service.
class FakeClient:
    def __init__(self, ready):
        self.proxy = object()
        self.closed = False
        self.calls = []
        self.saves = []
        GLib.idle_add(lambda: (ready(None), GLib.SOURCE_REMOVE)[1])
    def call(self, method, callback, parameters=None, timeout=10000):
        self.calls.append(method)
        if method == 'SetConfig':
            self.saves.append((parameters.unpack()[0], callback))
            return
        values = {
            'GetInterfaces': {'wifi_interfaces': ['wlo2'], 'all_interfaces': ['wlo2', 'eth0']},
            'GetCapabilities': {},
            'GetConfig': {'SSID': 'Test relay', 'BACKEND': 'create_ap', 'WIFI_IFACE': 'wlo2'},
            'GetStatus': {'active': False},
            'GetClients': [],
            'Start': {'success': True},
            'Stop': True,
        }
        GLib.idle_add(lambda: (callback(values[method], None), GLib.SOURCE_REMOVE)[1])
    def close(self):
        self.closed = True
main.ServiceClient = FakeClient
application = Adw.Application(application_id='io.github.wifirelay.SettingsSmokeTest')
application.register(None)
window = HotspotSettingsWindow(application)
drain_events()
assert window.get_title() == 'Wi-Fi Relay Settings'
assert window.switch_startup.get_sensitive() == main.desktop_integration_available()
assert window.switch_startup.get_active() == (main.get_auto_start() if main.desktop_integration_available() else False)
assert window.combo_wifi_iface.get_model().get_n_items() > 0
assert window.combo_inet_iface.get_model().get_n_items() > 0
assert window.entry_ssid.get_text()
assert window.combo_backend.get_model().get_n_items() == 2
window._populate_fields({**window.config_data, 'BACKEND': 'networkmanager'})
assert window.combo_backend.get_selected() == 1
assert not window.combo_inet_iface.get_sensitive()
window._populate_fields({**window.config_data, 'BACKEND': 'create_ap'})
assert window.combo_backend.get_selected() == 0
assert window.combo_inet_iface.get_sensitive()
window._loading_fields = True
window.entry_ssid.set_text('Test relay')
window.entry_pass.set_text('synthetic-test-password')
window._loading_fields = False
dialog = window._on_show_qr(None)
assert dialog is not None
picture = dialog.get_extra_child()
texture = picture.get_paintable()
assert texture.get_width() >= 250
assert texture.get_width() == texture.get_height()
assert picture.get_size_request() == (texture.get_width(), texture.get_height())
assert picture.get_alternative_text() == 'Wi-Fi connection QR code for Test relay'
dialog.destroy()
# Editing must save the latest form before Start reaches the service.
import json
window.entry_ssid.set_text('Latest relay')
assert window._pending_config['SSID'] == 'Latest relay'
assert window._on_switch_toggled(window.switch_hotspot, True)
assert window._hotspot_busy
assert not window.switch_hotspot.get_sensitive()
assert 'Start' not in window.client.calls
payload, saved = window.client.saves.pop(0)
assert json.loads(payload)['SSID'] == 'Latest relay'
saved(True, None)
assert window.client.calls[-1] == 'Start'
drain_events()
assert not window._hotspot_busy
assert window.switch_hotspot.get_sensitive()

# A rejected save keeps edits retryable and never starts broadcasting.
window.entry_ssid.set_text('Retry relay')
start_count = window.client.calls.count('Start')
window._on_switch_toggled(window.switch_hotspot, True)
_payload, saved = window.client.saves.pop(0)
saved(False, None)
drain_events()
assert window.client.calls.count('Start') == start_count
assert window._pending_config['SSID'] == 'Retry relay'
assert not window._hotspot_busy

# Closing waits for a save; failure leaves the editor open for a retry.
assert window._on_close()
assert not window.client.closed
assert not window.entry_ssid.get_sensitive()
_payload, saved = window.client.saves.pop(0)
saved(False, None)
assert not window.client.closed
assert window.entry_ssid.get_sensitive()
assert window._pending_config['SSID'] == 'Retry relay'
assert window._on_close()
_payload, saved = window.client.saves.pop(0)
saved(True, None)
assert window.client.closed
assert window._closed
assert window._status_timer == window._save_timer == 0
assert 'Stop' not in window.client.calls
print('Save-before-start, failed-save retry, and close-after-save checks passed.')
print('Real GTK4 settings window, backend selector, first-run fields, and startup checks passed.')

# About is a real, reusable window with no service or configuration access.
from unittest.mock import patch
with patch.object(main, 'ServiceClient', side_effect=AssertionError('About contacted service')):
    about_app = main.HotspotAboutApp()
    about_app.register(None)
    about_app.activate()
    drain_events()
    about = about_app.get_windows()[0]
    assert about.get_application_name() == 'Wi-Fi Relay'
    assert about.get_version() == '1.0.0'
    assert about.get_license_type() == main.Gtk.License.MIT_X11
    assert about.get_website() == 'https://github.com/3togo/gnome-wifi-hotspot'
    assert about.get_issue_url().endswith('/issues')
    about_app.activate()
    assert about_app.get_windows() == [about]
    about.close()
print('About metadata, window reuse, and service independence checks passed.')
