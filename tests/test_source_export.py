"""Release source exports must retain packaging templates without Git metadata."""
import importlib.util
import contextlib
import io
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('relay_source_builder', ROOT / 'packaging/build-source.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class SourceExportTests(unittest.TestCase):
    def test_source_package_builds_all_four_packages_with_bundle_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'packaging', root / 'packaging')
            with patch.object(builder, 'ROOT', root), patch('sys.argv', ['build-source.py']), \
                    contextlib.redirect_stdout(io.StringIO()):
                builder.main()
            archive = next((root / 'dist').glob('*.debian.tar.xz'))
            with tarfile.open(archive) as source:
                def read(name):
                    return source.extractfile('debian/' + name).read().decode()
                control = read('control')
                for suffix in ('', '-gnome', '-tray', '-bundle'):
                    self.assertIn('Package: gnome-wifi-hotspot' + suffix + '\n', control)
                self.assertIn('gnome-wifi-hotspot-bundle; do', read('rules'))
                self.assertIn('configuration.py', read('gnome-wifi-hotspot-bundle.postinst'))
                self.assertIn('start-tray-sessions.py', read('gnome-wifi-hotspot-bundle.postinst'))
                self.assertIn('start-tray-sessions.py --stop', read('gnome-wifi-hotspot-bundle.prerm'))
                self.assertIn('wifi-hotspot-autostart.desktop', read('gnome-wifi-hotspot-bundle.maintscript'))

    def test_export_retains_nested_debian_templates_and_excludes_generated_root_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            included = ['packaging/debian/control', 'packaging/debian/postinst',
                        'packaging/source-debian/rules', 'daemon/configuration.py', 'docs/releases/candidate.md']
            excluded = ['debian/control', 'dist/package.deb', 'settings/__pycache__/cached.pyc']
            for name in included + excluded:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            with patch.object(builder, 'ROOT', root):
                self.assertEqual(builder.source_files(), sorted(included))
