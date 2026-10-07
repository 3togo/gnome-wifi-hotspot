Name:           gnome-wifi-hotspot
Version:        1.0.0
Release:        1%{?dist}
Summary:        Native GNOME Shell Wi-Fi Hotspot with simultaneous AP+STA support

License:        MIT
URL:            https://github.com/3togo/gnome-wifi-hotspot
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

Requires:       hostapd
Requires:       dnsmasq
Requires:       iw
Requires:       iproute
Requires:       gnome-shell >= 45
Requires:       gtk4
Requires:       gtk3
Requires:       libayatana-appindicator-gtk3
Requires:       libadwaita
Requires:       python3-gobject
Requires:       polkit

%description
Share your Wi-Fi internet connection directly from GNOME Shell Quick Settings.
Features concurrent Wi-Fi reception and Access Point broadcasting (AP+STA mode),
automatic 2.4GHz/5GHz band checking, and automatic firewalld DHCP/DNS fixes.

%prep
%autosetup

%build
# No compilation required

%install
rm -rf $RPM_BUILD_ROOT

# Install extension
install -d -m 0755 %{buildroot}%{_datadir}/gnome-shell/extensions/wifi-relay@3togo.github.io
cp -r extension/* %{buildroot}%{_datadir}/gnome-shell/extensions/wifi-relay@3togo.github.io/

# Install daemon & create_ap
install -d -m 0755 %{buildroot}%{_libexecdir}/wifi-hotspot-daemon
install -m 0755 daemon/wifi-hotspot-daemon.py %{buildroot}%{_libexecdir}/wifi-hotspot-daemon/
install -m 0755 daemon/create_ap %{buildroot}%{_libexecdir}/wifi-hotspot-daemon/
install -m 0755 daemon/nm_backend.py %{buildroot}%{_libexecdir}/wifi-hotspot-daemon/
install -d -m 0755 %{buildroot}%{_libexecdir}/wifi-hotspot-daemon/tools
install -m 0755 tools/nm_ap_sta_probe.py %{buildroot}%{_libexecdir}/wifi-hotspot-daemon/tools/

# Install settings app
install -d -m 0755 %{buildroot}%{_datadir}/wifi-hotspot/settings
install -m 0755 settings/main.py settings/enable-extension.py settings/startup.py settings/tray.py %{buildroot}%{_datadir}/wifi-hotspot/settings/
cp -r settings/icons %{buildroot}%{_datadir}/wifi-hotspot/settings/
install -d -m 0755 %{buildroot}%{_bindir}
ln -s %{_datadir}/wifi-hotspot/settings/main.py %{buildroot}%{_bindir}/wifi-hotspot-settings
ln -s %{_datadir}/wifi-hotspot/settings/enable-extension.py %{buildroot}%{_bindir}/wifi-hotspot-enable-extension
install -d -m 0755 %{buildroot}%{_sysconfdir}/xdg/autostart
install -m 0644 data/wifi-hotspot-autostart.desktop %{buildroot}%{_sysconfdir}/xdg/autostart/

# Install system configuration files
install -d -m 0755 %{buildroot}%{_sysconfdir}/dbus-1/system.d
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.conf %{buildroot}%{_sysconfdir}/dbus-1/system.d/

install -d -m 0755 %{buildroot}%{_datadir}/polkit-1/actions
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.policy %{buildroot}%{_datadir}/polkit-1/actions/

install -d -m 0755 %{buildroot}%{_datadir}/polkit-1/rules.d
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.rules %{buildroot}%{_datadir}/polkit-1/rules.d/

install -d -m 0755 %{buildroot}%{_unitdir}
install -m 0644 data/wifi-hotspot-daemon.service %{buildroot}%{_unitdir}/

install -d -m 0755 %{buildroot}%{_sysconfdir}
install -m 0600 data/wifi-hotspot.conf %{buildroot}%{_sysconfdir}/

install -d -m 0755 %{buildroot}%{_datadir}/applications
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.desktop %{buildroot}%{_datadir}/applications/

install -d -m 0755 %{buildroot}%{_datadir}/metainfo
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.metainfo.xml %{buildroot}%{_datadir}/metainfo/

install -d -m 0755 %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
install -m 0644 data/icons/hotspot.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.erhanzeyrek.WifiHotspot.svg

%post
if [ -f %{_sysconfdir}/wifi-hotspot.conf ] && [ ! -L %{_sysconfdir}/wifi-hotspot.conf ]; then
    chmod 0600 %{_sysconfdir}/wifi-hotspot.conf
fi
%systemd_post wifi-hotspot-daemon.service
systemctl enable --now wifi-hotspot-daemon.service 2>/dev/null || :

%preun
%systemd_preun wifi-hotspot-daemon.service

%postun
%systemd_postun_with_restart wifi-hotspot-daemon.service

%files
%license LICENSE
%doc README.md
%{_datadir}/gnome-shell/extensions/wifi-relay@3togo.github.io
%{_libexecdir}/wifi-hotspot-daemon/
%{_datadir}/wifi-hotspot/
%{_bindir}/wifi-hotspot-settings
%{_bindir}/wifi-hotspot-enable-extension
%config(noreplace) %{_sysconfdir}/xdg/autostart/wifi-hotspot-autostart.desktop
%{_sysconfdir}/dbus-1/system.d/io.github.erhanzeyrek.WifiHotspot.conf
%{_datadir}/polkit-1/actions/io.github.erhanzeyrek.WifiHotspot.policy
%{_datadir}/polkit-1/rules.d/io.github.erhanzeyrek.WifiHotspot.rules
%{_unitdir}/wifi-hotspot-daemon.service
%config(noreplace) %{_sysconfdir}/wifi-hotspot.conf
%{_datadir}/applications/io.github.erhanzeyrek.WifiHotspot.desktop
%{_datadir}/metainfo/io.github.erhanzeyrek.WifiHotspot.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.erhanzeyrek.WifiHotspot.svg

%changelog
* Fri Aug 28 2026 Erhan Zeyrek <erhanzeyrek@users.noreply.github.com> - 1.0.0-1
- Initial native GNOME Shell Wi-Fi Hotspot package release
