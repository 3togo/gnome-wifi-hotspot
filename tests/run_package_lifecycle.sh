#!/bin/sh
# Build and test packages only inside a disposable container; never install on host.
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mirror_selection=$(python3 "$repo_dir/tools/select_test_mirrors.py")
IFS='|' read -r selected_country test_image WIFI_RELAY_APT_MIRROR <<EOF
$mirror_selection
EOF
export WIFI_RELAY_APT_MIRROR
printf 'Download country: %s; image: %s; APT mirror: %s\n' \
    "$selected_country" "$test_image" "${WIFI_RELAY_APT_MIRROR:-distribution default}"
case "$WIFI_RELAY_APT_MIRROR" in
    *[!a-zA-Z0-9:/._-]*) echo 'Invalid APT mirror URL.' >&2; exit 1 ;;
esac
case "$WIFI_RELAY_APT_MIRROR" in
    ''|http://*|https://*) ;;
    *) echo 'APT mirror must use HTTP or HTTPS.' >&2; exit 1 ;;
esac
exec docker run --rm --init --network bridge \
    --mount "type=bind,src=$repo_dir,dst=/source,readonly" \
    --tmpfs /tmp:exec,mode=1777 \
    -e DEBIAN_FRONTEND=noninteractive -e GTK_A11Y=none \
    -e WIFI_RELAY_APT_MIRROR \
    "$test_image" bash -eu -c '
        printf "#!/bin/sh\nexit 101\n" > /usr/sbin/policy-rc.d
        chmod 0755 /usr/sbin/policy-rc.d
        printf "Acquire::Retries \"2\";\nAcquire::http::Timeout \"30\";\nAcquire::https::Timeout \"30\";\n" > /etc/apt/apt.conf.d/80-wifi-relay-test
        if [ -n "$WIFI_RELAY_APT_MIRROR" ]; then
            sed -i -E "s#https?://(archive|security).ubuntu.com/ubuntu/?#${WIFI_RELAY_APT_MIRROR%/}/#g" /etc/apt/sources.list.d/ubuntu.sources
        fi
        apt-get update --error-on=any
        apt-get install -y --no-install-recommends ca-certificates make dpkg-dev \
            python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
            gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 dbus xvfb xauth
        cd /source
        WIFI_RELAY_BUILD_OUTPUT=/tmp/packages packaging/build-deb.sh
        version=$(dpkg-parsechangelog -l packaging/debian/changelog -S Version)
        python3 tests/build_legacy_package.py /tmp/packages "$version" /tmp/legacy.deb
        apt-get install -y --no-install-recommends /tmp/legacy.deb
        sh tests/check_package_lifecycle.sh "/tmp/packages/gnome-wifi-hotspot_${version}_all.deb"
    '
