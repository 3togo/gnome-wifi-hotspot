# Wi-Fi Relay user guide

This guide covers stable **Wi-Fi Relay 1.0.0**, package **1.0.0-18**, on Ubuntu
26.10 (Stonking). Sharing upstream Wi-Fi through one adapter requires AP+STA
support from its driver. The create_ap backend is the default; native
NetworkManager AP+STA remains experimental.

## Install or upgrade

Download the main package and `SHA256SUMS` from the
[stable release](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0).
Optionally download the matching GNOME or tray package.

| Download | Contents |
| :--- | :--- |
| [Standalone app](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0/gnome-wifi-hotspot_1.0.0-18_all.deb) | Service and GTK settings; required |
| [GNOME controls](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0/gnome-wifi-hotspot-gnome_1.0.0-18_all.deb) | Optional GNOME Shell Quick Settings and top-bar controls |
| [Tray controls](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0/gnome-wifi-hotspot-tray_1.0.0-18_all.deb) | Optional StatusNotifier/AppIndicator controls for XFCE and compatible desktops |
| [SHA256SUMS](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0/SHA256SUMS) | Checksums for release downloads |

In the download folder, verify the packages and install the combination you want:

```bash
sha256sum --ignore-missing -c SHA256SUMS
# Standalone app
sudo apt install ./gnome-wifi-hotspot_1.0.0-18_all.deb
# Optional GNOME controls
sudo apt install ./gnome-wifi-hotspot-gnome_1.0.0-18_all.deb
# Or optional tray controls
sudo apt install ./gnome-wifi-hotspot-tray_1.0.0-18_all.deb
```

Each downloaded package must report `OK`. APT installs dependencies. When
upgrading, stop sharing first and install the main and selected optional packages
in one APT command so their exact versions match. Existing credentials and
preferences are preserved. Upgrade stops sharing; enable it again afterward.
Log out and back in to load newly installed desktop controls. Older bundled
beta installs require an explicit choice of an optional control package.

## Configure sharing

Open **Wi-Fi Relay** from the application launcher, or run
`wifi-hotspot-settings` as your normal user. In **General**:

| Field | Choice |
| :--- | :--- |
| Hotspot Name (SSID) | A recognizable network name |
| Password | A strong WPA2 passphrase of 8–63 printable ASCII characters |
| Hotspot Backend | Start with create_ap |
| Wi-Fi Adapter | Your actual adapter; `wlan0` is only a default |
| Internet Sharing Interface | The same Wi-Fi adapter for a repeater, or the upstream Ethernet interface |
| Frequency Band | Start with Automatic (Recommended) |

The backend selector is under **Network Interfaces and Frequency Band**; scroll
below the network name and password. Settings save automatically. Stop active
or waiting sharing before editing settings. Leave Advanced options at their
defaults initially. Fresh installations receive a random password; an upgrade
preserves the previous password, so review it before broadcasting.

**create_ap** supports an explicit upstream sharing interface and advanced
options. On supported hardware, it can reconnect to a permitted 2.4 GHz access
point with the same upstream SSID when the current channel cannot host an AP.
This briefly interrupts the laptop connection. Different upstream SSIDs for
2.4 GHz and 5 GHz require manual selection.

**NetworkManager (Experimental)** requires the selected adapter to be connected
to upstream Wi-Fi first. It broadcasts on that channel and shares the host
default route, including a preferred Ethernet or VPN route. The sharing-interface
selector is disabled. It does not switch the upstream band to make a channel
usable. It supports WPA2, hidden SSID, client isolation, raw PSK, and a /24 gateway.
IEEE generation overrides, MAC filtering, custom DNS/country, and non-NAT modes
are unsupported and rejected. The shared password-field label does not imply
WPA3 support in this backend.

## Start and stop

1. Confirm the laptop has internet access. For NetworkManager, confirm the selected adapter is connected to upstream Wi-Fi.
2. Enable **General → Hotspot Status → Service Status** and wait for active status.
3. Connect a client with the configured name and password, or scan **Show QR**. QR generation stays on your computer.
4. Check internet access on the client and inspect **Devices & Sharing → Connected Devices**.

