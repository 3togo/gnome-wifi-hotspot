"""Run with python3 -m unittest discover -s tests (no network changes)."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "hotspot_daemon", Path(__file__).resolve().parents[1] / "daemon/wifi-hotspot-daemon.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Daemon = module.WifiHotspotDaemon

PHY = """Wiphy phy0
\tSupported interface modes:
\t\t * managed
\t\t * AP
\tBand 1:
\t\tFrequencies:
\t\t\t* 2412.0 MHz [1] (22.0 dBm)
\t\t\t* 2437 MHz [6] (22.0 dBm)
\t\t\t* 2484 MHz [14] (disabled)
\tBand 2:
\t\tFrequencies:
\t\t\t* 5180 MHz [36] (22.0 dBm) (no IR)
\t\t\t* 5200 MHz [40] (22.0 dBm) (radar detection)
\t\t\t* 5745 MHz [149] (22.0 dBm)
\tvalid interface combinations:
\t\t * #{ managed } <= 1, #{ AP, P2P-client, P2P-GO } <= 1,
\t\t   total <= 3, #channels <= 1
\tHT Capability overrides:
"""


def capabilities(freq=5180):
    channels, concurrent = Daemon._parse_phy_capabilities(PHY)
    band = Daemon._frequency_band(freq)
    return dict(ap_channels=channels, ap_2ghz=True, ap_5ghz=True,
                ap_sta_concurrent=concurrent, wifi_iface="wlo2",
                current_sta_frequency=freq, current_sta_band=band,
                current_sta_ssid="Home:WiFi", current_sta_bssid="aa:bb:cc:dd:ee:ff",
                current_sta_ap_allowed=any(c['frequency'] == freq for c in channels[band]))


class BandFallbackTests(unittest.TestCase):
    def setUp(self):
        self.daemon = Daemon.__new__(Daemon)
        log = patch.object(module, "prepare_startup_log", return_value="/nonexistent/relay-test.log")
        log.start()
        self.addCleanup(log.stop)
        self.daemon.create_ap_bin = "create_ap"
        self.daemon._read_config_dict = Mock(return_value={
            "WIFI_IFACE": "wlo2", "INTERNET_IFACE": "wlo2", "FREQ_BAND": "auto"
        })
        self.daemon._emit_signal = Mock()
        self.daemon.prepare_firewall = Mock()
        self.daemon._run_cmd = Mock(return_value=(0, "", ""))

    def test_regulatory_restrictions(self):
        channels, concurrent = Daemon._parse_phy_capabilities(PHY)
        self.assertTrue(concurrent)
        self.assertEqual([c['channel'] for c in channels['2.4']], [1, 6])
        self.assertEqual([c['channel'] for c in channels['5']], [149])

    def test_combined_group_needs_two_slots(self):
        output = PHY.replace('#{ managed } <= 1, #{ AP, P2P-client, P2P-GO } <= 1,',
                             '#{ managed, AP } <= 1,')
        self.assertFalse(Daemon._parse_phy_capabilities(output)[1])
        self.assertTrue(Daemon._parse_phy_capabilities(output.replace(
            '#{ managed, AP } <= 1', '#{ managed, AP } <= 2'))[1])

    def test_no_ap_mode(self):
        channels, concurrent = Daemon._parse_phy_capabilities(PHY.replace('\t\t * AP\n', ''))
        self.assertEqual(channels, {'2.4': [], '5': []})
        self.assertFalse(concurrent)

    def test_selected_phy_and_decimal_frequency(self):
        self.daemon._run_cmd.side_effect = [
            (0, 'Interface wlo2\n\twiphy 7', ''), (0, PHY, ''),
            (0, 'Connected to aa:bb:cc:dd:ee:ff\n\tSSID: Home:WiFi\n\tfreq: 5180.0', '')
        ]
        caps = self.daemon.get_capabilities()
        self.assertFalse(caps['current_sta_ap_allowed'])
        self.assertEqual(caps['current_sta_band'], '5')
        self.daemon._run_cmd.assert_any_call(['iw', 'phy', 'phy7', 'info'])

    def test_escaped_nmcli_fields(self):
        self.assertEqual(Daemon._split_nmcli_row(r'Home\:WiFi:aa\:bb\:cc\:dd\:ee\:ff:2412 MHz:90'),
                         ['Home:WiFi', 'aa:bb:cc:dd:ee:ff', '2412 MHz', '90'])

    def switch_setup(self, scan, result=(0, '', ''), verified=None):
        self.daemon.get_capabilities = Mock(side_effect=[capabilities(), verified or capabilities(2412)])
        self.daemon._run_cmd.side_effect = [(0, 'profile-uuid', ''), (0, scan, ''), result, (0, '', '')]

    def test_switch_reuses_profile_and_verifies_band(self):
        self.switch_setup(r'Home\:WiFi:aa\:bb\:cc\:dd\:ee\:01:2412 MHz:90')
        result = json.loads(self.daemon.switch_band_and_reconnect('2.4'))
        self.assertTrue(result['success'])
        self.daemon._run_cmd.assert_any_call([
            'nmcli', '--wait', '8', 'connection', 'up', 'uuid', 'profile-uuid',
            'ifname', 'wlo2', 'ap', 'aa:bb:cc:dd:ee:01'
        ], timeout=10)

    def test_missing_target_does_not_disconnect(self):
        self.switch_setup(r'Home\:WiFi:aa\:bb\:cc\:dd\:ee\:01:5180 MHz:90')
        result = json.loads(self.daemon.switch_band_and_reconnect('2.4'))
        self.assertFalse(result['success'])
        self.assertIn('No reachable 2.4', result['error'])
        self.assertEqual(self.daemon._run_cmd.call_count, 2)

    def test_failed_reconnection_restores_original(self):
        self.switch_setup(r'Home\:WiFi:aa\:bb\:cc\:dd\:ee\:01:2412 MHz:90',
                          result=(10, '', 'Activation failed'), verified=capabilities())
        result = json.loads(self.daemon.switch_band_and_reconnect('2.4'))
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Activation failed')
        self.assertEqual(self.daemon._run_cmd.call_args.args[0][-1], 'aa:bb:cc:dd:ee:ff')

    def test_successful_command_on_wrong_band_is_failure(self):
        self.daemon.get_capabilities = Mock(side_effect=[
            capabilities(), capabilities(), capabilities()
        ])
        self.daemon._run_cmd.side_effect = [
            (0, 'profile-uuid', ''),
            (0, r'Home\:WiFi:aa\:bb\:cc\:dd\:ee\:01:2412 MHz:90', ''),
            (0, '', ''), (0, '', ''), (0, '', ''), (0, '', ''), (0, '', ''), (0, '', ''),
        ]
        self.assertFalse(json.loads(self.daemon.switch_band_and_reconnect('2.4'))['success'])
        self.daemon._run_cmd.assert_any_call([
            'nmcli', 'connection', 'modify', 'uuid', 'profile-uuid',
            '802-11-wireless.band', ''
        ])

    def test_wrong_band_retries_with_temporary_profile_constraint(self):
        self.daemon.get_capabilities = Mock(side_effect=[
            capabilities(), capabilities(), capabilities(2412)
        ])
        self.daemon._run_cmd.side_effect = [
            (0, 'profile-uuid', ''),
            (0, r'Home\:WiFi:aa\:bb\:cc\:dd\:ee\:01:2412 MHz:90', ''),
            (0, '', ''), (0, '', ''), (0, '', ''), (0, '', ''), (0, '', ''),
        ]
        self.assertTrue(json.loads(self.daemon.switch_band_and_reconnect('2.4'))['success'])
        self.daemon._run_cmd.assert_any_call([
            'nmcli', 'connection', 'modify', 'uuid', 'profile-uuid',
            '802-11-wireless.band', 'bg'
        ])
        self.daemon._run_cmd.assert_any_call([
            'nmcli', 'connection', 'modify', 'uuid', 'profile-uuid',
            '802-11-wireless.band', ''
        ])

    def test_profile_constraint_restore_failure_is_reported(self):
        self.daemon.get_capabilities = Mock(side_effect=[
            capabilities(), capabilities(), capabilities(2412)
        ])
        self.daemon._run_cmd.side_effect = [
            (0, 'profile-uuid', ''),
            (0, r'Home\:WiFi:aa\:bb\:cc\:dd\:ee\:01:2412 MHz:90', ''),
            (0, '', ''), (0, '', ''), (0, '', ''), (0, '', ''),
            (1, '', 'Could not restore saved band'),
        ]
        result = json.loads(self.daemon.switch_band_and_reconnect('2.4'))
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Could not restore saved band')

    def test_scan_error_is_reported_without_activation(self):
        self.daemon.get_capabilities = Mock(return_value=capabilities())
        self.daemon._run_cmd.side_effect = [(0, 'profile-uuid', ''), (1, '', 'Scan failed')]
        result = json.loads(self.daemon.switch_band_and_reconnect('2.4'))
        self.assertEqual(result['error'], 'Scan failed')
        self.assertEqual(self.daemon._run_cmd.call_count, 2)

    def test_status_reports_runtime_band_after_fallback(self):
        self.daemon.cached_clients = []
        self.daemon._owned_create_ap_pid = Mock(return_value=123)
        self.daemon._read_config_dict.return_value['FREQ_BAND'] = '5'
        self.daemon._run_cmd.side_effect = [
            (0, '123 wlo2 (ap0)', ''), (0, 'channel 6 (2437 MHz), width: 20 MHz', '')
        ]
        self.assertEqual(self.daemon._get_status_dict()['band'], '2.4')

    def start_setup(self, caps):
        self.daemon.get_capabilities = Mock(return_value=caps)
        self.daemon._get_status_dict = Mock(side_effect=[{'active': False}, {'active': True, 'iface': 'ap0'}])
        self.daemon.switch_band_and_reconnect = Mock(return_value=json.dumps({'success': False, 'error': 'No target'}))

    def test_blocked_5ghz_triggers_fallback_even_with_other_5ghz_channels(self):
        self.start_setup(capabilities())
        result = json.loads(self.daemon.method_start())
        self.assertEqual(result['error'], 'No target')
        self.daemon.switch_band_and_reconnect.assert_called_once_with('2.4')
        self.daemon.prepare_firewall.assert_not_called()
        self.assertFalse(self.daemon.is_starting)

    def test_successful_fallback_starts_on_verified_channel(self):
        self.start_setup(capabilities())
        self.daemon.get_capabilities.side_effect = [capabilities(), capabilities(2437), capabilities(2437)]
        self.daemon.switch_band_and_reconnect.return_value = json.dumps({'success': True})
        with patch.object(module.GLib, 'usleep'), patch.object(module, 'get_config_path', return_value='/config'):
            self.assertTrue(json.loads(self.daemon.method_start())['success'])
        cmd = self.daemon._run_cmd.call_args.args[0]
        self.assertEqual(cmd[-4:], ['--freq-band', '2.4', '-c', '6'])

    def test_permitted_5ghz_stays_connected(self):
        self.start_setup(capabilities(5745))
        with patch.object(module.GLib, 'usleep'), patch.object(module, 'get_config_path', return_value='/config'):
            self.assertTrue(json.loads(self.daemon.method_start())['success'])
        self.daemon.switch_band_and_reconnect.assert_not_called()
        self.assertEqual(self.daemon._run_cmd.call_args.args[0][-4:], ['--freq-band', '5', '-c', '149'])

    def test_unsupported_concurrency_stops_before_switch(self):
        caps = capabilities()
        caps['ap_sta_concurrent'] = False
        self.start_setup(caps)
        self.assertFalse(json.loads(self.daemon.method_start())['success'])
        self.daemon.switch_band_and_reconnect.assert_not_called()
        self.daemon.prepare_firewall.assert_not_called()

    def test_upstream_loss_cancels_hotspot(self):
        self.start_setup(capabilities(5745))
        lost = capabilities(5745)
        lost['current_sta_ssid'] = ''
        self.daemon.get_capabilities.side_effect = [capabilities(5745), lost]
        self.daemon.method_stop = Mock()
        with patch.object(module.GLib, 'usleep'), patch.object(module, 'get_config_path', return_value='/config'):
            result = json.loads(self.daemon.method_start())
        self.assertFalse(result['success'])
        self.daemon.method_stop.assert_called_once()

    def test_physical_interface_cannot_count_as_concurrent_hotspot(self):
        self.start_setup(capabilities(5745))
        self.daemon._get_status_dict.side_effect = [{'active': False}, {'active': True, 'iface': 'wlo2'}]
        self.daemon.method_stop = Mock()
        with patch.object(module.GLib, 'usleep'), patch.object(module, 'get_config_path', return_value='/config'):
            self.assertFalse(json.loads(self.daemon.method_start())['success'])
        self.daemon.method_stop.assert_called_once()

    def test_explicit_2ghz_requests_switch_from_permitted_5ghz(self):
        self.start_setup(capabilities(5745))
        self.daemon._read_config_dict.return_value['FREQ_BAND'] = '2.4'
        self.assertFalse(json.loads(self.daemon.method_start())['success'])
        self.daemon.switch_band_and_reconnect.assert_called_once_with('2.4')

    def test_invalid_dedicated_channel_is_rejected(self):
        caps = capabilities()
        caps['current_sta_ssid'] = ''
        self.start_setup(caps)
        self.daemon._read_config_dict.return_value.update(INTERNET_IFACE='eth0', CHANNEL='36')
        self.assertFalse(json.loads(self.daemon.method_start())['success'])
        self.daemon.prepare_firewall.assert_not_called()

    def test_dedicated_ap_auto_uses_permitted_channel(self):
        caps = capabilities()
        caps['current_sta_ssid'] = ''
        self.start_setup(caps)
        self.daemon._read_config_dict.return_value['INTERNET_IFACE'] = 'eth0'
        with patch.object(module.GLib, 'usleep'), patch.object(module, 'get_config_path', return_value='/config'):
            self.assertTrue(json.loads(self.daemon.method_start())['success'])
        self.assertEqual(self.daemon._run_cmd.call_args.args[0][-4:], ['--freq-band', '5', '-c', '149'])


if __name__ == '__main__':
    unittest.main()
