#!/bin/bash
# Build the Ubuntu GNOME Settings Wi-Fi tab correction without installing it.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
version=${1:-1:51.0-1ubuntu1+relay1}
dpkg --validate-version "$version"
mkdir -p "$repo_dir/dist"
build_dir=$(mktemp -d "$repo_dir/dist/gnome-settings-build.XXXXXX")
cd "$build_dir"
apt-get source gnome-control-center=1:51.0-1ubuntu1
cd gnome-control-center-51.0
patch -p1 < "$repo_dir/integration/gnome-settings/stable-wifi-device-tabs.patch"
python3 - "$version" <<'PY'
from pathlib import Path
from email.utils import formatdate
import sys
path = Path('debian/changelog')
path.write_text('gnome-control-center (' + sys.argv[1] + ') stonking; urgency=medium\n\n'
    '  * Use stable Wi-Fi device paths to remove unrealized Relay tabs.\n\n'
    ' -- Wi-Fi Relay <3togo@users.noreply.github.com>  ' + formatdate(localtime=True)
    + '\n\n' + path.read_text())
PY
env -u LD_PRELOAD dpkg-buildpackage -b -uc -us -j8 > "$build_dir/build.log" 2>&1 || {
    tail -80 "$build_dir/build.log"
    exit 1
}
for package in ../*.deb; do
    cp "$package" "$repo_dir/dist/"
done
printf 'Packages: %s/dist\nBuild log: %s/build.log\n' "$repo_dir" "$build_dir"
