"""Run separately: GTK3 tray and GTK4 settings cannot share one process."""
from pathlib import Path
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'settings'))
from tray import HotspotTray, GLib, AppIndicator

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

# Visibility updates neither call Start/Stop nor discard the sharing state.
app.status = {'active': True, 'desired_active': True}
app.proxy.reset_mock()
with patch('tray.get_auto_start', return_value=True), \
        patch('tray.get_tray_visible', return_value=False):
    assert app._poll() == GLib.SOURCE_CONTINUE
    app.indicator.set_status.assert_called_with(AppIndicator.IndicatorStatus.PASSIVE)
    app.do_activate()
    app.indicator.set_status.assert_called_with(AppIndicator.IndicatorStatus.PASSIVE)
assert app.status['active'] and app.status['desired_active']
app.proxy.call.assert_not_called()
with patch('tray.get_tray_visible', return_value=True):
    app.do_activate()
    app.indicator.set_status.assert_called_with(AppIndicator.IndicatorStatus.ACTIVE)
command = Mock()
command.get_options_dict.return_value.contains.return_value = True
app.activate = Mock()
assert app.do_command_line(command) == 0
assert app.manual_start
app.activate.assert_called_once()
app.quit = Mock()
with patch('tray.get_auto_start', return_value=False), \
        patch('tray.get_tray_visible', return_value=True):
    assert app._poll() == GLib.SOURCE_CONTINUE
app.quit.assert_not_called()
app.manual_start = False
with patch('tray.get_auto_start', return_value=False):
    assert app._poll() == GLib.SOURCE_REMOVE
app.quit.assert_called_once()
print('Visibility, explicit launch, and independent sharing/startup checks passed.')

# A delayed client reply must not overwrite a newer Stop signal.
race = HotspotTray()
race.indicator = Mock()
race.proxy = Mock()
race._query()
status_callback = race.proxy.call.call_args.args[-1]
race.proxy.call_finish.return_value = GLib.Variant('(s)', ('{"active":true}',))
status_callback(race.proxy, None)
clients_callback = race.proxy.call.call_args.args[-1]
race._signal(None, None, 'StatusChanged', GLib.Variant('(s)', ('{"active":false}',)))
race.proxy.call_finish.return_value = GLib.Variant('(s)', ('[{"ip":"192.168.12.2"}]',))
clients_callback(race.proxy, None)
assert race.clients == []
assert race.status == {'active': False}

# Reload only once and defer it while an operation is running.
race.code_revision = Mock()
race.code_revision.changed.return_value = True
race.busy = True
with patch('tray.GLib.idle_add') as schedule, patch('tray.get_auto_start', return_value=True):
    race._poll()
    schedule.assert_not_called()
    race.busy = False
    race._poll()
    race._poll()
    schedule.assert_called_once()
race.manual_start = True
race._close = Mock()
with patch('tray.sys.argv', ['tray.py']), patch('tray.os.execv') as replace:
    race._restart_after_upgrade()
    assert replace.call_args.args[1][-1] == '--show-icon'
race._close.assert_called_once()
print('Stale clients, deferred code upgrade, and manual launch preservation checks passed.')
