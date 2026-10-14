"""Exercise the headless Shell wrapper without allowing a real desktop or network."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('dbus-run-session'), 'D-Bus runner required')
class GnomeShellIsolationTests(unittest.TestCase):
    def test_shell_and_probe_receive_a_private_system_bus(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            binary = temporary / 'bin'
            binary.mkdir()
            settings = binary / 'gsettings'
            settings.write_text('#!/bin/sh\nexit 0\n')
            settings.chmod(0o755)
            guard = '''import json, os, pathlib, sys, time
session = os.environ.get('DBUS_SESSION_BUS_ADDRESS')
assert session, 'No private session bus'
assert os.environ.get('DBUS_SYSTEM_BUS_ADDRESS') == session, 'Real system bus exposed to Shell'
assert session != 'unix:path=/unreachable-host-system-bus'
marker = pathlib.Path(os.environ['RELAY_ISOLATION_MARKER'])
if pathlib.Path(sys.argv[0]).name == 'gnome-shell':
    marker.write_text('private buses verified')
    while True: time.sleep(1)
else:
    sys.stdin.read()
    for _ in range(100):
        if marker.exists(): break
        time.sleep(.01)
    assert marker.exists(), 'Shell never verified its bus isolation'
    print(json.dumps({'headless_gnome': True, 'extension_loaded': True}))
'''
            for name in ('gnome-shell', 'python3'):
                script = binary / name
                script.write_text('#!' + sys.executable + '\n' + guard)
                script.chmod(0o755)
            marker = temporary / 'shell-isolated'
            environment = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                               DBUS_SYSTEM_BUS_ADDRESS='unix:path=/unreachable-host-system-bus',
                               RELAY_ISOLATION_MARKER=str(marker))
            result = subprocess.run(['bash', str(ROOT / 'tools/check_gnome_shell.sh')],
                                    env=environment, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(marker.read_text(), 'private buses verified')
