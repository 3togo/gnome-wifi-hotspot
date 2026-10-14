"""Real Relay dispatch/auth/config on a private bus; hardware is deterministic."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from gi.repository import Gio, GLib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, os.environ.get('WIFI_RELAY_TEST_SETTINGS_DIR') or str(ROOT / 'settings'))
from service_client import ServiceClient, BUS_NAME, OBJECT_PATH

DAEMON_DIR = Path(os.environ.get('WIFI_RELAY_TEST_DAEMON_DIR') or ROOT / 'daemon')
sys.path.insert(0, str(DAEMON_DIR))
spec = importlib.util.spec_from_file_location('private_relay_daemon', DAEMON_DIR / 'wifi-hotspot-daemon.py')
daemon_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daemon_module)

POLKIT_NAME = 'org.freedesktop.PolicyKit1'
POLKIT_PATH = '/org/freedesktop/PolicyKit1/Authority'
POLKIT_INTERFACE = POLKIT_NAME + '.Authority'
POLKIT_XML = f'''<node><interface name="{POLKIT_INTERFACE}">
<method name="CheckAuthorization">
<arg type="(sa{{sv}})" direction="in"/><arg type="s" direction="in"/>
<arg type="a{{ss}}" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/>
<arg type="(bba{{ss}})" direction="out"/>
</method></interface></node>'''


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        # Do not block on a main-context iteration: failed callbacks need a deadline.
        for _ in range(100):
            if not context.pending():
                break
            context.iteration(False)
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError('Private service did not reach the expected state within the deadline')


class HardwareFixture(daemon_module.WifiHotspotDaemon):
    """Replace hardware boundaries, retaining production dispatch and authorization."""
    def __init__(self, connection):
        self.connection = connection
        self.cached_clients = []
        self.cached_status_active = False
        self.status = {'active': False}
        self.operations = []

    def _run_cmd(self, *_args, **_kwargs):
        raise AssertionError('Integration fixture attempted a host command')

    def _get_status_dict(self):
        return dict(self.status)

    def _get_clients_list(self, _iface):
        return list(self.cached_clients)

    def method_get_interfaces(self):
        return json.dumps({'wifi_interfaces': ['wlan0'], 'all_interfaces': ['wlan0', 'eth0']})

    def get_capabilities(self):
        return {'ap_2ghz': True, 'ap_5ghz': True}

    def method_start(self):
        self.operations.append('Start')
        self.cached_status_active = True
        self.status = {'active': True, 'ssid': 'Integration relay', 'iface': 'wlan0'}
        return json.dumps({'success': True, 'status': self.status})

    def method_stop(self):
        self.operations.append('Stop')
        self.cached_status_active = False
        self.status = {'active': False}
        return True


class PrivateService:
    def __init__(self):
        address = os.environ.get('DBUS_SESSION_BUS_ADDRESS')
        if not address or os.environ.get('DBUS_SYSTEM_BUS_ADDRESS') != address:
            raise RuntimeError('Run on a private session bus mapped to DBUS_SYSTEM_BUS_ADDRESS')
        self.closed = False
        self.directory = tempfile.TemporaryDirectory(prefix='relay-service-')
        self.config_path = Path(self.directory.name) / 'wifi-hotspot.conf'
        self.config_path.write_text('SSID=Integration relay\nPASSPHRASE=synthetic-password\nBACKEND=create_ap\n')
        self.config_path.chmod(0o600)
        self.previous_config_path = daemon_module.get_config_path
        daemon_module.get_config_path = lambda for_write=False: str(self.config_path)
        self.connection = Gio.DBusConnection.new_for_address_sync(
            address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
            Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        self.daemon = HardwareFixture(self.connection)
        self.allowed = True
        self.authorization_results = []
        self.authorizations = []
        self.calls = []
        self.held = {}
        self.hold_methods = set()
        self.malformed_status = None
        self.registration = self.connection.register_object(
            OBJECT_PATH, Gio.DBusNodeInfo.new_for_xml(daemon_module.INTROSPECTION_XML).interfaces[0],
            self.dispatch, None, None)
        self.polkit_registration = self.connection.register_object(
            POLKIT_PATH, Gio.DBusNodeInfo.new_for_xml(POLKIT_XML).interfaces[0], self.authorize, None, None)
        self.name('RequestName', BUS_NAME)
        self.name('RequestName', POLKIT_NAME)

    def name(self, method, name):
        parameters = GLib.Variant('(su)', (name, 0)) if method == 'RequestName' else GLib.Variant('(s)', (name,))
        return self.connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', method, parameters, None, Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]

    def authorize(self, _connection, _sender, _path, _interface, _method, parameters, invocation):
        self.authorizations.append(parameters.unpack())
        allowed = self.authorization_results.pop(0) if self.authorization_results else self.allowed
        invocation.return_value(GLib.Variant('((bba{ss}))', ((allowed, not allowed, {}),)))

    def dispatch(self, connection, sender, path, interface, method, parameters, invocation):
        self.calls.append(method)
        if method in self.hold_methods:
            self.held.setdefault(method, []).append(invocation)
        elif method == 'GetStatus' and self.malformed_status is not None:
            invocation.return_value(GLib.Variant('(s)', (self.malformed_status,)))
        else:
            self.daemon.handle_method_call(connection, sender, path, interface, method, parameters, invocation)

    def reply(self, method, value):
        self.held[method].pop(0).return_value(GLib.Variant('(s)', (json.dumps(value),)))

    def close(self):
        if self.closed:
            return
        self.closed = True
        for invocations in self.held.values():
            for invocation in invocations:
                invocation.return_dbus_error('org.freedesktop.DBus.Error.Failed', 'Fixture shut down')
        self.connection.unregister_object(self.registration)
        self.connection.unregister_object(self.polkit_registration)
        self.connection.close_sync(None)
        daemon_module.get_config_path = self.previous_config_path
        self.directory.cleanup()
