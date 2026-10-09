#!/usr/bin/python3
"""Best-effort package hook: start installed tray controls as desktop users."""
import argparse
import os
import pwd
import shlex
import subprocess
import sys

UNIT = 'wifi-relay-tray.service'


def run(arguments):
    return subprocess.run(arguments, check=True, capture_output=True, text=True,
                          timeout=6, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})


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


def user_systemctl(account, *arguments):
    runtime = f'/run/user/{account.pw_uid}'
    # Drop privileges before connecting to the user's bus. Never evaluate the
    # user manager's environment as shell code or execute user files as root.
    return run(['/usr/sbin/runuser', '-u', account.pw_name, '--',
                '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin',
                'HOME=' + account.pw_dir, 'XDG_RUNTIME_DIR=' + runtime,
                'DBUS_SESSION_BUS_ADDRESS=unix:path=' + runtime + '/bus',
                '/usr/bin/systemctl', '--user', *arguments])


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
    user_systemctl(account, 'daemon-reload')
    user_systemctl(account, '--no-block', 'restart', UNIT)
    return True


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
                operation = 'shutdown' if stop else 'startup'
                print(f'Wi-Fi Relay: requested tray {operation} for desktop user {uid}.')
        except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
            print(f'Wi-Fi Relay: could not start tray for user {uid}: {error}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stop', action='store_true', help='Stop user tray services before package removal')
    sys.exit(main(stop=parser.parse_args().stop))
