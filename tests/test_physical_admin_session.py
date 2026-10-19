"""Administrator reuse and restoration, exercised without sudo or host changes."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import physical_admin_session as admin


class AdminSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.bench = Path(self.directory.name)
        self.events = []
        self.write('trial.py', "from pathlib import Path\nPath('trial-ran').touch()\n")
        self.write('cleanup.py', "from pathlib import Path\nPath('restored').touch()\n")

    def write(self, name, source):
        (self.bench / name).write_text(source)

    def session(self, commands, seconds=10):
        admin.session(self.bench, {'trial.py'}, 'cleanup.py', os.getuid(),
                      time.monotonic() + seconds, commands, self.events.append)

    def test_rebuilt_trial_reuses_the_session_after_failure(self):
        self.write('trial.py', 'raise SystemExit(7)\n')
        def commands():
            yield json.dumps({'script': 'trial.py'})
            self.assertTrue((self.bench / 'restored').exists())
            self.write('trial.py', "from pathlib import Path\nPath('retry-ran').touch()\n")
            yield json.dumps({'script': 'trial.py'})
            yield json.dumps({'finish': True})
        self.session(commands())
        results = [event['returncode'] for event in self.events if event['event'] == 'result']
        self.assertEqual(results, [7, 0])
        self.assertTrue((self.bench / 'retry-ran').exists())
        self.assertTrue((self.bench / 'restored').exists())
        self.assertEqual(sum(event['event'] == 'cleanup' for event in self.events), 2)

    def test_only_one_authentication_launch_for_all_prepared_jobs(self):
        class Launched(Exception):
            pass
        with patch.object(admin.os, 'execv', side_effect=Launched) as launch:
            with self.assertRaises(Launched):
                admin.main(['--bench', str(self.bench), '--allow', 'trial.py',
                            '--allow', 'cleanup.py', '--cleanup', 'cleanup.py'])
        launch.assert_called_once()
        executable, command = launch.call_args.args
        self.assertEqual(executable, '/usr/bin/pkexec')
        self.assertIn('--worker', command)
        self.assertEqual(command.count('/usr/bin/pkexec'), 1)

    def test_timeout_terminates_job_and_still_restores_state(self):
        self.write('trial.py', 'import time\ntime.sleep(30)\n')
        begin = time.monotonic()
        def commands():
            yield json.dumps({'script': 'trial.py', 'timeout': .15})
            self.assertTrue((self.bench / 'restored').exists())
        self.session(commands())
        self.assertLess(time.monotonic() - begin, 3)
        self.assertEqual(self.events[1]['returncode'], 124)
        self.assertTrue((self.bench / 'restored').exists())

    def test_unapproved_scripts_and_invalid_timeouts_are_rejected(self):
        self.session([json.dumps(request) for request in [
            {'script': '../trial.py'}, {'script': 'cleanup.py'},
            {'script': 'trial.py', 'timeout': -1},
            {'script': 'trial.py', 'timeout': float('nan')},
            {'script': 'trial.py', 'command': 'anything'},
        ]])
        self.assertEqual(sum(e['event'] == 'rejected' for e in self.events), 5)
        self.assertFalse((self.bench / 'trial-ran').exists())
        self.assertTrue((self.bench / 'restored').exists())

    def test_script_replaced_with_symlink_is_refused(self):
        path = self.bench / 'trial.py'
        path.unlink()
        path.symlink_to(self.bench / 'cleanup.py')
        self.session([json.dumps({'script': 'trial.py'})])
        self.assertEqual(self.events[1]['event'], 'rejected')
        self.assertTrue((self.bench / 'restored').exists())

    def test_deadline_and_input_close_both_restore_without_running_a_job(self):
        for commands, seconds in [([], 10), ([json.dumps({'script': 'trial.py'})], -1)]:
            with self.subTest(seconds=seconds):
                self.session(commands, seconds)
                self.assertTrue((self.bench / 'restored').exists())
                self.assertFalse((self.bench / 'trial-ran').exists())

    def test_interruption_runs_cleanup_and_reports_cleanup_failure(self):
        def interrupted():
            raise KeyboardInterrupt
            yield
        with self.assertRaises(KeyboardInterrupt):
            self.session(interrupted())
        self.assertTrue((self.bench / 'restored').exists())
        self.write('cleanup.py', 'raise SystemExit(2)\n')
        with self.assertRaisesRegex(RuntimeError, 'restoration failed'):
            self.session([])
        self.assertEqual(self.events[-1], {'event': 'cleanup', 'returncode': 2})

    def test_buffered_requests_are_consumed_without_waiting_for_another_write(self):
        reader, writer = os.pipe()
        self.addCleanup(os.close, writer)
        with os.fdopen(reader, 'rb', buffering=0) as stream:
            os.write(writer, b'{"script":"trial.py"}\n{"finish":true}\n')
            incoming = admin.requests(stream, time.monotonic() + 1)
            self.assertEqual(json.loads(next(incoming)), {'script': 'trial.py'})
            self.assertEqual(json.loads(next(incoming)), {'finish': True})
