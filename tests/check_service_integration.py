"""Real desktop transport and production daemon authorization on a private bus."""
import json
import unittest
from private_service import PrivateService, ServiceClient, wait_until, GLib, Gio, BUS_NAME, POLKIT_NAME


class ServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.service = PrivateService()
        self.addCleanup(self.service.close)
        self.ready = []
        self.signals = []
        self.client = ServiceClient(self.ready.append, lambda *args: self.signals.append(args))
        self.addCleanup(self.client.close)
        wait_until(lambda: self.ready and self.client.proxy.get_name_owner())
        self.assertIsNone(self.ready[-1])

    def call(self, method, parameters=None, timeout=1000):
        replies = []
        self.client.call(method, lambda *args: replies.append(args), parameters, timeout)
        wait_until(lambda: replies)
        return replies[0]

    def test_configuration_roundtrip_is_authorized_and_private(self):
        data, error = self.call('SetConfig', GLib.Variant('(s)', (json.dumps({'SSID': 'Saved relay'}),)))
        self.assertIsNone(error)
        self.assertTrue(data)
        data, error = self.call('GetConfig')
        self.assertIsNone(error)
        self.assertEqual(data['SSID'], 'Saved relay')
        self.assertEqual(data['PASSPHRASE'], 'synthetic-password')
        self.assertEqual(self.service.config_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(self.service.authorizations), 2)
        subject, action, _details, flags, _cancellation = self.service.authorizations[0]
        self.assertEqual(subject, ('system-bus-name', {'name': self.client.proxy.get_connection().get_unique_name()}))
        self.assertEqual(action, BUS_NAME + '.manage')
        self.assertEqual(flags, 1)

    def test_denied_mutations_never_change_configuration_or_start_hardware(self):
        original = self.service.config_path.read_bytes()
        self.service.allowed = False
        for method, parameters in [('Start', None), ('Stop', None), ('GetConfig', None),
                                   ('SetConfig', GLib.Variant('(s)', ('{"SSID":"Denied"}',)))]:
            with self.subTest(method=method):
                data, error = self.call(method, parameters)
                self.assertIsNone(data)
                self.assertTrue(error.matches(Gio.DBusError.quark(), Gio.DBusError.ACCESS_DENIED))
        self.assertEqual(self.service.config_path.read_bytes(), original)
        self.assertEqual(self.service.daemon.operations, [])
        data, error = self.call('GetStatus')
        self.assertEqual(data, {'active': False})
        self.assertIsNone(error)
        self.assertEqual(len(self.service.authorizations), 4)

    def test_missing_polkit_fails_closed(self):
        self.service.name('ReleaseName', POLKIT_NAME)
        data, error = self.call('Start')
        self.assertIsNone(data)
        self.assertTrue(error.matches(Gio.DBusError.quark(), Gio.DBusError.ACCESS_DENIED))
        self.assertEqual(self.service.daemon.operations, [])

    def test_invalid_configuration_returns_invalid_args_without_a_write(self):
        original = self.service.config_path.read_bytes()
        data, error = self.call('SetConfig', GLib.Variant('(s)', ('{"PASSPHRASE":"short"}',)))
        self.assertIsNone(data)
        self.assertTrue(error.matches(Gio.DBusError.quark(), Gio.DBusError.INVALID_ARGS))
        self.assertEqual(self.service.config_path.read_bytes(), original)

    def test_start_stop_replies_and_signals_reach_real_client(self):
        data, error = self.call('Start')
        self.assertIsNone(error)
        self.assertTrue(data['success'])
        wait_until(lambda: any(name == 'StatusChanged' and status.get('active') for name, status in self.signals))
        data, error = self.call('Stop')
        self.assertTrue(data)
        self.assertIsNone(error)
        wait_until(lambda: self.signals[-1] == ('StatusChanged', {'active': False}))
        self.assertEqual(self.service.daemon.operations, ['Start', 'Stop'])

    def test_malformed_status_and_signals_are_rejected(self):
        self.service.malformed_status = '{"active":"false"}'
        data, error = self.call('GetStatus')
        self.assertIsNone(data)
        self.assertIsInstance(error, ValueError)
        self.service.daemon._emit_signal('StatusChanged', '[]')
        self.service.daemon._emit_signal('StatusChanged', '{"active":false}')
        wait_until(lambda: self.signals)
        self.assertEqual(self.signals, [('StatusChanged', {'active': False})])

    def test_timeout_returns_error_and_late_reply_is_not_delivered_twice(self):
        self.service.hold_methods.add('GetStatus')
        replies = []
        self.client.call('GetStatus', lambda *args: replies.append(args), timeout=50)
        wait_until(lambda: replies)
        self.assertIsNone(replies[0][0])
        self.assertIsInstance(replies[0][1], GLib.Error)
        self.service.reply('GetStatus', {'active': True})
        self.service.malformed_status = None
        self.service.hold_methods.clear()
        self.assertEqual(self.call('GetStatus'), ({'active': False}, None))
        self.assertEqual(len(replies), 1)

    def test_owner_loss_fences_pending_reply_and_reacquisition_recovers(self):
        self.service.hold_methods.add('GetStatus')
        replies = []
        self.client.call('GetStatus', lambda *args: replies.append(args))
        wait_until(lambda: self.service.held.get('GetStatus'))
        generation = self.client.generation
        self.service.name('ReleaseName', BUS_NAME)
        wait_until(lambda: self.client.generation > generation)
        self.service.reply('GetStatus', {'active': True})
        wait_until(lambda: replies)
        self.assertIsNone(replies[0][0])
        self.assertIn('restarted', str(replies[0][1]))
        self.service.name('RequestName', BUS_NAME)
        wait_until(lambda: self.client.proxy.get_name_owner())
        self.service.hold_methods.clear()
        self.assertEqual(self.call('GetStatus'), ({'active': False}, None))

    def test_new_service_connection_recovers_after_a_restart(self):
        owner = self.client.proxy.get_name_owner()
        generation = self.client.generation
        self.service.close()
        wait_until(lambda: self.client.generation > generation)
        self.service = PrivateService()
        self.addCleanup(self.service.close)
        wait_until(lambda: self.client.proxy.get_name_owner() == self.service.connection.get_unique_name())
        self.assertNotEqual(self.client.proxy.get_name_owner(), owner)
        self.assertEqual(self.call('GetStatus'), ({'active': False}, None))

    def test_close_cancels_inflight_call_and_ignores_late_signal(self):
        self.service.hold_methods.add('GetStatus')
        replies = []
        self.client.call('GetStatus', lambda *args: replies.append(args))
        wait_until(lambda: self.service.held.get('GetStatus'))
        self.client.close()
        self.service.reply('GetStatus', {'active': True})
        self.service.daemon._emit_signal('StatusChanged', '{"active":true}')
        # A second live client provides an event-loop barrier on the same bus.
        ready = []
        barrier = ServiceClient(ready.append)
        try:
            wait_until(lambda: ready)
        finally:
            barrier.close()
        self.assertEqual(replies, [])
        self.assertEqual(self.signals, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
