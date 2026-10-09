"""Exercise the bundled shell runtime without starting networking commands."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_band_fallback import Daemon, module

SCRIPT = (Path(__file__).resolve().parents[1] / 'daemon/create_ap').read_text()


def function(name):
    return re.search(r'^' + name + r'\(\) \{.*?^\}', SCRIPT, re.M | re.S)[0]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.parent = Path(directory.name) / 'relay'
        self.runtime = self.parent / 'create-ap'

    def shell(self, body):
        return subprocess.run(['bash', '-c',
                               'set -e; umask 077; CREATE_AP_RUNTIME="$1"; ' + body,
                               'bash', str(self.runtime)], capture_output=True, text=True, timeout=5)

    def test_initializes_private_directories_and_locks(self):
        body = '\n'.join(function(name) for name in ('init_runtime', 'get_avail_fd', 'init_lock'))
        body += '\nLOCK_FD=0; COUNTER_LOCK_FILE="$CREATE_AP_RUNTIME/counter"; init_lock'
        result = self.shell(body)
        self.assertEqual(result.returncode, 0, result.stderr)
        for path, mode in [(self.parent, 0o700), (self.runtime, 0o700),
                           (self.runtime / 'create_ap.all.lock', 0o600),
                           (self.runtime / 'counter', 0o600)]:
            self.assertEqual(path.stat().st_mode & 0o777, mode)

    def test_refuses_symlinked_or_public_runtime_directories(self):
        self.parent.mkdir(mode=0o700)
        self.runtime.symlink_to(self.parent, target_is_directory=True)
        self.assertNotEqual(self.shell(function('init_runtime') + '\ninit_runtime').returncode, 0)
        self.runtime.unlink()
        self.runtime.mkdir(mode=0o700)
        self.runtime.chmod(0o755)
        self.assertNotEqual(self.shell(function('init_runtime') + '\ninit_runtime').returncode, 0)

    def test_refuses_foreign_owned_runtime(self):
        body = 'id() { echo 999999; };\n' + function('init_runtime') + '\ninit_runtime'
        self.assertNotEqual(self.shell(body).returncode, 0)

    def test_no_running_instance_balances_recursive_mutex(self):
        body = ('counter=0; mutex_lock() { ((counter+=1)); }; '
                'mutex_unlock() { counter=$((counter-1)); };\n')
        body += function('has_running_instance')
        body += '\nif has_running_instance; then exit 2; fi; test "$counter" = 0'
        self.assertEqual(self.shell(body).returncode, 0)

    def test_unused_descriptor_search_does_not_expand_entire_limit(self):
        body = 'seq() { exit 99; };\n' + function('get_avail_fd')
        body += '\nfd=$(get_avail_fd); test "$fd" -ge 3; test "$fd" -lt "$(ulimit -n)"'
        self.assertEqual(self.shell(body).returncode, 0)

    def test_dhcp_dns_runtime_rules_are_scoped_and_confinement_stays_enforced(self):
        start = SCRIPT.index('# start dhcp + dns (optional)')
        end = SCRIPT.index('# start access point', start)
        body = ('SHARE_METHOD=nat; NO_DNS=0; NO_DNSMASQ=0; WIFI_IFACE=ap0; '
                'GATEWAY=192.168.12.1; CONFDIR="$CREATE_AP_RUNTIME"; SCRIPT_UMASK=0077; '
                'iptables() { printf "%s\\n" "$*"; }; dnsmasq() { :; }; '
                'complain() { exit 99; }; aa-complain() { exit 99; }; die() { exit 98; };\n')
        result = self.shell(body + SCRIPT[start:end])
        self.assertEqual(result.returncode, 0, result.stderr)
        rules = result.stdout.splitlines()
        self.assertEqual(len(rules), 5)
        self.assertTrue(all('-i ap0' in rule for rule in rules))



class OwnershipTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.pidfile = self.root / 'create-ap.pid'
        self.process = self.root / 'proc' / '123'
        self.process.mkdir(parents=True)
        self.pidfile.write_text('123\n')
        self.daemon = Daemon.__new__(Daemon)
        self.daemon.create_ap_bin = '/usr/libexec/wifi-hotspot-daemon/create_ap'
        self.daemon.cached_clients = []
        self.daemon._read_config_dict = Mock(return_value={'SSID': 'owned'})
        self.daemon._emit_signal = Mock()
        self.argv = ['bash', self.daemon.create_ap_bin, '--pidfile', str(self.pidfile)]
        self.cmdline(self.argv)
        for name, value in [('CREATE_AP_PIDFILE', self.pidfile), ('PROC_DIRECTORY', self.process.parent)]:
            patcher = patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def cmdline(self, args):
        (self.process / 'cmdline').write_bytes(('\0'.join(args) + '\0').encode())

    def test_only_owned_pid_is_reported_even_when_another_instance_is_first(self):
        self.daemon._run_cmd = Mock(side_effect=[(0, '999 wlan0 (ap9)\n123 wlo2 (ap0)', ''),
                                                (0, 'channel 6 (2437 MHz)', '')])
        status = self.daemon._get_status_dict()
        self.assertEqual(status['pid'], 123)
        self.assertEqual(status['iface'], 'ap0')
        self.assertEqual(status['band'], '2.4')

    def test_reused_pid_or_missing_marker_is_never_adopted(self):
        for args in [['unrelated'], [self.daemon.create_ap_bin, '--pidfile'],
                     [self.daemon.create_ap_bin, '--pidfile', '/other.pid']]:
            with self.subTest(args=args):
                self.cmdline(args)
                self.daemon._run_cmd = Mock()
                self.assertFalse(self.daemon._get_status_dict()['active'])
                self.daemon._run_cmd.assert_not_called()

    def test_marker_cannot_adopt_a_process_from_another_user(self):
        with patch.object(module.os, 'geteuid', return_value=os.geteuid() + 1):
            self.assertIsNone(self.daemon._owned_create_ap_pid())

    def test_stop_targets_pid_and_does_not_stop_other_hotspots_on_same_adapter(self):
        self.daemon._get_status_dict = Mock(side_effect=[{'active': True, 'pid': 123,
                                                        'phy_iface': 'wlo2', 'iface': 'ap0'},
                                                       {'active': False}])
        self.daemon._run_cmd = Mock(return_value=(0, '', ''))
        with patch.object(module.GLib, 'usleep'):
            self.assertTrue(self.daemon.method_stop())
        self.daemon._run_cmd.assert_called_once_with([self.daemon.create_ap_bin, '--stop', '123'])

    def test_firewall_compatibility_call_does_not_change_global_policy(self):
        self.daemon._run_cmd = Mock()
        self.assertTrue(self.daemon.prepare_firewall())
        self.daemon._run_cmd.assert_not_called()

    def test_client_names_use_private_leases_without_blocking_reverse_dns(self):
        runtime = self.root / 'runtime'
        leases = runtime / 'create-ap' / 'create_ap.wlo2.conf.test' / 'dnsmasq.leases'
        leases.parent.mkdir(parents=True)
        leases.write_text('0 aa:bb:cc:dd:ee:ff 192.168.12.2 * *\n')
        self.daemon._run_cmd = Mock(return_value=(0, 'Station aa:bb:cc:dd:ee:ff (on ap0)', ''))
        with patch.object(module, 'RUNTIME_DIRECTORY', runtime), patch('socket.gethostbyaddr') as dns:
            clients = self.daemon._get_clients_list('ap0')
        self.assertEqual(clients[0]['hostname'], '')
        self.assertEqual(clients[0]['ip'], '192.168.12.2')
        dns.assert_not_called()
