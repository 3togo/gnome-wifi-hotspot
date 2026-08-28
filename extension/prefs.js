import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import Gtk from 'gi://Gtk';
import GLib from 'gi://GLib';
import { ExtensionPreferences, gettext as _ } from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

const BUS_NAME = 'io.github.erhanzeyrek.WifiHotspot';
const OBJECT_PATH = '/io/github/erhanzeyrek/WifiHotspot';
const INTERFACE_NAME = 'io.github.erhanzeyrek.WifiHotspot';

const HotspotDBusInterface = `
<node>
  <interface name="${INTERFACE_NAME}">
    <method name="Start">
      <arg type="s" name="result" direction="out"/>
    </method>
    <method name="Stop">
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="GetStatus">
      <arg type="s" name="status_json" direction="out"/>
    </method>
    <method name="GetClients">
      <arg type="s" name="clients_json" direction="out"/>
    </method>
    <method name="GetConfig">
      <arg type="s" name="config_json" direction="out"/>
    </method>
    <method name="SetConfig">
      <arg type="s" name="config_json" direction="in"/>
      <arg type="b" name="success" direction="out"/>
    </method>
    <method name="GetInterfaces">
      <arg type="s" name="ifaces_json" direction="out"/>
    </method>
    <method name="GetCapabilities">
      <arg type="s" name="caps_json" direction="out"/>
    </method>
  </interface>
</node>`;

const HotspotProxy = Gio.DBusProxy.makeProxyWrapper(HotspotDBusInterface);

function scanSystemInterfaces() {
    const wifi = [];
    const all = [];
    try {
        const netDir = Gio.File.new_for_path('/sys/class/net');
        const enumerator = netDir.enumerate_children('standard::name', Gio.FileQueryInfoFlags.NONE, null);
        let info;
        while ((info = enumerator.next_file(null)) !== null) {
            const name = info.get_name();
            if (name === 'lo') continue;
            all.push(name);
            const isWireless = Gio.File.new_for_path(`/sys/class/net/${name}/wireless`).query_exists(null) ||
                               Gio.File.new_for_path(`/sys/class/net/${name}/phy80211`).query_exists(null);
            if (isWireless) {
                wifi.push(name);
            }
        }
    } catch (e) {
        console.warn(`[Hotspot] Error scanning /sys/class/net: ${e}`);
    }
    return {
        wifi_interfaces: wifi.length > 0 ? wifi : ['wlp2s0', 'wlan0'],
        all_interfaces: all.length > 0 ? all : ['wlp2s0', 'enp1s0', 'wlan0', 'eth0'],
    };
}

