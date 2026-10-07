"""Exercise settings callbacks with mocked widgets; no display or D-Bus needed."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    'hotspot_settings', Path(__file__).resolve().parents[1] / 'settings/main.py'
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Window = module.HotspotSettingsWindow


class InterfaceSettingsTests(unittest.TestCase):
    def setUp(self):
        self.window = SimpleNamespace(
            _loading_fields=False, _hotspot_busy=False,
            config_data={'NO_VIRT': '0', 'SHARE_METHOD': 'nat', 'WIFI_IFACE': 'wlo2', 'INTERNET_IFACE': 'wlo2'},
            row_status=Mock(), dbus_proxy=Mock(), combo_wifi_iface=Mock(), combo_inet_iface=Mock(), combo_band=Mock(),
            combo_backend=Mock(),
        )
        self.window.combo_wifi_iface.get_selected_item.return_value.get_string.return_value = 'wlo2'
        self.window.combo_inet_iface.get_selected_item.return_value.get_string.return_value = 'wlo2'
        self.window.combo_band.get_selected.return_value = 0
        self.window.combo_backend.get_selected.return_value = 0
        for name, text in [('entry_ssid', 'Hotspot'), ('entry_pass', 'password123'),
                           ('entry_gateway', '192.168.12.1'), ('entry_channel', 'default')]:
            widget = Mock()
            widget.get_text.return_value = text
            setattr(self.window, name, widget)
        for name in ('switch_hidden', 'switch_isolate', 'switch_80211n', 'switch_80211ac', 'switch_80211ax'):
            widget = Mock()
            widget.get_active.return_value = False
            setattr(self.window, name, widget)
        # Gio's dynamic proxy takes a GVariant signature before method arguments.
        def save(signature, *args):
            value = module.GLib.Variant(signature, args)
            self.assertEqual(value.get_type_string(), '(s)')
            return True
        self.window.dbus_proxy.SetConfig.side_effect = save
        self.window._on_field_changed = lambda: Window._on_field_changed(self.window)

    def saved_config(self):
        signature, payload = self.window.dbus_proxy.SetConfig.call_args.args
        self.assertEqual(signature, '(s)')
        return json.loads(payload)

    def test_same_adapter_is_saved_for_upstream_and_hotspot(self):
        Window._on_field_changed(self.window)
        saved = self.saved_config()
        self.assertEqual(saved['WIFI_IFACE'], 'wlo2')
        self.assertEqual(saved['INTERNET_IFACE'], 'wlo2')
        self.assertEqual(saved['NO_VIRT'], '0')
        self.assertEqual(saved['SHARE_METHOD'], 'nat')

    def test_loading_does_not_overwrite_configuration(self):
        self.window._loading_fields = True
        Window._on_field_changed(self.window)
        self.window.dbus_proxy.SetConfig.assert_not_called()

    def test_networkmanager_backend_is_saved_from_selector(self):
        self.window.combo_backend.get_selected.return_value = 1
        Window._on_field_changed(self.window)
        saved = self.saved_config()
        self.assertEqual(saved["BACKEND"], "networkmanager")

    def test_populating_fields_selects_saved_interfaces_without_saving(self):
        for row in (self.window.combo_wifi_iface, self.window.combo_inet_iface):
            row.get_model.return_value.get_n_items.return_value = 2
            row.get_model.return_value.get_string.side_effect = ['eth0', 'wlo2']
            row.set_selected.side_effect = lambda *_: Window._on_field_changed(self.window)
        Window._populate_fields(self.window, self.window.config_data)
        self.window.combo_wifi_iface.set_selected.assert_called_once_with(1)
        self.window.combo_inet_iface.set_selected.assert_called_once_with(1)
        self.window.dbus_proxy.SetConfig.assert_not_called()
        self.assertFalse(self.window._loading_fields)

    def test_start_saves_visible_adapter_before_activation(self):
        self.window.config_data['WIFI_IFACE'] = 'wlan0'
        self.window._on_hotspot_finished = Mock()
        self.assertFalse(Window._on_switch_toggled(self.window, Mock(), True))
        self.assertEqual(self.saved_config()['WIFI_IFACE'], 'wlo2')
        self.assertEqual(self.window.dbus_proxy.call.call_args.args[0], 'Start')

    def test_failed_save_prevents_activation(self):
        self.window.dbus_proxy.SetConfig.side_effect = RuntimeError('Save failed')
        self.assertTrue(Window._on_switch_toggled(self.window, Mock(), True))
        self.window.dbus_proxy.call.assert_not_called()
        self.assertFalse(self.window._hotspot_busy)
