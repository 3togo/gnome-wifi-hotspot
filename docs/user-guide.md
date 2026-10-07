# Wi-Fi Relay user guide

This guide covers **Beta 2** on Ubuntu 26.10. Wi-Fi Relay shares an internet
connection with a phone, tablet, or another computer. Sharing an existing Wi-Fi
connection through the same adapter requires a driver that supports simultaneous
Wi-Fi client and access-point operation (AP+STA).

Beta 2 is experimental. Physical testing covers one Wi-Fi driver and XFCE.
GNOME 45–51 is declared compatible; GNOME 51 extension loading was checked in a
headless session, with full desktop interaction still awaiting validation.

## 1. Install or upgrade

Open the [Beta 2 downloads](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0-beta.2).
Download the recommended **[Wi-Fi Relay — Beta 2 for Ubuntu 26.10 (.deb)](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/gnome-wifi-hotspot_1.0.0-12%2Bubuntu26.10.11_all.deb)**
and `SHA256SUMS` into the same folder. The recommended package was built and
verified by automated tests.

Open a terminal in that folder and run:

```bash
sha256sum --ignore-missing -c SHA256SUMS
sudo apt install ./gnome-wifi-hotspot_1.0.0-12+ubuntu26.10.11_all.deb
```

The checksum check should report `OK` for your package. APT installs dependencies.

Log out and back in to load the desktop controls. An upgrade stops an active
hotspot; you must enable sharing again afterward. Existing configuration is preserved.

### Additional builds

The release also provides **[Wi-Fi Relay — Beta 2, standard build (.deb)](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/gnome-wifi-hotspot_1.0.0-12_all.deb)**,
tested on Ubuntu 26.10. Both builds contain the same app release; install only one.
If you choose the standard build, use `gnome-wifi-hotspot_1.0.0-12_all.deb`
in the install command above.

## 2. Open Settings and configure sharing

Open **Wi-Fi Relay** from the application launcher, or run this as your normal user:

```bash
wifi-hotspot-settings
```

In **General**, configure these fields:

| Location | Field | What to choose |
| :--- | :--- | :--- |
| Wireless Network Configuration | Hotspot Name (SSID) | The name your phone will see, for example `My-Laptop` |
| Wireless Network Configuration | Password (WPA2/WPA3) | A WPA2 passphrase of 8–63 printable ASCII characters for ordinary use |
| Network Interfaces and Frequency Band | Hotspot Backend | `create_ap`, or `NetworkManager (Experimental)` as explained below |
| Network Interfaces and Frequency Band | Wi-Fi Adapter | Your actual wireless adapter; `wlan0` is only a default and may not exist |
| Network Interfaces and Frequency Band | Internet Sharing Interface | For create_ap sharing Wi-Fi through one adapter, choose that same adapter; for Ethernet sharing, choose the Ethernet interface |
| Network Interfaces and Frequency Band | Frequency Band | Start with `Automatic (Recommended)` |

**Cannot find Hotspot Backend?** Stay on **General** and scroll down to
**Network Interfaces and Frequency Band**, below the network name and password.
It is the first row in that group. If the row is absent, check that Beta 2 is
installed, close Settings, and reopen it.

Settings save automatically. Stop an active or waiting sharing session before
changing settings or backends. Leave **Advanced** options at their defaults for
first use. The status switch is near the top of General, under **Hotspot Status**.

### Which backend should I use?

**create_ap** is the default and retains existing installations' behavior. It
supports selecting an internet sharing interface and exposes additional advanced
options. On supported hardware, it may reconnect to a permitted 2.4 GHz access
point with the same upstream SSID when the current channel cannot host an AP.
That switch briefly interrupts the laptop's connection. Different upstream SSIDs
for 2.4 GHz and 5 GHz require a manual switch.

