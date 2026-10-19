"""A slow backend cannot block the main context or starve an authorized Stop."""
import json
import sys
import threading
import tempfile
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch

from gi.repository import GLib
from daemon.operations import Operations
from test_band_fallback import Daemon, module


def wait_until(predicate):
    context = GLib.MainContext.default()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('Asynchronous operation did not complete')


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.operations = Operations()
        self.addCleanup(self.operations.close)

    def test_stop_cancels_start_while_status_and_main_context_remain_responsive(self):
        daemon = Daemon.__new__(Daemon)
        daemon._operations = self.operations
        daemon._status_snapshot = {'active': False}
        daemon.connection = Mock()
        daemon.cached_status_active = False
        daemon.cached_clients = []
        daemon._get_status_dict = lambda: {'active': False}
        started = threading.Event()
        cleanup_entered = threading.Event()
        cleanup_allowed = threading.Event()
        self.addCleanup(cleanup_allowed.set)

        def start():
            started.set()
            if not self.operations.cancelled.wait(2):
                raise AssertionError('Stop did not cancel the pending Start')
            return json.dumps({'success': False, 'error': 'cancelled'})

        def stop():
            cleanup_entered.set()
            if not cleanup_allowed.wait(2):
                raise AssertionError('Test did not permit cleanup')
            return True

        daemon.method_start = start
        daemon.method_stop = stop
        start_reply, stop_reply, status_reply = Mock(), Mock(), Mock()
        daemon._dispatch_method_call('Start', None, start_reply)
        wait_until(started.is_set)
        heartbeat = Mock(return_value=GLib.SOURCE_REMOVE)
        GLib.idle_add(heartbeat)
        wait_until(lambda: heartbeat.called)
        daemon._dispatch_method_call('Stop', None, stop_reply)
        wait_until(cleanup_entered.is_set)
        stop_reply.return_value.assert_not_called()
        daemon._dispatch_method_call('GetStatus', None, status_reply)
        status = json.loads(status_reply.return_value.call_args.args[0].unpack()[0])
        self.assertEqual(status['state'], 'stopping')
        cleanup_allowed.set()
        wait_until(lambda: stop_reply.return_value.called and not self.operations.busy)
        self.assertEqual(stop_reply.return_value.call_args.args[0].unpack(), (True,))

    def test_backend_access_is_serialized_and_busy_writes_are_rejected(self):
        running = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)
        completed = Mock()
        self.assertTrue(self.operations.submit(lambda: (running.set(), release.wait(2)), completed))
        wait_until(running.is_set)
        self.assertFalse(self.operations.submit(Mock(), Mock()))
        release.set()
        wait_until(lambda: not self.operations.busy)
        completed.assert_called_once()

    def test_worker_exception_is_reported_and_next_operation_still_runs(self):
        finished = Mock()
        self.operations.submit(lambda: 1 / 0, finished)
        wait_until(lambda: not self.operations.busy)
        self.assertIsInstance(finished.call_args.args[1], ZeroDivisionError)
        next_reply = Mock()
        self.operations.submit(lambda: True, next_reply)
        wait_until(lambda: not self.operations.busy)
        next_reply.assert_called_once_with(True, None)

    def test_cancellation_terminates_a_pending_command(self):
        daemon = Daemon.__new__(Daemon)
        daemon._operations = self.operations
        daemon._stopping = False
        timer = threading.Timer(.1, self.operations.cancelled.set)
        timer.start()
        self.addCleanup(timer.join)
        started = time.monotonic()
        code, _output, error = daemon._run_cmd([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.assertEqual(code, -1)
        self.assertIn('cancelled', error)
        self.assertLess(time.monotonic() - started, 2)

    def test_stop_owns_starting_shell_before_pid_or_running_instance_is_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / 'create_ap.py'
            pidfile = root / 'create-ap.pid'
            started = root / 'started'
            script.write_text('import os, pathlib, time\n'
                              'assert os.environ["RUNNING_AS_DAEMON"] == "1"\n'
                              f'pathlib.Path({str(started)!r}).touch()\n'
                              'time.sleep(30)\n')
            daemon = Daemon.__new__(Daemon)
            daemon.create_ap_bin = str(script)
            daemon._operations = self.operations
            daemon._stopping = False
            daemon._get_status_dict = Mock(return_value={'active': False})
            daemon._recover_legacy = Mock()
            daemon._read_config_dict = Mock(return_value={'BACKEND': 'create_ap'})
            daemon._emit_signal = Mock()
            daemon.cached_clients = []
            with patch.object(module, 'CREATE_AP_PIDFILE', pidfile):
                daemon._launch_create_ap([sys.executable, str(script), '--pidfile', str(pidfile)], root / 'log')
                child = daemon._legacy_process
                try:
                    wait_until(started.exists)
                    self.assertFalse(pidfile.exists())
                    self.assertEqual(daemon._owned_create_ap_pid(), child.pid)
                    begin = time.monotonic()
                    self.assertTrue(daemon.method_stop())
                    self.assertLess(time.monotonic() - begin, 2)
                    self.assertIsNotNone(child.poll())
                    daemon._recover_legacy.assert_called_once()
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.wait(timeout=3)

    def test_stop_does_not_signal_a_process_whose_identity_changed(self):
        daemon = Daemon.__new__(Daemon)
        daemon._owned_create_ap_pid = Mock(return_value=123)
        with (patch.object(module.legacy_runtime, 'process_identity', return_value={'pid': 123}),
              patch.object(module.legacy_runtime, 'same_process', return_value=False),
              patch.object(module.os, 'pidfd_open', return_value=9),
              patch.object(module.os, 'close') as close,
              patch.object(module.signal, 'pidfd_send_signal') as send):
            daemon._signal_create_ap_stop(123)
        send.assert_not_called()
        close.assert_called_once_with(9)

    def test_stop_precedes_deferred_reads_and_saves(self):
        release = threading.Event()
        self.addCleanup(release.set)
        order = []
        self.operations.submit(lambda: release.wait(2), lambda *_: None)
        self.operations.submit(lambda: order.append('read'), lambda *_: None, defer=True)
        self.operations.submit(lambda: order.append('stop'), lambda *_: None, urgent=True, cancel=True)
        release.set()
        wait_until(lambda: not self.operations.busy)
        self.assertEqual(order, ['stop', 'read'])

    def test_name_loss_preserves_failure_exit_for_systemd_restart(self):
        daemon = Mock()
        loop = Mock()
        with patch.object(module, '_daemon_instance', daemon), patch.object(module, '_main_loop', loop), \
                patch.object(module, '_exit_status', 0):
            module.on_name_lost(None, 'test')
            self.assertEqual(module._exit_status, 1)
            daemon.request_shutdown.assert_called_once_with(loop.quit)
