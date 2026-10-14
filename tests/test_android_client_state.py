"""Regression fixtures for cached Android associations and changing DHCP leases."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('client_state', Path(__file__).resolve().parents[1] / 'tools/android/client_state.py')
client_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_state)


class AndroidClientStateTests(unittest.TestCase):
    def setUp(self):
        self.wifi = ('Wifi is enabled\nWifi is connected to WifiInfo{SSID: "Test hotspot", '
                     'BSSID: 02:00:00:00:00:22, Supplicant state: COMPLETED}\n')
        self.addresses = '4: wlan0 inet 192.168.12.8/24 brd 192.168.12.255 scope global wlan0'

    def address(self, wifi=None, addresses=None):
        return client_state.hotspot_ipv4(wifi or self.wifi, addresses or self.addresses,
                                        'Test hotspot', '02:00:00:00:00:22', '192.168.12.0/24')

    def test_current_ap_and_refreshed_lease(self):
        self.assertEqual(self.address(), '192.168.12.8')
        changed = self.addresses.replace('192.168.12.8/', '192.168.12.23/')
        self.assertEqual(self.address(addresses=changed), '192.168.12.23')

    def test_same_ssid_on_previous_bssid_is_not_current(self):
        self.assertIsNone(self.address(wifi=self.wifi.replace('00:22', '00:11')))

    def test_disconnected_snapshot_with_cached_wifi_info_is_not_ready(self):
        wifi = self.wifi.replace('Wifi is connected to', 'Wifi is disconnected; last connection:')
        self.assertIsNone(self.address(wifi=wifi))

    def test_upstream_network_address_is_not_a_hotspot_lease(self):
        self.assertIsNone(self.address(addresses=self.addresses.replace('192.168.12.8/', '192.168.1.8/')))

    def test_ambiguous_addresses_are_not_silently_chosen(self):
        self.assertIsNone(self.address(addresses=self.addresses + '\ninet 192.168.12.23/24'))

    def test_malformed_snapshot_does_not_produce_a_client_address(self):
        self.assertIsNone(self.address(addresses='inet 192.999.12.8/24'))
