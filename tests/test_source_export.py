"""Release source exports must retain packaging templates without Git metadata."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('relay_source_builder', ROOT / 'packaging/build-source.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class SourceExportTests(unittest.TestCase):
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
