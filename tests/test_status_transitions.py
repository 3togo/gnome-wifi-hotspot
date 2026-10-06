"""Verify tray state signals for operations started by any D-Bus client."""
import json
import unittest
from unittest.mock import Mock

from test_band_fallback import Daemon


class StatusTransitionTests(unittest.TestCase):
    def test_operations_broadcast_transition_then_final_status(self):
        for method, state, active in [
            ('Start', 'connecting', True),
            ('Stop', 'stopping', False),
            ('SwitchBandAndReconnect', 'connecting', False),
        ]:
            with self.subTest(method=method):
                daemon = Daemon.__new__(Daemon)
                daemon._authorize = lambda sender, callback: callback(True)
                daemon.cached_status_active = method == 'Stop'
                daemon.cached_clients = []
                daemon._emit_signal = Mock()
                daemon._get_status_dict = Mock(return_value={'active': active})
                def operation(*args):
                    signal = daemon._emit_signal.call_args
                    self.assertEqual(signal.args[0], 'StatusChanged')
                    self.assertEqual(json.loads(signal.args[1])['state'], state)
                    return True if method == 'Stop' else '{"success": true}'
                daemon.method_start = operation
                daemon.method_stop = operation
                daemon.switch_band_and_reconnect = operation
                invocation = Mock()
                parameters = Mock()
                parameters.unpack.return_value = ['2.4']
                daemon.handle_method_call(None, None, None, None, method, parameters, invocation)
                invocation.return_value.assert_called_once()
                invocation.return_error_literal.assert_not_called()
                final = json.loads(daemon._emit_signal.call_args.args[1])
                self.assertEqual(final, {'active': active})

    def test_failed_start_clears_connecting_state(self):
        daemon = Daemon.__new__(Daemon)
        daemon._authorize = lambda sender, callback: callback(True)
        daemon.cached_status_active = False
        daemon.cached_clients = []
        daemon._emit_signal = Mock()
        daemon._get_status_dict = Mock(return_value={'active': False})
        daemon.method_start = Mock(side_effect=RuntimeError('start failed'))
        invocation = Mock()
        daemon.handle_method_call(None, None, None, None, 'Start', None, invocation)
        invocation.return_error_literal.assert_called_once()
        self.assertEqual(json.loads(daemon._emit_signal.call_args.args[1]), {'active': False})
