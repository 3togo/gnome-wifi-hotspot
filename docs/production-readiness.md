# Wi-Fi Relay production refactor

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
timestamps. Debian attribution includes both create_ap copyright notices; RPM
and Make installation include the shared modules. GNOME Shell is optional for
the standalone desktop app. CI additionally exercises install, upgrade, remove,
and purge inside its disposable Stonking environment.

Local non-destructive checks:

```
python3 -m unittest discover -s tests
node tests/test_tray.mjs
dbus-run-session -- python3 tests/check_settings_window.py
dbus-run-session -- python3 tests/check_desktop_tray.py
dbus-run-session -- env SANITIZE=1 integration/nm-applet/test.sh
```

Use xvfb-run in a headless environment. Desktop checks use fake transport and
real widgets; they do not start a hotspot or rewrite host preferences.
Never run check_package_lifecycle.sh on a workstation: it removes and purges
the package and is deliberately restricted to the disposable CI environment.

## Release gates

Passing automated tests does not certify wireless drivers or the patched GNOME
and NetworkManager stack. Before declaring a production release, exercise both
backends on the supported adapter/driver matrix, AP+STA contention and channel
changes, suspend/resume, upstream loss/recovery, daemon crashes/restarts,
repeated desktop upgrades, client traffic, and extended operation. Verify the
native-core, nm-applet, and GNOME Settings patches against their exact supported
package versions. Existing configurations may retain the old factory password;
users should choose a strong password before broadcasting.

RPM installation and full GNOME Shell integration require platform validation.
Source artifacts are unsigned; repository publication and signing are separate
release steps. This refactor does not replace those release gates.
