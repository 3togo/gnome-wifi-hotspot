"""Check actual .deb ownership, dependencies, and isolated launcher imports."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='relay-deb-test-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.output = Path(cls.directory.name)
        cls.version = '1.0.0-16+test'
        environment = dict(os.environ, WIFI_RELAY_BUILD_OUTPUT=str(cls.output), SOURCE_DATE_EPOCH="4102444800")
        subprocess.run(['bash', str(ROOT / 'packaging/build-deb.sh'), cls.version],
                       env=environment, capture_output=True, text=True, check=True)
        cls.roots = {}
        cls.depends = {}
        for suffix in ['', '-gnome', '-tray']:
            name = 'gnome-wifi-hotspot' + suffix
            deb = cls.output / f'{name}_{cls.version}_all.deb'
            root = cls.output / name
            subprocess.run(['dpkg-deb', '-x', str(deb), str(root)], check=True)
            cls.roots[suffix] = root
            cls.depends[suffix] = subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Depends'], text=True)

    def test_packages_are_reproducible_even_with_a_future_source_epoch(self):
        with tempfile.TemporaryDirectory(prefix='relay-repro-test-') as directory:
            environment = dict(os.environ, WIFI_RELAY_BUILD_OUTPUT=directory,
                               SOURCE_DATE_EPOCH='4102444800')
            subprocess.run(['bash', str(ROOT / 'packaging/build-deb.sh'), self.version],
                           env=environment, capture_output=True, text=True, check=True)
            for original in self.output.glob('*.deb'):
                self.assertEqual(original.read_bytes(), (Path(directory) / original.name).read_bytes())

    def test_optional_files_have_single_owners(self):
        ownership = {}
        for suffix, root in self.roots.items():
            for path in root.rglob('*'):
                if path.is_file() or path.is_symlink():
                    name = str(path.relative_to(root))
                    self.assertNotIn(name, ownership, f'{name} shared by {suffix} and {ownership.get(name)}')
                    ownership[name] = suffix
        self.assertEqual(ownership['usr/share/wifi-hotspot/settings/tray.py'], '-tray')
        self.assertEqual(ownership['usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io/metadata.json'], '-gnome')
        self.assertFalse((self.roots[''] / 'etc/xdg/autostart').exists())

    def test_core_does_not_require_desktop_integrations(self):
        self.assertNotIn('ayatana', self.depends[''])
        self.assertNotIn('gtk-3', self.depends[''])
        self.assertNotIn('gnome-shell', self.depends[''])
        for suffix in ['-gnome', '-tray']:
            self.assertIn(f'gnome-wifi-hotspot (= {self.version})', self.depends[suffix])
        self.assertIn('gnome-shell', self.depends['-gnome'])
        self.assertIn('ayatana', self.depends['-tray'])

    def test_standalone_launchers_import_outside_source_tree(self):
        root = self.roots['']
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        for name in ['wifi-hotspot-settings', 'wifi-relay-nm-probe']:
            result = subprocess.run(['python3', str(root / 'usr/bin' / name), '--help'],
                                    cwd=self.output, env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('usage:', result.stdout)
        self.assertTrue((root / 'usr/libexec/wifi-hotspot-daemon/nm_client.py').is_file())
