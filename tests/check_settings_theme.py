"""Real GTK theme changes on a private bus, with desktop settings fixtures."""
import os
from pathlib import Path
import subprocess
import shutil
import sys
import threading
import time

if len(sys.argv) == 1:
    cases = [('GNOME', 'normal'), ('KDE', 'normal'), ('XFCE', 'normal')]
    if not os.environ.get('WIFI_RELAY_TEST_LARGE_TEXT') and not os.environ.get('WIFI_RELAY_TEST_SMALL_SCREEN'):
        cases += [('GNOME', 'large-text'), ('XFCE', 'large-text')]
        if shutil.which('xvfb-run'):
            cases += [('GNOME', 'small-screen'), ('XFCE', 'small-screen')]
        else:
            print('Small-screen checks skipped: xvfb-run is unavailable')
    for desktop, scenario in cases:
        environment = dict(os.environ, WIFI_RELAY_TEST_SCENARIO=scenario)
        command = [sys.executable, __file__, desktop]
        if scenario != 'normal':
            environment['WIFI_RELAY_TEST_LARGE_TEXT'] = '1'
        if scenario == 'small-screen':
            environment['WIFI_RELAY_TEST_SMALL_SCREEN'] = '1'
            command = ['xvfb-run', '-a', '-s', '-screen 0 800x600x24', *command]
        subprocess.run(command, env=environment, check=True, timeout=20)
    raise SystemExit(0)

os.environ['XDG_CURRENT_DESKTOP'] = sys.argv[1]
os.environ['GSETTINGS_BACKEND'] = 'memory'
# Only the fixture portal supplies a preference; do not inherit developer overrides.
os.environ.pop('ADW_DEBUG_COLOR_SCHEME', None)
os.environ.pop('GTK_THEME', None)
import gi
from gi.repository import Gio, GLib

address = os.environ['DBUS_SESSION_BUS_ADDRESS']
assert address == os.environ.get('DBUS_SYSTEM_BUS_ADDRESS'), 'Private system bus required'
PORTAL = 'org.freedesktop.portal.Desktop'
PORTAL_PATH = '/org/freedesktop/portal/desktop'
SETTINGS = 'org.freedesktop.portal.Settings'
XFCONF = 'org.xfce.Xfconf'
XFCONF_PATH = '/org/xfce/Xfconf'
XML = '''<node><interface name="org.freedesktop.portal.Settings">
<method name="Read"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
<method name="ReadOne"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
<method name="ReadAll"><arg type="as" direction="in"/><arg type="a{sa{sv}}" direction="out"/></method>
<signal name="SettingChanged"><arg type="s"/><arg type="s"/><arg type="v"/></signal>
</interface><interface name="org.xfce.Xfconf">
<method name="GetAllProperties"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
<signal name="PropertyChanged"><arg type="s"/><arg type="s"/><arg type="v"/></signal>
</interface></node>'''


