"""Exercise the experimental NM probe without altering the host network."""
import contextlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "nm_probe", Path(__file__).resolve().parents[1] / "tools/nm_ap_sta_probe.py"
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

INVENTORY = """phy#0
    Interface ap0
        type AP
    Unnamed/non-netdev interface
        type P2P-device
    Interface wlo2
        type managed
phy#1
    Interface wlan1
        type managed
"""
BASELINE = ("upstream-uuid", "Home", "aa:bb:cc:dd:ee:ff", 2467)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "eligible_for_live_probe": True, "blockers": [], "station": "wlo2",
            "probe_interface": "wrnmtest", "band": "2.4", "channel": 12,
            "upstream_frequency_mhz": 2467,
        }
        self.nm = Mock()
        self.nm.device.return_value = "/device/probe"
        self.nm.activate.return_value = "/active/probe"
        self.nm.state.return_value = 2
        self.nm.device_state.return_value = (30, 0)

    def execute(self, command_failure=None, snapshots=None, observation=None, hold=0, **options):
        def command(args):
            if command_failure:
                command_failure(args)
            return "Interface wrnmtest\n\ttype AP\n\tchannel 12 (2467 MHz)"

        with patch.object(probe.os, "geteuid", return_value=0), \
                patch.object(probe, "inspect", return_value=self.report), \
                patch.object(probe, "upstream_snapshot",
                             side_effect=snapshots, return_value=BASELINE), \
                patch.object(probe, "client_observation", return_value=observation or {
                    "authorized_clients": 0, "clients_with_ipv4_neighbor": 0,
                    "gateway_ipv4_addresses": ["10.42.0.1"]}), \
                patch.object(probe, "command", side_effect=command) as commands:
            self.commands = commands
            return probe.run_probe(self.report, "Probe", hold, nm_factory=lambda: self.nm, **options)

    def test_expected_upstream_rejects_profile_change_before_interface_creation(self):
        with self.assertRaisesRegex(RuntimeError, "original Wi-Fi"):
            self.execute(expected_upstream_uuid="different-profile")
        self.commands.assert_not_called()
        self.nm.activate.assert_not_called()

    def test_inventory_tracks_phy_and_unnamed_interfaces(self):
        inventory = probe.interfaces(INVENTORY)
        self.assertEqual(inventory[1], {"phy": 0, "interface": None, "type": "P2P-device"})
        self.assertEqual(inventory[-1]["phy"], 1)

    def test_existing_ap_blocks_read_only_assessment(self):
        caps = {"current_sta_ssid": "Home", "ap_sta_concurrent": True,
                "current_sta_ap_allowed": True, "current_sta_frequency": 2467,
                "current_sta_band": "2.4",
                "ap_channels": {"2.4": [{"channel": 12, "frequency": 2467}]}}

        def command(args):
            if args == ["iw", "dev"]:
                return INVENTORY
            if "WIFI-PROPERTIES.AP" in args:
                return "yes"
            return "test-value"

        with patch.object(probe, "command", side_effect=command), \
                patch.object(probe, "capabilities", return_value=caps), \
                patch.object(probe, "api_compatibility", return_value={
                    "add_and_activate_connection2": True}), \
                patch.object(probe.Path, "exists", return_value=False):
            report = probe.inspect("wlo2", "wrnmtest")
        self.assertFalse(report["eligible_for_live_probe"])
        self.assertIn("Another AP", report["blockers"][0])
        self.assertNotIn("Home", str(report))

    def test_blocked_probe_does_not_mutate_network(self):
        self.report.update(eligible_for_live_probe=False, blockers=["Existing AP"])
        with patch.object(probe, "command") as commands, \
                self.assertRaisesRegex(RuntimeError, "Existing AP"):
            probe.run_probe(self.report, "Probe", 0)
        commands.assert_not_called()

    def test_race_with_another_ap_is_caught_before_creation(self):
        fresh = {**self.report, "eligible_for_live_probe": False, "blockers": ["Existing AP"]}
        with patch.object(probe.os, "geteuid", return_value=0), \
                patch.object(probe, "inspect", return_value=fresh), \
                patch.object(probe, "command") as commands, \
                self.assertRaisesRegex(RuntimeError, "Existing AP"):
            probe.run_probe(self.report, "Probe", 0)
        commands.assert_not_called()

    def test_success_deactivates_and_removes_only_owned_interface(self):
        result = self.execute()
        self.assertTrue(result["activation_verified"])
        self.assertTrue(result["upstream_preserved_after_cleanup"])
        self.assertFalse(result["client_connectivity_tested"])
        self.nm.deactivate.assert_called_once_with("/active/probe")
        self.nm.close.assert_called_once()
        self.commands.assert_any_call(["iw", "dev", "wrnmtest", "del"])
        self.assertFalse(any("wlo2" in c.args[0] and "del" in c.args[0]
                             for c in self.commands.call_args_list))

    def test_creation_failure_never_deletes_existing_interface(self):
        def fail(args):
            raise RuntimeError("Interface creation failed")
        with self.assertRaisesRegex(RuntimeError, "creation failed"):
            self.execute(command_failure=fail)
        self.assertEqual(self.commands.call_count, 1)
        self.nm.close.assert_not_called()

    def test_activation_request_failure_closes_bus_and_deletes_interface(self):
        self.nm.activate.side_effect = RuntimeError("Supplicant refused AP")
        with self.assertRaisesRegex(RuntimeError, "Supplicant refused"):
            self.execute()
        self.nm.close.assert_called_once()
        self.nm.deactivate.assert_not_called()
        self.commands.assert_any_call(["iw", "dev", "wrnmtest", "del"])

    def test_upstream_roaming_stops_and_cleans_up(self):
        changed = (*BASELINE[:3], 2412)
        with self.assertRaisesRegex(RuntimeError, "Upstream connection or channel changed"):
            self.execute(snapshots=[BASELINE, BASELINE, BASELINE, changed, changed])
        self.nm.deactivate.assert_called_once()
        self.nm.close.assert_called_once()
        self.commands.assert_any_call(["iw", "dev", "wrnmtest", "del"])

    def test_cleanup_continues_when_deactivation_fails(self):
        self.nm.deactivate.side_effect = RuntimeError("Already disconnected")
        with contextlib.redirect_stderr(io.StringIO()):
            result = self.execute()
        self.nm.close.assert_called_once()
        self.commands.assert_any_call(["iw", "dev", "wrnmtest", "del"])
        self.assertIn("Already disconnected", result["cleanup_errors"][0])

    def test_activation_state_failure_cleans_up(self):
        self.nm.state.return_value = 4
        with self.assertRaisesRegex(RuntimeError, "activation failed"):
            self.execute()
        self.nm.deactivate.assert_called_once()
        self.nm.close.assert_called_once()
        self.commands.assert_any_call(["iw", "dev", "wrnmtest", "del"])

    def test_signal_interruption_cleans_up(self):
        self.nm.state.side_effect = InterruptedError("Probe interrupted")
        with self.assertRaisesRegex(probe.ProbeFailure, "interrupted"):
            self.execute()
        self.nm.deactivate.assert_called_once()
        self.nm.close.assert_called_once()
        self.commands.assert_any_call(["iw", "dev", "wrnmtest", "del"])

    def test_bus_close_failure_still_deletes_interface(self):
        self.nm.close.side_effect = RuntimeError("Bus close failed")
        with contextlib.redirect_stderr(io.StringIO()):
            result = self.execute()
        self.commands.assert_any_call(["iw", "dev", "wrnmtest", "del"])
        self.assertIn("Bus close failed", result["cleanup_errors"][0])

    def test_profile_uses_shared_ipv4_and_current_channel(self):
        profile = probe.settings(self.report, "Probe", "private-password")
        self.assertEqual(profile["ipv4"]["method"].unpack(), "shared")
        self.assertEqual(profile["802-11-wireless"]["channel"].unpack(), 12)
        self.assertFalse(profile["connection"]["autoconnect"].unpack())
        self.assertEqual(profile["802-11-wireless-security"]["proto"].unpack(), ["rsn"])

    def test_activation_is_volatile_and_bound_to_private_bus(self):
        nm = probe.NetworkManager.__new__(probe.NetworkManager)
        nm.call = Mock(return_value=("/connection/probe", "/active/probe", {}))
        nm.activate("/device/probe", probe.settings(self.report, "Probe", "private-password"))
        args = nm.call.call_args.args[3].unpack()
        self.assertEqual(args[3], {"persist": "volatile", "bind-activation": "dbus-client"})

    def test_api_preflight_rejects_missing_activation_method(self):
        nm = probe.NetworkManager.__new__(probe.NetworkManager)
        nm.call = Mock(side_effect=[("<node/>",), ("1.58.1",)])
        result = nm.compatibility()
        self.assertFalse(result["add_and_activate_connection2"])

    def test_api_preflight_checks_signature_and_running_version(self):
        xml = '''<node><interface name="org.freedesktop.NetworkManager">
        <method name="AddAndActivateConnection2"><arg type="a{sa{sv}}" direction="in"/>
        <arg type="o" direction="in"/><arg type="o" direction="in"/>
        <arg type="a{sv}" direction="in"/><arg type="o" direction="out"/>
        </method></interface></node>'''
        nm = probe.NetworkManager.__new__(probe.NetworkManager)
        nm.call = Mock(side_effect=[(xml,), ("1.58.1",)])
        result = nm.compatibility()
        self.assertTrue(result["add_and_activate_connection2"])
        self.assertEqual(result["daemon_version"], "1.58.1")

    def test_credentials_private_and_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            probe.write_credentials(path, "Probe", "test-secret")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                probe.write_credentials(path, "Other", "replacement")
            self.assertEqual(json.loads(path.read_text())["password"], "test-secret")

    def test_credentials_removed_on_activation_failure(self):
        self.nm.activate.side_effect = RuntimeError("Activation failed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            with self.assertRaisesRegex(RuntimeError, "Activation failed"):
                self.execute(credentials_file=path)
            self.assertFalse(path.exists())

    def test_require_client_fails_without_evidence_and_cleans_up(self):
        with self.assertRaisesRegex(RuntimeError, "No authorized client"):
            self.execute(require_client=True)
        self.nm.close.assert_called_once()
        self.commands.assert_any_call(["iw", "dev", "wrnmtest", "del"])

    def test_client_evidence_does_not_claim_internet_or_dhcp(self):
        observation = {"authorized_clients": 1, "clients_with_ipv4_neighbor": 1,
                       "gateway_ipv4_addresses": ["10.42.0.1"]}
        result = self.execute(require_client=True, observation=observation)
        self.assertEqual(result["client_observation"]["clients_with_ipv4_neighbor_peak"], 1)
        self.assertFalse(result["client_connectivity_tested"])
        self.assertFalse(result["dhcp_verified"])
        self.assertFalse(result["internet_verified"])

    def test_neighbors_must_match_authorized_station_subnet_and_state(self):
        stations = '''Station aa:bb:cc:dd:ee:01 (on wrnmtest)
            authorized: yes
Station aa:bb:cc:dd:ee:02 (on wrnmtest)
            authorized: no
Station aa:bb:cc:dd:ee:03 (on wrnmtest)
            authorized: yes
Station aa:bb:cc:dd:ee:04 (on wrnmtest)
            authorized: yes
'''
        addresses = [{"addr_info": [{"family": "inet", "local": "10.42.0.1", "prefixlen": 24}]}]
        neighbors = [
            {"lladdr": "aa:bb:cc:dd:ee:01", "dst": "10.42.0.2", "state": ["REACHABLE"]},
            {"lladdr": "aa:bb:cc:dd:ee:02", "dst": "10.42.0.3", "state": ["REACHABLE"]},
            {"lladdr": "aa:bb:cc:dd:ee:03", "dst": "10.42.0.4", "state": ["FAILED"]},
            {"lladdr": "aa:bb:cc:dd:ee:04", "dst": "192.168.1.2", "state": ["STALE"]},
        ]
        with patch.object(probe, "command", side_effect=[
                stations, json.dumps(addresses), json.dumps(neighbors)]):
            evidence = probe.client_observation("wrnmtest")
        self.assertEqual(evidence["authorized_clients"], 3)
        self.assertEqual(evidence["clients_with_ipv4_neighbor"], 1)
        self.assertNotIn("aa:bb", str(evidence))

    def test_failure_keeps_lifecycle_and_cleanup_evidence(self):
        self.nm.state.return_value = 4
        with self.assertRaises(probe.ProbeFailure) as caught:
            self.execute()
        result = caught.exception.result
        self.assertEqual(result["failure_stage"], "activating")
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["lifecycle"][-1]["stage"], "failed")
        self.assertTrue(result["cleanup_verification"]["profile_removed"])
        self.assertTrue(result["cleanup_verification"]["interface_removed"])
        self.assertTrue(result["upstream_preserved_after_cleanup"])

    def test_cleanup_failure_cannot_report_passed(self):
        self.nm.close.side_effect = RuntimeError("Bus close failed")
        with contextlib.redirect_stderr(io.StringIO()):
            result = self.execute()
        self.assertEqual(result["outcome"], "failed")

    def test_volatile_profile_removal_allows_async_delay(self):
        with patch.object(probe, "command", side_effect=["probe-uuid", ""]), \
                patch.object(probe.time, "sleep") as sleep:
            checks = probe.cleanup_verification("wrnmtest", "probe-uuid", None)
        self.assertTrue(checks["profile_removed"])
        sleep.assert_called_once()

    def test_cleanup_verification_detects_surviving_credentials_and_interface(self):
        with patch.object(probe.Path, "exists", return_value=True):
            checks = probe.cleanup_verification("wrnmtest", None, Path("credentials.json"))
        self.assertFalse(checks["interface_removed"])
        self.assertFalse(checks["credentials_removed"])

    def test_profile_verification_timeout(self):
        with patch.object(probe, "command", return_value="probe-uuid"), \
                patch.object(probe.time, "monotonic", side_effect=[0, 6]):
            checks = probe.cleanup_verification("wrnmtest", "probe-uuid", None)
        self.assertFalse(checks["profile_removed"])

    def test_multiple_cycles_reinspect_and_stop_after_cleanup_failure(self):
        good = {"activation_verified": True, "cleanup_errors": [], "outcome": "passed"}
        bad = {"activation_verified": True, "cleanup_errors": ["leftover profile"], "outcome": "failed"}
        output = io.StringIO()
        with patch.object(probe.sys, "argv", ["probe", "--station", "wlo2", "--run", "--cycles", "3"]), \
                patch.object(probe.signal, "signal"), \
                patch.object(probe, "inspect", side_effect=lambda *args: dict(self.report)) as inspect, \
                patch.object(probe, "run_probe", side_effect=[good, bad]) as run, \
                contextlib.redirect_stdout(output):
            code = probe.main()
        self.assertEqual(code, 1)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(inspect.call_count, 2)
        self.assertEqual(len(json.loads(output.getvalue())["cycles"]), 2)

    def test_cli_failure_json_retains_completed_cycles_and_failed_stage(self):
        good = {"activation_verified": True, "cleanup_errors": [], "outcome": "passed"}
        bad = {"activation_verified": False, "cleanup_errors": [], "outcome": "failed",
               "failure_stage": "activating"}
        output = io.StringIO()
        with patch.object(probe.sys, "argv", ["probe", "--station", "wlo2", "--run", "--cycles", "3"]), \
                patch.object(probe.signal, "signal"), \
                patch.object(probe, "inspect", side_effect=lambda *args: dict(self.report)), \
                patch.object(probe, "run_probe", side_effect=[good, probe.ProbeFailure("failed", bad)]) as run, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = probe.main()
        result = json.loads(output.getvalue())["report"]
        self.assertEqual(code, 1)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(len(result["cycles"]), 2)
        self.assertEqual(result["live_test"]["failure_stage"], "activating")

    def test_device_readiness_waits_before_activation(self):
        self.nm.device_state.side_effect = [(20, 2), (30, 0)]
        with patch.object(probe.time, "sleep") as sleep:
            result = self.execute()
        self.assertEqual(self.nm.device_state.call_count, 2)
        self.nm.activate.assert_called_once()
        sleep.assert_called_once_with(0.25)
        self.assertEqual(result["device_state"], {"state": 30, "reason": 0})

    def test_unavailable_device_times_out_without_requesting_activation(self):
        self.nm.device_state.return_value = (20, 2)
        with patch.object(probe.time, "monotonic", side_effect=itertools.count(0, 5)), \
                patch.object(probe.time, "sleep"), self.assertRaises(probe.ProbeFailure) as caught:
            self.execute()
        self.nm.activate.assert_not_called()
        self.assertEqual(caught.exception.result["failure_stage"], "waiting-for-device")
        self.assertTrue(caught.exception.result["cleanup_verification"]["interface_removed"])

    def test_ap_restoration_changes_only_named_probe_interface(self):
        with patch.object(probe, "command", side_effect=["Interface wrnmtest\n\ttype managed", "", ""]) as cmd:
            self.assertTrue(probe.restore_ap_mode("wrnmtest"))
        self.assertEqual([c.args[0] for c in cmd.call_args_list], [
            ["iw", "dev", "wrnmtest", "info"],
            ["ip", "link", "set", "dev", "wrnmtest", "down"],
            ["iw", "dev", "wrnmtest", "set", "type", "__ap"]])

    def test_existing_ap_mode_is_not_reset(self):
        with patch.object(probe, "command", return_value="Interface wrnmtest\n\ttype AP") as cmd:
            self.assertFalse(probe.restore_ap_mode("wrnmtest"))
        self.assertEqual(cmd.call_count, 1)

    def test_opt_in_restoration_runs_once_then_activates_when_ready(self):
        self.nm.device_state.side_effect = [(20, 2), (20, 2), (30, 0)]
        with patch.object(probe, "restore_ap_mode", return_value=True) as restore, \
                patch.object(probe.time, "sleep"):
            result = self.execute(restore_ap=True)
        restore.assert_called_once_with("wrnmtest")
        self.assertTrue(result["ap_mode_restored"])
        self.nm.activate.assert_called_once()

    def test_default_probe_never_restores_ap_mode(self):
        self.nm.device_state.side_effect = [(20, 2), (30, 0)]
        with patch.object(probe, "restore_ap_mode") as restore, patch.object(probe.time, "sleep"):
            self.execute()
        restore.assert_not_called()

    def test_persistent_observation_stops_only_on_explicit_request(self):
        stopping = Mock(side_effect=itertools.chain(itertools.repeat(False, 6), itertools.repeat(True)))
        with patch.object(probe.time, "sleep"):
            result = self.execute(hold=None, stop_requested=stopping)
        self.assertEqual(result["outcome"], "stopped")
        self.assertTrue(result["activation_verified"])
        self.nm.deactivate.assert_called_once()
        self.assertTrue(result["cleanup_verification"]["profile_removed"])

    def test_stop_before_creation_never_mutates_radio(self):
        result = self.execute(stop_requested=lambda: True)
        self.assertEqual(result['outcome'], 'stopped')
        self.commands.assert_not_called()
        self.nm.activate.assert_not_called()

    def test_stop_while_waiting_for_device_cleans_owned_interface(self):
        stopping = Mock(side_effect=[False, False, True])
        result = self.execute(stop_requested=stopping)
        self.assertEqual(result['outcome'], 'stopped')
        self.nm.activate.assert_not_called()
        self.nm.close.assert_called_once()
        self.commands.assert_any_call(['iw', 'dev', 'wrnmtest', 'del'])

    def test_discovery_timeout_closes_bus_and_cleans_owned_interface(self):
        self.nm.device.side_effect = probe.GLib.Error('Missing device')
        with patch.object(probe.time, 'monotonic', side_effect=itertools.count(0, 5)), \
                patch.object(probe.time, 'sleep'), self.assertRaisesRegex(probe.ProbeFailure, 'discover'):
            self.execute()
        self.nm.close.assert_called_once()
        self.nm.activate.assert_not_called()
        self.commands.assert_any_call(['iw', 'dev', 'wrnmtest', 'del'])

    def test_activation_timeout_cleans_up_without_claiming_success(self):
        self.nm.state.return_value = 1
        with patch.object(probe.time, 'monotonic', side_effect=itertools.count(0, 5)), \
                patch.object(probe.time, 'sleep'), self.assertRaises(probe.ProbeFailure) as caught:
            self.execute()
        self.assertFalse(caught.exception.result['activation_verified'])
        self.nm.deactivate.assert_called_once()

    def test_active_connection_loss_stops_observation(self):
        self.nm.state.side_effect = [2, 4]
        with self.assertRaisesRegex(probe.ProbeFailure, 'stopped during observation'):
            self.execute()
        self.nm.deactivate.assert_called_once()

    def test_cleanup_runs_even_when_status_observer_fails(self):
        def callback(event):
            if event['stage'] == 'stopping':
                raise OSError('Observer disconnected')
        with contextlib.redirect_stderr(io.StringIO()):
            result = self.execute(event_callback=lambda e: callback(e) if e['event'] == 'stage' else None)
        self.nm.deactivate.assert_called_once()
        self.nm.close.assert_called_once()
        self.commands.assert_any_call(['iw', 'dev', 'wrnmtest', 'del'])
        self.assertEqual(result['outcome'], 'failed')
        self.assertIn('Observer disconnected', '; '.join(result['cleanup_errors']))

    def test_terminal_status_observer_failure_is_retained_in_report(self):
        def callback(event):
            if event.get('stage') == 'passed':
                raise OSError('Terminal observer failed')
        with contextlib.redirect_stderr(io.StringIO()):
            result = self.execute(event_callback=callback)
        self.assertEqual(result['outcome'], 'failed')
        self.assertIn('Terminal observer failed', '; '.join(result['cleanup_errors']))


if __name__ == "__main__":
    unittest.main()
