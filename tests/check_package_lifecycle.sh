#!/bin/sh
# Run inside a disposable Debian/Ubuntu container after installing version 1.0.0-7.
# Never run on a workstation: this deliberately removes and purges the package.
set -eu
if [ ! -f /.dockerenv ]; then
    echo 'This check requires a disposable Docker container.' >&2
    exit 1
fi
package=${1:?Pass the absolute path to the new Debian package}
config=/etc/wifi-hotspot.conf
# Fresh-install defaults belong to the new package, not the old fixture version.
mkdir -p /tmp/new-hotspot-defaults
dpkg-deb -x "$package" /tmp/new-hotspot-defaults
cp /tmp/new-hotspot-defaults/etc/wifi-hotspot.conf /tmp/new-hotspot-config
sed -i 's/^SSID=.*/SSID=BetaLifecycle/; s/^PASSPHRASE=.*/PASSPHRASE=synthetic-test-secret/' "$config"
chmod 0644 "$config"
cp "$config" /tmp/expected-hotspot-config
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    -o Dpkg::Options::=--force-confold "$package" > /tmp/wifi-relay-upgrade.log 2>&1
cmp "$config" /tmp/expected-hotspot-config
test "$(stat -c %a "$config")" = 600
test -f /usr/share/gnome-shell/extensions/wifi-relay@3togo.github.io/metadata.json
test ! -e /usr/share/gnome-shell/extensions/wifi-hotspot@erhanzeyrek
test -x /usr/bin/wifi-hotspot-settings
test -x /usr/bin/wifi-hotspot-enable-extension
test -f /etc/xdg/autostart/wifi-hotspot-autostart.desktop
echo 'Upgrade preserves settings, tightens permissions, and replaces the extension UUID.'
DEBIAN_FRONTEND=noninteractive apt-get remove -y gnome-wifi-hotspot > /tmp/wifi-relay-remove.log 2>&1
test ! -e /usr/bin/wifi-hotspot-settings
test ! -e /usr/libexec/wifi-hotspot-daemon/wifi-hotspot-daemon.py
cmp "$config" /tmp/expected-hotspot-config
echo 'Removal deletes executables and preserves user configuration.'
DEBIAN_FRONTEND=noninteractive apt-get purge -y gnome-wifi-hotspot > /tmp/wifi-relay-purge.log 2>&1
test ! -e "$config"
test ! -e /etc/xdg/autostart/wifi-hotspot-autostart.desktop
test ! -e /etc/polkit-1/rules.d/io.github.erhanzeyrek.WifiHotspot.rules
echo 'Purge removes system configuration, autostart, and authorization files.'
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "$package" > /tmp/wifi-relay-fresh-install.log 2>&1
cmp "$config" /tmp/new-hotspot-config
test "$(stat -c %a "$config")" = 600
test -x /usr/bin/wifi-hotspot-settings
test -x /usr/bin/wifi-hotspot-enable-extension
echo 'Fresh installation restores defaults and working launcher paths.'
