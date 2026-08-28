Name:           gnome-wifi-hotspot
Version:        1.0.0
Release:        1%{?dist}
Summary:        Native GNOME Shell Wi-Fi Hotspot with simultaneous AP+STA support

License:        MIT
URL:            https://github.com/erhanzeyrek/gnome-wifi-hotspot
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

Requires:       hostapd
Requires:       dnsmasq
Requires:       iw
Requires:       iproute
Requires:       gnome-shell >= 45
Requires:       gtk4
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
install -d -m 0755 %{buildroot}%{_datadir}/gnome-shell/extensions/wifi-hotspot@erhanzeyrek
cp -r extension/* %{buildroot}%{_datadir}/gnome-shell/extensions/wifi-hotspot@erhanzeyrek/

# Install daemon & create_ap
install -d -m 0755 %{buildroot}%{_libexecdir}/wifi-hotspot-daemon
install -m 0755 daemon/wifi-hotspot-daemon.py %{buildroot}%{_libexecdir}/wifi-hotspot-daemon/
install -m 0755 daemon/create_ap %{buildroot}%{_libexecdir}/wifi-hotspot-daemon/

# Install settings app
install -d -m 0755 %{buildroot}%{_datadir}/wifi-hotspot/settings
install -m 0755 settings/main.py %{buildroot}%{_datadir}/wifi-hotspot/settings/
install -d -m 0755 %{buildroot}%{_bindir}
ln -s %{_datadir}/wifi-hotspot/settings/main.py %{buildroot}%{_bindir}/wifi-hotspot-settings

# Install system configuration files
install -d -m 0755 %{buildroot}%{_sysconfdir}/dbus-1/system.d
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.conf %{buildroot}%{_sysconfdir}/dbus-1/system.d/

install -d -m 0755 %{buildroot}%{_datadir}/polkit-1/actions
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.policy %{buildroot}%{_datadir}/polkit-1/actions/

install -d -m 0755 %{buildroot}%{_datadir}/polkit-1/rules.d
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.rules %{buildroot}%{_datadir}/polkit-1/rules.d/

install -d -m 0755 %{buildroot}%{_unitdir}
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.service %{buildroot}%{_unitdir}/

install -d -m 0755 %{buildroot}%{_sysconfdir}
install -m 0644 data/wifi-hotspot.conf %{buildroot}%{_sysconfdir}/

install -d -m 0755 %{buildroot}%{_datadir}/applications
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.desktop %{buildroot}%{_datadir}/applications/

install -d -m 0755 %{buildroot}%{_datadir}/metainfo
install -m 0644 data/io.github.erhanzeyrek.WifiHotspot.metainfo.xml %{buildroot}%{_datadir}/metainfo/

install -d -m 0755 %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
install -m 0644 data/icons/hotspot.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.erhanzeyrek.WifiHotspot.svg

%post
%systemd_post io.github.erhanzeyrek.WifiHotspot.service
systemctl enable --now io.github.erhanzeyrek.WifiHotspot.service 2>/dev/null || :

%preun
%systemd_preun io.github.erhanzeyrek.WifiHotspot.service

%postun
%systemd_postun_with_restart io.github.erhanzeyrek.WifiHotspot.service

%files
%license LICENSE
%doc README.md
%{_datadir}/gnome-shell/extensions/wifi-hotspot@erhanzeyrek
%{_libexecdir}/wifi-hotspot-daemon/
%{_datadir}/wifi-hotspot/
%{_bindir}/wifi-hotspot-settings
%{_sysconfdir}/dbus-1/system.d/io.github.erhanzeyrek.WifiHotspot.conf
%{_datadir}/polkit-1/actions/io.github.erhanzeyrek.WifiHotspot.policy
%{_datadir}/polkit-1/rules.d/io.github.erhanzeyrek.WifiHotspot.rules
%{_unitdir}/io.github.erhanzeyrek.WifiHotspot.service
%config(noreplace) %{_sysconfdir}/wifi-hotspot.conf
%{_datadir}/applications/io.github.erhanzeyrek.WifiHotspot.desktop
%{_datadir}/metainfo/io.github.erhanzeyrek.WifiHotspot.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.erhanzeyrek.WifiHotspot.svg

%changelog
* Fri Aug 28 2026 Erhan Zeyrek <erhanzeyrek@users.noreply.github.com> - 1.0.0-1
- Initial native GNOME Shell Wi-Fi Hotspot package release
