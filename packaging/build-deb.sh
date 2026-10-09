#!/bin/bash
# Build without root, installing packages, or changing host services.
set -euo pipefail
umask 022
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
version=${1:-$(dpkg-parsechangelog -l "$repo_dir/packaging/debian/changelog" -S Version)}
dpkg --validate-version "$version"
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(python3 -c 'from email.utils import parsedate_to_datetime; import sys; print(int(parsedate_to_datetime(sys.argv[1]).timestamp()))' "$(dpkg-parsechangelog -l "$repo_dir/packaging/debian/changelog" -S Date)")}
output_dir=${WIFI_RELAY_BUILD_OUTPUT:-"$repo_dir/dist"}
build_root=$(mktemp -d)
stage_dir="$build_root/main"
mkdir -p "$stage_dir"
trap 'rm -rf -- "$build_root"' EXIT

install_file() {
    install -D -m "$3" "$repo_dir/$1" "$stage_dir/$2"
}

install -d -m 0755 "$stage_dir/DEBIAN"
sed "s/@VERSION@/$version/g" "$repo_dir/packaging/debian/control" > "$stage_dir/DEBIAN/control"
for script in preinst postinst prerm postrm; do
    install_file "packaging/debian/$script" "DEBIAN/$script" 0755
done

install_file daemon/wifi-hotspot-daemon.py usr/libexec/wifi-hotspot-daemon/wifi-hotspot-daemon.py 0755
install_file daemon/create_ap usr/libexec/wifi-hotspot-daemon/create_ap 0755
install_file daemon/nm_backend.py usr/libexec/wifi-hotspot-daemon/nm_backend.py 0755
install_file daemon/nm_client.py usr/libexec/wifi-hotspot-daemon/nm_client.py 0644
install_file daemon/configuration.py usr/libexec/wifi-hotspot-daemon/configuration.py 0644
install_file tools/nm_ap_sta_probe.py usr/libexec/wifi-hotspot-daemon/tools/nm_ap_sta_probe.py 0755
install_file settings/main.py usr/share/wifi-hotspot/settings/main.py 0755
install_file settings/launcher.py usr/share/wifi-hotspot/settings/launcher.py 0755
for module in startup visibility preferences lifecycle service_client wifi_qr qrcodegen; do
    install_file "settings/$module.py" "usr/share/wifi-hotspot/settings/$module.py" 0644
done
install_file settings/enable-extension.py usr/share/wifi-hotspot/settings/enable-extension.py 0755
install -d -m 0755 "$stage_dir/usr/bin"
ln -s ../share/wifi-hotspot/settings/launcher.py "$stage_dir/usr/bin/wifi-hotspot-settings"
ln -s ../share/wifi-hotspot/settings/enable-extension.py "$stage_dir/usr/bin/wifi-hotspot-enable-extension"
ln -s ../libexec/wifi-hotspot-daemon/tools/nm_ap_sta_probe.py "$stage_dir/usr/bin/wifi-relay-nm-probe"
install_file data/wifi-hotspot.conf etc/wifi-hotspot.conf 0600
install_file data/wifi-hotspot.conf usr/share/wifi-hotspot/default.conf 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.conf usr/share/dbus-1/system.d/io.github.erhanzeyrek.WifiHotspot.conf 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.rules etc/polkit-1/rules.d/io.github.erhanzeyrek.WifiHotspot.rules 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.policy usr/share/polkit-1/actions/io.github.erhanzeyrek.WifiHotspot.policy 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.dbus-service usr/share/dbus-1/system-services/io.github.erhanzeyrek.WifiHotspot.service 0644
install_file data/wifi-hotspot-daemon.service usr/lib/systemd/system/wifi-hotspot-daemon.service 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.desktop usr/share/applications/io.github.erhanzeyrek.WifiHotspot.desktop 0644
install_file data/io.github.erhanzeyrek.WifiHotspot.metainfo.xml usr/share/metainfo/io.github.erhanzeyrek.WifiHotspot.metainfo.xml 0644
install_file data/icons/hotspot.svg usr/share/icons/hicolor/scalable/apps/io.github.erhanzeyrek.WifiHotspot.svg 0644
install_file settings/QR-ENCODER.md usr/share/doc/gnome-wifi-hotspot/QR-ENCODER.md 0644
install_file packaging/debian/copyright usr/share/doc/gnome-wifi-hotspot/copyright 0644
install_file README.md usr/share/doc/gnome-wifi-hotspot/README.md 0644
install_file docs/dependency-review.md usr/share/doc/gnome-wifi-hotspot/dependency-review.md 0644
install_file docs/production-readiness.md usr/share/doc/gnome-wifi-hotspot/production-readiness.md 0644
install_file docs/releases/1.0.0-17.md usr/share/doc/gnome-wifi-hotspot/releases/1.0.0-17.md 0644
install_file docs/networkmanager-prototype.md usr/share/doc/gnome-wifi-hotspot/networkmanager-prototype.md 0644
install_file docs/networkmanager-upstream-proposal.md usr/share/doc/gnome-wifi-hotspot/networkmanager-upstream-proposal.md 0644

