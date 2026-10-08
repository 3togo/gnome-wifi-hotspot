import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from settings.preferences import get_boolean, set_boolean, read_preferences, MAX_PREFERENCE_BYTES
from settings.lifecycle import CodeRevision


class PreferenceTests(unittest.TestCase):
    def test_writes_are_private_and_preserve_unrelated_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tray.json'
            path.write_text('{"other":"keep"}')
            set_boolean(path, 'visible', False)
            self.assertFalse(get_boolean(path, 'visible'))
            self.assertEqual(read_preferences(path)['other'], 'keep')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_failed_replace_keeps_original_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tray.json'
            path.write_text('{"visible":true}')
            with patch('settings.preferences.os.replace', side_effect=OSError('Disk error')):
                with self.assertRaises(OSError):
                    set_boolean(path, 'visible', False)
            self.assertTrue(get_boolean(path, 'visible'))
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_oversized_or_nonobject_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tray.json'
            for contents in ['[]', 'x' * (MAX_PREFERENCE_BYTES + 1)]:
                path.write_text(contents)
                self.assertEqual(read_preferences(path), {})

    def test_startup_disk_failure_restores_extension_choices(self):
        from settings.startup import set_auto_start, UUID
        from unittest.mock import Mock
        state = {'enabled-extensions': ['other'], 'disabled-extensions': [UUID]}
        original = {key: list(value) for key, value in state.items()}
        settings = Mock()
        settings.get_strv.side_effect = lambda key: list(state[key])
        def save(key, values):
            state[key] = list(values)
            return True
        settings.set_strv.side_effect = save
        with patch('settings.startup.set_boolean', side_effect=OSError('Disk full')):
            with self.assertRaisesRegex(OSError, 'Disk full'):
                set_auto_start(True, settings, Mock())
        self.assertEqual(state, original)


class CodeRevisionTests(unittest.TestCase):
    def test_changed_module_is_detected_only_after_upgrade_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'first.py', Path(directory) / 'second.py'
            first.write_text('old'); second.write_text('old')
            revision = CodeRevision([first, second])
            self.assertFalse(revision.changed())
            second.unlink(); first.write_text('new code')
            self.assertFalse(revision.changed())
            second.write_text('new')
            self.assertTrue(revision.changed())
