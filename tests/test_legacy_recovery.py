"""Failure-path ownership checks; no host networking commands are executed."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from daemon import legacy_runtime as runtime
from test_band_fallback import Daemon, module

SCRIPT = (Path(__file__).resolve().parents[1] / 'daemon/create_ap').read_text()


def function(name):
    return re.search(r'^' + name + r'\(\) \{.*?^\}', SCRIPT, re.M | re.S)[0]


class ManagementTests(unittest.TestCase):
    def run_management(self, unmanaged=False):
        body = '\n'.join(function(name) for name in (
            'networkmanager_add_unmanaged', 'networkmanager_rm_unmanaged',
            'networkmanager_rm_unmanaged_if_needed'))
        body += '''
is_interface() { return 0; }
save_recovery_state() { echo snapshot; }
networkmanager_iface_is_unmanaged() { [[ $state == unmanaged ]]; }
nmcli() { echo "$*"; if [[ $5 == no ]]; then state=unmanaged; else state=managed; fi; }
die() { exit 99; }
ADDED_UNMANAGED=
networkmanager_add_unmanaged wlan0
networkmanager_rm_unmanaged_if_needed wlan0
test -z "${ADDED_UNMANAGED// /}"
'''
        return subprocess.run(['bash', '-c', 'state=' + ('unmanaged' if unmanaged else 'managed') + '\n' + body],
                              capture_output=True, text=True, check=True).stdout.splitlines()

    def test_changed_physical_adapter_is_restored(self):
        self.assertEqual(self.run_management(), ['snapshot', 'device set wlan0 managed no',
                                                'device set wlan0 managed yes'])

    def test_preexisting_unmanaged_adapter_is_not_claimed(self):
        self.assertEqual(self.run_management(unmanaged=True), [])

    def test_failed_start_cleanup_does_not_delete_an_untagged_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            body = '''
mutex_lock() { :; }; mutex_unlock() { :; }; cleanup_lock() { :; }
stop_recorded_children() { :; }; has_running_instance() { return 0; }
list_running_conf() { :; }; is_interface() { return 1; }
cp() { :; }; rm() { :; }; python3() { :; }
iptables() {
    echo "$*"
    [[ $* == *'--comment wifi-relay-test'* ]] || { admin_rule_removed=yes; return 0; }
    return 1 # No owned rule was inserted before the startup failure.
}
CONFDIR="$1"; COMMON_CONFDIR="$1/common"; RULE_COMMENT=wifi-relay-test
SHARE_METHOD=nat; NO_VIRT=0; NO_DNS=1; RUNNING_AS_DAEMON=0
WIFI_IFACE=ap0; INTERNET_IFACE=eth0; GATEWAY=192.168.12.1
'''
            body += function('_cleanup') + '\n_cleanup\ntest -z "$admin_rule_removed"'
            result = subprocess.run(['bash', '-c', body, 'test', directory],
                                    capture_output=True, text=True, check=True)
            self.assertTrue(result.stdout.strip())
            self.assertTrue(all('--comment wifi-relay-test' in line for line in result.stdout.splitlines()))


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.runtime = self.root / 'relay/create-ap'
        self.runtime.mkdir(parents=True, mode=0o700)
        self.instance = self.runtime / 'create_ap.wlan0.conf.abcdefgh'
        self.instance.mkdir(mode=0o755)
        self.net = self.root / 'net'
        self.net.mkdir()
        for name, value in [('RUNTIME', self.runtime), ('SYS_NET', self.net)]:
            patcher = patch.object(runtime, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.values = [f'CONFDIR={self.instance}',
                       f'COMMON_CONFDIR={self.runtime}/create_ap.common.conf',
                       'DAEMON_PIDFILE=/run/wifi-relay/create-ap.pid',
                       'RULE_COMMENT=wifi-relay-fixture', 'WIFI_IFACE=wlan0', 'VWIFI_IFACE=ap0']

    def save_stale(self):
        runtime.save(self.instance, os.getpid(), self.values)
        data = runtime.read_private(self.instance / 'recovery.json')
        data['owner']['starttime'] = 'not-the-current-owner'
        runtime.write_private(self.instance / 'recovery.json', data)

    def test_live_owner_is_never_recovered(self):
        runtime.save(self.instance, os.getpid(), self.values)
        with self.assertRaisesRegex(RuntimeError, 'owner is alive'):
            runtime.assignments(self.instance)
        self.assertEqual(runtime.pending_directories('/run/wifi-relay/create-ap.pid'), [])

    def test_crashed_owner_with_retained_config_is_selected(self):
        self.save_stale()
        self.assertEqual(runtime.pending_directories('/run/wifi-relay/create-ap.pid'), [self.instance])
        self.assertEqual(runtime.pending_directories('/another-controller.pid'), [])

    def test_old_service_state_without_a_journal_cannot_be_declared_clean(self):
        marker = self.root / 'create-ap.pid'
        marker.write_text('12345')
        (self.instance / 'pid').write_text('12345')
        with self.assertRaisesRegex(RuntimeError, 'no recovery journal'):
            runtime.pending_directories(marker)
        marker.write_text('99999')
        self.assertEqual(runtime.pending_directories(marker), [])

    def test_snapshot_assignments_cannot_execute_shell_values(self):
        sentinel = self.root / 'must-not-exist'
        self.values += [f'GATEWAY=$(touch {sentinel})', 'IP_ADDRS[]=literal ; false']
        self.save_stale()
        result = subprocess.run(['bash', '-c', 'eval "$1"; printf "%s" "$GATEWAY"',
                                 'test', runtime.assignments(self.instance)],
                                capture_output=True, text=True, check=True)
        self.assertIn('$(touch ', result.stdout)
        self.assertFalse(sentinel.exists())

    def test_reused_interface_is_never_removed(self):
        interface = self.net / 'ap0'
        interface.mkdir()
        (interface / 'ifindex').write_text('5')
        (interface / 'address').write_text('02:00:00:00:00:01')
        self.save_stale()
        (interface / 'ifindex').write_text('6')
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            runtime.assignments(self.instance)

    def test_failed_recovery_keeps_its_record_for_retry(self):
        self.save_stale()
        with patch.object(runtime.subprocess, 'run', return_value=Mock(returncode=0)):
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                runtime.recover_owned('/run/wifi-relay/create-ap.pid', '/bundled/create_ap')
        self.assertTrue((self.instance / 'recovery.json').exists())

    def test_private_record_refuses_symlinks_and_public_files(self):
        self.save_stale()
        record = self.instance / 'recovery.json'
        record.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
            runtime.read_private(record)
        record.unlink()
        record.symlink_to(self.root / 'unrelated')
        with self.assertRaises(OSError):
            runtime.read_private(record)

    def test_stop_without_shell_attempts_recovery_and_propagates_failure(self):
        daemon = Daemon.__new__(Daemon)
        daemon.create_ap_bin = '/bundled/create_ap'
        daemon._owned_create_ap_pid = Mock(return_value=None)
        daemon._emit_signal = Mock()
        with patch.object(module.legacy_runtime, 'recover_owned', side_effect=RuntimeError('cleanup failed')) as recover:
            with self.assertRaisesRegex(RuntimeError, 'cleanup failed'):
                daemon.method_stop()
            recover.assert_called_once()

    def test_cleanup_verification_checks_only_owned_firewall_rules(self):
        self.save_stale()
        with patch.object(runtime.subprocess, 'run', return_value=Mock(stdout='-A FORWARD -j ACCEPT')):
            runtime.verify_cleanup(self.instance)
        with patch.object(runtime.subprocess, 'run', return_value=Mock(stdout='--comment wifi-relay-fixture')):
            with self.assertRaisesRegex(RuntimeError, 'rules survived'):
                runtime.verify_cleanup(self.instance)

    def test_unrecorded_live_child_cannot_be_reported_as_cleaned(self):
        self.save_stale()
        (self.instance / 'watchdog.pid').write_text(str(os.getpid()))
        with self.assertRaisesRegex(RuntimeError, 'Unverified legacy child'):
            runtime.verify_cleanup(self.instance)

    def test_parent_mac_change_does_not_prevent_owned_ap_cleanup(self):
        parent = self.net / 'wlan0'
        parent.mkdir()
        (parent / 'ifindex').write_text('2')
        (parent / 'address').write_text('02:00:00:00:00:01')
        self.save_stale()
        (parent / 'address').write_text('02:00:00:00:00:02')
        self.assertIn('CONFDIR=', runtime.assignments(self.instance))


class ChildIdentityTests(unittest.TestCase):
    def test_replacing_an_installed_executable_does_not_hide_its_running_child(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'sleep'
            shutil.copy2(shutil.which('sleep'), executable)
            child = subprocess.Popen([str(executable), '30'])
            try:
                pidfile = Path(directory) / 'child.pid'
                pidfile.write_text(str(child.pid))
                runtime.record_child(pidfile, 'sleep')
                executable.unlink()
                runtime.stop_child(pidfile.with_suffix('.identity'))
                self.assertIsNotNone(child.poll())
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait()

    def test_reused_pid_is_not_signalled(self):
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / 'child.identity'
            identity = runtime.process_identity(os.getpid())
            identity['starttime'] = 'old-starttime'
            runtime.write_private(record, identity)
            with patch.object(runtime.os, 'pidfd_open') as opened:
                runtime.stop_child(record)
            opened.assert_not_called()

    def test_recorded_child_is_stopped_through_its_pidfd(self):
        with tempfile.TemporaryDirectory() as directory:
            child = subprocess.Popen(['sleep', '30'])
            try:
                pidfile = Path(directory) / 'child.pid'
                pidfile.write_text(str(child.pid))
                runtime.record_child(pidfile, 'sleep')
                runtime.stop_child(pidfile.with_suffix('.identity'))
                self.assertIsNotNone(child.poll())
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait()
