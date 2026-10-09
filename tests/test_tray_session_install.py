"""Package activation must use real desktop users, never a root GUI."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('tray_sessions', Path(__file__).resolve().parents[1] / 'packaging/start-tray-sessions.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class TraySessionInstallTests(unittest.TestCase):
    def test_only_active_local_graphical_users_are_selected_and_deduplicated(self):
        sessions = [
            ('1', 1000, 'yes', 'no', 'x11'),
            ('2', 1000, 'yes', 'no', 'wayland'),
            ('3', 1001, 'yes', 'yes', 'x11'),
            ('4', 1002, 'no', 'no', 'x11'),
            ('5', 1003, 'yes', 'no', 'tty'),
            ('6', 0, 'yes', 'no', 'x11'),
        ]
        replies = [SimpleNamespace(stdout='\n'.join(s[0] for s in sessions))]
        replies += [SimpleNamespace(stdout=f'User={uid}\nActive={active}\nRemote={remote}\nType={kind}\n')
                    for _, uid, active, remote, kind in sessions]
        with patch.object(hook, 'run', side_effect=replies):
            self.assertEqual(hook.active_desktop_users(), [1000])

    def test_starts_as_user_with_clean_environment_and_fixed_unit(self):
        account = SimpleNamespace(pw_name='desktop-user', pw_uid=1000, pw_dir='/home/desktop-user')
        with patch.object(hook, 'run') as run:
            hook.user_systemctl(account, '--no-block', 'start', hook.UNIT)
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ['/usr/sbin/runuser', '-u', 'desktop-user', '--'])
        self.assertEqual(command[4:6], ['/usr/bin/env', '-i'])
        self.assertIn('XDG_RUNTIME_DIR=/run/user/1000', command)
        self.assertIn('DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus', command)
        self.assertEqual(command[-5:], ['/usr/bin/systemctl', '--user', '--no-block', 'start', hook.UNIT])

    def test_skips_gnome_missing_environment_and_headless_managers(self):
        for environment in ['', 'XDG_CURRENT_DESKTOP=XFCE\n',
                            'XDG_CURRENT_DESKTOP=ubuntu:GNOME\nDISPLAY=:0\n',
                            "XDG_CURRENT_DESKTOP='ubuntu:GNOME'\nDISPLAY=:0\n"]:
            with self.subTest(environment=environment), patch.object(hook.pwd, 'getpwuid'), \
                    patch.object(hook, 'user_systemctl', return_value=SimpleNamespace(stdout=environment)) as control:
                self.assertFalse(hook.start_user(1000))
                self.assertEqual(control.call_count, 1)

    def test_active_desktop_starts_after_reloading_units(self):
        for display in ['DISPLAY=:0', 'WAYLAND_DISPLAY=wayland-0']:
            with self.subTest(display=display), patch.object(hook.pwd, 'getpwuid'), \
                    patch.object(hook, 'user_systemctl', return_value=SimpleNamespace(stdout='XDG_CURRENT_DESKTOP=XFCE\n'+display)) as control:
                self.assertTrue(hook.start_user(1000))
                self.assertEqual([call.args[1:] for call in control.call_args_list],
                                 [('show-environment',), ('daemon-reload',), ('--no-block', 'start', hook.UNIT)])

    def test_missing_session_manager_and_user_start_failure_are_nonfatal(self):
        with patch.object(hook.os, 'geteuid', return_value=0), patch.object(hook, 'active_desktop_users', side_effect=FileNotFoundError), patch('sys.stderr'):
            self.assertEqual(hook.main(), 0)
        with patch.object(hook.os, 'geteuid', return_value=0), patch.object(hook, 'active_desktop_users', return_value=[1000]), \
                patch.object(hook, 'start_user', side_effect=subprocess.TimeoutExpired('systemctl', 6)), patch('sys.stderr'):
            self.assertEqual(hook.main(), 0)

    def test_subprocesses_are_bounded_and_do_not_inherit_root_environment(self):
        with patch.object(hook.subprocess, 'run') as run:
            hook.run(['/usr/bin/loginctl', 'list-sessions'])
        self.assertEqual(run.call_args.kwargs['timeout'], 6)
        self.assertEqual(run.call_args.kwargs['env'], {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})

    def test_removal_stops_only_the_user_tray_service(self):
        account = SimpleNamespace(pw_name='desktop-user', pw_uid=1000, pw_dir='/home/desktop-user')
        with patch.object(hook.pwd, 'getpwuid', return_value=account), patch.object(hook, 'user_systemctl') as control:
            self.assertTrue(hook.stop_user(1000))
        control.assert_called_once_with(account, '--no-block', 'stop', hook.UNIT)
