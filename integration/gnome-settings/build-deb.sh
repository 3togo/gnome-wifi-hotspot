#!/bin/bash
# Build the Ubuntu GNOME Settings Wi-Fi tab correction without installing it.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
source_version=1:51.0-1ubuntu1
version=${1:-1:51.0-1ubuntu1+relay2}
all_packages=${2:-}
[[ -z $all_packages || $all_packages == --all ]] || { echo 'Usage: build-deb.sh [version] [--all]' >&2; exit 2; }
dpkg --validate-version "$version"
mkdir -p "$repo_dir/dist"
build_dir=$(mktemp -d "$repo_dir/dist/gnome-settings-build.XXXXXX")
cd "$build_dir"
apt-get source "gnome-control-center=$source_version"
cd gnome-control-center-51.0
python3 "$repo_dir/packaging/minimize-integrations.py" settings "$source_version" debian/control
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
artifacts=(../gnome-control-center_"${version#*:}"_*.deb)
[[ $all_packages != --all ]] || artifacts=(../*.deb)
for package in "${artifacts[@]}"; do
    cp "$package" "$repo_dir/dist/"
done
printf 'Packages: %s/dist\nBuild log: %s/build.log\n' "$repo_dir" "$build_dir"
