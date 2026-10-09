"""GTK4 smoke check. Run with a display (or Xvfb) in a separate process."""
from pathlib import Path
import sys
import os

sys.path.insert(0, os.environ.get('WIFI_RELAY_TEST_SETTINGS_DIR') or
                str(Path(__file__).resolve().parents[1] / 'settings'))
import main
from main import Adw, Gio, GLib, HotspotSettingsWindow

# Build real widgets without contacting or changing the host network service.
class FakeClient:
    def __init__(self, ready):
        self.proxy = object()
        self.closed = False
        GLib.idle_add(lambda: (ready(None), GLib.SOURCE_REMOVE)[1])
    def call(self, method, callback, parameters=None, timeout=10000):
        values = {
            'GetInterfaces': {'wifi_interfaces': ['wlo2'], 'all_interfaces': ['wlo2', 'eth0']},
            'GetCapabilities': {},
            'GetConfig': {'SSID': 'Test relay', 'BACKEND': 'create_ap', 'WIFI_IFACE': 'wlo2'},
            'GetStatus': {'active': False},
        }
        GLib.idle_add(lambda: (callback(values[method], None), GLib.SOURCE_REMOVE)[1])
    def close(self):
        self.closed = True
main.ServiceClient = FakeClient
application = Adw.Application(application_id='io.github.wifirelay.SettingsSmokeTest')
application.register(None)
window = HotspotSettingsWindow(application)
while GLib.MainContext.default().pending():
    GLib.MainContext.default().iteration(False)
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
window._pending_config = None
window._on_close()
window.destroy()
assert window.client.closed
print('Real GTK4 settings window, backend selector, first-run fields, and startup checks passed.')
