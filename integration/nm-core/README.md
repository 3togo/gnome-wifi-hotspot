# Native Wi-Fi Relay development build for Stonking

This is a downstream prototype against NetworkManager `1.58.1-1ubuntu3` on Ubuntu
26.10 Stonking. It moves child AP creation and ownership into NetworkManager.
The applet submenu still calls Wi-Fi Relay's service; Relay's NetworkManager
backend detects the native capability and submits an ordinary WPA2/shared-IPv4
AP profile instead of creating or deleting an interface with `iw`.

The native implementation is a development build. Its automated tests do not
establish successful AP+STA activation on a physical radio. Driver/supplicant
initialization, NM crash/restart cleanup, suspend/resume, client connectivity,
and multiple-driver behavior remain live-validation gates. The existing helper
backend remains available on an unpatched NetworkManager.

## Profile contract

The Wi-Fi plugin advertises downstream capability `0x7001`, within NetworkManager's
reserved downstream range. A native profile uses the existing `user.data` field:

```text
org.freedesktop.NetworkManager.wifi-relay.parent = <station interface name>
```

This key is a local development contract, not a standardized NetworkManager
wireless property. It avoids adding a public libnm ABI while the behavior is
evaluated. The profile must specify a distinct child `connection.interface-name`,
AP mode, a fixed `bg` or `a` band/channel, `cloned-mac-address=preserve`, WPA2
(`wpa-psk`, only `rsn`), shared IPv4, and `autoconnect=false`.

Activation follows the existing authorization and virtual-device paths. It requires
an already active wpa_supplicant station parent and does not activate or switch the
parent. Fresh nl80211 queries check interface combinations, existing netdev/P2P
capacity, and channel restrictions before creating an AP. Disabled, no-IR, and
radar channels are rejected. The new interface's kernel index and generated MAC
are checked before realization; deletion checks its index, name, type, and MAC.
The AP cannot scan. The first implementation stops the child on parent connection
or channel change, and requires reactivation to change its parent.

Relay continues to use `AddAndActivateConnection2` with volatile persistence and
activation bound to its worker's private D-Bus connection. The native path writes
no helper interface-deletion journal and never deletes interfaces itself.
NetworkManager supplies AP activation, DHCP/DNS, and IPv4 sharing. Egress follows
the host routing policy, as with the existing NM backend.

## Build without Docker

Install build dependencies on Stonking, then build as your normal user:

```sh
sudo apt-get build-dep network-manager=1.58.1-1ubuntu3
bash integration/nm-core/build-deb.sh
```

The builder fetches the exact distribution source, preserves Ubuntu's patches,
applies `native-relay.patch`, and builds/tests the complete package. Its default
development version is `1.58.1-1ubuntu3+relay1+dev3`. Outputs go to `dist/`.
It does not install packages or restart networking.

Build the matching Relay app and applet integration:

```sh
bash packaging/build-deb.sh 1.0.0-12+native3
bash integration/nm-applet/build-deb.sh 1.36.0-4ubuntu1+relay3+dev1
```

The applet builder requires a display, or `xvfb-run` when no display is available.
For sanitizer verification, omit any unrelated preload from the test process:

```sh
env -u LD_PRELOAD SANITIZE=1 bash integration/nm-applet/test.sh
```

The prepared local source trees and builds are under
`/home/eli/git/networkmanager-reference/relay-core/` and `relay-applet/`. Baseline
sources and packages remain under `ubuntu/`; upstream development checkouts remain
separate. See [the workspace guide](../../docs/networkmanager-development.md).

## Prepared development bundle

The local bundle is `dist/native-relay-stonking-dev1/`. It contains the matching
core/libnm, applet, and Relay packages, complete corresponding source archives,
validation logs, and `SHA256SUMS`. The clean native build passed all 85 upstream
test targets, including four new Relay regression cases. The applet passed its
three upstream tests; Relay passed 174 Python tests and its Node tray checks;
all 16 menu cases passed AddressSanitizer and UndefinedBehaviorSanitizer.
These results cover automated behavior, not physical AP+STA operation.

The corrective Relay package `1.0.0-12+native2` accepts the native worker's
`native-interface-request` stage. The original `+native1` daemon rejected that
stage as an invalid worker event. The correction passed 175 Python tests and
Node tray checks; NetworkManager and applet packages are unchanged.

Relay `1.0.0-12+native3` also corrects the native profile's D-Bus MAC policy:
`assigned-mac-address` carries the string `preserve`; the legacy
`cloned-mac-address` wire property expects bytes. The incorrect field caused
profile parsing to fail before native device selection. Both generated probe
and service profiles now pass parsing and validation with real libnm. All
176 Python tests and Node tray checks passed. Core/applet packages are unchanged.

The first physical native activation reached AP creation but crashed in WPS
cancellation with a null supplicant interface. Core `+relay1+dev2` postpones
AP preparation until asynchronous supplicant initialization completes, resumes
preparation on the ready callback, and fails cleanly when initialization fails.
It also avoids starting supplicant acquisition for an unrealized placeholder.
This addresses the observed preparation fault; end-to-end hardware operation
and crash-orphan recovery still require validation. A crash-orphan interface
must not be adopted or deleted without checking its identity.

The local system also has `libnm-dev` and `network-manager-tui` installed with
exact libnm dependencies. Upgrade their matching packages and `gir1.2-nm-1.0`
alongside NetworkManager and libnm0 to keep package dependencies consistent.

Physical activation with core `+relay1+dev2` successfully started the AP and
NetworkManager's DHCP service. After an external device disconnect, the child
remained because generic RTM_DELLINK deletion returned `EOPNOTSUPP`. Core
`+relay1+dev3` instead uses nl80211 `DEL_INTERFACE` with the exact child index,
after the existing name/index/type/MAC ownership checks. A regression case
checks the actual generic-netlink delete request and ensures no PHY-wide target
is sent. The Relay child also no longer acts as a P2P controller. Client DHCP,
DNS, internet traffic, and repeated cleanup still require live verification.

Relay `1.0.0-12+native4` honors an external NetworkManager GUI Disconnect.
The worker subscribes before activation to active-connection state changes,
filters them to its own connection, and remembers the explicit user-disconnect
reason even after the active object disappears. Its result clears the service's
resume intent; upstream interruptions and suspend retain that intent. Cleanup
accepts an already inactive connection while retaining other D-Bus errors.
All 183 Python tests and Node tray checks pass. Core/applet packages are unchanged;
the installed-system Disconnect behavior still needs verification after upgrading.

## Scope of verification

The native regression cases exercise profile validation and D-Bus round-tripping,
ordinary AP compatibility, interface-combination limits including P2P capacity,
and ownership identity mismatches. Relay tests exercise capability negotiation,
native activation failure, service operation without an interface journal, and
cleanup without helper creation/deletion commands. The menu has private-bus tests
for asynchronous operation, authorization failure, cancellation, and service changes.

The existing [native integration proposal](../../docs/networkmanager-upstream-proposal.md)
still describes the hardware gates and upstream design discussion required before
production deployment or an upstream submission. This patch has not been submitted.
New native additions are available under LGPL-2.1-or-later; upstream source files
retain their original licenses. The applet integration is GPL-2.0-or-later.
