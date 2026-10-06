"""Authorization and config regression tests; never change host networking."""
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from test_band_fallback import module, Daemon


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.daemon = Daemon.__new__(Daemon)
        self.daemon.connection = Mock()
        self.daemon._dispatch_method_call = Mock()
        self.invocation = Mock()

    def invoke(self, method):
        self.daemon.handle_method_call(None, ':1.42', None, None, method, None, self.invocation)

    def complete(self, allowed):
        self.daemon.connection.call_finish.return_value = module.GLib.Variant(
            '((bba{ss}))', ((allowed, not allowed, {}),))
        self.daemon.connection.call.call_args.args[-1](self.daemon.connection, None)

    def test_every_privileged_method_waits_for_authorization(self):
        protected = {'Start', 'Stop', 'SetConfig', 'GetConfig', 'SwitchBandAndReconnect', 'PrepareFirewall'}
        self.assertEqual(module.PROTECTED_METHODS, protected)
        for method in protected:
            with self.subTest(method=method):
                self.setUp()
                self.invoke(method)
                self.daemon._dispatch_method_call.assert_not_called()
                args = self.daemon.connection.call.call_args.args
                subject, action, details, flags, cancellation = args[4].unpack()
                self.assertEqual(subject, ('system-bus-name', {'name': ':1.42'}))
                self.assertEqual(action, 'io.github.erhanzeyrek.WifiHotspot.manage')
                self.assertEqual(flags, 1)
                self.complete(True)
                self.daemon._dispatch_method_call.assert_called_once_with(method, None, self.invocation)

    def test_denied_call_never_dispatches(self):
        for method in module.PROTECTED_METHODS:
            with self.subTest(method=method):
                self.setUp()
                self.invoke(method)
                self.complete(False)
                self.daemon._dispatch_method_call.assert_not_called()
                self.assertEqual(self.invocation.return_error_literal.call_args.args[1], module.Gio.DBusError.ACCESS_DENIED)

    def test_polkit_unavailable_fails_closed(self):
        self.daemon.connection.call.side_effect = RuntimeError('Unavailable')
        self.invoke('Start')
        self.daemon._dispatch_method_call.assert_not_called()
        self.invocation.return_error_literal.assert_called_once()

    def test_polkit_async_failure_fails_closed(self):
        self.invoke('SetConfig')
        self.daemon.connection.call_finish.side_effect = RuntimeError('Service vanished')
        self.daemon.connection.call.call_args.args[-1](self.daemon.connection, None)
        self.daemon._dispatch_method_call.assert_not_called()
        self.invocation.return_error_literal.assert_called_once()

    def test_status_queries_do_not_prompt(self):
        for method in ('GetStatus', 'GetClients', 'GetInterfaces', 'GetCapabilities'):
            self.invoke(method)
        self.daemon.connection.call.assert_not_called()
        self.assertEqual(self.daemon._dispatch_method_call.call_count, 4)

    def test_missing_or_nonunique_subject_is_rejected(self):
        for sender in (None, 'root', 'org.example.Client', ':1.42\n'):
            result = Mock()
            self.daemon._authorize(sender, result)
            result.assert_called_once_with(False)
        self.daemon.connection.call.assert_not_called()


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'wifi-hotspot.conf'
        self.daemon = Daemon.__new__(Daemon)
        self.original = '# Existing\nSSID=Original\nFREQ_BAND=5\nPASSPHRASE=original secret\n'
        self.path.write_text(self.original)
        patcher = patch.object(module, 'get_config_path', return_value=str(self.path))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rejects_unknown_keys_types_control_characters_and_invalid_values(self):
        invalid = [[], None, {'UNSUPPORTED': 'x'}, {'HIDDEN': True}, {'SSID': 'name\nHIDDEN=1'},
                   {'SSID': 'name\rline'}, {'SSID': 'name\x00'}, {'SSID': 'name\x1b'},
                   {'SSID': '😀' * 9}, {'WIFI_IFACE': '-bad'}, {'WIFI_IFACE': 'too-long-interface'},
                   {'PASSPHRASE': 'short'}, {'PASSPHRASE': 'é' * 8}, {'PASSPHRASE': ''},
                   {'GATEWAY': '127.0.0.1'}, {'GATEWAY': '192.168.12.0'}, {'GATEWAY': '::1'},
                   {'CHANNEL': '1;anything'}, {'CHANNEL': '0'}, {'CHANNEL': '197'},
                   {'FREQ_BAND': '6'}, {'HIDDEN': '2'}, {'COUNTRY': 'invalid'},
                   {'MAC_FILTER_ACCEPT': '/etc/hostapd/../../etc/shadow'}, {'DHCP_DNS': '8.8.8.8\ncommand'},
                   {'USE_PSK': '1', 'PASSPHRASE': 'z' * 64}]
        for config in invalid:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    self.daemon._write_config_dict(config)
                self.assertEqual(self.path.read_text(), self.original)

    def test_patch_preserves_other_settings_and_sets_private_permissions(self):
        self.path.chmod(0o644)
        self.daemon._write_config_dict({'SSID': 'New name'})
        saved = self.daemon._read_config_dict()
        self.assertEqual(saved['SSID'], 'New name')
        self.assertEqual(saved['FREQ_BAND'], '5')
        self.assertEqual(saved['PASSPHRASE'], 'original secret')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_write_failure_leaves_original_file_and_no_temp_files(self):
        with patch.object(module.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.daemon._write_config_dict({'SSID': 'New name'})
        self.assertEqual(self.path.read_text(), self.original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_validation_errors_are_dbus_invalid_args(self):
        invocation = Mock()
        parameters = module.GLib.Variant('(s)', ('{"SSID":"bad\\nline"}',))
        self.daemon._dispatch_method_call('SetConfig', parameters, invocation)
        self.assertEqual(invocation.return_error_literal.call_args.args[1], module.Gio.DBusError.INVALID_ARGS)
        self.assertEqual(self.path.read_text(), self.original)

    def test_backend_roundtrip_treats_shell_metacharacters_and_spaces_literally(self):
        sentinel = self.path.parent / 'executed'
        ssid = ' "quoted" \\name $HOME '
        password = '$(touch ' + str(sentinel) + ')'
        self.daemon._write_config_dict({'SSID': ssid, 'PASSPHRASE': password})
        self.assertEqual(self.daemon._read_config_dict()['SSID'], ssid)
        script = (Path(__file__).resolve().parents[1] / 'daemon/create_ap').read_text()
        functions = script[script.index('is_config_opt() {'):script.index('\n\nARGS=(')]
        command = 'CONFIG_OPTS=(SSID PASSPHRASE FREQ_BAND); LOAD_CONFIG="$1"; ' + functions
        command += '\nread_config; printf "%s\\0%s" "$SSID" "$PASSPHRASE"'
        output = subprocess.run(['bash', '-c', command, 'bash', str(self.path)],
                                capture_output=True, check=True).stdout
        self.assertEqual(output, ssid.encode() + b'\0' + password.encode())
        self.assertFalse(sentinel.exists())

    def test_valid_hex_psk_and_multibyte_ssid(self):
        result = module.validate_config({'SSID': '😀' * 8, 'USE_PSK': '1', 'PASSPHRASE': 'a' * 64})
        self.assertEqual(result['USE_PSK'], '1')
