"""Validation evidence must distinguish failures and track the tested worktree."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('relay_validation', Path(__file__).resolve().parents[1] / 'tools/validate.py')
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


class ValidationReportTests(unittest.TestCase):
    def test_failed_command_keeps_exit_code_and_log(self):
        with tempfile.TemporaryDirectory() as directory:
            result = validation.run_check('failed', [sys.executable, '-c',
                'import sys; print("failure evidence"); sys.exit(7)'], Path(directory), 5)
            self.assertEqual(result['status'], 'fail')
            self.assertEqual(result['exit_code'], 7)
            self.assertIn('failure evidence', (Path(directory) / result['log']).read_text())

    def test_timeout_is_a_failure_and_missing_tool_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            result = validation.run_check('timeout', [sys.executable, '-c',
                'import time; time.sleep(10)'], Path(directory), 0.1)
            self.assertEqual(result['status'], 'fail')
            self.assertIn('Timed out', result['reason'])
            result = validation.run_check('missing', [str(Path(directory) / 'missing-tool')], Path(directory), 1)
            self.assertEqual(result['status'], 'blocked')

    def test_manifest_tracks_edits_untracked_files_modes_and_removals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / '.gitignore').write_text('dist/\n')
            tracked = root / 'app.py'
            tracked.write_text('original')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                            'commit', '-qm', 'fixture'], check=True)
            output = root / 'dist/validation'
            output.mkdir(parents=True)
            with patch.object(validation, 'ROOT', root):
                original = validation.source_manifest(output)
                (output / 'report.json').write_text('{}')
                self.assertEqual(validation.source_manifest(output)['sha256'], original['sha256'])
                tracked.write_text('edited')
                edited = validation.source_manifest(output)
                self.assertNotEqual(edited['sha256'], original['sha256'])
                tracked.chmod(0o755)
                self.assertNotEqual(validation.source_manifest(output)['sha256'], edited['sha256'])
                (root / 'new-test.py').write_text('new regression')
                self.assertIn('new-test.py', [item['path'] for item in validation.source_manifest(output)['files']])
                tracked.unlink()
                missing = next(item for item in validation.source_manifest(output)['files'] if item['path'] == 'app.py')
                self.assertTrue(missing['missing'])
