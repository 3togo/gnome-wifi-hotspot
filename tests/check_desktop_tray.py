"""Run separately: GTK3 tray and GTK4 settings cannot share one process."""
from pathlib import Path
import sys
import os
from unittest.mock import Mock, patch

sys.path.insert(0, os.environ.get('WIFI_RELAY_TEST_SETTINGS_DIR') or
                str(Path(__file__).resolve().parents[1] / 'settings'))
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
race.code_revision.removed.return_value = False
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


# Removing the optional tray exits the GUI without stopping service-owned sharing.
removed = HotspotTray()
removed.proxy = Mock()
removed.quit = Mock()
removed.code_revision.removed = lambda: True
assert removed._poll() == GLib.SOURCE_REMOVE
removed.quit.assert_called_once()
removed.proxy.call.assert_not_called()
print('Tray removal exits controls without a network operation.')

# About remains usable with an unavailable service and performs no network call.
about_tray = HotspotTray()
about_tray.indicator = Mock()
about_tray.status = {'active': False, 'unavailable': True}
about_tray._render()
about_item = next(item for item in about_tray.menu.get_children()
                  if item.get_label() == 'About')
assert about_item.get_sensitive()
with patch('tray.Gio.Subprocess.new') as launch:
    about_item.activate()
    command = launch.call_args.args[0]
    assert command[-1] == '--about'
    assert Path(command[1]).name == 'launcher.py'
assert about_tray.proxy is None
assert about_tray.status == {'active': False, 'unavailable': True}
print('About opens independently of the hotspot service.')

# Quit stops sharing (including pending recovery) before closing controls.
for status in [{'active': True}, {'active': False, 'desired_active': True, 'state': 'waiting'}, {'active': False}]:
    quitting = HotspotTray()
    quitting.indicator = Mock()
    quitting.proxy = Mock()
    quitting.quit = Mock()
    quitting._query = Mock()
    quitting.status = status.copy()
    quitting._render()
    next(item for item in quitting.menu.get_children() if item.get_label() == 'Quit').activate()
    assert quitting.proxy.call.call_args.args[0] == 'Stop'
    assert quitting.busy
    quitting.quit.assert_not_called()
    callback = quitting.proxy.call.call_args.args[-1]
    quitting.proxy.call_finish.return_value = GLib.Variant('(b)', (True,))
    callback(quitting.proxy, None)
    quitting.quit.assert_called_once()
    quitting._query.assert_not_called()

# A denied or failed Stop must leave the tray available for retry.
failed_quit = HotspotTray()
failed_quit.indicator = Mock()
failed_quit.proxy = Mock()
failed_quit.quit = Mock()
failed_quit._error = Mock()
failed_quit._query = Mock()
failed_quit._quit_hotspot(None)
callback = failed_quit.proxy.call.call_args.args[-1]
failed_quit.proxy.call_finish.return_value = GLib.Variant('(b)', (False,))
callback(failed_quit.proxy, None)
failed_quit.quit.assert_not_called()
failed_quit._error.assert_called_once()
assert not failed_quit.busy
failed_quit._quit_hotspot(None)
callback = failed_quit.proxy.call.call_args.args[-1]
failed_quit.proxy.call_finish.side_effect = GLib.Error('Authorization denied')
callback(failed_quit.proxy, None)
failed_quit.quit.assert_not_called()
assert not failed_quit.busy
print('Quit stops active or waiting sharing; failed Stop keeps controls available.')

# A package-started instance honors disabled login startup before contacting D-Bus.
disabled = HotspotTray()
disabled.quit = Mock()
with patch('tray.get_auto_start', return_value=False), patch('tray.Gio.DBusProxy.new_for_bus') as connect:
    disabled.do_activate()
    disabled.quit.assert_called_once()
    connect.assert_not_called()
assert disabled.indicator is None
print('Package-started tray respects disabled startup without contacting the service.')