For a hidden SSID, add the network manually or use the QR code. Leave Hidden
SSID off for initial troubleshooting. Closing Settings leaves sharing running.
Turn off the status switch to stop sharing and disconnect clients.

## Desktop controls

All controls operate the same service and reflect changes made in other clients.

| Control | Use |
| :--- | :--- |
| Standalone Settings | Service Status switch; available without optional packages |
| GNOME package | Quick Settings → Wi-Fi Relay, with settings and client information |
| Tray package | Relay icon → Enable hotspot or Hotspot Settings |

**Start desktop controls at login** shows the controls at login; it does not
start broadcasting. On GNOME, an explicit disable choice in Extensions is
preserved. Re-enable there or run:

```bash
gnome-extensions enable wifi-relay@3togo.github.io
```

GNOME compatibility is declared for Shell 45–51, with automated loading checked
on 51. Tray controls require a desktop supporting StatusNotifier/AppIndicator.
The stable packages leave the distribution's network menu and Settings intact.
Version-specific downstream [applet patches](../integration/nm-applet/README.md)
and [GNOME Settings patches](../integration/gnome-settings/README.md) are separate
maintainer experiments. Their old beta binary downloads have been retired.

## Status and recovery

| Status | Meaning |
| :--- | :--- |
| Off / gray | Sharing is not requested |
| Connecting / amber | AP activation is in progress |
| Waiting / amber | NetworkManager sharing is requested, but upstream or channel eligibility is not ready |
| Active / green | Clients can connect |
| Stopping / amber | Session cleanup is running |
| Error / unavailable | Read the error and inspect diagnostics |

NetworkManager temporarily stops the AP on upstream loss and retains the request.
It retries when the original Wi-Fi profile is stable on a permitted channel,
including after NetworkManager restart or suspend. Seamless roaming is not
promised. Stop, radio-off, or changing settings cancels recovery. Re-enabling the
radio alone does not request sharing. A daemon restart or reboot clears the
request; desktop client restart alone does not stop a service-owned hotspot.

## Troubleshooting

| Problem | Action |
| :--- | :--- |
| Missing desktop controls | Install the optional package, log out/in, enable startup controls; check GNOME Extensions. Settings remains available. |
| Wrong adapter | Select the actual interface listed by `nmcli device status`. |
| Unsupported NetworkManager options | Stop sharing and clear unsupported advanced overrides. |
| Ineligible channel | Connect upstream on a permitted channel, often 2.4 GHz. Disabled, no-IR, and DFS/radar channels are excluded. |
| Waiting indefinitely | Reconnect the original upstream profile. After deliberately changing profiles, stop and start a new request. |
| No AP+STA support | Use another compatible adapter/driver; software cannot add missing hardware support. |
| Client cannot see hotspot | Confirm active status, SSID, hidden-network choice, and client band support. |
| Client connects without internet | Verify host access, client DHCP address/gateway, sharing interface, routing, and VPN policy. |
| Authorization failure | Use an active local desktop session and complete administrator authentication if requested; run Settings as your normal user. |
| AppArmor denies dnsmasq files | Review the denial; an administrator may grant narrowly scoped local access under `/run/wifi-relay/create-ap/`. Keep enforcement enabled. |

Read service and connection state with:

```bash
systemctl status wifi-hotspot-daemon.service --no-pager
journalctl -u wifi-hotspot-daemon.service -n 80 --no-pager
nmcli device status
wifi-relay-nm-probe --station wlo2
```

Replace `wlo2` with your adapter. The probe is read-only unless explicitly asked
for a live test. Include package version, desktop, backend, adapter/driver, and
errors in a bug report. Remove personal network details and passwords; do not
post `/etc/wifi-hotspot.conf`. Broader hardware, suspend/resume, and extended
traffic coverage remains unverified; see the [release notes](../RELEASE_NOTES.md).

## Remove or roll back

Stop sharing before removal. Remove installed optional packages along with the
main package using `sudo apt remove`; use `sudo apt purge` to remove their system
configuration too. Per-user preferences remain. Removing just an integration
leaves the standalone app, service, and credentials intact. For a downgrade,
follow [release maintenance and rollback](releases/1.0.0-18.md), keeping all
selected package versions matched. A patched distribution applet must be
[restored separately](../integration/nm-applet/README.md#maintenance-and-rollback).