class DesktopFixture:
    def __init__(self):
        self.color = 0 if sys.argv[1] == 'XFCE' else 1
        self.theme = 'Adwaita-dark'
        self.prefer_dark = False
        self.reads = 0
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()
        assert self.ready.wait(5), 'Desktop fixture did not start'

    def serve(self):
        context = GLib.MainContext.new()
        context.push_thread_default()
        self.connection = Gio.DBusConnection.new_for_address_sync(address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        for name in (PORTAL, XFCONF):
            self.name('RequestName', GLib.Variant('(su)', (name, 0)))
        interfaces = Gio.DBusNodeInfo.new_for_xml(XML).interfaces
        self.connection.register_object(PORTAL_PATH, interfaces[0], self.call, None, None)
        self.connection.register_object(XFCONF_PATH, interfaces[1], self.call, None, None)
        self.loop = GLib.MainLoop.new(context, False)
        self.ready.set()
        self.loop.run()
        self.connection.close_sync(None)
        context.pop_thread_default()

    def name(self, method, parameters):
        self.connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', method, parameters, None, 0, 2000, None)

    def call(self, _connection, _sender, _path, interface, method, parameters, invocation):
        appearance = {'color-scheme': GLib.Variant('u', self.color), 'contrast': GLib.Variant('u', 0)}
        if interface == XFCONF:
            self.reads += 1
            invocation.return_value(GLib.Variant('(a{sv})', ({'/Net/ThemeName': GLib.Variant('s', self.theme),
                '/Gtk/ApplicationPreferDarkTheme': GLib.Variant('b', self.prefer_dark)},)))
        elif method == 'ReadAll':
            invocation.return_value(GLib.Variant('(a{sa{sv}})', ({'org.freedesktop.appearance': appearance},)))
        else:
            namespace, key = parameters.unpack()
            if namespace != 'org.freedesktop.appearance' or key not in appearance:
                invocation.return_dbus_error('org.freedesktop.portal.Error.NotFound', 'No such fixture setting')
            else:
                value = appearance[key]
                # Legacy Read returns a doubly boxed value; ReadOne fixes that ABI.
                if method == 'Read':
                    value = GLib.Variant('v', value)
                invocation.return_value(GLib.Variant('(v)', (value,)))

    def set_color(self, color):
        self.color = color
        self.connection.emit_signal(None, PORTAL_PATH, SETTINGS, 'SettingChanged',
            GLib.Variant('(ssv)', ('org.freedesktop.appearance', 'color-scheme', GLib.Variant('u', color))))

    def set_theme(self, theme, prefer_dark=False):
        self.theme, self.prefer_dark = theme, prefer_dark
        for key, value in [('/Net/ThemeName', GLib.Variant('s', theme)),
                           ('/Gtk/ApplicationPreferDarkTheme', GLib.Variant('b', prefer_dark))]:
            self.connection.emit_signal(None, XFCONF_PATH, XFCONF, 'PropertyChanged',
                GLib.Variant('(ssv)', ('xsettings', key, value)))


fixture = DesktopFixture()
sys.path.insert(0, os.environ.get('WIFI_RELAY_TEST_SETTINGS_DIR') or
                str(Path(__file__).resolve().parents[1] / 'settings'))
import main


class NoNetworkClient:
    def __init__(self, ready):
        self.proxy = None
        GLib.idle_add(lambda: (ready(RuntimeError('Isolated appearance check')), False)[1])
    def close(self):
        pass


if os.environ.get('WIFI_RELAY_TEST_LARGE_TEXT') == '1':
    main.Gtk.init()
    provider = main.Gtk.CssProvider()
    provider.load_from_string('* { font-size: 22px; }')
    main.Gtk.StyleContext.add_provider_for_display(main.Gdk.Display.get_default(), provider,
                                                  main.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

main.ServiceClient = NoNetworkClient
main.get_default_ssid = lambda: "Theme test"
app = main.HotspotSettingsApp()
app.register(None)
app.activate()
window = app.get_active_window()
manager = app.get_style_manager()


def wait_for_dark(dark):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        context = GLib.MainContext.default()
        for _ in range(100):
            if not context.pending():
                break
            context.iteration(False)
        if manager.get_dark() == dark and window.get_mapped():
            return
        time.sleep(.005)
    raise AssertionError(f'{sys.argv[1]} did not switch to dark={dark}')


def screenshot(name):
    directory = os.environ.get('WIFI_RELAY_THEME_SCREENSHOTS')
    if directory:
        # ImageMagick is optional and only used for local visual verification.
        time.sleep(.3)
        for _ in range(100):
            if not GLib.MainContext.default().pending():
                break
            GLib.MainContext.default().iteration(False)
        subprocess.run(['import', '-window', 'root', str(Path(directory) / (sys.argv[1].lower() + '-' + os.environ.get('WIFI_RELAY_TEST_SCENARIO', 'normal') + '-' + name + '.png'))], check=True)


def check_layout():
    assert window.gnome_layout == (sys.argv[1] == 'GNOME')
    dimensions = []
    for index, scroll in enumerate(window.page_scrolls):
        if window.gnome_layout:
            window.view_stack.set_visible_child(scroll)
        else:
            window.notebook.set_current_page(index)
        deadline = time.monotonic() + .15
        while time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(.005)
        adjustment = scroll.get_vadjustment()
        assert adjustment.get_page_size() > 0
        if os.environ.get('WIFI_RELAY_TEST_SMALL_SCREEN') != '1':
            assert adjustment.get_upper() <= adjustment.get_page_size() + 1, (
                sys.argv[1], index, adjustment.get_upper(), adjustment.get_page_size())
        minimum, _natural, _min_baseline, _natural_baseline = scroll.get_child().measure(main.Gtk.Orientation.HORIZONTAL, -1)
        assert minimum <= scroll.get_width(), (sys.argv[1], index, 'horizontal clipping')
        dimensions.append((round(adjustment.get_upper()), round(adjustment.get_page_size())))
        screenshot('page-' + str(index))
    if window.gnome_layout:
        window.view_stack.set_visible_child(window.page_scrolls[0])
    else:
        window.notebook.set_current_page(0)
    assert window.get_height() <= window.get_display().get_monitors().get_item(0).get_geometry().height
    print(f'{sys.argv[1]}: page bounds at {window.get_width()}×{window.get_height()}; {dimensions}')


try:
    wait_for_dark(True)
    check_layout()
    screenshot('dark')
    if sys.argv[1] == 'XFCE':
        fixture.set_theme('Adwaita')
        wait_for_dark(False)
        screenshot('light')
        fixture.set_theme('Adwaita', True)
        wait_for_dark(True)
        fixture.set_theme('Arc-Darker')
        wait_for_dark(False)
        fixture.set_theme('Greybird-dark')
        wait_for_dark(True)
    fixture.set_color(2)
    wait_for_dark(False)
    fixture.set_color(1)
    wait_for_dark(True)
    fixture.set_color(0)
    wait_for_dark(sys.argv[1] == 'XFCE')
    if sys.argv[1] == 'XFCE':
        fixture.name('ReleaseName', GLib.Variant('(s)', (XFCONF,)))
        wait_for_dark(False)
        fixture.name('RequestName', GLib.Variant('(su)', (XFCONF, 0)))
        wait_for_dark(True)
    # A smaller window must retain reachable controls through page scrolling.
    window.set_default_size(640, 360)
    scrolled = False
    for index, scroll in enumerate(window.page_scrolls):
        if window.gnome_layout:
            window.view_stack.set_visible_child(scroll)
        else:
            window.notebook.set_current_page(index)
        deadline = time.monotonic() + .15
        while time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(.005)
        adjustment = scroll.get_vadjustment()
        maximum = max(0, adjustment.get_upper() - adjustment.get_page_size())
        adjustment.set_value(adjustment.get_upper())
        assert abs(adjustment.get_value() - maximum) <= 1
        scrolled = scrolled or maximum > 0
    assert scrolled, 'Small-window case did not exercise scrolling'
    fit = 'screen-constrained pages' if os.environ.get('WIFI_RELAY_TEST_SMALL_SCREEN') else 'default pages fit'
    print(f'{sys.argv[1]}: {fit}; small-window scrolling, live themes and system preference precedence passed')
finally:
    window._close_resources()
    window.destroy()
    app.appearance.close()
    fixture.loop.quit()
    fixture.thread.join(5)
