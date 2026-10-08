#!/bin/bash
# Build the Ubuntu 1.36.0 applet with the optional Relay menu. Never installs it.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
source_version=1.36.0-4ubuntu1
version=${1:-1.36.0-4ubuntu1+relay5}
dpkg --validate-version "$version"
make -C "$repo_dir" test
if [[ -n ${DISPLAY:-} || -n ${WAYLAND_DISPLAY:-} ]]; then
    "$repo_dir/integration/nm-applet/test.sh"
else
    xvfb-run -a "$repo_dir/integration/nm-applet/test.sh"
fi
mkdir -p "$repo_dir/dist"
build_dir=$(mktemp -d "$repo_dir/dist/nm-applet-build.XXXXXX")
cd "$build_dir"
apt-get source "network-manager-applet=$source_version"
cd network-manager-applet-1.36.0
patch -p1 < "$repo_dir/integration/nm-applet/relay-menu.patch"
patch -p1 < "$repo_dir/integration/nm-applet/hotspot-icon.patch"
install -m 0644 "$repo_dir/integration/nm-applet/wifi-relay.c" src/wifi-relay.c
install -m 0644 "$repo_dir/integration/nm-applet/wifi-relay.h" src/wifi-relay.h
python3 - "$version" <<'PY'
from pathlib import Path
import sys
from email.utils import formatdate
path = Path('debian/changelog')
path.write_text('network-manager-applet (' + sys.argv[1] + ') stonking; urgency=medium\n\n'
    '  * Add optional Wi-Fi Relay service controls to the network menu.\n\n'
    ' -- Wi-Fi Relay <3togo@users.noreply.github.com>  ' + formatdate(localtime=True) + '\n\n'
    + path.read_text())
PY
dpkg-buildpackage -b -uc -us > "$build_dir/build.log" 2>&1 || {
    tail -80 "$build_dir/build.log"
    exit 1
}
for package in network-manager-applet network-manager-gnome nm-connection-editor; do
    cp ../"${package}_${version}_"*.deb "$repo_dir/dist/"
done
cd "$repo_dir/dist"
for package in network-manager-applet network-manager-gnome nm-connection-editor; do
    for deb in "${package}_${version}_"*.deb; do
        sha256sum "$deb" > "$deb.sha256"
        printf '%s\n' "$repo_dir/dist/$deb"
    done
done
printf 'Build log: %s/build.log\n' "$build_dir"
