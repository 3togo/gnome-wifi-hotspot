"""Verify the shared D-Bus client contract without touching host networking."""
import unittest
from unittest.mock import Mock, patch
from daemon import nm_client


class NetworkManagerClientTests(unittest.TestCase):
    def test_subscribes_before_activation_and_binds_volatile_profile(self):
        bus = Mock()
        bus.signal_subscribe.return_value = 12
        bus.call_sync.return_value.unpack.return_value = ('/profile/1', '/active/1', {})
        with patch.object(nm_client.Gio, 'dbus_address_get_for_bus_sync', return_value='private-test-bus'), \
             patch.object(nm_client.Gio.DBusConnection, 'new_for_address_sync', return_value=bus):
            client = nm_client.NetworkManager()
        self.assertEqual(bus.signal_subscribe.call_count, 1)
        bus.call_sync.assert_not_called()
        self.assertEqual(client.activate('/device/1', {}), '/active/1')
        call = bus.call_sync.call_args.args
        self.assertEqual(call[:4], (nm_client.NM_NAME, nm_client.NM_PATH, nm_client.NM_NAME, 'AddAndActivateConnection2'))
        profile, device, specific, options = call[4].unpack()
        self.assertEqual((device, specific), ('/device/1', '/'))
        self.assertEqual(options, {'persist': 'volatile', 'bind-activation': 'dbus-client'})
        client.close()
        bus.signal_unsubscribe.assert_called_once_with(12)
        bus.close_sync.assert_called_once_with(None)
