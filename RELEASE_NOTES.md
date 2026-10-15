# Wi-Fi Relay 1.0.0-30 — all-in-one bundle

**[Download bundle.deb — recommended](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-30/bundle.deb)**

Install with `sudo apt install ./bundle.deb`. Stop sharing before upgrading.

This release adds a single downloadable Debian package containing
settings, the daemon, GNOME controls and tray controls. The separate packages
remain available. GNOME Shell is optional; supported GNOME versions remain 45–51.
Build all four packages with `./build.sh`; output is in `build/dist/`.

The bundle conflicts with and replaces the separate packages. Stop sharing before
switching package layouts or upgrading. APT still supplies system dependencies.
Checksums are supplied alongside the release packages; artifacts are unsigned.

Automated checks and disposable-container package lifecycle checks passed,
including split/bundle transitions and credential preservation.
USB client validation completed four start/connect/traffic/stop cycles on one
Android 15 phone, covering DHCP, fresh DNS, verified HTTPS and cleanup; invalid
TLS was rejected separately. Earlier endpoint timeout and upstream DNS-answer
variation observations remain recorded. Six containerized LightDM fresh logins
passed on GNOME and XFCE with startup enabled, disabled and re-enabled, including
extension loading and tray registration. Host graphics and GDM logins remain
outside this validation scope. See
[release scope and rollback](docs/releases/1.0.0-30.md) and the
[candidate evidence](docs/releases/1.0.0-30-rc1.md). Final packages retain the
validated candidate runtime payloads; release documentation and version metadata
are updated.

---

# Wi-Fi Relay 1.0.0 — Debian revision 29

Desktop appearance maintenance release for Ubuntu 26.10 (Stonking), package
**1.0.0-29**. The stable default remains create_ap. NetworkManager AP+STA and
separate downstream desktop patches remain experimental.

## Changes

- XFCE and KDE settings now use native GTK themes, fonts, accent colors, and
  window-manager decorations. GNOME retains Libadwaita and its desktop styling.
- Compact tabbed settings fit the full loaded content, including larger text.
  Scrolling keeps every control reachable on small displays.
- Notifications, Wi-Fi QR codes, and About dialogs preserve desktop appearance.
- Follow dark/light theme changes and recover KDE portal preferences after
  service restarts, including portals that use the legacy Read method.
- Exercise the actual application across GNOME, KDE, and XFCE settings fixtures,
  enlarged text, and 800×600 screens.

## Downloads and upgrade

Download matching standalone and optional GNOME/tray packages from
[revision 29](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0-29).
Stop sharing before installing or downgrading. Keep a private backup of
`/etc/wifi-hotspot.conf` and your previous matching packages. See the
[user guide](docs/user-guide.md) and [rollback instructions](docs/releases/1.0.0-29.md).
Artifacts are unsigned; this release does not establish a signed APT repository.

## Validation scope

Release reports record exact source and package hashes, executed checks, and
unperformed checks. Desktop fixtures exercise real GTK windows with simulated
GNOME/KDE/XFCE preferences; they do not certify separate live desktop sessions.

The daemon and network backend payloads are unchanged from revision 28. Its
[two-client Intel AX200 physical baseline](docs/evidence/hardware-release-1.0.0-28.json)
records Wi-Fi-only forwarding, restart/rejoin cycles, DNS, HTTPS, invalid TLS
rejection, and concurrent integrity-checked transfers. Physical traffic tests
were not repeated for revision 29. The published baseline retains its original
package versions and hashes.

Other drivers, multi-adapter routing, suspend/resume, long soaks, and RPM builds
remain outside the validated release scope. NetworkManager remains experimental.
