"""Validate generated return rules without modifying the host firewall."""
from pathlib import Path
import shutil
import subprocess
import unittest

SCRIPT = (Path(__file__).resolve().parents[1] / 'daemon/create_ap').read_text()


class NatReturnRulesTests(unittest.TestCase):
    def rule(self, action):
        lines = [line.strip().removesuffix(' || die') for line in SCRIPT.splitlines()
                 if f'iptables -w {action} FORWARD' in line and '--ctstate' in line]
        self.assertEqual(len(lines), 1)
        command = lines[0]
        result = subprocess.run([
            'bash', '-c',
            'iptables() { printf "%s\\n" "$@"; }; '
            'WIFI_IFACE=ap0; INTERNET_IFACE=wlo2; GATEWAY=192.168.12.1; ' + command
        ], capture_output=True, text=True, check=True)
        return result.stdout.splitlines()

    def test_start_and_cleanup_use_identical_return_rule(self):
        added, removed = self.rule('-I'), self.rule('-D')
        self.assertEqual(added[2:], removed[2:])

    @unittest.skipUnless(shutil.which('iptables-translate'), 'iptables-translate unavailable')
    def test_return_rule_accepts_replies_without_restricting_incoming_uplink(self):
        args = self.rule('-I')
        args[1] = '-A'
        result = subprocess.run(['iptables-translate', *args], capture_output=True, text=True, check=True)
        self.assertIn('oifname "ap0"', result.stdout)
        self.assertIn('ip daddr 192.168.12.0/24', result.stdout)
        self.assertIn('ct state related,established', result.stdout)
        self.assertNotIn('iifname', result.stdout)
