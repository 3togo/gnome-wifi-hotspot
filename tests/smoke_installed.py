#!/usr/bin/env python3
"""Read-only checks of an installed Relay; never activate or mutate services."""
import json
from pathlib import Path
import subprocess
import unittest

import gi
from gi.repository import Gio, GLib

BUS = 'io.github.erhanzeyrek.WifiHotspot'


class InstalledSmokeTests(unittest.TestCase):
    def test_installed_payload(self):
        root = Path('/usr/libexec/wifi-hotspot-daemon')
        if not root.exists():
            self.skipTest('Relay is not installed')
        for name in ['wifi-hotspot-daemon.py', 'configuration.py', 'nm_client.py', 'create_ap']:
            self.assertTrue((root / name).is_file(), name)
        self.assertTrue(Path('/usr/bin/wifi-hotspot-settings').is_file())

    def test_running_daemon_status(self):
        try:
            connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            owned = connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'NameHasOwner', GLib.Variant('(s)', (BUS,)),
                GLib.VariantType.new('(b)'), Gio.DBusCallFlags.NO_AUTO_START, 3000, None).unpack()[0]
        except GLib.Error as error:
            self.skipTest(f'System bus unavailable: {error.domain}')
        if not owned:
            self.skipTest('Relay daemon is not running; smoke never activates it')
        response = connection.call_sync(BUS, '/io/github/erhanzeyrek/WifiHotspot', BUS,
            'GetStatus', None, GLib.VariantType.new('(s)'), Gio.DBusCallFlags.NO_AUTO_START,
            5000, None).unpack()[0]
        status = json.loads(response)
        self.assertIsInstance(status, dict)
        self.assertIs(type(status.get('active')), bool)

    def test_service_definition(self):
        if not Path('/run/systemd/system').is_dir():
            self.skipTest('systemd is unavailable')
        result = subprocess.run(['systemctl', 'show', 'wifi-hotspot-daemon.service',
            '--property=LoadState', '--value'], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        if result.stdout.strip() == 'not-found':
            self.skipTest('Relay service is not installed')
        self.assertEqual(result.stdout.strip(), 'loaded')


if __name__ == '__main__':
    unittest.main(verbosity=2)
