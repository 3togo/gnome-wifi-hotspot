"""First-install secret initialization never changes existing or linked config."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from daemon.configuration import detect_wifi_interface, initialize_factory_password


class FactoryPasswordTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'config'
        self.factory = Path(self.directory.name) / 'factory'
        self.original = 'SSID=Hotspot\nPASSPHRASE=12345678\n'
        self.factory.write_text(self.original)
        self.path.write_text(self.original)

    def test_fresh_install_gets_private_random_password_only_once(self):
        self.assertTrue(initialize_factory_password(self.path, self.factory))
        saved = self.path.read_text()
        self.assertRegex(saved, r'^SSID=Hotspot\nPASSPHRASE=[0-9a-f]{32}\n$')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(initialize_factory_password(self.path, self.factory))
        self.assertEqual(self.path.read_text(), saved)

    def test_make_install_can_keep_its_hostname_ssid(self):
        initialize_factory_password(self.path, self.factory, 'Workstation-Hotspot')
        self.assertTrue(self.path.read_text().startswith('SSID=Workstation-Hotspot\n'))

    def test_fresh_install_uses_the_only_wifi_interface(self):
        self.original = 'WIFI_IFACE=wlan0\nINTERNET_IFACE=wlan0\n' + self.original
        self.factory.write_text(self.original)
        self.path.write_text(self.original)
        initialize_factory_password(self.path, self.factory, wifi_interface='wlp4s0')
        saved = self.path.read_text()
        self.assertIn('WIFI_IFACE=wlp4s0\n', saved)
        self.assertIn('INTERNET_IFACE=wlp4s0\n', saved)

    def test_detection_requires_exactly_one_wifi_interface(self):
        net = Path(self.directory.name) / 'net'
        net.mkdir()
        (net / 'wlp4s0' / 'wireless').mkdir(parents=True)
        self.assertEqual(detect_wifi_interface(net), 'wlp4s0')
        (net / 'wlp5s0' / 'phy80211').mkdir(parents=True)
        self.assertIsNone(detect_wifi_interface(net))

    def test_customized_configuration_and_symlink_are_preserved(self):
        self.path.write_text('SSID=Mine\nPASSPHRASE=custom-secret\n')
        self.assertFalse(initialize_factory_password(self.path, self.factory))
        self.path.unlink()
        self.path.symlink_to(self.factory)
        self.assertFalse(initialize_factory_password(self.path, self.factory))
        self.assertEqual(self.factory.read_text(), self.original)

    def test_atomic_write_failure_preserves_factory_config(self):
        with patch('os.replace', side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):
                initialize_factory_password(self.path, self.factory)
        self.assertEqual(self.path.read_text(), self.original)
        self.assertEqual(set(Path(self.directory.name).iterdir()), {self.path, self.factory})
