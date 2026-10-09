"""Failure contracts for the service worker; all subprocesses and network I/O are fake."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_nm_backend import module, CONFIG, PROFILE


class WorkerFailureTests(unittest.TestCase):
    def setUp(self):
        self.recovery = patch.object(module, 'recover').start()
        patch.object(module.probe, 'upstream_snapshot', return_value=(PROFILE, 'ssid', 'bssid', 2467)).start()
        self.addCleanup(patch.stopall)
        self.backend = module.Backend()
        reader, self.writer = os.pipe()
        self.stream = os.fdopen(reader, 'rb')
        os.set_blocking(reader, False)
        self.addCleanup(self.stream.close)
        self.addCleanup(os.close, self.writer)
        self.process = Mock(stdout=self.stream, returncode=0)
        self.process.poll.return_value = None

    def send(self, value):
        os.write(self.writer, value if isinstance(value, bytes) else json.dumps(value).encode() + b'\n')

    def test_automatic_start_is_nonblocking_and_pins_worker_profile(self):
        self.backend._desired_config = dict(CONFIG)
        self.backend._upstream_uuid = PROFILE
        with patch.object(module.subprocess, 'Popen', return_value=self.process), \
                patch.object(module.time, 'monotonic', return_value=0), \
                patch.object(module.select, 'select') as select:
            status = self.backend.start(CONFIG, automatic=True)
        self.assertTrue(status['desired_active'])
        self.assertEqual(status['state'], 'connecting')
        self.assertFalse(status['active'])
        payload = json.loads(self.process.stdin.write.call_args.args[0])
        self.assertEqual(payload['EXPECTED_UPSTREAM_UUID'], PROFILE)
        self.process.wait.assert_not_called()
        select.assert_not_called()

    def test_automatic_start_timeout_terminates_then_escalates_and_recovers(self):
        self.backend._desired_config = dict(CONFIG)
        self.backend._upstream_uuid = PROFILE
        with patch.object(module.subprocess, 'Popen', return_value=self.process), \
                patch.object(module.time, 'monotonic', return_value=0):
            self.backend.start(CONFIG, automatic=True)
        with patch.object(module.time, 'monotonic', return_value=54):
            self.backend.get_status()
        self.process.terminate.assert_not_called()
        with patch.object(module.time, 'monotonic', return_value=55):
            status = self.backend.get_status()
        self.assertIn('timed out', status['error'])
        self.assertTrue(status['desired_active'])
        self.process.terminate.assert_called_once()
        with patch.object(module.time, 'monotonic', return_value=95):
            self.backend.get_status()
        self.process.kill.assert_called_once()
        self.process.wait.assert_not_called()
        self.process.poll.return_value = -9
        self.backend.get_status()
        self.assertIsNone(self.backend.process)
        self.assertIsNone(self.backend._activation_deadline)

    def test_successful_automatic_activation_cancels_watchdog(self):
        self.backend._desired_config = dict(CONFIG)
        self.backend._upstream_uuid = PROFILE
        with patch.object(module.subprocess, 'Popen', return_value=self.process), \
                patch.object(module.time, 'monotonic', return_value=0):
            self.backend.start(CONFIG, automatic=True)
        self.send({'event': 'stage', 'stage': 'active', 'interface': 'wrnm123abc'})
        with patch.object(module.time, 'monotonic', return_value=10):
            self.backend.get_status()
        with patch.object(module.time, 'monotonic', return_value=100):
            self.assertTrue(self.backend.get_status()['active'])
        self.process.terminate.assert_not_called()
        self.assertIsNone(self.backend._activation_deadline)

    def test_sleep_shutdown_has_a_kill_deadline_without_losing_intent(self):
        self.backend.process = self.process
        self.backend._desired_config = dict(CONFIG)
        with patch.object(module.time, 'monotonic', return_value=100):
            self.backend.prepare_for_sleep(True)
        self.process.terminate.assert_called_once()
        with patch.object(module.time, 'monotonic', return_value=140):
            status = self.backend.get_status()
        self.process.kill.assert_called_once()
        self.assertTrue(status['desired_active'])
        self.process.wait.assert_not_called()

    def test_spawn_failure_leaves_backend_off(self):
        with patch.object(module.subprocess, 'Popen', side_effect=OSError('No worker binary')):
            with self.assertRaisesRegex(RuntimeError, 'No worker binary'):
                self.backend.start(CONFIG)
        self.assertEqual(self.backend.status['state'], 'off')
        self.assertIsNone(self.backend.process)

    def test_broken_credentials_pipe_reaps_worker_and_recovers(self):
        self.process.stdin.write.side_effect = BrokenPipeError('Worker exited')
        self.process.poll.return_value = 1
        self.process.returncode = 1
        with patch.object(module.subprocess, 'Popen', return_value=self.process):
            with self.assertRaisesRegex(RuntimeError, 'Worker exited'):
                self.backend.start(CONFIG)
        self.process.stdin.close.assert_called_once()
        self.process.wait.assert_called_once()
        self.assertIsNone(self.backend.process)
        self.assertEqual(self.backend.status['state'], 'off')
        self.assertGreaterEqual(self.recovery.call_count, 2)

    def test_start_timeout_terminates_worker(self):
        self.process.poll.side_effect = [None, 0]
        with patch.object(module.subprocess, 'Popen', return_value=self.process), \
                patch.object(module.time, 'monotonic', side_effect=[0, 56]):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                self.backend.start(CONFIG)
        self.process.terminate.assert_called_once()
        self.assertIsNone(self.backend.process)
        self.assertFalse(self.backend.status['active'])

    def test_stop_escalates_only_after_graceful_timeout(self):
        self.backend.process = self.process
        self.process.poll.side_effect = [None, -9]
        self.process.returncode = -9
        self.process.wait.side_effect = [subprocess.TimeoutExpired('worker', 40), None]
        self.assertTrue(self.backend.stop())
        self.process.terminate.assert_called_once()
        self.process.kill.assert_called_once()
        self.assertEqual(self.process.wait.call_args_list[1].kwargs['timeout'], 5)
        self.assertIsNone(self.backend.process)

    def test_worker_crash_is_reported_and_recovers_once(self):
        self.backend.process = self.process
        self.process.poll.return_value = -9
        self.process.returncode = -9
        self.assertIn('unexpectedly', self.backend.get_status()['error'])
        calls = self.recovery.call_count
        self.backend.get_status()
        self.assertEqual(self.recovery.call_count, calls)
        self.assertIsNone(self.backend.process)

    def test_cleanup_error_survives_reaping(self):
        self.backend.process = self.process
        self.send({'event': 'result', 'result': {'cleanup_errors': ['interface survived']}})
        self.process.poll.return_value = 1
        self.process.returncode = 1
        self.assertEqual(self.backend.get_status()['error'], 'interface survived')

    def test_gui_disconnect_cancels_resume_even_with_cleanup_error(self):
        self.backend.process = self.process
        self.backend._desired_config = dict(CONFIG)
        self.backend._upstream_uuid = PROFILE
        self.backend._candidate = ('stable', 0)
        self.send({'event': 'result', 'result': {
            'user_disconnected': True, 'cleanup_errors': ['cleanup retry needed']}})
        self.process.poll.return_value = 0
        with patch.object(self.backend, 'start') as start:
            status = self.backend.poll(CONFIG)
            self.backend.poll(CONFIG)
        self.assertFalse(status['desired_active'])
        self.assertEqual(status['state'], 'off')
        self.assertIsNone(self.backend._upstream_uuid)
        self.assertIsNone(self.backend._candidate)
        start.assert_not_called()

    def test_transient_failure_preserves_resume_intent(self):
        self.backend.process = self.process
        self.backend._desired_config = dict(CONFIG)
        self.backend._upstream_uuid = PROFILE
        self.send({'event': 'result', 'result': {'error': 'Upstream interrupted'}})
        self.process.poll.return_value = 0
        status = self.backend.get_status()
        self.assertTrue(status['desired_active'])
        self.assertEqual(status['state'], 'waiting')
        self.assertEqual(self.backend._upstream_uuid, PROFILE)

    def test_user_disconnect_intent_must_be_boolean(self):
        with self.assertRaisesRegex(ValueError, 'Invalid worker result'):
            self.backend._validate_event({'event': 'result', 'result': {
                'user_disconnected': 'true'}})

    def test_stage_messages_may_be_split_across_pipe_reads(self):
        self.backend.process = self.process
        self.send(b'{"event":"stage","stage":"active",')
        self.assertFalse(self.backend.get_status()['active'])
        self.send(b'"interface":"wrnm123abc","band":"2.4"}\n')
        self.assertTrue(self.backend.get_status()['active'])
        self.assertEqual(self.backend.status['band'], '2.4')

    def test_malformed_worker_output_cannot_escape_get_status(self):
        self.backend.process = self.process
        self.send(b'not-json\n')
        status = self.backend.get_status()
        self.assertFalse(status['active'])
        self.assertIn('Invalid worker event', status['error'])

    def test_native_interface_request_keeps_worker_connecting(self):
        self.backend.process = self.process
        self.send({'event': 'stage', 'stage': 'native-interface-request',
                   'interface': 'wrnm123abc', 'band': '2.4'})
        status = self.backend.get_status()
        self.assertEqual(status['state'], 'connecting')
        self.assertFalse(status['active'])
        self.assertEqual(status['iface'], 'wrnm123abc')
        self.assertEqual(status['band'], '2.4')
        self.assertFalse(status.get('error'))
        self.process.terminate.assert_not_called()
        self.send({'event': 'stage', 'stage': 'active',
                   'interface': 'wrnm123abc', 'band': '2.4'})
        self.assertTrue(self.backend.get_status()['active'])

    def test_worker_event_schema_is_checked(self):
        for event in ([], {}, {'event': 'stage'}, {'event': 'clients', 'authorized_clients': -1},
                      {'event': 'result', 'result': []}, {'event': 'stage', 'stage': 'active', 'interface': 'wlo2'}):
            with self.subTest(event=event):
                self.backend = module.Backend()
                self.backend.process = self.process
                self.send(event)
                self.assertIn('Invalid worker event', self.backend.get_status()['error'])

    def test_worker_error_clears_stale_client_count(self):
        self.backend.process = self.process
        self.backend.status['client_count'] = 3
        self.send({'event': 'error', 'message': 'Upstream disconnected'})
        self.assertEqual(self.backend.get_status()['client_count'], 0)

    def test_cleanup_recovery_failure_is_reported(self):
        self.backend.process = self.process
        self.process.poll.return_value = 1
        self.process.returncode = 1
        self.recovery.side_effect = RuntimeError('Interface identity changed')
        self.assertEqual(self.backend.get_status()['error'], 'Interface identity changed')
        self.assertIsNone(self.backend.process)

    def test_nm_restart_recovery_retries_after_worker_is_reaped(self):
        self.backend.process = self.process
        self.process.poll.return_value = 1
        self.process.returncode = 1
        self.recovery.side_effect = [RuntimeError('NetworkManager is not running'), None]
        self.assertIn('not running', self.backend.get_status()['error'])
        self.assertIsNone(self.backend.process)
        self.assertTrue(self.backend._recovery_pending)
        self.backend.get_status()
        self.assertFalse(self.backend._recovery_pending)
        calls = self.recovery.call_count
        self.backend.get_status()
        self.assertEqual(self.recovery.call_count, calls)

    def test_startup_recovery_retries_without_a_worker(self):
        self.recovery.side_effect = [RuntimeError('NetworkManager is not running'), None]
        backend = module.Backend()
        self.assertTrue(backend._recovery_pending)
        self.assertFalse(backend.get_status()['active'])
        self.assertFalse(backend._recovery_pending)

    def test_stop_recovery_failure_remains_pending_for_polling(self):
        self.recovery.side_effect = [RuntimeError('NetworkManager is not running'), None]
        with self.assertRaisesRegex(RuntimeError, 'not running'):
            self.backend.stop()
        self.assertTrue(self.backend._recovery_pending)
        self.backend.get_status()
        self.assertFalse(self.backend._recovery_pending)

    def test_recovery_retry_never_runs_over_a_live_worker(self):
        self.backend._recovery_pending = True
        self.backend.process = self.process
        calls = self.recovery.call_count
        self.backend.get_status()
        self.assertEqual(self.recovery.call_count, calls)

    def test_failure_result_keeps_primary_error_before_cleanup_detail(self):
        self.backend.process = self.process
        self.send({'event': 'result', 'result': {'error': 'Upstream disconnected', 'cleanup_errors': ['Busy']}})
        self.assertEqual(self.backend.get_status()['error'], 'Upstream disconnected')

    def test_start_cleanup_failure_retains_original_error(self):
        with patch.object(module.subprocess, 'Popen', side_effect=OSError('Spawn failed')), \
                patch.object(self.backend, 'stop', side_effect=RuntimeError('Recovery failed')):
            with self.assertRaisesRegex(RuntimeError, 'Spawn failed; cleanup: Recovery failed'):
                self.backend.start(CONFIG)
        self.assertEqual(self.backend.status['state'], 'off')

    def test_second_start_does_not_spawn_or_recover_over_live_worker(self):
        self.backend.process = self.process
        with patch.object(module.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                self.backend.start(CONFIG)
        spawn.assert_not_called()

    def test_get_status_returns_copy(self):
        result = self.backend.get_status()
        result['active'] = True
        self.assertFalse(self.backend.get_status()['active'])

    def test_oversized_partial_output_is_bounded(self):
        self.backend.process = self.process
        self.backend.buffer = b'x' * 65536
        status = self.backend.get_status()
        self.assertIn('Invalid worker event', status['error'])
        self.assertLess(len(self.backend.buffer), 65536)

    def test_continuous_partial_output_is_rejected_on_first_full_chunk(self):
        self.backend.process = self.process
        with patch.object(module.os, 'read', return_value=b'x' * module.MAX_EVENT_BYTES) as read:
            self.backend.get_status()
        self.assertEqual(read.call_count, 1)
        self.process.terminate.assert_called_once()
        self.assertEqual(self.backend.buffer, b'')

    def test_continuous_valid_output_yields_with_a_bounded_read_budget(self):
        self.backend.process = self.process
        event = b'{"event":"clients","authorized_clients":2}\n'
        with patch.object(module.os, 'read', return_value=event) as read:
            status = self.backend.get_status()
        self.assertEqual(status['client_count'], 2)
        self.assertLessEqual(read.call_count * len(event), module.MAX_DRAIN_BYTES + len(event))
        self.process.terminate.assert_not_called()

    def test_protocol_failure_escalates_without_blocking_and_recovers_after_exit(self):
        self.backend.process = self.process
        self.send(b'not-json\n')
        with patch.object(module.time, 'monotonic', return_value=100):
            self.backend.get_status()
        self.process.terminate.assert_called_once()
        with patch.object(module.time, 'monotonic', return_value=139):
            self.backend.get_status()
        self.process.kill.assert_not_called()
        with patch.object(module.time, 'monotonic', return_value=140):
            self.backend.get_status()
            self.backend.get_status()
        self.process.kill.assert_called_once()
        self.process.wait.assert_not_called()
        self.process.poll.return_value = -9
        self.process.returncode = -9
        calls = self.recovery.call_count
        self.backend.get_status()
        self.assertIsNone(self.backend.process)
        self.assertGreater(self.recovery.call_count, calls)
        self.assertIsNone(self.backend._termination_deadline)

    def test_deeply_nested_event_is_rejected_without_crashing_service(self):
        self.backend.process = self.process
        self.send(b'[' * 2000 + b'0' + b']' * 2000 + b'\n')
        self.assertIn('Invalid worker event', self.backend.get_status()['error'])
        self.process.terminate.assert_called_once()


class OwnershipFailureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.record = self.root / 'owned.json'
        self.sysnet = self.root / 'sysnet'
        self.iface = self.sysnet / 'wrnm123abc'
        self.iface.mkdir(parents=True)
        (self.iface / 'ifindex').write_text('123\n')
        (self.iface / 'address').write_text('02:00:00:00:00:01\n')
        self.data = {'interface': 'wrnm123abc', 'ifindex': 123, 'mac': '02:00:00:00:00:01',
                     'profile_uuid': PROFILE, 'profile_id': 'Wi-Fi Relay Hotspot'}
        patch.object(module, 'STATE_FILE', self.record).start()
        patch.object(module, 'SYS_NET', self.sysnet, create=True).start()
        self.command = patch.object(module.probe, 'command').start()
        self.addCleanup(patch.stopall)

    def save(self):
        self.record.write_text(json.dumps(self.data))

    def test_matching_identity_removes_owned_resources_and_journal(self):
        self.save()
        self.command.side_effect = [PROFILE, 'Wi-Fi Relay Hotspot', '', '']
        module.recover()
        self.command.assert_any_call(['iw', 'dev', 'wrnm123abc', 'del'])
        self.assertFalse(self.record.exists())

    def test_mac_mismatch_preserves_interface_profile_and_journal(self):
        self.data['mac'] = '02:00:00:00:00:02';self.save()
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            module.recover()
        self.command.assert_not_called()
        self.assertTrue(self.record.exists())

    def test_changed_profile_name_preserves_journal(self):
        self.save()
        self.command.side_effect = [PROFILE, 'Someone else']
        with self.assertRaisesRegex(RuntimeError, 'Profile identity changed'):
            module.recover()
        self.assertEqual(self.command.call_count, 2)
        self.assertTrue(self.record.exists())

    def test_failed_profile_delete_never_deletes_interface(self):
        self.save()
        self.command.side_effect = [PROFILE, 'Wi-Fi Relay Hotspot', RuntimeError('NM unavailable')]
        with self.assertRaisesRegex(RuntimeError, 'NM unavailable'):
            module.recover()
        self.assertEqual(self.command.call_count, 3)
        self.assertTrue(self.record.exists())

    def test_failed_interface_delete_preserves_journal_for_retry(self):
        self.save()
        self.command.side_effect = ['', RuntimeError('Interface busy')]
        with self.assertRaisesRegex(RuntimeError, 'Interface busy'):
            module.recover()
        self.assertTrue(self.record.exists())

    def test_already_absent_resources_are_idempotent(self):
        self.save()
        (self.iface / 'ifindex').unlink();(self.iface / 'address').unlink();self.iface.rmdir()
        self.command.return_value = ''
        module.recover();module.recover()
        self.command.assert_called_once_with(['nmcli', '-g', 'UUID', 'connection', 'show'])

    def test_journal_rejects_credential_fields(self):
        with self.assertRaisesRegex(ValueError, 'ownership record'):
            module.write_ownership({**self.data, 'PASSPHRASE': 'secret'})
        self.assertFalse(self.record.exists())

    def test_journal_replace_failure_preserves_previous_record(self):
        self.save()
        with patch.object(module.os, 'replace', side_effect=OSError('Disk failure')):
            with self.assertRaises(OSError):
                module.write_ownership({**self.data, 'ifindex': 456})
        self.assertEqual(json.loads(self.record.read_text())['ifindex'], 123)

    def test_existing_temporary_journal_cannot_weaken_permissions(self):
        temporary = self.record.with_suffix('.new')
        temporary.write_text('stale');temporary.chmod(0o644)
        module.write_ownership(self.data)
        self.assertEqual(self.record.stat().st_mode & 0o777, 0o600)

    def test_interface_replaced_during_profile_delete_is_not_removed(self):
        self.record.write_text(json.dumps(self.data))
        def command(args):
            if args == ['nmcli', '-g', 'UUID', 'connection', 'show']:
                return PROFILE
            if args == ['nmcli', '-g', 'connection.id', 'connection', 'show', 'uuid', PROFILE]:
                return 'Wi-Fi Relay Hotspot'
            if args == ['nmcli', 'connection', 'delete', 'uuid', PROFILE]:
                (self.iface / 'ifindex').write_text('456\n')
                return ''
            self.fail('Unexpected interface deletion: ' + str(args))
        self.command.side_effect = command
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            module.recover()
        self.assertTrue(self.record.exists())

    def test_invalid_ownership_schema_never_replaces_journal(self):
        self.save()
        for change in ({'ifindex': True}, {'ifindex': 0}, {'mac': 'invalid'},
                       {'profile_uuid': 'not-a-uuid'}, {'profile_uuid': None},
                       {'profile_id': 'Someone else'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.write_ownership({**self.data, **change})
            self.assertEqual(json.loads(self.record.read_text()), self.data)

    def test_profile_name_without_uuid_is_rejected(self):
        data = dict(self.data);data.pop('profile_uuid')
        with self.assertRaises(ValueError):
            module.validate_ownership(data)

    def test_recovery_rejects_invalid_saved_schema_without_commands(self):
        self.data['ifindex'] = False;self.save()
        with self.assertRaises(RuntimeError):
            module.recover()
        self.command.assert_not_called()

class WorkerContractTests(unittest.TestCase):
    def run_worker(self, config=None, report=None, effect=None):
        import contextlib
        import io
        config = config or CONFIG
        report = report or {'band': '2.4', 'channel': 12}
        output = io.StringIO()
        with patch.object(module.sys, 'stdin', io.StringIO(json.dumps(config))), \
                patch.object(module.signal, 'signal'), \
                patch.object(module.probe, 'inspect', return_value=report), \
                patch.object(module.probe, 'run_probe', side_effect=effect,
                    return_value={'cleanup_errors': [], 'outcome': 'stopped'}) as run, \
                patch.object(module, 'recover') as recover, contextlib.redirect_stdout(output):
            code = module.worker()
        return code, [json.loads(line) for line in output.getvalue().splitlines()], run, recover

    def test_worker_passes_expected_profile_to_activation_guard(self):
        code, events, run, recover = self.run_worker({**CONFIG, 'EXPECTED_UPSTREAM_UUID': PROFILE})
        self.assertEqual(code, 0)
        self.assertEqual(run.call_args.kwargs['expected_upstream_uuid'], PROFILE)

    def test_worker_rejects_invalid_expected_profile(self):
        code, events, run, recover = self.run_worker({**CONFIG, 'EXPECTED_UPSTREAM_UUID': ['wrong']})
        self.assertEqual(code, 1)
        run.assert_not_called()

    def test_band_mismatch_never_creates_interface(self):
        code, events, run, recover = self.run_worker({**CONFIG, 'FREQ_BAND': '5'})
        self.assertEqual(code, 1)
        self.assertIn('upstream band', events[0]['message'])
        run.assert_not_called()

    def test_channel_mismatch_never_creates_interface(self):
        code, events, run, recover = self.run_worker({**CONFIG, 'CHANNEL': '1'})
        self.assertEqual(code, 1)
        self.assertIn('upstream Wi-Fi channel', events[0]['message'])
        run.assert_not_called()

    def test_worker_uses_indefinite_lifetime_and_saved_configuration(self):
        code, events, run, recover = self.run_worker()
        self.assertEqual(code, 0)
        self.assertIsNone(run.call_args.args[2])
        self.assertEqual(run.call_args.kwargs['service_config']['PASSPHRASE'], CONFIG['PASSPHRASE'])
        self.assertIs(run.call_args.kwargs['ownership_callback'], module.write_ownership)
        self.assertNotIn(CONFIG['PASSPHRASE'], json.dumps(events))
        recover.assert_called_once()

    def test_cleanup_failure_is_a_failed_worker_exit(self):
        code, events, run, recover = self.run_worker(effect=lambda *a, **kw: {'cleanup_errors': ['interface busy']})
        self.assertEqual(code, 1)
        self.assertEqual(events[0]['result']['cleanup_errors'], ['interface busy'])
        recover.assert_not_called()

    def test_probe_failure_preserves_structured_evidence(self):
        result = {'cleanup_errors': [], 'outcome': 'failed', 'failure_stage': 'activating'}
        code, events, run, recover = self.run_worker(effect=module.probe.ProbeFailure('NM failed', result))
        self.assertEqual(code, 1)
        self.assertEqual(events[0]['result'], result)

    def test_every_unsupported_override_is_explicitly_rejected(self):
        changes = [{key: '1'} for key in ('NO_VIRT', 'NO_DNS', 'NO_DNSMASQ', 'ETC_HOSTS',
                    'MAC_FILTER', 'IEEE80211N', 'IEEE80211AC', 'IEEE80211AX')]
        changes += [{'COUNTRY': 'CN'}, {'DHCP_DNS': '1.1.1.1'}, {'WPA_VERSION': '1'}, {'SHARE_METHOD': 'none'}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.validate_options({**CONFIG, **change})

    def test_closed_parent_pipe_requests_cooperative_stop(self):
        import io
        def run(*args, **options):
            options['event_callback']({'event': 'stage', 'stage': 'active'})
            self.assertTrue(options['stop_requested']())
            return {'cleanup_errors': [], 'outcome': 'stopped'}
        with patch.object(module.sys, 'stdin', io.StringIO(json.dumps(CONFIG))), \
                patch.object(module.signal, 'signal'), \
                patch.object(module.probe, 'inspect', return_value={'band': '2.4', 'channel': 12}), \
                patch.object(module.probe, 'run_probe', side_effect=run), \
                patch.object(module, 'recover'), patch('builtins.print', side_effect=BrokenPipeError):
            self.assertEqual(module.worker(), 0)

    def test_sigterm_requests_cooperative_stop(self):
        handlers = {}
        def run(*args, **options):
            handlers[module.signal.SIGTERM](module.signal.SIGTERM, None)
            self.assertTrue(options['stop_requested']())
            return {'cleanup_errors': [], 'outcome': 'stopped'}
        with patch.object(module.signal, 'signal', side_effect=lambda sig, fn: handlers.setdefault(sig, fn)):
            import contextlib, io
            with patch.object(module.sys, 'stdin', io.StringIO(json.dumps(CONFIG))), \
                    patch.object(module.probe, 'inspect', return_value={'band': '2.4', 'channel': 12}), \
                    patch.object(module.probe, 'run_probe', side_effect=run), \
                    patch.object(module, 'recover'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.worker(), 0)


if __name__ == '__main__':
    unittest.main()