install_file packaging/debian/wifi-hotspot-settings.1 usr/share/man/man1/wifi-hotspot-settings.1 0644
gzip -n -9 "$stage_dir/usr/share/man/man1/wifi-hotspot-settings.1"
sed "1s/([^)]*)/($version)/" "$repo_dir/packaging/debian/changelog" | gzip -n -9 > "$stage_dir/usr/share/doc/gnome-wifi-hotspot/changelog.Debian.gz"
finish_package() {
    local package=$1
    install_file packaging/debian/copyright "usr/share/doc/$package/copyright" 0644
    install -d -m 0755 "$stage_dir/usr/share/doc/$package"
    sed "1s/([^)]*)/($version)/" "$repo_dir/packaging/debian/changelog" | gzip -n -9 > "$stage_dir/usr/share/doc/$package/changelog.Debian.gz"
    find "$stage_dir" -type d -exec chmod 0755 {} +
    # Each package owns only its own configuration and file checksums.
    if [[ -d $stage_dir/etc ]]; then
        (cd "$stage_dir" && find etc -type f -printf '/%p\n' | sort) > "$stage_dir/DEBIAN/conffiles"
    fi
    (cd "$stage_dir" && find usr -type f -print0 | sort -z | xargs -0 md5sum) > "$stage_dir/DEBIAN/md5sums"
    if [[ -d $stage_dir/etc ]]; then
        (cd "$stage_dir" && find etc -type f -print0 | sort -z | xargs -0 md5sum) >> "$stage_dir/DEBIAN/md5sums"
    fi
    local installed_size
    installed_size=$(du -sk "$stage_dir" | awk '{print $1}')
    printf 'Installed-Size: %s\n' "$installed_size" >> "$stage_dir/DEBIAN/control"
    mkdir -p "$output_dir"
    # dpkg only clamps mtimes newer than SOURCE_DATE_EPOCH. Normalize every
    # member explicitly, including when the supplied epoch is in the future.
    find "$stage_dir" -exec touch --no-dereference --date="@$SOURCE_DATE_EPOCH" {} +
    dpkg-deb --root-owner-group --build "$stage_dir" "$output_dir/${package}_${version}_all.deb"
}

finish_package gnome-wifi-hotspot

for integration in gnome tray; do
    stage_dir="$build_root/$integration"
    install -d -m 0755 "$stage_dir/DEBIAN"
    sed "s/@VERSION@/$version/g" "$repo_dir/packaging/debian/control-$integration" > "$stage_dir/DEBIAN/control"
    install_file "data/wifi-relay-$integration.desktop" "etc/xdg/autostart/wifi-relay-$integration.desktop" 0644
    if [[ $integration == gnome ]]; then
        extension_dir=usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io
        install -d -m 0755 "$stage_dir/$extension_dir"
        cp -R "$repo_dir/extension/." "$stage_dir/$extension_dir/"
        find "$stage_dir/$extension_dir" -type f -exec chmod 0644 {} +
    else
        install_file settings/tray.py usr/share/wifi-hotspot/settings/tray.py 0755
        for icon in off connecting on; do
            install_file "settings/icons/wifi-hotspot-$icon.svg" "usr/share/wifi-hotspot/settings/icons/wifi-hotspot-$icon.svg" 0644
        done
    fi
    finish_package "gnome-wifi-hotspot-$integration"
done
