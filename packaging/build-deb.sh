#!/bin/bash
# Build without root, installing packages, or changing host services.
set -euo pipefail
umask 022
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
version=${1:-1.0.0-11+nm5}
dpkg --validate-version "$version"
output_dir="$repo_dir/dist"
stage_dir=$(mktemp -d)
trap 'rm -rf -- "$stage_dir"' EXIT

install_file() {
    install -D -m "$3" "$repo_dir/$1" "$stage_dir/$2"
}

install -d -m 0755 "$stage_dir/DEBIAN"
sed "s/@VERSION@/$version/" "$repo_dir/packaging/debian/control" > "$stage_dir/DEBIAN/control"
for script in postinst prerm postrm; do
    install_file "packaging/debian/$script" "DEBIAN/$script" 0755
done

extension_dir=usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io
install -d -m 0755 "$stage_dir/$extension_dir"
cp -R "$repo_dir/extension/." "$stage_dir/$extension_dir/"
find "$stage_dir/$extension_dir" -type d -exec chmod 0755 {} +
find "$stage_dir/$extension_dir" -type f -exec chmod 0644 {} +
install_file daemon/wifi-hotspot-daemon.py usr/libexec/wifi-hotspot-daemon/wifi-hotspot-daemon.py 0755
install_file daemon/create_ap usr/libexec/wifi-hotspot-daemon/create_ap 0755
install_file daemon/nm_backend.py usr/libexec/wifi-hotspot-daemon/nm_backend.py 0755
install_file tools/nm_ap_sta_probe.py usr/libexec/wifi-hotspot-daemon/tools/nm_ap_sta_probe.py 0755
install_file settings/main.py usr/share/wifi-hotspot/settings/main.py 0755
install_file settings/tray.py usr/share/wifi-hotspot/settings/tray.py 0755
for icon in off connecting on; do
    install_file "settings/icons/wifi-hotspot-$icon.svg" "usr/share/wifi-hotspot/settings/icons/wifi-hotspot-$icon.svg" 0644
done
install_file settings/startup.py usr/share/wifi-hotspot/settings/startup.py 0644
install_file settings/enable-extension.py usr/share/wifi-hotspot/settings/enable-extension.py 0755
install_file data/wifi-hotspot-autostart.desktop etc/xdg/autostart/wifi-hotspot-autostart.desktop 0644
install -d -m 0755 "$stage_dir/usr/bin"
ln -s ../share/wifi-hotspot/settings/main.py "$stage_dir/usr/bin/wifi-hotspot-settings"
ln -s ../share/wifi-hotspot/settings/enable-extension.py "$stage_dir/usr/bin/wifi-hotspot-enable-extension"
ln -s ../libexec/wifi-hotspot-daemon/tools/nm_ap_sta_probe.py "$stage_dir/usr/bin/wifi-relay-nm-probe"
install_file data/wifi-hotspot.conf etc/wifi-hotspot.conf 0600
install_file data/io.github.erhanzeyrek.WifiHotspot.conf usr/share/dbus-1/system.d/io.github.erhanzeyrek.WifiHotspot.conf 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.rules etc/polkit-1/rules.d/io.github.erhanzeyrek.WifiHotspot.rules 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.policy usr/share/polkit-1/actions/io.github.erhanzeyrek.WifiHotspot.policy 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.dbus-service usr/share/dbus-1/system-services/io.github.erhanzeyrek.WifiHotspot.service 0644
install_file data/wifi-hotspot-daemon.service usr/lib/systemd/system/wifi-hotspot-daemon.service 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.desktop usr/share/applications/io.github.erhanzeyrek.WifiHotspot.desktop 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.metainfo.xml usr/share/metainfo/io.github.erhanzeyrek.WifiHotspot.metainfo.xml 0644
install_file data/icons/hotspot.svg usr/share/icons/hicolor/scalable/apps/io.github.erhanzeyrek.WifiHotspot.svg 0644
install_file LICENSE usr/share/doc/gnome-wifi-hotspot/copyright 0644
install_file README.md usr/share/doc/gnome-wifi-hotspot/README.md 0644
install_file docs/networkmanager-prototype.md usr/share/doc/gnome-wifi-hotspot/networkmanager-prototype.md 0644
install_file docs/networkmanager-upstream-proposal.md usr/share/doc/gnome-wifi-hotspot/networkmanager-upstream-proposal.md 0644

install_file packaging/debian/wifi-hotspot-settings.1 usr/share/man/man1/wifi-hotspot-settings.1 0644
gzip -n -9 "$stage_dir/usr/share/man/man1/wifi-hotspot-settings.1"
sed "1s/([^)]*)/($version)/" "$repo_dir/packaging/debian/changelog" | gzip -n -9 > "$stage_dir/usr/share/doc/gnome-wifi-hotspot/changelog.Debian.gz"
find "$stage_dir" -type d -exec chmod 0755 {} +

# dpkg preserves modified configuration on upgrades and removes it only on purge.
(cd "$stage_dir" && find etc -type f -printf '/%p\n' | sort) > "$stage_dir/DEBIAN/conffiles"
(cd "$stage_dir" && find usr etc -type f -print0 | sort -z | xargs -0 md5sum) > "$stage_dir/DEBIAN/md5sums"
installed_size=$(du -sk "$stage_dir/usr" "$stage_dir/etc" | awk '{n += $1} END {print n}')
printf 'Installed-Size: %s\n' "$installed_size" >> "$stage_dir/DEBIAN/control"
mkdir -p "$output_dir"
dpkg-deb --root-owner-group --build "$stage_dir" "$output_dir/gnome-wifi-hotspot_${version}_all.deb"
