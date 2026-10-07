# Wi-Fi Relay 1.0.0 Beta 2

Beta 2 adds an optional NetworkManager sharing backend, recoverable hotspot
sessions, and a Wi-Fi Relay submenu in Ubuntu's NetworkManager Applet. It remains
an experimental prerelease tested primarily on Ubuntu 26.10/XFCE.

## Install or upgrade

Download `gnome-wifi-hotspot_1.0.0-12_all.deb` and `SHA256SUMS` from this release.
The Ubuntu 26.10 CI build is also supplied with its original versioned filename.
Choose one Relay package, verify its checksum, and install it:

```sh
sha256sum --ignore-missing -c SHA256SUMS
sudo apt install ./gnome-wifi-hotspot_1.0.0-12_all.deb
wifi-hotspot-settings
```

For the CI build, substitute its downloaded filename in the install command.
In Settings, choose the actual Wi-Fi adapter and sharing interface, set an SSID
and password, and choose the hotspot backend. Existing configurations retain
`create_ap`; NetworkManager is opt-in and needs an associated upstream on a
permitted AP channel. Unsupported options are rejected rather than silently ignored.

Upgrading restarts the service and stops an active hotspot. Log out and back in
so the desktop controls load the new code, then explicitly enable sharing again.
A reboot or daemon restart clears the in-memory sharing request.

## Optional XFCE network-menu integration

These downstream **amd64 Ubuntu 26.10** packages add a Wi-Fi Relay submenu beside
VPN Connections. Install all three matching versions together with Relay:

```sh
sudo apt install ./network-manager-applet_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./network-manager-gnome_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./nm-connection-editor_1.36.0-4ubuntu1+relay3_amd64.deb
```

The hotspot is a Wi-Fi AP; it is not registered as a VPN. GNOME Shell uses the
separate Quick Settings extension and does not need these applet replacements.
Distribution updates can replace the patched applet. See
[integration/nm-applet/README.md](integration/nm-applet/README.md) for rollback.

## Changes since Beta 1

- Optional service-owned NetworkManager AP+STA backend with volatile profiles,
  credentials passed through a pipe, and identity-checked resource cleanup.
- Retry owned-resource cleanup when NetworkManager is temporarily unavailable.
- Resume authorized sharing after temporary upstream loss, NetworkManager restart,
  or suspend, once the original Wi-Fi profile and a permitted channel are stable.
- Keep recovery pinned to the original upstream profile. Stop, radio-off, or a
  settings change cancels recovery. Waiting and connecting retries remain cancellable.
- Show waiting state in Settings, desktop tray, GNOME Quick Settings, and the
  optional applet submenu, without reporting waiting sessions as active.
- GNOME Shell 51 support, checked with an isolated headless load and disable/re-enable.
- Repeatable Android DNS/HTTPS probes and sanitized live validation reports.

## Validation and remaining limits

170 Python tests, Node menu-state checks, and 16 applet cases under address and
undefined-behavior sanitizers pass locally. The release source is also checked by
the Ubuntu 26.10 CI workflow, including GTK widgets and package lifecycle checks.

Physical checks passed upstream disconnect/reconnect, Stop while waiting,
NetworkManager restart, suspend/resume, and installed menu Start/Stop. Android
HTTPS returned 200 from two endpoints with TLS certificate and hostname checks;
an invalid-hostname endpoint failed at the TLS handshake. Ten gateway DNS result
codes matched direct upstream queries, locating the observed negative-answer
variation upstream rather than specifically in Relay startup.

Coverage is limited to one physical Wi-Fi driver. Full GNOME desktop interaction,
natural roaming, multiple-client soak, distribution applet upgrades, and RPM
installation still need coverage. Earlier combined upgrade/restart trials lost
sharing intent; the cancellation source was not conclusively identified. The
combined run passed after the desktop clients were restarted with current code.
This is not a native upstream NetworkManager merge, and seamless roaming is not
promised. QR image rendering remains planned.

See [the live validation report](docs/networkmanager-live-validation.md) and
[its evidence](docs/evidence/nm5-validation-2026-10-07.json) for results and limits.
