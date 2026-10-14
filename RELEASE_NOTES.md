# Wi-Fi Relay 1.0.0 — Debian revision 28

Maintenance release for Ubuntu 26.10 (Stonking), package **1.0.0-28**.
The default backend remains create_ap. Native NetworkManager AP+STA and the
separate downstream desktop patches remain experimental.

## Changes

- Wait for hostapd to enable the AP before reporting successful startup; clean up
  failed launches and stop the owned worker even before it becomes active.
- Launch hostapd directly so shutdown reaches the actual process. Recover from
  stale Relay-owned hostapd processes and release the adapter before reuse.
- Avoid MAC collisions with unnamed P2P interfaces.
- Honor an explicit hotspot band, retry upstream activation with a temporary
  band constraint, and restore the saved profile preference afterward.
- Detect the sole Wi-Fi adapter on fresh installations and repair obsolete
  wlan0 configuration during upgrades.
- Add settings retry controls. Extend private-bus authorization, settings,
  startup, Android probe parsing, and package lifecycle coverage.
- Run desktop smoke checks on private buses and preferences so loading test
  controls cannot stop a live hotspot.

## Downloads and upgrade

Download matching standalone and optional GNOME/tray packages from
[revision 28](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0-28).
Stop sharing before installing or downgrading. Keep a private backup of
`/etc/wifi-hotspot.conf` and your previous matching packages. See the
[user guide](docs/user-guide.md) and [rollback instructions](docs/releases/1.0.0-28.md).
Artifacts are unsigned; this release does not establish a signed APT repository.

## Validation scope

The merged candidate passes 336 unit tests. Release validation reports record
exact source hashes, executed checks, package hashes, and unperformed checks.
The installed revision-28 packages also pass a two-client Intel AX200 physical
regression: Wi-Fi-only forwarding, three create_ap restart/rejoin cycles, DNS
comparison with the upstream resolver, HTTPS, invalid TLS rejection, and 448 MiB
of concurrent integrity-checked transfers across both backends. Network and device
power settings were restored. See [versioned physical evidence](docs/evidence/hardware-release-1.0.0-28.json)
for exact payload hashes, the initial Android automation failure, and limits.
Earlier fixed-payload evidence is retained separately.

Hardware coverage is limited to the recorded Intel AX200 and Android 14 bench.
Other drivers, multi-adapter routing, suspend/resume, long soaks, and RPM builds
remain outside the validated release scope. NetworkManager remains experimental.
