# Wi-Fi Relay architecture and release validation

This refactor preserves the native NetworkManager and create_ap backends and the
existing desktop controls. It improves the application around those backends;
the native AP+STA integration remains a hardware-dependent prototype.

## Runtime boundaries

`daemon/configuration.py` owns configuration defaults and validation without
GTK or D-Bus imports. The daemon still owns authorization, atomic system config
writes, worker supervision, and activation. SetConfig rejects requests over
64 KiB before parsing. Fresh factory installations receive a random 128-bit
password; upgrades and customized configuration preserve existing credentials.
The Settings window displays the configured password. Clearing it is validated
by the service rather than silently restoring a shared password.

`settings/service_client.py` owns asynchronous D-Bus transport, reply validation,
cancellation, and service owner generations. ConfigurationWriter serializes
writes and coalesces queued edits. Settings waits for the visible configuration
to be acknowledged before activation; close waits for outstanding edits and
keeps the window open if saving fails. Status and client replies from an older
operation cannot replace newer state. Controls are disabled during activation
so edits are not silently dropped.

`settings/preferences.py` owns bounded JSON reads and private atomic writes.
Startup and visibility wrappers retain their existing filenames and keys,
preserve unknown fields, and share the same semantics. The applet also preserves
unknown visibility fields. Startup rolls back GNOME extension choices after a
failed preference save. The standalone tray tracks and cancels requests and
poll sources at shutdown. It reloads itself after all watched modules are
present and changed, while preserving a manual Show Icon request.

Settings generates Wi-Fi QR images locally using the bundled MIT-licensed
Nayuki encoder. Payloads escape special characters and identify hidden networks;
UTF-8 encoding supports international network names. GTK4 displays opaque RGB
pixels with a white quiet zone. No imaging or QR package is required at runtime.

## Service hardening

create_ap startup logs live under the private, service-owned
`/run/wifi-relay` directory with mode 0600. Startup refuses symlinked runtime
paths, unsafe directory permissions, foreign ownership, linked log files, and
nonregular logs before truncation. Failure replies read only the last 16 KiB
and retain up to four lines. The service no longer opens a predictable file in
the shared `/tmp` directory with root privileges.

The NetworkManager worker protocol limits each event to 64 KiB and each poll's
read budget to 256 KiB. Continuous output yields back to the service loop;
oversized or deeply nested messages stop the worker. A worker that ignores
SIGTERM after a protocol failure receives SIGKILL after 40 seconds through
nonblocking polling, then ownership recovery runs after the process exits.
Automatic NetworkManager recovery also times out activation after 55 seconds;
suspend termination receives the same 40-second kill deadline. Successful
activation cancels its watchdog, and Stop cancels recovery intent.

Legacy backend locks and state now live in `/run/wifi-relay/create-ap`. Relay
tracks a private PID marker and verifies the command and process owner before
reporting or stopping it. Separately started hotspots are not adopted. The
backend balances recursive locks even when no instance remains, and searches
for a free file descriptor without expanding the entire process limit.

DHCP/DNS rules are scoped to the hotspot interface. The firewall compatibility
method leaves permanent policies untouched, and startup does not reload
firewalld or put dnsmasq AppArmor policy into complain mode. Client names come
from DHCP leases without synchronous reverse DNS. Transient polling failures
are logged once until they change or recover. Malformed, excessively nested
per-user JSON preferences fall back to defaults.

These checks use fake network transports and temporary files. Live driver,
suspend/resume, and extended traffic testing remain outside automated coverage.

## Build and verification

Build the standalone binary without installing or restarting anything:

```
./packaging/build-deb.sh
```

Build unsigned Debian source artifacts, or source and binaries with package
build tests, on native Stonking:

```
python3 packaging/build-source.py
python3 packaging/build-source.py --binary
```

The source build requires debhelper, dh-python, Python/GI, GTK3/GTK4/adwaita,
Ayatana AppIndicator, Node.js, D-Bus, Xvfb/xauth, GCC, pkgconf, GTK3 development
headers, and Jansson development headers. Its quilt source tree is isolated
under dist and removed after building; logs and artifacts remain. Both package
builders share the same payload templates. SOURCE_DATE_EPOCH controls archive
timestamps; the direct builder normalizes every staged archive member to that
epoch, including future epochs. Repeated builds are compared byte for byte.
Debian attribution includes both create_ap copyright notices; RPM
and Make installation include the shared modules. GNOME Shell is optional for
the standalone desktop app. CI additionally exercises install, upgrade, remove,
and purge inside its disposable Stonking environment.

Local non-destructive checks:

```
python3 -m unittest discover -s tests
node tests/test_tray.mjs
dbus-run-session -- python3 tests/check_settings_window.py
dbus-run-session -- python3 tests/check_desktop_tray.py
dbus-run-session -- xvfb-run -a python3 tests/check_tray_startup.py
dbus-run-session -- env SANITIZE=1 integration/nm-applet/test.sh
```

Use xvfb-run in a headless environment. Desktop checks use fake transport and
real widgets; they do not start a hotspot or rewrite host preferences.
Never run check_package_lifecycle.sh on a workstation: it removes and purges
the package and is deliberately restricted to the disposable CI environment.

## Supported scope and remaining validation

Use the [candidate hardware checklist](release-hardware-validation.md) to record
physical checks for the exact next build. The [fork maintenance policy](fork-maintenance.md)
defines upstream review, compatible upgrades, and publication evidence.

Passing automated tests does not certify wireless drivers or the patched GNOME
and NetworkManager stack. For deployment hardware, exercise both
backends on the supported adapter/driver matrix, AP+STA contention and channel
changes, suspend/resume, upstream loss/recovery, daemon crashes/restarts,
repeated desktop upgrades, client traffic, and extended operation. Verify the
native-core, nm-applet, and GNOME Settings patches against their exact supported
package versions. Existing configurations may retain the old factory password;
users should choose a strong password before broadcasting.

RPM installation and full interactive GNOME Shell coverage require platform validation.
Headless GNOME Shell 51 extension loading and disable/re-enable are checked.
Source artifacts are unsigned; repository publication and signing are separate
release steps. Publication does not certify untested hardware combinations.

The stable release is `v1.0.0-22`, package `1.0.0-22`. Native Ubuntu 26.10 checks
passed 283 unit tests with no skips, real GTK4/GTK3 widgets, 17 sanitized applet
cases, and private-bus daemon authorization. Source exports retain nested
`packaging/debian` templates and rebuild without Git metadata; a regression test
covers this path. Exact provenance and CI results accompany release downloads.

Release maintenance and rollback are documented in [the stable release notes](releases/1.0.0-22.md).
