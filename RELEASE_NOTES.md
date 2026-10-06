# Wi-Fi Relay 1.0.0 Beta 1

Wi-Fi Relay shares an existing Wi-Fi connection through a concurrent hotspot
on supported adapters, with a persistent desktop tray and a GTK settings app.

## Install and configure

Download `gnome-wifi-hotspot_1.0.0-10_all.deb`, then run:

```bash
sudo apt install ./gnome-wifi-hotspot_1.0.0-10_all.deb
wifi-hotspot-settings
```

Choose the actual Wi-Fi adapter and internet sharing interface. For sharing Wi-Fi
from a single adapter, select that adapter for both fields. Set the network name
and password before enabling the hotspot. Tray startup defaults to on and can be
changed under **General → Startup → Start tray at login**. Log out and back in
after installation to activate the session startup entry.

## Changes

- Gray tray icon when off, amber while connecting/stopping, and green when on.
- XFCE StatusNotifier tray with hotspot control, connected devices, and settings.
- GNOME extension renamed to `wifi-relay@3togo.github.io`, with migration of the
  previous extension's enabled and disabled choices.
- Channel-aware AP+STA checks and automatic reconnection to a permitted 2.4 GHz
  access point on the same upstream network when necessary.
- Polkit authorization for network changes and configuration/password reads.
- Configuration validation, literal backend parsing, atomic saving, and
  owner-only permissions for the password file.

Existing package names, commands, configuration paths, and D-Bus identifiers
remain compatible. Upgrading restarts the daemon and may stop an active hotspot;
enable it again from the tray after the upgrade.

## Beta scope and known limitations

- Initial beta focus: Debian/Ubuntu packages and the XFCE tray.
- Concurrent sharing depends on the Wi-Fi adapter, driver, and permitted channels.
  Band fallback can briefly interrupt the upstream connection.
- Real GNOME desktop integration and RPM installation remain unverified. The
  extension declares GNOME 45–50; GNOME 51 is not supported by this beta.
- The settings app's sharing dialog displays connection text; it does not yet
  render a scannable QR image.
- Debian package linting has warnings for direct service-policy reloads, the
  missing autostart-helper manual page, and intentional `0600` config permissions.

## Verification

- 55 automated tests pass, including denied authorization, malformed settings,
  atomic-write failure, startup preferences, and extension UUID migration.
- GNOME tray controller checks pass. Real GTK4 settings and GTK3 desktop-tray
  checks also pass on Ubuntu 24.04 under Xvfb.
- Native GJS startup preference checks and package checksum verification pass.
- Installed version `1.0.0-9` passes authorized configuration reads and rejection
  of malformed updates without changing the saved settings.
- Debian linting has no errors; AppStream validation succeeds.
- Ubuntu 24.04 container: installation with full dependencies, upgrade from
  `1.0.0-7`, removal, purge, and fresh installation of `1.0.0-10` pass. Upgrade
  preserves a modified config and changes its permissions from `0644` to `0600`.
- Physical reboot on Ubuntu 26.10/XFCE: the installed `1.0.0-9` daemon starts at
  boot and the tray starts automatically at login. The final `1.0.0-10` adds
  settings heading fixes and release documentation; startup/security code is
  unchanged.
