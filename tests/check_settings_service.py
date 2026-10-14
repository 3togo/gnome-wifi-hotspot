"""Real GTK settings, ServiceClient, and daemon dispatch on a private D-Bus bus."""
import json
import unittest
from unittest.mock import patch

from private_service import PrivateService, wait_until, GLib
import main


class SettingsServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = main.Adw.Application(application_id='io.github.wifirelay.ServiceSmoke',
                                       flags=main.Gio.ApplicationFlags.NON_UNIQUE)
        cls.app.register(None)

    def setUp(self):
        self.service = PrivateService()
        self.addCleanup(self.service.close)
        self.windows = []
        self.addCleanup(self.close_windows)

    def close_windows(self):
        for window in self.windows:
            if not window._closed:
                window._close_resources()
            window.destroy()

    def window(self):
        window = main.HotspotSettingsWindow(self.app)
        self.windows.append(window)
        wait_until(lambda: window._loaded and not window._status_pending or window._retry_action == 'load')
        return window

    def flush_edit(self, window):
        if window._save_timer:
            GLib.source_remove(window._save_timer)
            window._save_timer = 0
        window._flush_config()

    def test_loading_and_starting_use_real_configuration_and_authorization(self):
        window = self.window()
        self.assertTrue(window._loaded)
        self.assertEqual(window.entry_ssid.get_text(), 'Integration relay')
        window.entry_ssid.set_text('Latest edit')
        window._on_switch_toggled(window.switch_hotspot, True)
        self.assertTrue(window._hotspot_busy)
        wait_until(lambda: not window._hotspot_busy and not window._status_pending)
        self.assertEqual(self.service.daemon._read_config_dict()['SSID'], 'Latest edit')
        self.assertEqual(self.service.daemon.operations, ['Start'])
        methods = self.service.calls
        self.assertLess(methods.index('SetConfig'), methods.index('Start'))
        self.assertTrue(window.switch_hotspot.get_active())

    def test_denied_load_can_be_retried_without_reopening_the_window(self):
        self.service.allowed = False
        original_exists = main.os.path.exists
        with patch.object(main.os.path, 'exists', side_effect=lambda path:
                          False if path == '/etc/wifi-hotspot.conf' else original_exists(path)):
            window = self.window()
        self.assertFalse(window._loaded)
        self.assertFalse(window.entry_ssid.get_sensitive())
        self.assertTrue(window.retry_button.get_visible())
        self.service.allowed = True
        window.retry_button.emit('clicked')
        wait_until(lambda: window._loaded and not window._status_pending)
        self.assertTrue(window.entry_ssid.get_sensitive())
        self.assertFalse(window.retry_button.get_visible())
        self.assertEqual(window.entry_ssid.get_text(), 'Integration relay')

    def test_failed_save_keeps_latest_edit_and_retry_saves_without_starting(self):
        window = self.window()
        self.service.allowed = False
        window.entry_ssid.set_text('Unsaved relay')
        self.flush_edit(window)
        wait_until(lambda: window._retry_action == 'save')
        self.assertEqual(window._pending_config['SSID'], 'Unsaved relay')
        self.assertEqual(window.row_status.get_title(), 'Settings were not saved')
        self.assertTrue(window.retry_button.get_visible())
        self.service.allowed = True
        window.entry_ssid.set_text('Latest retry')
        window.retry_button.emit('clicked')
        wait_until(lambda: not window.writer.inflight)
        self.assertEqual(self.service.daemon._read_config_dict()['SSID'], 'Latest retry')
        self.assertFalse(window.retry_button.get_visible())
        self.assertEqual(self.service.daemon.operations, [])

    def test_failed_stop_remains_visible_and_retry_stops_sharing(self):
        window = self.window()
        window._on_switch_toggled(window.switch_hotspot, True)
        wait_until(lambda: not window._hotspot_busy and not window._status_pending)
        self.service.allowed = False
        window._on_switch_toggled(window.switch_hotspot, False)
        wait_until(lambda: not window._hotspot_busy and not window._status_pending)
        self.assertEqual(window._retry_action, 'stop')
        self.assertEqual(window.row_status.get_title(), 'Hotspot could not stop')
        self.assertTrue(window.switch_hotspot.get_active())
        self.assertEqual(self.service.daemon.operations, ['Start'])
        self.service.allowed = True
        window.retry_button.emit('clicked')
        wait_until(lambda: not window._hotspot_busy and not window._status_pending)
        self.assertEqual(self.service.daemon.operations, ['Start', 'Stop'])
        self.assertFalse(window.retry_button.get_visible())
        self.assertFalse(window.switch_hotspot.get_active())

    def test_denied_start_keeps_controls_available_for_explicit_retry(self):
        window = self.window()
        # Permit the save, then deny activation through the real authorization flow.
        self.service.authorization_results = [True, False]
        window._on_switch_toggled(window.switch_hotspot, True)
        wait_until(lambda: not window._hotspot_busy and not window._status_pending)
        self.assertEqual(window._retry_action, 'start')
        self.assertFalse(window.switch_hotspot.get_active())
        self.assertTrue(window.switch_hotspot.get_sensitive())
        self.assertEqual(self.service.daemon.operations, [])
        window.retry_button.emit('clicked')
        wait_until(lambda: not window._hotspot_busy and not window._status_pending)
        self.assertEqual(self.service.daemon.operations, ['Start'])
        self.assertFalse(window.retry_button.get_visible())

    def test_delayed_clients_cannot_overwrite_newer_stopped_status(self):
        window = self.window()
        self.service.hold_methods.add('GetClients')
        self.service.daemon.status = {'active': True}
        window._refresh_status()
        wait_until(lambda: self.service.held.get('GetClients'))
        self.service.daemon.status = {'active': False}
        window._refresh_status()
        wait_until(lambda: not window._status_pending)
        self.service.reply('GetClients', [{'hostname': 'Stale client', 'ip': '192.168.12.2'}])
        wait_until(lambda: not window._clients_pending)
        self.assertEqual(window.row_no_clients.get_title(), 'No devices connected')
        self.assertFalse(window.switch_hotspot.get_active())

    def test_malformed_status_has_retry_and_recovers_on_valid_reply(self):
        window = self.window()
        self.service.malformed_status = '{"active":"false"}'
        window._refresh_status()
        wait_until(lambda: window._retry_action == 'status')
        self.assertFalse(window.switch_hotspot.get_sensitive())
        self.service.malformed_status = None
        window.retry_button.emit('clicked')
        wait_until(lambda: not window._status_pending)
        self.assertTrue(window.switch_hotspot.get_sensitive())
        self.assertFalse(window.retry_button.get_visible())

    def test_rapid_edits_coalesce_while_a_real_write_is_inflight(self):
        window = self.window()
        self.service.hold_methods.add('SetConfig')
        window.entry_ssid.set_text('First edit')
        self.flush_edit(window)
        wait_until(lambda: self.service.held.get('SetConfig'))
        window.entry_ssid.set_text('Partial')
        self.flush_edit(window)
        window.entry_ssid.set_text('Latest edit')
        self.flush_edit(window)
        self.assertEqual(self.service.calls.count('SetConfig'), 1)
        # Complete the held write, then let the latest queued write use production dispatch.
        self.service.hold_methods.clear()
        self.service.held['SetConfig'].pop(0).return_value(GLib.Variant('(b)', (True,)))
        wait_until(lambda: not window.writer.inflight)
        self.assertEqual(self.service.calls.count('SetConfig'), 2)
        self.assertEqual(self.service.daemon._read_config_dict()['SSID'], 'Latest edit')


if __name__ == '__main__':
    unittest.main(verbosity=2)