**NetworkManager (Experimental)** is the optional Beta 2 integration. Connect the
selected Wi-Fi adapter to your upstream Wi-Fi first. It broadcasts on that upstream
channel and shares the host default route, including a preferred Ethernet or VPN
route. The Internet Sharing Interface selector is disabled for this backend.
It does not reconnect the upstream to another band to make a channel usable.

The NetworkManager backend supports WPA2, hidden SSID, client isolation, raw PSK,
and a /24 gateway. IEEE 802.11n/ac/ax overrides, MAC filtering, custom DNS/country,
and non-NAT modes are unsupported and rejected. Despite the shared password-field
label, this backend uses WPA2.

## 3. Start sharing and connect a device

1. Confirm the laptop has internet access. For the NetworkManager backend, confirm
   the selected Wi-Fi adapter is connected to the upstream Wi-Fi profile.
2. In **General → Hotspot Status**, turn on the switch beside **Service Status**.
   Wait for the status to show active; an amber icon is a transition or waiting state.
3. On your phone or tablet, open Wi-Fi settings, choose your hotspot name, and enter
   the password you set in Relay.
4. Open a website on the connected device to check internet access.
5. Open **Devices & Sharing → Connected Devices** in Relay to see connected clients.

If **Hidden SSID** is enabled, add the network manually on the client using its
name and password. For easier first-time setup, leave Hidden SSID off.

The **Show QR** button currently displays connection information and Wi-Fi text;
a scannable QR image is planned. Connect using the network name and password.

Closing Settings does not stop the hotspot. To stop sharing, turn off the same
status switch or use one of the desktop controls below. Connected clients will
lose their hotspot connection.

## 4. Use desktop controls

All of these controls operate the same Relay service. A change in one is reflected
in the others.

| Desktop control | How to use it |
| :--- | :--- |
| Settings, on any supported desktop | General → Hotspot Status → Service Status switch |
| GNOME Shell | Open Quick Settings in the top-right system menu → Wi-Fi Relay; its submenu includes Hotspot Settings and client information |
| XFCE or another desktop with a StatusNotifier tray | Open the Relay tray icon → Enable hotspot or Hotspot Settings |
| XFCE with the optional patched NetworkManager Applet | Open the usual network icon → Wi-Fi Relay beside VPN Connections → Hotspot or Settings |

**Start tray at login**, in **General → Startup**, shows the desktop controls at
login. It does not start hotspot broadcasting. Turning it off hides the controls;
Settings remains available from the application launcher.

On GNOME, a choice to disable Relay in the Extensions app is preserved. To enable
it again, use Extensions or run:

```bash
gnome-extensions enable wifi-relay@3togo.github.io
```

This command is only for GNOME. XFCE uses the tray or optional applet instead.

### Optional: put Relay in XFCE's existing network menu

Relay must already be installed and configured. Download the following matching
**Ubuntu 26.10 amd64** packages from the Beta 2 release, verify them with the release
`SHA256SUMS`, and install them together:

```bash
sudo apt install ./network-manager-applet_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./network-manager-gnome_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./nm-connection-editor_1.36.0-4ubuntu1+relay3_amd64.deb
```

Log out and back in. Open the usual network icon and look for **Wi-Fi Relay** beside
**VPN Connections**. The Hotspot checkbox uses whichever backend you selected in
Relay Settings. This menu integration does not register the hotspot as a VPN.
GNOME Shell uses its separate extension and does not require these replacement packages.

