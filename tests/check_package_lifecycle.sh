#!/bin/sh
# Destructive package tests, exclusively inside a disposable container.
set -eu
if [ ! -f /.dockerenv ]; then
    echo 'This check requires a disposable Docker container.' >&2
    exit 1
fi
package=${1:?Pass the absolute path to the new main Debian package}
version=$(dpkg-deb -f "$package" Version)
package_dir=$(dirname "$package")
gnome="$package_dir/gnome-wifi-hotspot-gnome_${version}_all.deb"
tray="$package_dir/gnome-wifi-hotspot-tray_${version}_all.deb"
config=/etc/wifi-hotspot.conf
legacy=/etc/xdg/autostart/wifi-hotspot-autostart.desktop
mkdir -p /tmp/new-hotspot-defaults
dpkg-deb -x "$package" /tmp/new-hotspot-defaults
cp /tmp/new-hotspot-defaults/etc/wifi-hotspot.conf /tmp/new-hotspot-config
sed -i 's/^SSID=.*/SSID=SplitLifecycle/; s/^PASSPHRASE=.*/PASSPHRASE=synthetic-test-secret/' "$config"
chmod 0644 "$config"
cp "$config" /tmp/expected-hotspot-config
# A modified obsolete conffile must be backed up, never silently discarded.
printf '\n# preserved local startup customization\n' >> "$legacy"
cp "$legacy" /tmp/expected-legacy-autostart
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    -o Dpkg::Options::=--force-confold "$package" > /tmp/wifi-relay-upgrade.log 2>&1
cmp "$config" /tmp/expected-hotspot-config
test "$(stat -c %a "$config")" = 600
test ! -e "$legacy"
cmp "$legacy.dpkg-bak" /tmp/expected-legacy-autostart
test ! -e /usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io/metadata.json
test ! -e /usr/share/wifi-hotspot/settings/tray.py
test -x /usr/bin/wifi-hotspot-settings
python3 /usr/bin/wifi-hotspot-settings --help >/dev/null
python3 /usr/bin/wifi-relay-nm-probe --help >/dev/null
dbus-run-session -- xvfb-run -a env WIFI_RELAY_TEST_SETTINGS_DIR=/usr/share/wifi-hotspot/settings \
    python3 tests/check_settings_window.py
echo 'Monolithic upgrade preserves credentials and customized startup backup; main needs no integration.'
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "$gnome" "$tray" > /tmp/wifi-relay-integrations-install.log 2>&1
test -f /usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io/metadata.json
test -f /usr/share/wifi-hotspot/settings/tray.py
test -f /etc/xdg/autostart/wifi-relay-gnome.desktop
test -f /etc/xdg/autostart/wifi-relay-tray.desktop
python3 - <<'PY'
import sys
sys.path.insert(0, '/usr/share/wifi-hotspot/settings')
from startup import desktop_integration_available
assert desktop_integration_available(gnome=False)
assert desktop_integration_available(gnome=True)
PY
DEBIAN_FRONTEND=noninteractive apt-get purge -y gnome-wifi-hotspot-gnome \
    > /tmp/wifi-relay-gnome-remove.log 2>&1
test ! -e /usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io/metadata.json
test ! -e /etc/xdg/autostart/wifi-relay-gnome.desktop
test -f /usr/share/wifi-hotspot/settings/tray.py
test -x /usr/bin/wifi-hotspot-settings
DEBIAN_FRONTEND=noninteractive apt-get purge -y gnome-wifi-hotspot-tray \
    > /tmp/wifi-relay-tray-remove.log 2>&1
test ! -e /usr/share/wifi-hotspot/settings/tray.py
test ! -e /etc/xdg/autostart/wifi-relay-tray.desktop
test -x /usr/bin/wifi-hotspot-settings
test -x /usr/libexec/wifi-hotspot-daemon/wifi-hotspot-daemon.py
cmp "$config" /tmp/expected-hotspot-config
echo 'Integration removal leaves the standalone GUI, daemon, and configuration intact.'
DEBIAN_FRONTEND=noninteractive apt-get remove -y gnome-wifi-hotspot > /tmp/wifi-relay-remove.log 2>&1
test ! -e /usr/bin/wifi-hotspot-settings
test ! -e /usr/libexec/wifi-hotspot-daemon/wifi-hotspot-daemon.py
cmp "$config" /tmp/expected-hotspot-config
DEBIAN_FRONTEND=noninteractive apt-get purge -y gnome-wifi-hotspot > /tmp/wifi-relay-purge.log 2>&1
test ! -e "$config"
test ! -e /etc/polkit-1/rules.d/io.github.erhanzeyrek.WifiHotspot.rules
echo 'Main removal preserves configuration; purge removes it.'
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "$package" > /tmp/wifi-relay-fresh-install.log 2>&1
python3 - "$config" /tmp/new-hotspot-config <<'PY'
from pathlib import Path
import re
import sys
actual, factory = [Path(path).read_text() for path in sys.argv[1:]]
password = re.search(r'^PASSPHRASE=(.+)$', actual, re.M).group(1)
assert re.fullmatch('[0-9a-f]{32}', password)
assert actual.replace('PASSPHRASE=' + password, 'PASSPHRASE=12345678') == factory
sys.path.insert(0, '/usr/share/wifi-hotspot/settings')
from startup import desktop_integration_available
assert not desktop_integration_available(gnome=False)
assert not desktop_integration_available(gnome=True)
PY
test "$(stat -c %a "$config")" = 600
test -x /usr/bin/wifi-hotspot-settings
test ! -e /etc/xdg/autostart/wifi-relay-gnome.desktop
test ! -e /etc/xdg/autostart/wifi-relay-tray.desktop
dpkg --audit
echo 'Fresh main-only installation has secure defaults and no desktop autostart.'

# Upgrade an already split installation with both integrations in one transaction.
next_version="${version}+splitupgrade"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WIFI_RELAY_BUILD_OUTPUT=/tmp/relay-split-upgrade bash "$script_dir/../packaging/build-deb.sh" "$next_version" \
    > /tmp/wifi-relay-split-rebuild.log 2>&1
cp "$config" /tmp/expected-fresh-config
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "$gnome" "$tray" > /tmp/wifi-relay-reinstall-integrations.log 2>&1
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    /tmp/relay-split-upgrade/gnome-wifi-hotspot*_"${next_version}"_all.deb \
    > /tmp/wifi-relay-split-upgrade.log 2>&1
cmp "$config" /tmp/expected-fresh-config
for name in gnome-wifi-hotspot gnome-wifi-hotspot-gnome gnome-wifi-hotspot-tray; do
    test "$(dpkg-query -W -f='${Version}' "$name")" = "$next_version"
done
dpkg --audit
echo 'Coordinated split-package upgrade keeps matching versions and existing credentials.'
