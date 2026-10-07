# Wi-Fi Relay 1.0.0 Beta 2

Beta 2 adds an optional NetworkManager sharing backend, recoverable hotspot
sessions, and a Wi-Fi Relay submenu in Ubuntu's NetworkManager Applet. It remains
an experimental beta release tested primarily on Ubuntu 26.10/XFCE.

**[Read the user guide](docs/user-guide.md)** for step-by-step setup, desktop controls,
recovery behavior, and troubleshooting.

## Install or upgrade

| Download | Purpose |
| :--- | :--- |
| [Relay `1.0.0-12` (.deb)](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/gnome-wifi-hotspot_1.0.0-12_all.deb) | Base package, tested on Ubuntu 26.10 |
| [Relay `1.0.0-12+ubuntu26.10.11` (.deb)](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/gnome-wifi-hotspot_1.0.0-12%2Bubuntu26.10.11_all.deb) | Package built and lifecycle-tested by CI |
| [SHA256SUMS](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/SHA256SUMS) | Checksums for packages, applet sources, and build information |
| [BUILD_INFO.txt](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/BUILD_INFO.txt) | Source commit, build provenance, and validation summary |

Download either Relay package and `SHA256SUMS` into the same directory,
verify its checksum, and install it:

```sh
sha256sum --ignore-missing -c SHA256SUMS
sudo apt install ./gnome-wifi-hotspot_1.0.0-12_all.deb
wifi-hotspot-settings
```

For the CI build, substitute its downloaded filename in the install command.

### First-run setup

Open **Wi-Fi Relay** from the application launcher or run `wifi-hotspot-settings`
as your normal user. In **General**:

1. Set **Hotspot Name (SSID)** and a password of at least eight characters.
2. Under **Network Interfaces and Frequency Band**, choose the actual **Wi-Fi Adapter**.
   For `create_ap` sharing Wi-Fi through one adapter, choose the same adapter as the
   **Internet Sharing Interface**; the default `wlan0` may not exist on your machine.
3. Select **Hotspot Backend**. Existing configurations retain `create_ap`.
   **NetworkManager (Experimental)** is opt-in; connect the selected adapter to
   upstream Wi-Fi on a permitted AP channel first. It follows the host default route
   and does not switch upstream bands. Unsupported overrides are rejected.
4. Enable sharing with **Hotspot Status → Service Status**, the tray Hotspot switch,
   or the GNOME Quick Settings toggle. Settings save automatically.

**Start tray at login** starts the desktop controls; it does not start hotspot
broadcasting. Stop sharing before changing backends. The NetworkManager backend
supports WPA2, hidden SSID, client isolation, raw PSK, and a /24 gateway; IEEE
generation overrides, custom DNS/country, MAC filtering, and non-NAT modes are
unsupported. See the [setup and backend guide](https://github.com/3togo/gnome-wifi-hotspot#hotspot-backends).

Upgrading restarts the service and stops an active hotspot. Log out and back in
so the desktop controls load the new code, then explicitly enable sharing again.
A reboot or daemon restart clears the in-memory sharing request.

## Optional XFCE network-menu integration

These downstream **amd64 Ubuntu 26.10** packages add a Wi-Fi Relay submenu beside
VPN Connections. Download all three matching packages:

- [network-manager-applet](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/network-manager-applet_1.36.0-4ubuntu1%2Brelay3_amd64.deb)
- [network-manager-gnome](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/network-manager-gnome_1.36.0-4ubuntu1%2Brelay3_amd64.deb)
- [nm-connection-editor](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/nm-connection-editor_1.36.0-4ubuntu1%2Brelay3_amd64.deb)

Verify them with `SHA256SUMS`, then install them together with Relay installed:

```sh
sudo apt install ./network-manager-applet_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./network-manager-gnome_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./nm-connection-editor_1.36.0-4ubuntu1+relay3_amd64.deb
```

Log out and back in, then click the usual network icon → **Wi-Fi Relay** beside
**VPN Connections**. Its Hotspot checkbox controls the backend selected in Relay
Settings and can cancel waiting recovery. Install and configure Relay first.

The hotspot is a Wi-Fi AP; it is not registered as a VPN. GNOME Shell uses the
separate Quick Settings extension and does not need these applet replacements.
The [matching patched applet source archive](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/network-manager-applet_1.36.0-4ubuntu1%2Brelay3_source.tar.xz) is included for rebuilding with
`sudo apt-get build-dep network-manager-applet` and `dpkg-buildpackage -b -uc -us`.
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

## Recovery behavior

Temporary upstream loss stops the current AP and leaves the sharing request
waiting. Recovery retries after the original Wi-Fi profile is stable on a permitted
channel, including after NetworkManager restart or suspend. Waiting and connecting
sessions appear amber and remain cancellable. Stop, radio-off, or changing settings
cancels recovery. A daemon restart or reboot clears the in-memory sharing request;
seamless roaming is not promised.

## Validation and remaining limits

170 Python tests, Node menu-state checks, and 16 applet cases under address and
undefined-behavior sanitizers pass locally. The release source is also checked by
[the passing Ubuntu 26.10 CI workflow](https://github.com/3togo/gnome-wifi-hotspot/actions/runs/37675244790),
including GTK widgets and package lifecycle checks.

Release source commit: `bfd860c64270855a1d6e38bad5e87705015543b8`. Published
downloads were verified against their checksums.

An isolated Ubuntu 26.10 upgrade from the published Beta 1 `1.0.0-10` package
to `1.0.0-12` preserved settings and passed removal, purge, fresh-install, and
`dpkg --audit` checks.

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
