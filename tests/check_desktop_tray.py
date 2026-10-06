"""Run separately: GTK3 tray and GTK4 settings cannot share one process."""
from pathlib import Path
import sys
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'settings'))
from tray import HotspotTray, GLib

app = HotspotTray()
app.indicator = Mock()
app.proxy = Mock()
app._query = Mock()
app._error = Mock()
app._render()
assert app.indicator.set_icon_full.call_args.args[0] == 'wifi-hotspot-off'
app._toggle(None)
assert app.indicator.set_icon_full.call_args.args[0] == 'wifi-hotspot-connecting'
assert app.menu.get_children()[1].get_sensitive() is False
callback = app.proxy.call.call_args.args[-1]
app.proxy.call_finish.return_value = GLib.Variant('(s)', ('{"success":false,"error":"No channel"}',))
callback(app.proxy, None)
assert app.indicator.set_icon_full.call_args.args[0] == 'wifi-hotspot-off'
assert app.menu.get_children()[1].get_sensitive() is True
app._error.assert_called_once_with('No channel')
app._signal(None, None, 'StatusChanged', GLib.Variant('(s)', ('{"active":true,"ssid":"Test"}',)))
assert app.indicator.set_icon_full.call_args.args[0] == 'wifi-hotspot-on'
assert app.menu.get_children()[1].get_active() is True
app._signal(None, None, 'StatusChanged', GLib.Variant('(s)', ('{"active":true,"state":"stopping"}',)))
assert app.indicator.set_icon_full.call_args.args[0] == 'wifi-hotspot-connecting'
assert 'Stopping' in app.indicator.set_icon_full.call_args.args[1]
app._signal(None, None, 'StatusChanged', GLib.Variant('(s)', ('{"active":false}',)))
assert app.indicator.set_icon_full.call_args.args[0] == 'wifi-hotspot-off'
print('Desktop tray state, menu sensitivity, and startup failure checks passed.')
