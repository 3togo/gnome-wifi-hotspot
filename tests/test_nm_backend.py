"""Service backend lifecycle and resource ownership checks without network changes."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "nm_service_backend", Path(__file__).resolve().parents[1] / "daemon/nm_backend.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CONFIG = {**module.probe.daemon.CONFIG_DEFAULTS, "BACKEND": "networkmanager",
          "WIFI_IFACE": "wlo2", "INTERNET_IFACE": "wlo2", "PASSPHRASE": "private-password"}
PROFILE = "1490513b-fb87-43b5-8a41-d9ea69a97e81"


class BackendTests(unittest.TestCase):
    def test_failed_recovery_does_not_break_legacy_service_startup(self):
        with patch.object(module, "recover", side_effect=RuntimeError("Identity mismatch")):
            backend = module.Backend()
        self.assertFalse(backend.status["active"])
        self.assertEqual(backend.status["error"], "Identity mismatch")

    def test_daemon_routes_start_stop_to_selected_backend(self):
        from test_band_fallback import Daemon
        daemon = Daemon.__new__(Daemon)
        daemon.nm_backend = Mock()
        daemon.nm_backend.process = None
        daemon.nm_backend.start.return_value = {"active": True, "backend": "networkmanager"}
        daemon.nm_backend.get_status.return_value = {"active": False, "backend": "networkmanager"}
        daemon._read_config_dict = Mock(return_value=CONFIG)
        daemon._get_status_dict = Mock(return_value={"active": False})
        daemon._emit_signal = Mock()
        daemon.cached_clients = []
        daemon.cached_status_active = False
        daemon.prepare_firewall = Mock()
        self.assertTrue(json.loads(daemon.method_start())["success"])
        daemon.nm_backend.start.assert_called_once()
        daemon.prepare_firewall.assert_not_called()
        daemon.method_stop()
        daemon.nm_backend.stop.assert_called_once()

    def test_backend_change_is_rejected_while_hotspot_is_active(self):
        from test_band_fallback import Daemon
        daemon = Daemon.__new__(Daemon)
        daemon._read_config_dict = Mock(return_value={**CONFIG, "BACKEND": "create_ap"})
        daemon._get_status_dict = Mock(return_value={"active": True})
        with self.assertRaisesRegex(ValueError, "Stop the hotspot"):
            daemon._write_config_dict({"BACKEND": "networkmanager"})

    def test_rejects_unsupported_overrides_instead_of_ignoring_them(self):
        for change in ({"MAC_FILTER": "1"}, {"WPA_VERSION": "3"}, {"SHARE_METHOD": "bridge"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.validate_options({**CONFIG, **change})

    def test_service_profile_uses_saved_credentials_gateway_and_visibility(self):
        profile = module.probe.service_settings(
            {"probe_interface": "wrnm123abc", "channel": 12, "band": "2.4"},
            {**CONFIG, "HIDDEN": "1", "ISOLATE_CLIENTS": "1"})
        self.assertEqual(profile["802-11-wireless-security"]["psk"].unpack(), "private-password")
        self.assertEqual(profile["ipv4"]["address-data"].unpack(), [{"address": "192.168.12.1", "prefix": 24}])
        self.assertTrue(profile["802-11-wireless"]["hidden"].unpack())
        self.assertEqual(profile["802-11-wireless"]["ap-isolation"].unpack(), 1)

    def test_recovery_deletes_only_recorded_uuid(self):
        with tempfile.TemporaryDirectory() as d:
            record = Path(d) / "owned.json"
            record.write_text(json.dumps({"interface": "wrnm123abc", "ifindex": 123,
                                         "mac": "02:00:00:00:00:01", "profile_uuid": PROFILE,
                                         "profile_id": "Wi-Fi Relay Hotspot"}))
            with patch.object(module, "STATE_FILE", record), \
                    patch.object(module.probe, "command", side_effect=[PROFILE, "Wi-Fi Relay Hotspot", ""]) as cmd:
                module.recover()
            cmd.assert_any_call(["nmcli", "connection", "delete", "uuid", PROFILE])
            self.assertFalse(record.exists())

    def test_recovery_refuses_changed_interface_identity(self):
        record = {"interface": "wrnm123abc", "ifindex": 123, "mac": "02:00:00:00:00:01"}
        with patch.object(module.Path, "exists", return_value=True), \
                patch.object(module.Path, "read_text", side_effect=[json.dumps(record), "456"]), \
                patch.object(module.probe, "command") as cmd, \
                self.assertRaisesRegex(RuntimeError, "identity changed"):
            module.recover()
        cmd.assert_not_called()

    def test_recovery_refuses_non_probe_interface_name(self):
        with patch.object(module.Path, "exists", return_value=True), \
                patch.object(module.Path, "read_text", return_value=json.dumps({"interface": "wlo2"})), \
                patch.object(module.probe, "command") as cmd, \
                self.assertRaisesRegex(RuntimeError, "Invalid owned-interface"):
            module.recover()
        cmd.assert_not_called()

    def test_resource_record_has_no_credentials_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "owned.json"
            data = {"interface": "wrnm123abc", "ifindex": 123, "mac": "02:00:00:00:00:01"}
            with patch.object(module, "STATE_FILE", path):
                module.write_ownership(data)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), data)

    def test_start_and_stop_use_pipe_and_status_events(self):
        reader, writer = os.pipe()
        stream = os.fdopen(reader, "rb")
        os.write(writer, json.dumps({"event": "stage", "stage": "active", "interface": "wrnm123abc"}).encode() + b"\n")
        os.close(writer)
        process = Mock(stdout=stream, returncode=0)
        process.poll.return_value = None
        try:
            with patch.object(module.probe, "upstream_snapshot", return_value=(PROFILE, "ssid", "bssid", 2467)), patch.object(module, "recover"), patch.object(module.subprocess, "Popen", return_value=process) as popen:
                backend = module.Backend()
                status = backend.start(CONFIG)
                self.assertTrue(status["active"])
                argv = popen.call_args.args[0]
                self.assertNotIn("private-password", str(argv))
                sent = json.loads(process.stdin.write.call_args.args[0])
                self.assertEqual(sent["PASSPHRASE"], "private-password")
                process.poll.side_effect = [None, 0]
                backend.stop()
                process.terminate.assert_called_once()
                self.assertFalse(backend.status["active"])
        finally:
            stream.close()


if __name__ == "__main__":
    unittest.main()
