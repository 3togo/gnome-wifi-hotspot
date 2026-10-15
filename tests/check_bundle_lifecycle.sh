#!/bin/sh
# Destructive package checks, exclusively inside a disposable container.
set -eu
test -f /.dockerenv || { echo 'A disposable Docker container is required.' >&2; exit 1; }
package=${1:?Pass the main Debian package path}
version=$(dpkg-deb -f "$package" Version)
package_dir=$(dirname "$package")
bundle="$package_dir/gnome-wifi-hotspot-bundle_${version}_all.deb"
config=/etc/wifi-hotspot.conf
cp "$config" /tmp/expected-bundle-config

apt-get install -y --no-install-recommends "$bundle"
test "$(dpkg-query -W -f='${Status}' gnome-wifi-hotspot-bundle)" = 'install ok installed'
cmp "$config" /tmp/expected-bundle-config
test "$(stat -c %a "$config")" = 600
dpkg-query -S /usr/bin/wifi-hotspot-settings | grep '^gnome-wifi-hotspot-bundle:'
test -f /usr/share/wifi-hotspot/settings/tray.py
test -f /usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io/metadata.json
WIFI_RELAY_TEST_SETTINGS_DIR=/usr/share/wifi-hotspot/settings \
    WIFI_RELAY_TEST_DAEMON_DIR=/usr/libexec/wifi-hotspot-daemon make test-integration test-smoke
echo 'Separate packages replaced by bundle; credentials and installed UI preserved.'

next_version="${version}+bundleupgrade"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WIFI_RELAY_BUILD_OUTPUT=/tmp/relay-bundle-upgrade \
    bash "$script_dir/../packaging/build-deb.sh" "$next_version"
apt-get install -y --no-install-recommends \
    "/tmp/relay-bundle-upgrade/gnome-wifi-hotspot-bundle_${next_version}_all.deb"
test "$(dpkg-query -W -f='${Version}' gnome-wifi-hotspot-bundle)" = "$next_version"
cmp "$config" /tmp/expected-bundle-config
echo 'Bundle upgrade preserves credentials.'

apt-get install -y --allow-downgrades --no-install-recommends "$package" \
    "$package_dir/gnome-wifi-hotspot-gnome_${version}_all.deb" \
    "$package_dir/gnome-wifi-hotspot-tray_${version}_all.deb"
cmp "$config" /tmp/expected-bundle-config
dpkg-query -S /usr/bin/wifi-hotspot-settings | grep '^gnome-wifi-hotspot:'
echo 'Switching back to separate packages preserves credentials and ownership.'

apt-get install -y --no-install-recommends "$bundle"
apt-get remove -y gnome-wifi-hotspot-bundle
cmp "$config" /tmp/expected-bundle-config
test ! -e /usr/bin/wifi-hotspot-settings
test ! -e /usr/share/wifi-hotspot/settings/tray.py
test ! -e /usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io/metadata.json
# Purge obsolete split-package conffile records as well as the bundle.
apt-get purge -y gnome-wifi-hotspot-bundle gnome-wifi-hotspot \
    gnome-wifi-hotspot-gnome gnome-wifi-hotspot-tray
test ! -e "$config"
test ! -e /etc/xdg/autostart/wifi-relay-gnome.desktop
test ! -e /etc/xdg/autostart/wifi-relay-tray.desktop
apt-get install -y --no-install-recommends "$bundle"
python3 - "$config" <<'PY'
from pathlib import Path
import re
import sys
configuration = Path(sys.argv[1]).read_text()
assert re.search(r'^PASSPHRASE=[0-9a-f]{32}$', configuration, re.M)
PY
test "$(stat -c %a "$config")" = 600
apt-get purge -y gnome-wifi-hotspot-bundle
test ! -e "$config"
test ! -e /etc/xdg/autostart/wifi-relay-gnome.desktop
test ! -e /etc/xdg/autostart/wifi-relay-tray.desktop
dpkg --audit
echo 'Bundle removal, purge, fresh installation and fresh purge passed.'
