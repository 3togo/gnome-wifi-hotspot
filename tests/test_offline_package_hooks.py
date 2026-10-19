"""Chrootless dpkg hooks may initialize target credentials, never host services."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OfflineHookTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / 'image'
        self.root.mkdir()
        self.bin = Path(self.directory.name) / 'bin'
        self.bin.mkdir()
        for name in ('systemctl', 'deb-systemd-helper', 'deb-systemd-invoke', 'runuser', 'dpkg-query'):
            script = self.bin / name
            script.write_text('#!/bin/sh\necho "unexpected host operation" >&2\nexit 99\n')
            script.chmod(0o755)
        helper = self.bin / 'dpkg-maintscript-helper'
        helper.write_text('#!/bin/sh\nexit 0\n')
        helper.chmod(0o755)
        for name, source in (
                ('usr/libexec/wifi-hotspot-daemon/configuration.py', 'daemon/configuration.py'),
                ('usr/share/wifi-hotspot/default.conf', 'data/wifi-hotspot.conf'),
                ('etc/wifi-hotspot.conf', 'data/wifi-hotspot.conf')):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, target)

    def hook(self, name, *arguments):
        return subprocess.run(['sh', str(ROOT / 'packaging/debian' / name), *arguments],
                              env=dict(os.environ, DPKG_ROOT=str(self.root),
                                       PATH=str(self.bin) + ':/usr/bin:/bin'),
                              capture_output=True, text=True, check=True)

    def test_fresh_image_receives_unique_credentials_without_host_adapter_detection(self):
        result = self.hook('postinst', 'configure')
        self.assertEqual(result.stderr, '')
        config = (self.root / 'etc/wifi-hotspot.conf').read_text()
        self.assertNotIn('PASSPHRASE=12345678\n', config)
        self.assertIn('WIFI_IFACE=wlan0\n', config)
        self.assertEqual((self.root / 'etc/wifi-hotspot.conf').stat().st_mode & 0o777, 0o600)

    def test_upgrade_preserves_target_configuration(self):
        config = self.root / 'etc/wifi-hotspot.conf'
        original = config.read_bytes()
        self.hook('postinst', 'configure', '1.0.0-30')
        self.assertEqual(config.read_bytes(), original)
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_remove_and_purge_do_not_manage_host_services(self):
        for name, action in [('prerm', 'remove'), ('prerm', 'deconfigure'),
                             ('postrm', 'remove'), ('postrm', 'purge')]:
            with self.subTest(name=name, action=action):
                result = self.hook(name, action)
                self.assertEqual(result.stderr, '')
