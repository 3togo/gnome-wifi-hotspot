#!/bin/bash
# Real display-manager login tests in a disposable, software-rendered container.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
selection=$(python3 "$repo_dir/tools/select_test_mirrors.py")
IFS='|' read -r country base_image apt_mirror <<< "$selection"
case "$apt_mirror" in
    *[!a-zA-Z0-9:/._-]*) echo 'Invalid APT mirror URL.' >&2; exit 1 ;;
esac
case "$apt_mirror" in
    ''|http://*|https://*) ;;
    *) echo 'APT mirror must use HTTP or HTTPS.' >&2; exit 1 ;;
esac
context=$(mktemp -d)
trap 'rm -rf -- "$context"' EXIT
export WIFI_RELAY_DESKTOP_OUTPUT=${WIFI_RELAY_DESKTOP_OUTPUT:-"$repo_dir/dist/desktop-login"}
export WIFI_RELAY_DESKTOP_IMAGE=${WIFI_RELAY_DESKTOP_IMAGE:-wifi-relay-desktop-test:local}
mkdir -p "$WIFI_RELAY_DESKTOP_OUTPUT"
WIFI_RELAY_BUILD_OUTPUT="$context/packages" bash "$repo_dir/packaging/build-deb.sh"
cp "$context"/packages/gnome-wifi-hotspot-bundle_*_all.deb "$context/candidate.deb"
cp "$repo_dir/tests/desktop-login/Dockerfile" "$context/Dockerfile"
printf 'Download country: %s; image: %s; APT mirror: %s\n' "$country" "$base_image" "${apt_mirror:-distribution default}"
docker build --build-arg "BASE_IMAGE=$base_image" --build-arg "APT_MIRROR=$apt_mirror" \
    -t "$WIFI_RELAY_DESKTOP_IMAGE" "$context"
python3 "$repo_dir/tests/desktop-login/run.py"
