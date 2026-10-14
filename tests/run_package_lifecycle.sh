#!/bin/sh
# Build and test packages only inside a disposable container; never install on host.
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec docker run --rm --init --network bridge \
    --mount "type=bind,src=$repo_dir,dst=/source,readonly" \
    --tmpfs /tmp:exec,mode=1777 \
    -e DEBIAN_FRONTEND=noninteractive -e GTK_A11Y=none \
    ubuntu:26.10 bash -eu -c '
        printf "#!/bin/sh\nexit 101\n" > /usr/sbin/policy-rc.d
        chmod 0755 /usr/sbin/policy-rc.d
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
