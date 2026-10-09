"""Real private-bus handover from a legacy tray to the installed-session GUI."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

SOURCE = Path(os.environ.get('WIFI_RELAY_TEST_SETTINGS_DIR') or Path(__file__).resolve().parents[1] / 'settings')

# Source builds may run as root. Keep the desktop replacement test unprivileged
# and its session bus/display isolated from both the host and the build user.
if os.geteuid() == 0:
    import pwd
    account = pwd.getpwnam('nobody')
    with tempfile.TemporaryDirectory(prefix='relay-tray-unprivileged-') as directory:
        stage = Path(directory)
        shutil.copytree(SOURCE, stage / 'settings', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(__file__, stage / 'check.py')
        os.chown(stage, account.pw_uid, account.pw_gid)
        result = subprocess.run(['/usr/sbin/runuser', '-u', account.pw_name, '--', '/usr/bin/env',
            'WIFI_RELAY_TEST_SETTINGS_DIR=' + str(stage / 'settings'),
            '/usr/bin/dbus-run-session', '--', 'xvfb-run', '-a', '/usr/bin/python3', str(stage / 'check.py')])
        sys.exit(result.returncode)

from gi.repository import Gio, GLib
BUS_NAME = 'io.github.erhanzeyrek.WifiHotspot.Tray'
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

def dbus(method, value):
    return bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
        method, GLib.Variant('(s)', (value,)), None, Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]

def wait_for(predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except GLib.Error:
            pass
        time.sleep(0.05)
    raise AssertionError('Tray startup did not reach the expected state')

legacy_source = '''import sys
from gi.repository import Gio
app = Gio.Application(application_id="io.github.erhanzeyrek.WifiHotspot.Tray", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
app.connect("activate", lambda app: app.hold())
app.connect("command-line", lambda app, command: (app.activate(), 0)[1])
sys.exit(app.run(sys.argv))
'''

for visible, auto_start in ((True, True), (False, True), (True, False)):
    with tempfile.TemporaryDirectory(prefix='relay-tray-handover-') as directory:
        fixture = Path(directory)
        settings = fixture / 'settings'
        shutil.copytree(SOURCE, settings, ignore=shutil.ignore_patterns('__pycache__'))
        script = settings / 'tray.py'
        updated_source = script.read_text()
        config = fixture / 'config/wifi-hotspot'
        config.mkdir(parents=True)
        preference = config / 'tray.json'
        original = '{"visible":' + ('true' if visible else 'false') + '}\n'
        preference.write_text(original)
        if not auto_start:
            (config / 'startup.json').write_text('{"auto_start":false}\n')
        environment = dict(os.environ, XDG_CONFIG_HOME=str(fixture / 'config'),
                           DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'])
        script.write_text(legacy_source)
        processes = []
        with (fixture / 'tray.log').open('w') as log:
            try:
                legacy = subprocess.Popen([sys.executable, str(script)], env=environment, stdout=log, stderr=log)
                processes.append(legacy)
                wait_for(lambda: dbus('GetConnectionUnixProcessID', dbus('GetNameOwner', BUS_NAME)) == legacy.pid)
                script.write_text(updated_source)
                updated = subprocess.Popen([sys.executable, str(script), '--session-start'], env=environment, stdout=log, stderr=log)
                processes.append(updated)
                if not auto_start:
                    assert updated.wait(timeout=5) == 0
                    assert legacy.poll() is None
                    assert dbus('GetConnectionUnixProcessID', dbus('GetNameOwner', BUS_NAME)) == legacy.pid
                    assert preference.read_text() == original
                    print('Disabled startup leaves the existing manually launched tray unchanged.')
                    continue
                wait_for(lambda: dbus('GetConnectionUnixProcessID', dbus('GetNameOwner', BUS_NAME)) == updated.pid)
                legacy.wait(timeout=5)
                expected = 'Active' if visible else 'Passive'
                def indicator_ready():
                    result = bus.call_sync(BUS_NAME, '/org/ayatana/NotificationItem/wifi_hotspot',
                        'org.freedesktop.DBus.Properties', 'Get',
                        GLib.Variant('(ss)', ('org.kde.StatusNotifierItem', 'Status')), None,
                        Gio.DBusCallFlags.NONE, 1000, None)
                    return result.unpack()[0] == expected
                wait_for(indicator_ready)
                assert updated.poll() is None
                assert preference.read_text() == original
                print(f'Legacy tray replaced by a live instance; initial visibility {expected}; preferences unchanged.')
            except Exception:
                print((fixture / 'tray.log').read_text(), file=sys.stderr)
                raise
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=5)
print('Private-bus tray handover passed without hotspot or host-preference changes.')