function readLocalConfigFile() {
    const paths = ['/etc/wifi-hotspot.conf', GLib.build_filenamev([GLib.get_home_dir(), '.config', 'wifi-hotspot.conf'])];
    const conf = {};
    for (const p of paths) {
        if (GLib.file_test(p, GLib.FileTest.EXISTS)) {
            try {
                const [ok, content] = GLib.file_get_contents(p);
                if (ok) {
                    const text = new TextDecoder().decode(content);
                    for (const line of text.split('\n')) {
                        const trimmed = line.trim();
                        if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
                            const [k, ...vParts] = trimmed.split('=');
                            conf[k.trim()] = vParts.join('=').trim().replace(/^["']|["']$/g, '');
                        }
                    }
                    return conf;
                }
            } catch (e) {}
        }
    }
    return conf;
}

function getDefaultSsid() {
    try {
        const host = GLib.get_host_name();
        if (host && host.toLowerCase() !== 'localhost' && host !== '(none)') {
            return `${host}-Hotspot`;
        }
    } catch (e) {}
    return 'Hotspot';
}

export default class HotspotPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        window.set_default_size(650, 550);

        let isLoading = true;

        // Immediate interface detection
        const detected = scanSystemInterfaces();
        let wifiList = detected.wifi_interfaces;
        let allList = detected.all_interfaces;
        let selectedWifiIface = wifiList[0] || 'wlp2s0';
        let selectedInetIface = wifiList[0] || 'wlp2s0';

        // ---------------- Page 1: General ---------------- //
        const pageGeneral = new Adw.PreferencesPage({
            title: _('General'),
            iconName: 'network-wireless-hotspot-symbolic',
        });
        window.add(pageGeneral);

        // Basic Settings Group
        const grpBasic = new Adw.PreferencesGroup({
            title: _('Hotspot Configuration'),
            description: _('Wi-Fi broadcast name and security credentials'),
        });
        pageGeneral.add(grpBasic);

        const entrySsid = new Adw.EntryRow({ title: _('Hotspot Name (SSID)') });
        entrySsid.connect('changed', () => saveConfig());
        grpBasic.add(entrySsid);

        const entryPass = new Adw.PasswordEntryRow({ title: _('Password (WPA2/WPA3)') });
        entryPass.connect('changed', () => saveConfig());
        grpBasic.add(entryPass);

        // Network Interfaces Group
        const grpNet = new Adw.PreferencesGroup({
            title: _('Network & Hardware'),
        });
        pageGeneral.add(grpNet);

        const comboWifi = new Adw.ComboRow({ title: _('Wi-Fi Interface') });
        comboWifi.set_model(Gtk.StringList.new(wifiList));
        comboWifi.connect('notify::selected', () => {
            if (!isLoading) {
                const idx = comboWifi.get_selected();
                if (idx >= 0 && idx < wifiList.length) {
                    selectedWifiIface = wifiList[idx];
                }
                saveConfig();
            }
        });
        grpNet.add(comboWifi);

        const comboInet = new Adw.ComboRow({ title: _('Internet Interface') });
        comboInet.set_model(Gtk.StringList.new(allList));
        comboInet.connect('notify::selected', () => {
            if (!isLoading) {
                const idx = comboInet.get_selected();
                if (idx >= 0 && idx < allList.length) {
                    selectedInetIface = allList[idx];
                }
                saveConfig();
            }
        });
        grpNet.add(comboInet);

        const comboBand = new Adw.ComboRow({ title: _('Frequency Band') });
        comboBand.set_model(Gtk.StringList.new([_('Automatic (Recommended)'), '2.4 GHz', '5 GHz']));
        comboBand.connect('notify::selected', () => saveConfig());
        grpNet.add(comboBand);

        const rowCaps = new Adw.ActionRow({
            title: _('Hardware Capabilities'),
            subtitle: _('Checking service status...'),
        });
        grpNet.add(rowCaps);

        // ---------------- Page 2: Advanced ---------------- //
        const pageAdv = new Adw.PreferencesPage({
            title: _('Advanced'),
            iconName: 'emblem-system-symbolic',
        });
        window.add(pageAdv);

        const grpAdv = new Adw.PreferencesGroup({ title: _('Protocol & Security') });
        pageAdv.add(grpAdv);

        const switchHidden = new Adw.SwitchRow({ title: _('Hidden SSID'), subtitle: _('Hide network name from broadcast') });
        switchHidden.connect('notify::active', () => saveConfig());
        grpAdv.add(switchHidden);

        const switchIsolate = new Adw.SwitchRow({ title: _('Client Isolation'), subtitle: _('Prevent communication between connected devices') });
        switchIsolate.connect('notify::active', () => saveConfig());
        grpAdv.add(switchIsolate);

        const switch80211n = new Adw.SwitchRow({ title: _('IEEE 802.11n (Wi-Fi 4)') });
        switch80211n.connect('notify::active', () => saveConfig());
        grpAdv.add(switch80211n);

        const switch80211ac = new Adw.SwitchRow({ title: _('IEEE 802.11ac (Wi-Fi 5)') });
        switch80211ac.connect('notify::active', () => saveConfig());
        grpAdv.add(switch80211ac);

        const switch80211ax = new Adw.SwitchRow({ title: _('IEEE 802.11ax (Wi-Fi 6)') });
        switch80211ax.connect('notify::active', () => saveConfig());
        grpAdv.add(switch80211ax);

        const grpIp = new Adw.PreferencesGroup({ title: _('Gateway & Channel') });
        pageAdv.add(grpIp);

        const entryGateway = new Adw.EntryRow({ title: _('Gateway IP') });
        entryGateway.connect('changed', () => saveConfig());
        grpIp.add(entryGateway);

        const entryChannel = new Adw.EntryRow({ title: _('Channel Number') });
        entryChannel.connect('changed', () => saveConfig());
        grpIp.add(entryChannel);

        // Populate initial data from local file immediately
        const initialConf = readLocalConfigFile();
        applyConfigToUI(initialConf);
        isLoading = false;

        let proxy = null;

        function applyConfigToUI(conf) {
            if (!conf) return;
            const prevLoading = isLoading;
            isLoading = true;

            if (conf.SSID !== undefined) entrySsid.set_text(conf.SSID);
            if (conf.PASSPHRASE !== undefined) entryPass.set_text(conf.PASSPHRASE);
            if (conf.GATEWAY !== undefined) entryGateway.set_text(conf.GATEWAY);
            if (conf.CHANNEL !== undefined) entryChannel.set_text(conf.CHANNEL);
            if (conf.HIDDEN !== undefined) switchHidden.set_active(conf.HIDDEN === '1');
            if (conf.ISOLATE_CLIENTS !== undefined) switchIsolate.set_active(conf.ISOLATE_CLIENTS === '1');
            if (conf.IEEE80211N !== undefined) switch80211n.set_active(conf.IEEE80211N === '1');
            if (conf.IEEE80211AC !== undefined) switch80211ac.set_active(conf.IEEE80211AC === '1');
            if (conf.IEEE80211AX !== undefined) switch80211ax.set_active(conf.IEEE80211AX === '1');

            const band = conf.FREQ_BAND || 'auto';
            comboBand.set_selected(band === '2.4' ? 1 : (band === '5' ? 2 : 0));

            // Select matching Wi-Fi & Internet interface
            if (conf.WIFI_IFACE) {
                selectedWifiIface = conf.WIFI_IFACE;
                const idx = wifiList.indexOf(conf.WIFI_IFACE);
                if (idx >= 0) comboWifi.set_selected(idx);
            }
            if (conf.INTERNET_IFACE) {
                selectedInetIface = conf.INTERNET_IFACE;
                const idx = allList.indexOf(conf.INTERNET_IFACE);
                if (idx >= 0) comboInet.set_selected(idx);
            }

            isLoading = prevLoading;
        }

        function loadDataFromDBus() {
            if (!proxy) return;

            proxy.GetInterfacesRemote((res, err) => {
                if (!err && res) {
                    try {
                        const [ifacesJson] = res;
                        const ifaces = JSON.parse(ifacesJson);
                        const prevLoading = isLoading;
                        isLoading = true;

                        if (ifaces.wifi_interfaces?.length) {
                            wifiList = ifaces.wifi_interfaces;
                            comboWifi.set_model(Gtk.StringList.new(wifiList));
                            const wIdx = wifiList.indexOf(selectedWifiIface);
                            comboWifi.set_selected(wIdx >= 0 ? wIdx : 0);
                        }
                        if (ifaces.all_interfaces?.length) {
                            allList = ifaces.all_interfaces;
                            comboInet.set_model(Gtk.StringList.new(allList));
                            const iIdx = allList.indexOf(selectedInetIface);
                            comboInet.set_selected(iIdx >= 0 ? iIdx : 0);
                        }

                        isLoading = prevLoading;
                    } catch (e) {}
                }
            });

            proxy.GetConfigRemote((res, err) => {
                if (!err && res) {
                    try {
                        const [confJson] = res;
                        const conf = JSON.parse(confJson);
                        applyConfigToUI(conf);
                    } catch (e) {}
                }
            });

            proxy.GetCapabilitiesRemote((res, err) => {
                if (!err && res) {
                    try {
                        const [capsJson] = res;
                        const caps = JSON.parse(capsJson);
                        const ap5g = caps.ap_5ghz ? _('Yes') : _('No');
                        const staB = caps.current_sta_band ? (caps.current_sta_ssid ? `${caps.current_sta_band} GHz (${caps.current_sta_ssid})` : `${caps.current_sta_band} GHz`) : _('Not Connected');
                        rowCaps.set_subtitle(`5GHz AP: ${ap5g} | Active Wi-Fi: ${staB}`);
                    } catch (e) {
                        rowCaps.set_subtitle(_('Could not parse D-Bus response.'));
                    }
                } else {
                    rowCaps.set_subtitle(_('⚠️ Daemon offline — background service is not running'));
                }
            });
        }

        function saveConfig() {
            if (isLoading) return;

            const bandIdx = comboBand.get_selected();
            const bandStr = bandIdx === 0 ? 'auto' : (bandIdx === 1 ? '2.4' : '5');

            const selectedWifiIdx = comboWifi.get_selected();
            const wifiIface = (selectedWifiIdx >= 0 && selectedWifiIdx < wifiList.length) ? wifiList[selectedWifiIdx] : selectedWifiIface;

            const selectedInetIdx = comboInet.get_selected();
            const inetIface = (selectedInetIdx >= 0 && selectedInetIdx < allList.length) ? allList[selectedInetIdx] : selectedInetIface;

            selectedWifiIface = wifiIface;
            selectedInetIface = inetIface;

            const conf = {
                SSID: entrySsid.get_text() || getDefaultSsid(),
                PASSPHRASE: entryPass.get_text() || '12345678',
                GATEWAY: entryGateway.get_text() || '192.168.12.1',
                CHANNEL: entryChannel.get_text() || 'default',
                FREQ_BAND: bandStr,
                HIDDEN: switchHidden.get_active() ? '1' : '0',
                ISOLATE_CLIENTS: switchIsolate.get_active() ? '1' : '0',
                IEEE80211N: switch80211n.get_active() ? '1' : '0',
                IEEE80211AC: switch80211ac.get_active() ? '1' : '0',
                IEEE80211AX: switch80211ax.get_active() ? '1' : '0',
                WIFI_IFACE: wifiIface,
                INTERNET_IFACE: inetIface,
            };

            if (proxy) {
                proxy.SetConfigRemote(JSON.stringify(conf), () => {});
            }
        }

        // Initialize D-Bus Proxy
        try {
            proxy = new HotspotProxy(
                Gio.DBus.system,
                BUS_NAME,
                OBJECT_PATH,
                (p, err) => {
                    if (!err) {
                        loadDataFromDBus();
                    } else {
                        rowCaps.set_subtitle(_('⚠️ Daemon offline — background service is not running'));
                    }
                }
            );
        } catch (e) {
            rowCaps.set_subtitle(_('⚠️ Daemon offline — background service is not running'));
        }
    }
}
