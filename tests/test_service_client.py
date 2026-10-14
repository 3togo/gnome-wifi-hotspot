"""Desktop transport, generation fencing, and serialized configuration writes."""
import unittest
from unittest.mock import Mock
from gi.repository import GLib
from settings.service_client import ServiceClient, ConfigurationWriter, decode_reply, MAX_REPLY_BYTES


class ProtocolTests(unittest.TestCase):
    def reply(self, value):
        import json
        return GLib.Variant('(s)', (json.dumps(value),))

    def test_status_requires_real_booleans_and_a_nonnegative_count(self):
        for value in [{'active': 'false'}, {'active': False, 'desired_active': 1},
                      {'active': True, 'client_count': -1}, {'active': True, 'error': {}}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_reply('GetStatus', self.reply(value))

    def test_transition_status_does_not_require_optional_fields(self):
        self.assertEqual(decode_reply('GetStatus', self.reply({'active': False})), {'active': False})

    def test_clients_and_interfaces_reject_wrong_shapes(self):
        for method, value in [('GetClients', [1]), ('GetClients', [{'hostname': {}}]),
                              ('GetInterfaces', {'wifi_interfaces': 'wlo2', 'all_interfaces': []}),
                              ('GetConfig', {'SSID': False}), ('Start', {'success': 'yes'}),
                              ('Start', {'success': True, 'status': 'invalid'}),
                              ('Start', {'success': False, 'error': {}})]:
            with self.subTest(method=method), self.assertRaises(ValueError):
                decode_reply(method, self.reply(value))

    def test_boolean_methods_reject_string_replies(self):
        with self.assertRaises(ValueError):
            decode_reply('Stop', GLib.Variant('(s)', ('false',)))

    def test_reply_size_limit_counts_utf8_bytes(self):
        # A character count would admit a reply twice the permitted size.
        reply = GLib.Variant('(s)', ('{"SSID":"' + 'é' * (MAX_REPLY_BYTES // 2) + '"}',))
        with self.assertRaises(ValueError):
            decode_reply('GetConfig', reply)

    def test_malformed_json_and_excessive_nesting_are_rejected(self):
        for payload in ['{', '[' * 2000 + '0' + ']' * 2000]:
            with self.subTest(payload=payload[:20]), self.assertRaises(ValueError):
                decode_reply('GetStatus', GLib.Variant('(s)', (payload,)))

    def test_client_limit_and_boolean_client_count(self):
        self.assertEqual(len(decode_reply('GetClients', self.reply([{}] * 1024))), 1024)
        for method, value in [('GetClients', [{}] * 1025),
                              ('GetStatus', {'active': True, 'client_count': True})]:
            with self.subTest(method=method), self.assertRaises(ValueError):
                decode_reply(method, self.reply(value))


class ServiceClientTests(unittest.TestCase):
    def setUp(self):
        self.client = ServiceClient.__new__(ServiceClient)
        self.client.proxy = Mock()
        self.client.cancel = Mock()
        self.client.closed = False
        self.client.generation = 0
        self.client._ready = Mock()
        self.client._signal = Mock()
        self.client._handlers = [1, 2]

    def complete(self, value):
        self.client.proxy.call_finish.return_value = GLib.Variant('(s)', (value,))
        self.client.proxy.call.call_args.args[-1](self.client.proxy, None)

    def test_call_returns_before_the_service_replies(self):
        callback = Mock()
        self.client.call('GetStatus', callback)
        callback.assert_not_called()
        self.complete('{"active":true}')
        callback.assert_called_once_with({'active': True}, None)

    def test_old_owner_reply_cannot_override_new_service_state(self):
        callback = Mock()
        self.client.call('GetStatus', callback)
        self.client._owner_changed(None, None)
        self.complete('{"active":true}')
        self.assertIsNone(callback.call_args.args[0])
        self.assertIn('restarted', str(callback.call_args.args[1]))

    def test_close_cancels_requests_and_ignores_late_callbacks(self):
        callback = Mock()
        self.client.call('GetStatus', callback)
        self.client.close(); self.client.close()
        self.complete('{"active":true}')
        callback.assert_not_called()
        self.client.cancel.cancel.assert_called_once()
        self.assertEqual(self.client.proxy.disconnect.call_count, 2)

    def test_malformed_signal_does_not_reach_widgets(self):
        self.client._on_signal(None, None, 'StatusChanged', GLib.Variant('(s)', ('[]',)))
        self.client._signal.assert_not_called()

    def test_unavailable_service_reports_error_without_sending(self):
        proxy = self.client.proxy
        self.client.proxy = None
        callback = Mock()
        self.client.call('GetStatus', callback)
        proxy.call.assert_not_called()
        callback.assert_called_once()
        self.assertIsNone(callback.call_args.args[0])
        self.assertIsInstance(callback.call_args.args[1], RuntimeError)

    def test_transport_and_decode_failures_reach_callback(self):
        for failure in [GLib.Error('Service disconnected'), ValueError('Invalid reply')]:
            with self.subTest(failure=failure):
                callback = Mock()
                self.client.call('GetStatus', callback)
                self.client.proxy.call_finish.side_effect = failure
                self.client.proxy.call.call_args.args[-1](self.client.proxy, None)
                callback.assert_called_once_with(None, failure)

    def test_valid_signals_are_forwarded_but_closed_and_unknown_signals_are_ignored(self):
        reply = GLib.Variant('(s)', ('{"active":false}',))
        self.client._on_signal(None, None, 'StatusChanged', reply)
        self.client._signal.assert_called_once_with('StatusChanged', {'active': False})
        signal = self.client._signal
        self.client._on_signal(None, None, 'Unknown', reply)
        self.client.close()
        self.client._on_signal(None, None, 'StatusChanged', reply)
        self.assertEqual(signal.call_count, 1)


class ConfigurationWriterTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock(closed=False)
        self.writer = ConfigurationWriter(self.client)

    def finish(self, value=True, error=None):
        self.client.call.call_args.args[1](value, error)

    def test_latest_edit_is_saved_after_inflight_write_and_before_start_callback(self):
        first, second, start = Mock(), Mock(), Mock()
        self.writer.submit({'SSID': 'Old'}, first)
        self.writer.submit({'SSID': 'Partial'}, second)
        self.writer.submit({'SSID': 'Latest'}, start)
        self.assertEqual(self.client.call.call_count, 1)
        start.assert_not_called()
        self.finish()
        self.assertEqual(self.client.call.call_count, 2)
        start.assert_not_called()
        self.finish()
        first.assert_called_once_with({'SSID': 'Old'}, None)
        second.assert_called_once_with({'SSID': 'Latest'}, None)
        start.assert_called_once_with({'SSID': 'Latest'}, None)

    def test_failed_save_is_reported_instead_of_starting(self):
        start = Mock()
        self.writer.submit({'SSID': 'Latest'}, start)
        self.finish(False)
        self.assertIsInstance(start.call_args.args[1], RuntimeError)
        self.assertFalse(self.writer.inflight)

    def test_closed_client_never_sends_another_write(self):
        self.client.closed = True
        self.writer.submit({'SSID': 'Latest'}, Mock())
        self.client.call.assert_not_called()

    def test_submitted_config_is_a_snapshot(self):
        import json
        config = {'SSID': 'Original'}
        callback = Mock()
        self.writer.submit(config, callback)
        config['SSID'] = 'Changed'
        parameters = self.client.call.call_args.args[2]
        self.assertEqual(json.loads(parameters.unpack()[0]), {'SSID': 'Original'})
        self.finish()
        callback.assert_called_once_with({'SSID': 'Original'}, None)

    def test_failed_inflight_write_does_not_discard_newer_edit(self):
        first, latest = Mock(), Mock()
        self.writer.submit({'SSID': 'Old'}, first)
        self.writer.submit({'SSID': 'Latest'}, latest)
        error = GLib.Error('Authorization denied')
        self.finish(None, error)
        first.assert_called_once_with({'SSID': 'Old'}, error)
        latest.assert_not_called()
        self.assertEqual(self.client.call.call_count, 2)
        self.finish()
        latest.assert_called_once_with({'SSID': 'Latest'}, None)
        self.assertFalse(self.writer.inflight)

    def test_close_during_write_suppresses_callbacks_and_pending_write(self):
        first, latest = Mock(), Mock()
        self.writer.submit({'SSID': 'Old'}, first)
        self.writer.submit({'SSID': 'Latest'}, latest)
        self.client.closed = True
        self.finish()
        first.assert_not_called()
        latest.assert_not_called()
        self.assertEqual(self.client.call.call_count, 1)
