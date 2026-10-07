"""GTK4 smoke check. Run with a display (or Xvfb) in a separate process."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'settings'))
from main import Adw, Gio, HotspotSettingsWindow

# Build real widgets without contacting or changing the host network service.
HotspotSettingsWindow._init_dbus = lambda self: None
application = Adw.Application(application_id='io.github.wifirelay.SettingsSmokeTest')
application.register(None)
window = HotspotSettingsWindow(application)
assert window.get_title() == 'Wi-Fi Relay Settings'
assert window.switch_startup.get_active() is True
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
window.destroy()
print('Real GTK4 settings window, backend selector, first-run fields, and startup checks passed.')
