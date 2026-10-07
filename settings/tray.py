#!/usr/bin/python3
"""StatusNotifier tray for desktops that do not run GNOME Shell."""
import json
from pathlib import Path
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, Gio, GLib, AyatanaAppIndicator3 as AppIndicator

from startup import get_auto_start

BUS_NAME = 'io.github.erhanzeyrek.WifiHotspot'
OBJECT_PATH = '/io/github/erhanzeyrek/WifiHotspot'


class HotspotTray(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=BUS_NAME + '.Tray')
        self.proxy = None
        self.indicator = None
        self.status = {'active': False}
        self.clients = []
        self.busy = False
        self.revision = 0
        self.query_pending = False

    def do_activate(self):
        if self.indicator:
            return
        if not get_auto_start():
            self.quit()
            return
        self.hold()
        icon_dir = Path(__file__).resolve().parent / 'icons'
        self.indicator = AppIndicator.Indicator.new_with_path(
            'wifi-hotspot', 'wifi-hotspot-off',
            AppIndicator.IndicatorCategory.HARDWARE, str(icon_dir))
        self.indicator.set_title('Wi-Fi Relay')
        self._render()
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
            BUS_NAME, OBJECT_PATH, BUS_NAME, None, self._proxy_ready)
        GLib.timeout_add_seconds(3, self._poll)

    def _proxy_ready(self, _source, result):
        try:
            self.proxy = Gio.DBusProxy.new_for_bus_finish(result)
            self.proxy.set_default_timeout(60000)
            self.proxy.connect('g-signal', self._signal)
            self._query()
        except GLib.Error as error:
            self._error(str(error))

    def _signal(self, _proxy, _sender, name, parameters):
        try:
            data = json.loads(parameters.unpack()[0])
            if name == 'StatusChanged':
                self.status = data
                self.revision += 1
            elif name == 'ClientsChanged':
                self.clients = data
                self.status['client_count'] = len(data)
            else:
                return
            self._render()
        except (ValueError, TypeError, IndexError):
            pass

    def _poll(self):
        if not get_auto_start():
            self.indicator.set_status(AppIndicator.IndicatorStatus.PASSIVE)
            self.quit()
            return GLib.SOURCE_REMOVE
        self._query()
        return GLib.SOURCE_CONTINUE

    def _query(self):
        if not self.proxy or self.busy or self.query_pending:
            return
        revision = self.revision
        self.query_pending = True
        def finished(proxy, result):
            self.query_pending = False
            try:
                status = json.loads(proxy.call_finish(result).unpack()[0])
                if revision != self.revision:
                    return
                self.status = status
                self.revision += 1
                self._render()
                if status.get('active'):
                    self.proxy.call('GetClients', None, Gio.DBusCallFlags.NONE,
                                    10000, None, clients_finished)
            except (GLib.Error, ValueError, TypeError):
                if revision == self.revision:
                    self.status = {'active': False, 'unavailable': True}
                    self._render()
        def clients_finished(proxy, result):
            try:
                if not self.status.get('active') or self.busy:
                    return
                self.clients = json.loads(proxy.call_finish(result).unpack()[0])
                self.status['client_count'] = len(self.clients)
                self._render()
            except (GLib.Error, ValueError, TypeError):
                pass
        self.proxy.call('GetStatus', None, Gio.DBusCallFlags.NONE,
                        10000, None, finished)

    def _render(self):
        stopping = self.status.get('state') == 'stopping'
        transition = self.busy or self.status.get('state') in ('connecting', 'stopping')
        active = bool(self.status.get('active'))
        requested = active or bool(self.status.get('desired_active'))
        state = 'connecting' if transition or (requested and not active) else 'on' if active else 'off'
        label = ('Stopping…' if stopping else 'Connecting…') if transition else 'On' if active else 'Waiting for Wi-Fi' if requested else 'Off'
        self.indicator.set_icon_full('wifi-hotspot-' + state, 'Wi-Fi Relay: ' + label)
        menu = Gtk.Menu()
        status_item = Gtk.MenuItem(label='Wi-Fi Relay: ' + label)
        status_item.set_sensitive(False)
        menu.append(status_item)
        switch = Gtk.CheckMenuItem(label='Enable hotspot')
        switch.set_active(requested)
        switch.set_sensitive(not self.busy and not stopping and
                             (self.status.get('state') != 'connecting' or requested) and self.proxy is not None)
        switch.connect('toggled', self._toggle)
        menu.append(switch)
        if self.status.get('unavailable'):
            row = Gtk.MenuItem(label='Hotspot service unavailable')
            row.set_sensitive(False)
            menu.append(row)
        if active:
            for text in ['SSID: ' + self.status.get('ssid', 'Hotspot'),
                         f"Connected devices: {self.status.get('client_count', len(self.clients))}"]:
                row = Gtk.MenuItem(label=text)
                row.set_sensitive(False)
                menu.append(row)
            for client in self.clients:
                text = client.get('hostname') or 'Device'
                if client.get('ip'):
                    text += f" ({client['ip']})"
                row = Gtk.MenuItem(label=text)
                row.set_sensitive(False)
                menu.append(row)
        menu.append(Gtk.SeparatorMenuItem())
        settings = Gtk.MenuItem(label='Hotspot Settings')
        settings.connect('activate', self._open_settings)
        menu.append(settings)
        menu.show_all()
        self.menu = menu
        self.indicator.set_menu(menu)

    def _toggle(self, _item):
        if (self.busy or not self.proxy or self.status.get('state') == 'stopping' or
                (self.status.get('state') == 'connecting' and not self.status.get('desired_active'))):
            return
        method = 'Stop' if (self.status.get('active') or self.status.get('desired_active')) else 'Start'
        self.busy = True
        self.status['state'] = 'stopping' if method == 'Stop' else 'connecting'
        self.revision += 1
        self._render()
        def finished(proxy, result):
            self.busy = False
            self.status.pop('state', None)
            try:
                value = proxy.call_finish(result).unpack()[0]
                if method == 'Start':
                    response = json.loads(value)
                    if not response.get('success'):
                        self._error(response.get('error', 'Hotspot failed to start.'))
                    elif response.get('status'):
                        self.status = response['status']
                elif not value:
                    self._error('Hotspot could not be stopped.')
            except (GLib.Error, ValueError) as error:
                self._error(str(error))
            self.revision += 1
            self._render()
            self._query()
        self.proxy.call(method, None, Gio.DBusCallFlags.NONE, 60000, None, finished)

    def _open_settings(self, _item):
        Gio.Subprocess.new(['/usr/bin/python3', str(Path(__file__).resolve().parent / 'main.py')],
                           Gio.SubprocessFlags.NONE)

    def _error(self, message):
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE, text='Wi-Fi Relay')
        dialog.format_secondary_text(message)
        dialog.connect('response', lambda widget, _response: widget.destroy())
        dialog.show_all()


if __name__ == '__main__':
    sys.exit(HotspotTray().run(sys.argv))
