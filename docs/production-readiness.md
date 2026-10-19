# Wi-Fi Relay architecture and release validation

This refactor preserves the native NetworkManager and create_ap backends and the
existing desktop controls. It improves the application around those backends;
the native AP+STA integration remains a hardware-dependent prototype.

## Current release baseline: revision 31

[v1.0.0-31](releases/1.0.0-31.md) is the 19 October 2026 reliability release
for Ubuntu 26.10. The recommended `bundle.deb` contains the daemon, settings,
GNOME and tray controls; matching separate packages remain available. GNOME
Shell is optional. create_ap remains the stable default and native
NetworkManager AP+STA remains experimental.

Final source validation covers 383 Python tests, Node tray checks, private
D-Bus and GTK checks, extracted packages, sanitized applet checks and isolated
GNOME Shell checks. Source/binary builds and disposable-container package
lifecycle checks cover installation, upgrades, split/bundle transitions,
removal, purge, credential preservation and secure fresh-install defaults.
The release asset `VALIDATION.json` identifies final source, checks, CI and
package hashes; the final runtime matches the physically tested `~fix7` packages.

The [development fault trials](releases/1.0.0-31-development.md) retain earlier
failed candidates and the successful `~fix7` physical/virtual AP, two-client
traffic, six cancellation timings and shell-crash cleanup results. A separate
[installed 2.4 GHz record](evidence/physical-installed-2.4ghz-2026-10-19.json)
verifies channel 12 with the Android 14 phone and tablet and Ethernet egress.
The physical host used a downstream NetworkManager build, not stock networking.
Strict NXDOMAIN failures with matching upstream NOERROR/NODATA responses remain
recorded. Other drivers/client OSes, reboot/suspend, native-backend physical
recovery, the ten-cycle matrix and extended soaks remain untested for this build.

Historical revision-30 [candidate](releases/1.0.0-30-rc1.md),
[USB traffic](evidence/physical-usb-1.0.0-30-rc1.json),
[container login](evidence/desktop-login-container-1.0.0-30-rc1.json) and
[release-source CI](https://github.com/3togo/gnome-wifi-hotspot/actions/runs/38684574384)
records retain their original build and scope. They are not reclassified as new
revision-31 results. See [release notes](releases/1.0.0-31.md) for upgrade,
rollback and testing limits, and [distribution readiness](distribution-readiness.md)
for announcement/PPA decisions.

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
so edits are not silently dropped. Failed loads, saves, status requests, and
Start/Stop operations expose a persistent message and a Retry button. Retrying a
save uses the current form and never starts sharing automatically.

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

Build the bundle and separate binary packages without installing or restarting
anything:

```
./build.sh
```

The CMake entry point writes packages and checksums under `build/dist/`.
`./packaging/build-deb.sh` remains available for direct builds under `dist/`.

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
the standalone desktop app and bundle. CI additionally exercises install,
upgrade, remove, and purge inside its disposable Stonking environment.

Local non-destructive checks:

```
make test
make test-integration
make test-smoke
make smoke
make validate
# Optional wider validation, including disposable-container package operations:
make validate VALIDATE_ARGS="--full --with-lifecycle"
```

The installed-system smoke test reads service and network state and calls the
read-only `GetStatus` method. It never starts, stops, or reconfigures a hotspot.
Checks unavailable in the current environment are reported as skipped.

Use xvfb-run in a headless environment. Desktop checks use isolated transport and
real widgets; they do not start a hotspot or rewrite host preferences.
Never run check_package_lifecycle.sh on a workstation: it removes and purges
the package and is deliberately restricted to the disposable CI environment.

The integration suite uses the production ServiceClient and daemon dispatch,
configuration validation/writes, and authorization flow on a private D-Bus bus.
A local Polkit fixture returns authorization decisions; deterministic hardware
boundaries replace Wi-Fi operations. Real GTK tests cover denied loads, saves,
and Stop, rapid edits, stale clients, and status recovery. These tests exercise
transport and UI behavior without certifying actual Polkit session policy or
radio behavior.

Validation reports under `dist/validation/` include UTC timing, the Git commit,
worktree state, hashes and modes for source files, environment, commands, results,
logs, and package hashes when built. A changed source tree fails the report;
unperformed checks remain `not_run`. An overall pass describes only executed
checks. The full run tests extracted package contents as well as source.
`--with-lifecycle` builds and installs packages exclusively inside a disposable
Ubuntu 26.10 Docker container; it needs Docker and network access.

## Historical validation

Revision 22 passed 283 unit tests with no skips, real GTK4/GTK3 widgets, 17
sanitized applet cases, and private-bus daemon authorization on Ubuntu 26.10.
Source exports retained nested `packaging/debian` templates and rebuilt without
Git metadata; a regression test covers this path. Its
[release maintenance record](releases/1.0.0-22.md) remains unchanged.

The October 14 correction passed 322 unit tests, private D-Bus and GTK checks,
sanitized applet tests, isolated headless GNOME checks, package builds, and
container install/upgrade/remove/purge checks. The
[physical correction evidence](evidence/hardware-fixes-2026-10-14.json) records
ten two-client DNS/HTTPS restart cycles per backend and 480 MiB of additional
Wi-Fi-only transfers with no integrity errors. It retains the
[initial failures](evidence/hardware-validation-2026-10-14.json) separately.
The fixed legacy backend waits for hostapd readiness and tracks its actual PID.
Android fixtures validate the current BSSID and refresh DHCP addresses; the
headless GNOME check isolates its system bus so disabling the extension cannot
stop a workstation hotspot. These results identify the worktree's daemon hashes,
not the previously published package payloads.

[Installed revision-28 evidence](evidence/hardware-release-1.0.0-28.json) separately
records two Android 14 clients on Intel AX200, Wi-Fi-only egress, restart/rejoin,
concurrent transfers, and cleanup. Earlier
[live validation](networkmanager-live-validation.md) retains its own recovery and
suspend results. These dated records do not complete the revision-31 hardware
matrix or certify a newly built candidate.

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

Revision-31 traffic coverage does not complete the ten-cycle matrix, other
client/driver cohorts, multi-adapter routing, suspend/reboot fault trials, or
extended multi-client soaks. RPM installation and physical interactive GNOME
coverage also require platform validation. Headless GNOME Shell 51 loading and
disable/re-enable, plus containerized GNOME/XFCE fresh logins, have recorded checks.
Source artifacts are unsigned; repository publication and signing are separate
release steps. Publication does not certify untested hardware combinations.
