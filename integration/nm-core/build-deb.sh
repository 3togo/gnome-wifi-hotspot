#!/bin/bash
# Build the downstream native Relay prototype on Ubuntu Stonking; never install it.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
version=${1:-1.58.1-1ubuntu3+relay1+dev3}
all_packages=${2:-}
[[ -z $all_packages || $all_packages == --all ]] || { echo 'Usage: build-deb.sh [version] [--all]' >&2; exit 2; }
dpkg --validate-version "$version"
make -C "$repo_dir" test
mkdir -p "$repo_dir/dist"
build_dir=$(mktemp -d "$repo_dir/dist/nm-core-build.XXXXXX")
cd "$build_dir"
apt-get source network-manager=1.58.1-1ubuntu3
cd network-manager-1.58.1
patch -p1 < "$repo_dir/integration/nm-core/native-relay.patch"
python3 - "$version" <<'PY'
from pathlib import Path
from email.utils import formatdate
import sys
path = Path('debian/changelog')
path.write_text('network-manager (' + sys.argv[1] + ') stonking; urgency=medium\n\n'
    '  * Add experimental native Wi-Fi Relay child AP ownership and activation.\n\n'
    ' -- Wi-Fi Relay <3togo@users.noreply.github.com>  ' + formatdate(localtime=True)
    + '\n\n' + path.read_text())
PY
env -u LD_PRELOAD dpkg-buildpackage -b -uc -us -j4 > "$build_dir/build.log" 2>&1 || {
    tail -80 "$build_dir/build.log"
    exit 1
}
packages=(network-manager libnm0)
if [[ $all_packages == --all ]]; then
    artifacts=(../*"_${version}_"*.deb)
else
    artifacts=()
    for package in "${packages[@]}"; do
        artifacts+=(../"${package}_${version}_"*.deb)
    done
fi
for package in "${artifacts[@]}"; do
    cp "$package" "$repo_dir/dist/"
    (cd "$repo_dir/dist" && sha256sum "$(basename -- "$package")" > "$(basename -- "$package").sha256")
done
printf 'If installed, exact-version libnm-dev and network-manager-tui also need matching builds; use --all.\n'
printf 'Packages: %s/dist\nBuild log: %s/build.log\n' "$repo_dir" "$build_dir"