A distribution update may replace the patched applet. See the
[applet maintenance and rollback guide](../integration/nm-applet/README.md#maintenance-and-rollback).

## 5. Understand status and recovery

| Status | Meaning and action |
| :--- | :--- |
| Off / gray | Sharing is not requested. Enable it when ready. |
| Connecting / amber | AP activation is in progress. Wait for active status. |
| Waiting / amber | NetworkManager sharing is requested, but the upstream or a permitted channel is not ready. Clients are not being served. |
| Active / green | The hotspot is running. Clients can connect. |
| Stopping / amber | Relay is cleaning up the sharing session. |
| Error or service unavailable | Read the status message and use the troubleshooting steps below. |

For **NetworkManager (Experimental)**, temporary upstream loss stops the current
AP while retaining the sharing request. Relay retries when the **original Wi-Fi
profile** is stable on a permitted channel, including after NetworkManager restart
or suspend. Recovery can take time while association and channel checks settle.
Seamless roaming is not promised.

Turn sharing off to cancel a waiting or connecting recovery request. Radio-off or
changing settings also cancels recovery. Turning the radio back on does not by
itself create a new sharing request. A daemon restart or reboot clears the request;
start sharing explicitly afterward. Restarting or closing the desktop controls
does not by itself stop the service-owned hotspot.

## 6. Troubleshooting

| Problem | What to check |
| :--- | :--- |
| No Relay tray or toggle | Log out and back in after installation; enable Start tray at login. On GNOME, also check the Extensions app. Settings can still control sharing. |
| No Wi-Fi Relay entry in the usual XFCE network menu | That entry needs the optional three matching applet packages. The base Relay package provides its own tray. |
| Wrong adapter or `wlan0` does not exist | Select the actual adapter in General. `nmcli device status` lists interface names and connection state. |
| NetworkManager reports unsupported options | Stop sharing, disable IEEE generation overrides and other unsupported settings, then start again. |
| Channel cannot host an AP | Connect the upstream to a permitted channel. For example, manually select a suitable 2.4 GHz network when the 5 GHz channel is blocked. Disabled, no-IR, and DFS/radar channels are excluded; Relay does not override those restrictions. |
| Waiting never becomes active | Check that the original upstream profile is connected and has internet access on a permitted channel. After intentionally changing profiles, turn sharing off and then on to begin a new request. |
| Hardware does not support AP+STA | This adapter cannot provide the single-adapter repeater setup. Another adapter/driver may be needed; broader hardware coverage remains unverified. |
| Phone cannot see the hotspot | Confirm active status and the hotspot name; disable Hidden SSID for setup. Check the client's band support. NetworkManager uses the upstream band. |
| Phone connects but has no internet | Test internet access on the laptop, then check the client received an IP address and gateway automatically. Check the configured create_ap sharing interface or, for NetworkManager, the host route and any VPN policy. |
| Authorization fails | Use an active local desktop session and complete the administrator authentication prompt if requested. Run Settings as your normal user. |
| Sharing stops after upgrade, reboot, or service restart | This clears the sharing request. Reopen Settings and enable sharing explicitly. |

For a diagnostic report, these commands read service and connection state:

```bash
systemctl status wifi-hotspot-daemon.service --no-pager
journalctl -u wifi-hotspot-daemon.service -n 80 --no-pager
nmcli device status
```

For a read-only NetworkManager hardware/channel assessment, replace `wlo2` with
your selected Wi-Fi adapter:

```bash
wifi-relay-nm-probe --station wlo2
```

The probe does not start a hotspot unless explicitly asked to run a live test.
When reporting a problem, include the Relay package version, desktop, adapter/driver,
backend, status/error message, and relevant diagnostic output. Review logs for
personal network details before posting; do not include the hotspot password or
`/etc/wifi-hotspot.conf`.

## 7. Change settings or uninstall

Turn sharing off before changing the backend, adapter, name, password, or advanced
options. Make the changes in Settings, then enable sharing again. Clients need the
new password if you changed it.

For a package installation, remove Relay while preserving configuration with:

```bash
sudo apt remove gnome-wifi-hotspot
```

To also remove its system configuration and authorization files:

```bash
sudo apt purge gnome-wifi-hotspot
```

If you installed the optional applet packages, follow the
[rollback instructions](../integration/nm-applet/README.md#maintenance-and-rollback)
to restore the distribution applet separately. Source-install removal is covered
in the [README](../README.md).

See the [Beta 2 release notes](../RELEASE_NOTES.md) and
[live validation report](networkmanager-live-validation.md) for tested behavior
and remaining limitations.
