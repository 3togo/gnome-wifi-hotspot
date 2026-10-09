#!/usr/bin/python3
"""Best-effort package hook: start installed tray controls as desktop users."""
import argparse
import json
import os
from pathlib import Path
import pwd
import shlex
import subprocess
import sys
import time

UNIT = 'wifi-relay-tray.service'
STARTUP_DISABLED = 77


def run(arguments, timeout=6):
    return subprocess.run(arguments, check=True, capture_output=True, text=True,
                          timeout=timeout, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})


def active_desktop_users():
    users = set()
    for row in run(['/usr/bin/loginctl', 'list-sessions', '--no-legend', '--no-pager']).stdout.splitlines():
        session = row.split()[0]
        info = run(['/usr/bin/loginctl', 'show-session', session,
                    '-p', 'User', '-p', 'Active', '-p', 'Remote', '-p', 'Type']).stdout
        fields = dict(line.split('=', 1) for line in info.splitlines() if '=' in line)
        if (fields.get('Active') == 'yes' and fields.get('Remote') == 'no'
                and fields.get('Type') in {'x11', 'wayland'}):
            uid = int(fields['User'])
            if uid > 0:
                users.add(uid)
    return sorted(users)


def run_as_user(account, arguments, config_home=None, timeout=6):
    runtime = f'/run/user/{account.pw_uid}'
    # Drop privileges before connecting to the user's bus. Never evaluate the
    # user manager's environment as shell code or execute user files as root.
    command = ['/usr/sbin/runuser', '-u', account.pw_name, '--',
                '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin',
                'HOME=' + account.pw_dir, 'XDG_RUNTIME_DIR=' + runtime,
                'DBUS_SESSION_BUS_ADDRESS=unix:path=' + runtime + '/bus']
    if config_home:
        command.append('XDG_CONFIG_HOME=' + config_home)
    return run([*command, *arguments], timeout=timeout)


def user_systemctl(account, *arguments, timeout=6):
    return run_as_user(account, ['/usr/bin/systemctl', '--user', *arguments], timeout=timeout)


def check_startup():
    """Read preferences only after dropping privileges to the desktop user."""
    if os.geteuid() == 0:
        raise PermissionError('Startup preferences must be checked as the desktop user')
    config = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    try:
        with (config / 'wifi-hotspot/startup.json').open('rb') as stream:
            data = stream.read(16385)
        values = json.loads(data) if len(data) <= 16384 else {}
        return not (isinstance(values, dict) and values.get('auto_start') is False)
    except (OSError, ValueError, RecursionError):
        return True  # Match the tray's default for missing/invalid preferences.


def startup_enabled(account, config_home):
    try:
        run_as_user(account, ['/usr/bin/python3', '-I', str(Path(__file__).resolve()),
                             '--check-startup'], config_home=config_home)
        return True
    except subprocess.CalledProcessError as error:
        if error.returncode == STARTUP_DISABLED:
            return False
        raise


def verify_running(account, settle_seconds=7):
    """Require one process to survive two tray polling intervals."""
    deadline = time.monotonic() + settle_seconds
    original_pid = None
    while True:
        state = user_systemctl(account, 'show', UNIT, '-p', 'ActiveState', '-p', 'MainPID', '-p', 'Result').stdout
        fields = dict(line.split('=', 1) for line in state.splitlines() if '=' in line)
        pid = fields.get('MainPID', '0')
        if fields.get('ActiveState') != 'active' or not pid.isdecimal() or int(pid) == 0:
            return False
        if original_pid is None:
            original_pid = pid
        elif pid != original_pid:
            return False
        if time.monotonic() >= deadline:
            return True
        time.sleep(1)


def start_user(uid):
    account = pwd.getpwuid(uid)
    environment = user_systemctl(account, 'show-environment').stdout
    entries = [shlex.split(line) for line in environment.splitlines()]
    fields = dict(entry[0].split('=', 1) for entry in entries
                  if len(entry) == 1 and '=' in entry[0])
    desktop = fields.get('XDG_CURRENT_DESKTOP', '')
    if (not desktop or 'GNOME' in desktop.upper().split(':')
            or not (fields.get('DISPLAY') or fields.get('WAYLAND_DISPLAY'))):
        return False
    config_home = fields.get('XDG_CONFIG_HOME')
    if not startup_enabled(account, config_home):
        return False
    user_systemctl(account, 'daemon-reload')
    for attempt in range(2):
        try:
            # Wait for the restart job, then check actual process survival.
            user_systemctl(account, 'restart', UNIT, timeout=12)
            if verify_running(account):
                return True
        except subprocess.SubprocessError:
            if attempt == 1:
                raise
        if not startup_enabled(account, config_home):
            return False
    raise RuntimeError('tray exited after both startup attempts; inspect systemctl --user status ' + UNIT)


def stop_user(uid):
    user_systemctl(pwd.getpwuid(uid), '--no-block', 'stop', UNIT)
    return True


def main(stop=False):
    if os.geteuid() != 0:
        print('This package hook must run as root.', file=sys.stderr)
        return 1
    try:
        users = active_desktop_users()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Wi-Fi Relay: immediate tray startup unavailable: {error}', file=sys.stderr)
        return 0
    for uid in users:
        try:
            if (stop_user if stop else start_user)(uid):
                description = 'requested tray shutdown' if stop else 'verified tray startup'
                print(f'Wi-Fi Relay: {description} for desktop user {uid}.')
        except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print(f'Wi-Fi Relay: could not start tray for user {uid}: {error}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stop', action='store_true', help='Stop user tray services before package removal')
    parser.add_argument('--check-startup', action='store_true', help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.check_startup:
        sys.exit(0 if check_startup() else STARTUP_DISABLED)
    sys.exit(main(stop=arguments.stop))
