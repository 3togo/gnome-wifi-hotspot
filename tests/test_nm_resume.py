"""Automatic sharing must retain explicit intent and its original upstream."""
import unittest
from unittest.mock import Mock, patch
from test_nm_backend import module, CONFIG, PROFILE

UPSTREAM = (PROFILE, 'ssid', 'bssid', 2467)

class ResumeTests(unittest.TestCase):
    def setUp(self):
        patch.object(module, 'recover').start()
        self.addCleanup(patch.stopall)
        self.backend = module.Backend()
        self.backend._desired_config = dict(CONFIG)
        self.backend._upstream_uuid = PROFILE
        self.clock = patch.object(module.time, 'monotonic', return_value=100).start()
        self.snapshot = patch.object(module.probe, 'upstream_snapshot', return_value=UPSTREAM).start()
        self.inspect = patch.object(module.probe, 'inspect', return_value={
            'eligible_for_live_probe': True, 'blockers': []}).start()
        self.start = patch.object(self.backend, 'start').start()

    def stable(self):
        self.backend.poll(CONFIG)
        self.clock.return_value += 4
        return self.backend.poll(CONFIG)

    def test_read_status_never_starts_sharing(self):
        status = self.backend.get_status()
        self.assertFalse(status['active'])
        self.assertTrue(status['desired_active'])
        self.assertEqual(status['state'], 'waiting')
        self.start.assert_not_called()
        self.snapshot.assert_not_called()
        self.assertNotIn('private-password', str(status))

    def test_stable_original_profile_rechecks_eligibility_and_starts_asynchronously(self):
        self.stable()
        self.inspect.assert_called_once()
        self.start.assert_called_once_with(CONFIG, automatic=True)

    def test_other_profile_never_resumes(self):
        self.snapshot.return_value = ('different', *UPSTREAM[1:])
        self.stable()
        self.start.assert_not_called()
        self.inspect.assert_not_called()

    def test_missing_association_never_resumes(self):
        self.snapshot.return_value = (PROFILE, '', '', 0)
        self.stable()
        self.start.assert_not_called()

    def test_channel_change_restarts_stability_timer(self):
        self.backend.poll(CONFIG)
        self.clock.return_value += 4
        self.snapshot.return_value = (*UPSTREAM[:3], 2412)
        self.backend.poll(CONFIG)
        self.start.assert_not_called()
        self.clock.return_value += 4
        self.backend.poll(CONFIG)
        self.start.assert_called_once()

    def test_regulatory_block_does_not_launch_and_backs_off(self):
        self.inspect.return_value = {'eligible_for_live_probe': False, 'blockers': ['no IR']}
        status = self.stable()
        self.assertEqual(status['error'], 'no IR')
        self.start.assert_not_called()
        self.clock.return_value += 2
        self.backend.poll(CONFIG)
        self.inspect.assert_called_once()

    def test_spawn_error_retains_intent_and_backs_off(self):
        self.start.side_effect = RuntimeError('worker failed')
        status = self.stable()
        self.assertTrue(status['desired_active'])
        self.clock.return_value += 2
        self.backend.poll(CONFIG)
        self.start.assert_called_once()

    def test_stop_while_waiting_cancels_future_recovery(self):
        self.backend.stop()
        self.stable()
        self.assertFalse(self.backend.get_status()['desired_active'])
        self.start.assert_not_called()

    def test_config_change_requires_new_start(self):
        status = self.backend.poll({**CONFIG, 'SSID': 'Changed'})
        self.assertFalse(status['desired_active'])
        self.start.assert_not_called()

    def test_default_normalization_does_not_cancel_intent(self):
        conf = {k: v for k, v in CONFIG.items() if v != module.probe.daemon.CONFIG_DEFAULTS.get(k)}
        self.backend.poll(conf)
        self.assertTrue(self.backend.get_status()['desired_active'])

    def test_sleep_preserves_intent_and_resume_waits_for_stability(self):
        self.backend.prepare_for_sleep(True)
        self.stable()
        self.start.assert_not_called()
        self.backend.prepare_for_sleep(False)
        self.clock.return_value += 4
        self.stable()
        self.start.assert_called_once()

    def test_cleanup_pending_prevents_reactivation(self):
        self.backend._recovery_pending = True
        with patch.object(self.backend, '_recover_owned', side_effect=RuntimeError('NM unavailable')):
            self.stable()
        self.start.assert_not_called()

    def test_no_previous_start_never_resumes(self):
        self.backend._desired_config = None
        self.stable()
        self.start.assert_not_called()

    def test_backend_switch_rejected_while_waiting(self):
        from test_band_fallback import Daemon
        daemon = Daemon.__new__(Daemon)
        daemon._read_config_dict = Mock(return_value=CONFIG)
        daemon._get_status_dict = Mock(return_value={'active': False, 'desired_active': True})
        with self.assertRaisesRegex(ValueError, 'Stop the hotspot'):
            daemon._write_config_dict({'BACKEND': 'create_ap'})

    def test_radio_off_cancels_waiting_intent(self):
        from test_band_fallback import Daemon
        daemon = Daemon.__new__(Daemon)
        daemon.is_starting = False
        daemon._suspending = False
        daemon._get_status_dict = Mock(return_value={'active': False, 'desired_active': True})
        daemon.method_stop = Mock()
        parameters = Mock()
        parameters.unpack.return_value = ('org.freedesktop.NetworkManager', {'WirelessEnabled': False}, [])
        daemon._on_nm_properties_changed(None, None, None, None, None, parameters, None)
        daemon.method_stop.assert_called_once()

    def test_sleep_radio_change_preserves_intent(self):
        from test_band_fallback import Daemon
        daemon = Daemon.__new__(Daemon)
        daemon.is_starting = False
        daemon._suspending = True
        daemon.method_stop = Mock()
        parameters = Mock()
        parameters.unpack.return_value = ('org.freedesktop.NetworkManager', {'WirelessEnabled': False}, [])
        daemon._on_nm_properties_changed(None, None, None, None, None, parameters, None)
        daemon.method_stop.assert_not_called()
