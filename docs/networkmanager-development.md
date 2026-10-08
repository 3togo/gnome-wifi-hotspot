# NetworkManager source development workspace

The local source workspace is `/home/eli/git/networkmanager-reference`. It keeps
complete source trees outside Wi-Fi Relay's repository. These checkouts are
development references; Relay continues to use the distribution's installed
NetworkManager. The build commands do not install the rebuilt networking packages
or restart the service.

## Pinned sources

| Tree under the workspace | Baseline | Purpose |
| --- | --- | --- |
| `NetworkManager/` | Upstream tag `1.58.1`, commit `7406dfbcc35beed79bf2734e3e7376ead320bd99` | Native AP+STA development, branch `feature/ap-sta-integration` |
| `network-manager-applet/` | Upstream tag `1.36.0`, commit `8accd508caa0400304a01da718eeab587ee8fb04` | Upstream menu comparison, branch `feature/relay-menu-integration` |
| `ubuntu/network-manager-1.58.1/` | Ubuntu source `1.58.1-1ubuntu3` | Distribution patches, packaging, and baseline build |
| `ubuntu/network-manager-applet-1.36.0/` | Ubuntu source `1.36.0-4ubuntu1` | Distribution applet baseline and Relay patch compatibility |

The Git clones contain the complete source tree at each tag, with shallow history.
Fetch additional history when needed for blame or upstream comparisons. The Ubuntu
trees were obtained with `apt-get source` and include the distribution patches.
`source-archives.sha256` records the downloaded source archives. The installed
applet has the additional `+relay3` revision; the baseline applet tree omits it.

Read any upstream `AGENTS.md` and `CONTRIBUTING.md` before future edits. Neither
pinned checkout contains `AGENTS.md`. NetworkManager's contribution guidelines
require new contributions under LGPL-2.1-or-later, including changes to currently
GPL-licensed files. Keep upstream patches separate from Relay's MIT-licensed code
and review the licenses of any code being reused.

## Baseline builds

The unchanged Ubuntu applet is built as the normal user:

```sh
cd /home/eli/git/networkmanager-reference/ubuntu/network-manager-applet-1.36.0
dpkg-checkbuilddeps
dpkg-buildpackage -b -uc -us -j4
```

Packages are emitted into the parent `ubuntu/` directory. The initial run is logged
in `applet-baseline-build.log`. A dry run of Relay's existing `relay-menu.patch`
against this source succeeds. Keep this baseline unchanged; extract a separate
Ubuntu source tree before applying the Relay patch for a comparison build.

The host runs Ubuntu 26.10 Stonking, matching the target. Build directly on the
host. The full NetworkManager package build needs additional build dependencies:

```sh
sudo apt-get build-dep network-manager=1.58.1-1ubuntu3
/home/eli/git/networkmanager-reference/build-networkmanager.sh
```

This builds and tests the distribution package with its own `debian/rules`, rather
than disabling features to accommodate missing dependencies. The script checks
build dependencies before running `dpkg-buildpackage` as the normal user. No Docker
is needed. The native build log is `networkmanager-native-baseline-build.log` in
the workspace. When changing toolchains, clean existing build output with
`dpkg-buildpackage -Tclean` before rebuilding.

The applet baseline completed successfully with three upstream tests passing.
NetworkManager's native build passed all 85 upstream test targets, including Wi-Fi
device and supplicant configuration tests, and completed package assembly with
`dpkg-buildpackage` exit status 0 on 8 October 2026. The resulting core package is
`ubuntu/network-manager_1.58.1-1ubuntu3_amd64.deb`; matching libnm, introspection,
development, optional-component, and debug packages are alongside it.
`baseline-packages.sha256` records checksums for the built NetworkManager and
applet packages. These packages retain their original distribution versions and
are comparison baselines, not Relay integration releases. Neither was installed.

## Initial investigation targets

- `src/core/devices/wifi/nm-device-wifi.c`: activation/deactivation and station
  preservation. In this baseline, `deactivate()` explicitly returns the interface
  to infrastructure mode. This is a lead, not proof of the observed startup fault.
- `src/core/supplicant/nm-supplicant-manager.c`: the `CreateInterface` request
  supplies the driver and interface name. Trace initialization through
  wpa_supplicant before attributing an AP-mode reset to NetworkManager.
- `src/libnm-platform/wifi/nm-wifi-utils-nl80211.c`: existing Wi-Fi mode control;
  evaluate where concurrent child-interface creation and ownership should fit.
- `src/core/devices/wifi/tests/test-devices-wifi.c`: existing native Wi-Fi tests.
- Relay's `tools/nm_ap_sta_probe.py` and `daemon/nm_backend.py`: the current
  preflight, ownership, cleanup, channel restrictions, and recovery reference.

The downstream prototype below establishes explicit parent/child AP ownership,
preserves the station connection, and checks resource identity during cleanup.
Channel roaming and automatic recovery remain later changes. An unchanged build and unit tests
do not validate radio concurrency or end-to-end client connectivity; those need
isolated hardware testing before deployment.

See [the native integration proposal](networkmanager-upstream-proposal.md) for the
networking contract and contribution sequence.

## Relay integration work

The `feature/native-wifi-relay-stonking` branch in Wi-Fi Relay contains a
[native downstream patch and builder](../integration/nm-core/README.md). The
upstream NetworkManager checkout contains the corresponding core changes on
`feature/ap-sta-integration`; the applet checkout contains the Relay submenu on
`feature/relay-menu-integration`.

Modified Ubuntu build trees are separate from the baselines:

- `relay-core/network-manager-1.58.1/`: `1.58.1-1ubuntu3+relay1+dev1`.
- `relay-applet/network-manager-applet-1.36.0/`: `1.36.0-4ubuntu1+relay3+dev1`.

The matching Relay app version is `1.0.0-12+native1`. The native profile contract
and pending hardware checks are documented in the integration guide. These are
development packages; the installed networking packages remain unchanged.

The prepared bundle is `dist/native-relay-stonking-dev1/` in the Relay repository.
It includes binary packages, complete matching source archives, checksums, and
validation logs. The final clean core build passed 85 test targets including
four native Relay cases; the applet passed three upstream targets. Relay's
174 Python tests, Node tray checks, and 16 sanitizer menu cases also passed.
Physical AP+STA and service crash/restart behavior remain unvalidated.
