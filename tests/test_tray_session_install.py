"""Package activation must use real desktop users, never a root GUI."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
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
            hook.user_systemctl(account, '--no-block', 'restart', hook.UNIT)
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ['/usr/sbin/runuser', '-u', 'desktop-user', '--'])
        self.assertEqual(command[4:6], ['/usr/bin/env', '-i'])
        self.assertIn('XDG_RUNTIME_DIR=/run/user/1000', command)
        self.assertIn('DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus', command)
        self.assertEqual(command[-5:], ['/usr/bin/systemctl', '--user', '--no-block', 'restart', hook.UNIT])

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
                    patch.object(hook, 'user_systemctl', return_value=SimpleNamespace(stdout='XDG_CURRENT_DESKTOP=XFCE\n'+display)) as control, \
                    patch.object(hook, 'startup_enabled', return_value=True), patch.object(hook, 'verify_running', return_value=True):
                self.assertTrue(hook.start_user(1000))
                self.assertEqual([call.args[1:] for call in control.call_args_list],
                                 [('show-environment',), ('daemon-reload',), ('restart', hook.UNIT)])
                self.assertEqual(control.call_args.kwargs, {'timeout': 12})

    def test_disabled_startup_does_not_restart_or_replace_manual_tray(self):
        with patch.object(hook.pwd, 'getpwuid'), patch.object(hook, 'startup_enabled', return_value=False), \
                patch.object(hook, 'user_systemctl', return_value=SimpleNamespace(stdout='XDG_CURRENT_DESKTOP=XFCE\nDISPLAY=:0')) as control:
            self.assertFalse(hook.start_user(1000))
        self.assertEqual(control.call_count, 1)

    def test_exited_startup_retries_once_and_verifies_recovery(self):
        with patch.object(hook.pwd, 'getpwuid'), patch.object(hook, 'startup_enabled', return_value=True), \
                patch.object(hook, 'user_systemctl', return_value=SimpleNamespace(stdout='XDG_CURRENT_DESKTOP=XFCE\nDISPLAY=:0')) as control, \
                patch.object(hook, 'verify_running', side_effect=[False, True]) as verify:
            self.assertTrue(hook.start_user(1000))
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(sum(call.args[1:] == ('restart', hook.UNIT) for call in control.call_args_list), 2)

    def test_repeated_exit_reports_failure_instead_of_success(self):
        with patch.object(hook.pwd, 'getpwuid'), patch.object(hook, 'startup_enabled', return_value=True), \
                patch.object(hook, 'user_systemctl', return_value=SimpleNamespace(stdout='XDG_CURRENT_DESKTOP=XFCE\nDISPLAY=:0')), \
                patch.object(hook, 'verify_running', return_value=False) as verify:
            with self.assertRaisesRegex(RuntimeError, 'both startup attempts'):
                hook.start_user(1000)
        self.assertEqual(verify.call_count, 2)
        with patch.object(hook.os, 'geteuid', return_value=0), patch.object(hook, 'active_desktop_users', return_value=[1000]), \
                patch.object(hook, 'start_user', side_effect=RuntimeError('tray exited')), patch('sys.stderr') as stderr, patch('builtins.print') as output:
            self.assertEqual(hook.main(), 0)
        self.assertEqual(output.call_count, 1)
        self.assertIs(output.call_args.kwargs['file'], stderr)
        self.assertIn('tray exited', output.call_args.args[0])

    def test_verify_requires_same_live_process_through_settle_period(self):
        alive = SimpleNamespace(stdout='ActiveState=active\nMainPID=123\nResult=success')
        with patch.object(hook, 'user_systemctl', return_value=alive) as control, \
                patch.object(hook.time, 'monotonic', side_effect=[0, 0, 3, 7]), patch.object(hook.time, 'sleep'):
            self.assertTrue(hook.verify_running(object()))
        self.assertEqual(control.call_count, 3)

    def test_verify_rejects_exit_failure_or_changing_pid(self):
        alive = SimpleNamespace(stdout='ActiveState=active\nMainPID=123')
        for state in ['ActiveState=inactive\nMainPID=0', 'ActiveState=failed\nMainPID=0',
                      'ActiveState=active\nMainPID=456', 'ActiveState=active\nMainPID=0']:
            with self.subTest(state=state), patch.object(hook, 'user_systemctl', side_effect=[alive, SimpleNamespace(stdout=state)]), \
                    patch.object(hook.time, 'monotonic', return_value=0), patch.object(hook.time, 'sleep'):
                self.assertFalse(hook.verify_running(object()))

    def test_preference_probe_drops_privileges_and_preserves_config_home(self):
        account = SimpleNamespace(pw_name='desktop-user', pw_uid=1000, pw_dir='/home/desktop-user')
        with patch.object(hook, 'run') as run:
            self.assertTrue(hook.startup_enabled(account, '/custom config'))
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ['/usr/sbin/runuser', '-u', 'desktop-user', '--'])
        self.assertIn('XDG_CONFIG_HOME=/custom config', command)
        self.assertEqual(command[-4:], ['/usr/bin/python3', '-I', str(Path(hook.__file__).resolve()), '--check-startup'])

    def test_preference_probe_only_treats_disabled_exit_code_as_disabled(self):
        with patch.object(hook, 'run_as_user', side_effect=subprocess.CalledProcessError(hook.STARTUP_DISABLED, 'probe')):
            self.assertFalse(hook.startup_enabled(object(), None))
        for code in (1, 2):
            with patch.object(hook, 'run_as_user', side_effect=subprocess.CalledProcessError(code, 'probe')):
                with self.assertRaises(subprocess.CalledProcessError):
                    hook.startup_enabled(object(), None)

    def test_restart_job_failure_is_retried_with_bounded_timeout(self):
        calls = [SimpleNamespace(stdout='XDG_CURRENT_DESKTOP=XFCE\nDISPLAY=:0'),
                 SimpleNamespace(stdout=''), subprocess.TimeoutExpired('systemctl', 12), SimpleNamespace(stdout='')]
        with patch.object(hook.pwd, 'getpwuid'), patch.object(hook, 'startup_enabled', return_value=True), \
                patch.object(hook, 'user_systemctl', side_effect=calls) as control, \
                patch.object(hook, 'verify_running', return_value=True) as verify:
            self.assertTrue(hook.start_user(1000))
        self.assertEqual(verify.call_count, 1)
        self.assertEqual(control.call_count, 4)
        self.assertEqual(control.call_args.kwargs, {'timeout': 12})

    def test_preference_defaults_match_tray_and_root_never_reads_preferences(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(hook.os.environ, {'XDG_CONFIG_HOME': directory}), \
                patch.object(hook.os, 'geteuid', return_value=1000):
            config = Path(directory) / 'wifi-hotspot/startup.json'
            config.parent.mkdir()
            self.assertTrue(hook.check_startup())
            for text, expected in [('{"auto_start":false}', False), ('{"auto_start":true}', True),
                                   ('{"auto_start":0}', True), ('broken json', True), ('[]', True), ('x' * 16385, True)]:
                config.write_text(text)
                self.assertEqual(hook.check_startup(), expected)
        with patch.object(hook.os, 'geteuid', return_value=0), patch.object(hook.Path, 'open') as read:
            with self.assertRaises(PermissionError):
                hook.check_startup()
            read.assert_not_called()

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
