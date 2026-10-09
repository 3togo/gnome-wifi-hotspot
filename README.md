# Wi-Fi Relay 🌐

**Wi-Fi hotspot and connection sharing for Linux.**

**[User guide: setup, desktop controls, recovery, and troubleshooting](docs/user-guide.md)**

## Download Beta 2

**Latest experimental beta release — ready-to-install packages, no source build required.**

- **[Download Wi-Fi Relay — Beta 2 for Ubuntu 26.10 (.deb)](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/gnome-wifi-hotspot_1.0.0-12%2Bubuntu26.10.11_all.deb)** — recommended; built and verified by automated tests.
- [Optional XFCE network-menu packages and matching source archive](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0-beta.2)
- [Release notes and all downloads](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0-beta.2) · [SHA256 checksums](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/SHA256SUMS)

The recommended download is named `gnome-wifi-hotspot_1.0.0-12+ubuntu26.10.11_all.deb`.
Download `SHA256SUMS` into the same directory, then run each command separately
from a terminal in that directory.

Verify the checksum:

```bash
sha256sum --ignore-missing -c SHA256SUMS
```

Install the recommended package:

```bash
sudo apt install ./gnome-wifi-hotspot_1.0.0-12+ubuntu26.10.11_all.deb
```

**Open settings before starting the hotspot**, as your normal user:

```bash
wifi-hotspot-settings
```

In Settings, select your Wi-Fi adapter and internet sharing interface, and set the
network name and password. The NetworkManager backend is opt-in; existing settings
retain create_ap. Log out and back in after installation or upgrade to load the new
controls, then enable sharing. Upgrades stop active sharing, and sharing requests
are not retained across a daemon restart or reboot.

### Additional builds

[Wi-Fi Relay — Beta 2, standard build (.deb)](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.2/gnome-wifi-hotspot_1.0.0-12_all.deb) is also available,
tested on Ubuntu 26.10. Both packages contain the same app release; install only
one. If you downloaded `gnome-wifi-hotspot_1.0.0-12_all.deb`, use this install
command instead of the recommended-package command:

```bash
sudo apt install ./gnome-wifi-hotspot_1.0.0-12_all.deb
```

**Beta scope:** Debian/Ubuntu packaging and the XFCE tray, with optional downstream
NetworkManager Applet packages for Ubuntu 26.10 amd64. GNOME 45–51 is declared;
GNOME 51 loading and disable/re-enable passed in a headless session. Full GNOME
interaction, additional physical drivers, multi-client soak, and RPM installation
remain unverified. Earlier upgrade/restart cancellations remain documented in the
[validation report](docs/networkmanager-live-validation.md).

[![GNOME Shell](https://img.shields.io/badge/GNOME-45%E2%80%9351-blue?logo=gnome&logoColor=white)](https://www.gnome.org/)
[![GTK4 & Libadwaita](https://img.shields.io/badge/UI-GTK4%20%2F%20Libadwaita-purple)](https://gnome.pages.gitlab.gnome.org/libadwaita/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ubuntu package CI](https://github.com/3togo/gnome-wifi-hotspot/actions/workflows/ubuntu-stonking.yml/badge.svg)](https://github.com/3togo/gnome-wifi-hotspot/actions/workflows/ubuntu-stonking.yml)

**Wi-Fi hotspot and repeater (AP+STA)** controls for GNOME Shell and desktop trays.
Share an existing Wi-Fi connection through the same adapter when its driver and
regulatory channel permissions support concurrent station and access-point operation.

---

## 🎯 Overview

Wi-Fi Relay provides a GTK4/Libadwaita settings application, a Polkit-protected
system D-Bus service, and desktop controls. GNOME uses a Quick Settings extension;
XFCE and other desktops use a StatusNotifier tray. An optional patched
NetworkManager Applet adds Relay to the existing XFCE network menu.

### Split Debian packages (development version 1.0.0-16)

The Beta 2 downloads above remain the earlier bundled release. Building the current
branch produces three packages; the split is not yet a published release:

| Package | Contents |
| --- | --- |
| `gnome-wifi-hotspot` | Service, shared NetworkManager client, standalone GTK4 editor, and diagnostics |
| `gnome-wifi-hotspot-gnome` | GNOME Shell launch, status, and hotspot controls |
| `gnome-wifi-hotspot-tray` | StatusNotifier tray launch, status, and hotspot controls |

Build all three with `bash packaging/build-deb.sh`. Install the main application:

```sh
sudo apt install ./dist/gnome-wifi-hotspot_1.0.0-16_all.deb
```

For GNOME, install its optional controls in the same transaction:

```sh
sudo apt install ./dist/gnome-wifi-hotspot_1.0.0-16_all.deb \
  ./dist/gnome-wifi-hotspot-gnome_1.0.0-16_all.deb
```

For XFCE or another desktop with a StatusNotifier host, choose the matching
`gnome-wifi-hotspot-tray_1.0.0-16_all.deb` instead. The tray is also usable on KDE
with a compatible StatusNotifier host; a native Plasma widget is not provided.
Integrations require the same Relay version, so upgrade them together. The
standalone package only suggests integrations; APT does not select either one.

When upgrading the old bundled package, explicitly select the desired integration.
Configuration and per-user startup/visibility preferences are preserved. The old
system autostart file is retired through dpkg; modified copies are backed up as
`.dpkg-bak`. Log out and back in to refresh GNOME controls. Removing an integration
leaves the service and standalone editor installed; a running tray exits after
its files have been absent for ten seconds. Startup controls in the editor are
unavailable until the relevant integration is installed.

Patched GNOME Settings and nm-applet packages remain separate experimental
integrations; the main application does not require replacement desktop packages.
The RPM spec retains its bundled layout. Source installs use `make install` for
the standalone app and `make install-gnome` or `make install-tray` for controls
(after installing the app); `make install-all` installs all three components.

### Desktop integration and upgrade resilience

Use `wifi-hotspot-settings` as the shared entry point. On GNOME with the optional
[Wi-Fi panel bridge](integration/gnome-settings/README.md) installed, it opens
**GNOME Settings → Wi-Fi**; the **Wi-Fi Relay** button there opens Relay's controls.
Stock GNOME, XFCE, KDE, and other desktops open the same Relay editor directly.
`wifi-hotspot-settings --standalone` always opens that editor, including for recovery.
The Shell extension preferences and tray use this entry point instead of maintaining
separate configuration forms. Existing hotspot toggles retain their service calls.

The production D-Bus lifecycle client lives in `daemon/nm_client.py`; both the
backend worker and diagnostic probe reuse it. For resilience across desktops,
keep network ownership in the service/backend and
use desktop UIs as optional clients. Requiring a GUI process for hotspot lifetime
would prevent sharing from surviving its closure. Launching through GNOME Settings
does not change networking permissions or make the experimental native backend
production-ready. The stock NetworkManager backend uses its public D-Bus API but
still needs helper-created AP interfaces; native AP+STA ownership currently requires
the optional downstream core patch. These distribution patches require rebasing
and validation when their upstream packages change. Existing backend choices are
preserved; this UI refactor does not switch adapters, routing, or active sharing.

### Names and terminology

| Term | Meaning |
| :--- | :--- |
| **Wi-Fi Relay** | The product name: the settings app, service, and desktop controls in this project. |
| **Wi-Fi hotspot** | The wireless network your computer creates for phones, tablets, and other clients. Labels such as “Enable hotspot” and “Hotspot Name” describe this feature. |
| **Relay / repeater mode (AP+STA)** | Sharing an existing Wi-Fi connection through a hotspot while the computer remains connected to upstream Wi-Fi. Using one adapter requires compatible hardware, drivers, and channel permissions. |

We use **Wi-Fi Relay** for the app's branding and **hotspot** for the network it
creates. The term “repeater” here describes internet connection sharing through a
separate access point; it does not promise seamless roaming or a transparent Wi-Fi
range extender.

The repository and Debian package still use `gnome-wifi-hotspot`, and commands
such as `wifi-hotspot-settings`, the `wifi-hotspot-daemon.service` service, and
`/etc/wifi-hotspot.conf` retain their existing names for compatibility. They all
belong to **Wi-Fi Relay**. Use the filenames and commands shown in the installation
instructions. Any future technical renaming will need aliases and upgrade migration;
the branding change alone does not rename these interfaces.

### Hotspot backends

Choose **General → Network Interfaces and Frequency Band → Hotspot Backend** in Settings.
Stop sharing before changing backends.

| Behavior | `create_ap` (default) | `NetworkManager (Experimental)` |
| :--- | :--- | :--- |
| AP and IPv4 sharing | `hostapd`, `dnsmasq`, and firewall rules | NetworkManager AP profile with shared IPv4 |
| Internet route | Configured sharing interface | Host default route, including preferred Ethernet or VPN routes |
| Upstream band | May switch to a reachable permitted 2.4 GHz AP with the same SSID | Uses the current upstream channel; does not switch bands |
| Settings | Existing create_ap options | WPA2, hidden SSID, client isolation, raw PSK, and /24 gateway; unsupported overrides are rejected |
| Temporary upstream loss | Existing create_ap behavior | Waits and retries the original Wi-Fi profile on a permitted channel |

The NetworkManager backend creates a service-owned virtual AP interface and a
volatile connection profile. Credentials travel through an anonymous pipe;
cleanup checks resource identities before deleting anything. Existing installations
keep `create_ap` until the NetworkManager backend is explicitly selected.

---

## ✨ Features

- 🚦 **Persistent Tray Icon:** A clickable top-bar hotspot icon stays visible: gray when off, amber while waiting, connecting, or stopping, and green when on. Its menu provides the hotspot switch, connected devices, and settings; changes from the settings app update the icon too.
- ⚡ **1-Click Quick Settings Toggle:** Turn your hotspot on and off right from the GNOME status menu.
- 📱 **Expandable Submenu:** View active SSID, real-time frequency band (2.4/5 GHz), connected device count, and individual device names & IP addresses.
- 🔄 **True AP+STA Concurrent Mode:** Receive Wi-Fi internet and broadcast a hotspot simultaneously from a single Wi-Fi adapter.
- 🔄 **NetworkManager Recovery:** Resume requested sharing after temporary upstream loss, NetworkManager restart, or suspend once the original Wi-Fi profile is stable on a permitted channel. Stop, radio-off, or changing settings cancels recovery; daemon restart or reboot clears the request.
- 🛡️ **IPv4 Sharing:** The selected backend manages AP activation, DHCP/DNS, and forwarding.
- 📶 **Wi-Fi Standards Control:** The create_ap backend exposes **IEEE 802.11n/ac/ax** options where supported by the hardware and hostapd. The NetworkManager backend rejects generation overrides.
- 🎛️ **Libadwaita Preferences App:** Beautiful native GNOME preferences window for configuring credentials, interfaces, hidden SSIDs, client isolation, and gateways.
- 📷 **Connection Details:** Display credentials and Wi-Fi connection text for sharing. Rendering a scannable QR image is planned.

### Name and upgrade compatibility

The app is **Wi-Fi Relay**, with GNOME extension ID
`wifi-relay@3togo.github.io`. On upgrade, the login helper migrates the old
`wifi-hotspot@erhanzeyrek` enabled/disabled choice to the new ID. Existing
configuration, startup preferences, package/command names, and D-Bus identifiers
are retained for compatibility.

### Authorization and configuration

The daemon checks Polkit before starting, stopping, changing network settings,
preparing firewall rules, or returning configuration (which includes the password).
Active local users in `sudo` or `wheel` are authorized without a prompt; other
active local users must authenticate as an administrator. Status queries remain
available without authentication. Configuration is stored with owner-only
permissions and accepts only the supported keys in `data/wifi-hotspot.conf`, plus
an optional uppercase two-letter `COUNTRY`. Values are single-line literal text;
SSID is limited to 32 UTF-8 bytes, and WPA passphrases to 8–63 printable ASCII
characters (or a 64-digit hexadecimal PSK with `USE_PSK=1`).

### Automatic band fallback (create_ap)

The create_ap backend checks the selected adapter's AP+STA support and permitted channels.
When the current Wi-Fi channel cannot host an access point, it automatically
reconnects the existing Wi-Fi profile to a reachable 2.4 GHz access point with
**the same SSID**, then starts the hotspot on that channel. This briefly interrupts
internet access. An explicit 2.4 GHz preference also requests this switch; otherwise,
a permitted upstream channel is retained because concurrent mode uses the same channel.

Channels marked disabled, `no IR`, or requiring radar detection are excluded;
this backend does not configure DFS/CAC. If no suitable 2.4 GHz access point exists,
startup reports an error without disconnecting Wi-Fi. Failed reconnections attempt
to restore the original access point. Networks with different SSIDs for each band
must be switched manually. With Ethernet or another adapter as the uplink, no
upstream band switch is needed. Hotspot traffic follows the host routing
policy, including an Ethernet or VPN route that has priority over Wi-Fi.

---

## 📦 Requirements

See [the dependency review and minimum custom packages](docs/dependency-review.md)
for the smallest Stonking bundle for each integration option.

The released `.deb` installs its dependencies through APT. Source installations
need the core networking packages below. Fedora/Atomic and Arch installation paths
are provided for development; this release was validated on Ubuntu 26.10.

- **Fedora / Bluefin / Bazzite / Silverblue / RHEL:**
  ```bash
  sudo dnf install hostapd dnsmasq iw iptables python3-gobject libadwaita
  ```
- **Ubuntu / Debian / Pop!_OS:**
  ```bash
  sudo apt install hostapd dnsmasq iw iptables python3-gi gir1.2-adw-1
  ```
- **Arch Linux:**
  ```bash
  sudo pacman -S hostapd dnsmasq iw iptables python-gobject libadwaita
  ```

---

## 🛠️ Installation

### Debian / Ubuntu package

For Ubuntu 26.10 **Stonking**, the
[Ubuntu Stonking package workflow](https://github.com/3togo/gnome-wifi-hotspot/actions/workflows/ubuntu-stonking.yml)
builds and tests a `.deb` in an Ubuntu 26.10 container on pushes and pull requests.
It can also be run manually with an optional base package version. Download the
`wifi-relay-ubuntu-stonking-…` artifact from a successful run; it contains the
package and `SHA256SUMS`. Verify the checksum with `sha256sum -c SHA256SUMS`, then
install the downloaded `.deb` with `sudo apt install ./gnome-wifi-hotspot_…_all.deb`.
The workflow runs Python and Node tests, GTK widget checks, applet tests under
address/undefined-behavior sanitizers, AppStream validation, and Lintian, then checks
installation, upgrade, removal, purge, and fresh installation. It does not test an
actual desktop login or GNOME Shell session.

Build the package from this checkout without root:

```bash
./packaging/build-deb.sh
sudo apt install ./dist/gnome-wifi-hotspot_1.0.0-15+qr1_all.deb
```

The package includes the current working-tree changes. An optional first argument
sets the package version. See [production refactor and release gates](docs/production-readiness.md)
for source packaging, runtime boundaries, and required release validation. Fresh
factory installs generate a random password, visible in Settings; upgrades keep
existing credentials.

**Required first-run setup:** Launch the settings app as your normal user:

```bash
wifi-hotspot-settings
```

You can also open **Wi-Fi Relay** from your application launcher. In **General**,
select your actual **Wi-Fi Adapter** and **Internet Sharing Interface**; the
default `wlan0` may not exist on your machine. To share an existing Wi-Fi
connection using one adapter, choose that adapter for both fields. Set the
hotspot name and a password of at least eight characters. Settings save
automatically. **Start tray at login** starts the desktop controls; enable the
hotspot separately using the **Hotspot Status → Service Status** switch or tray menu.

Then log out and back in. The tray extension is enabled automatically at your first
desktop login after installation and starts on subsequent logins. GNOME uses the
Shell extension; XFCE and other desktops use a StatusNotifier tray.

### Optional XFCE network-menu integration

Download these three matching **Ubuntu 26.10 amd64** packages from the
[Beta 2 release](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0-beta.2),
verify them with the release `SHA256SUMS`, and install them together:

```bash
sudo apt install ./network-manager-applet_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./network-manager-gnome_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./nm-connection-editor_1.36.0-4ubuntu1+relay3_amd64.deb
```

Log out and back in, then open the usual network icon → **Wi-Fi Relay** beside
**VPN Connections**. Its Hotspot checkbox controls Relay's selected backend and
can cancel a waiting recovery request. Install and configure Relay first.
GNOME Shell uses the separate Quick Settings extension and does not require these
applet packages. This is a downstream applet integration; Relay is a Wi-Fi AP and
is not registered as a VPN or merged into upstream NetworkManager.

Distribution updates may replace the patched applet. The release includes matching
patched sources; see the [applet guide](integration/nm-applet/README.md) for building,
maintenance, and rollback.

### Source installation

#### 1. Clone the Repository
```bash
git clone https://github.com/3togo/gnome-wifi-hotspot.git
cd gnome-wifi-hotspot
```

#### 2. Install System Components
```bash
sudo make install
```
*This installs the daemon to `/usr/local/libexec/wifi-hotspot-daemon`, configuration and D-Bus policies to `/etc`, and registers the systemd service to start automatically on boot.*

#### 3. Configure Before First Use

**Run the settings app as your normal user before starting the hotspot:**

```bash
wifi-hotspot-settings
```

Select the Wi-Fi adapter and internet sharing interface in **General**, then set
the hotspot name and password. For sharing Wi-Fi from a single adapter, select
the same adapter for both interfaces. Settings save automatically.

#### 4. Start the Tray
Log out of your desktop session and log back in (**Logout → Login**). The tray
starts automatically at login. GNOME uses the Shell extension, while XFCE and
other desktops use the standalone StatusNotifier tray. You can control this in
**Settings → General → Startup → Start tray at login**
(default: on). Turning it off hides the tray immediately and prevents it from
starting at login; turning it on shows it again. The standalone settings app
remains available from the application launcher. Hotspot broadcasting is still
controlled by the tray switch.

**GNOME only:** Manual disabling in the Extensions app is also preserved. If you
disabled the extension there, you can optionally re-enable it with:

```bash
gnome-extensions enable wifi-relay@3togo.github.io
```

**XFCE and other desktops:** No `gnome-extensions` command is needed. Use
**Start tray at login** in the settings app to enable or disable the tray.

---

## 🗑️ Uninstallation

For a Debian/Ubuntu package installation, remove the application while preserving
configuration:

```bash
sudo apt remove gnome-wifi-hotspot
```

To remove its system configuration and authorization files as well:

```bash
sudo apt purge gnome-wifi-hotspot
```

If you installed the optional patched applet, follow its
[rollback instructions](integration/nm-applet/README.md#maintenance-and-rollback)
to restore the distribution packages.

For a source installation, remove the extension, daemon, systemd services, and D-Bus policies:

```bash
sudo make uninstall
```

*(Note: Your custom settings in `/etc/wifi-hotspot.conf` are preserved. To wipe them completely, run `sudo rm -f /etc/wifi-hotspot.conf`)*

---

## 💻 Developer & Live Hacking Workflow

An experimental service-owned **NetworkManager backend** is available in Settings →
General → **Hotspot Backend**. Connect the selected adapter to Wi-Fi, stop any
existing hotspot, and select **NetworkManager (Experimental)**. Configure the
SSID/password, then use the existing GNOME Quick Settings toggle, desktop tray,
or Settings switch. It runs until switched off; closing Settings does not stop it.
It shares the host default route and requires WPA2 and the current upstream channel.
Temporary upstream loss stops the current AP and leaves the requested sharing
session waiting. Recovery retries only after the original upstream profile returns
on a permitted channel. Stop cancels waiting or connecting retries. Recovery intent
is held in memory and is cleared by a daemon restart or reboot. GNOME's built-in
hotspot menu remains separate; seamless roaming is not promised.

On XFCE, an optional [patched NetworkManager Applet](integration/nm-applet/README.md)
adds **Wi-Fi Relay** directly to the existing network icon menu, with a Hotspot
checkbox, status/client count, and Settings launcher. This is a separate downstream
applet package; the normal Relay package also keeps its existing tray controls.

The [native NetworkManager integration proposal](docs/networkmanager-upstream-proposal.md)
defines upstream responsibilities, tested invariants, and the hardware checks still
needed before a production merge. Run `make test` and `make test-nm-menu` to verify
the reference implementation; CI also runs the menu tests with memory/UB sanitizers.

A [Stonking native Relay development patch](integration/nm-core/README.md) adds
NetworkManager-owned child AP interfaces and connects them to Relay's existing
controls. It is a downstream prototype with physical-radio validation still pending.

An experimental [NetworkManager AP+STA probe](docs/networkmanager-prototype.md)
assesses whether NetworkManager can own a virtual hotspot while keeping the
upstream Wi-Fi connection. It is read-only by default, with an explicit temporary
live-test mode. Existing installations default to `create_ap` until the new backend
is explicitly selected.

For developers iterating on the GNOME Shell extension or daemon on Immutable/Atomic OS without requiring reboots:

```bash
# 1. Set up symlinks and D-Bus development policies
make dev-setup

# 2. Run the D-Bus daemon in foreground with live debug output
make dev-run-daemon

# 3. Test GNOME Shell extension in a nested Wayland session
make dev-run-shell

# 4. Launch the Libadwaita settings app directly
make dev-run-settings

# 5. Query or monitor D-Bus calls
make dev-test-dbus
make dev-monitor-dbus
```

---

## Validation

[Beta 2 CI passed](https://github.com/3togo/gnome-wifi-hotspot/actions/runs/37675244790)
for release commit `bfd860c64270855a1d6e38bad5e87705015543b8`: **170 Python tests**,
Node state checks, GTK settings/tray checks, **16 applet sanitizer cases**, and package
lifecycle checks. An additional isolated upgrade from the published Beta 1
`1.0.0-10` package preserved settings and passed remove, purge, fresh-install, and
`dpkg --audit` checks. Published release downloads were verified against their checksums.

Physical tests covered upstream loss/reconnection, Stop while waiting,
NetworkManager restart, suspend/resume, and installed-menu Start/Stop on one
Wi-Fi driver. Android HTTPS checks verified certificate and hostname validation;
gateway DNS result codes matched direct upstream queries. GNOME 51 extension
loading and disable/re-enable passed in an isolated headless session.

Full GNOME desktop interaction, additional drivers, natural roaming, multiple-client
soak, distribution applet upgrades, and RPM installation still need coverage.
Earlier combined upgrade/restart trials lost sharing intent; the cancellation
source was not conclusively identified. See the
[live validation report](docs/networkmanager-live-validation.md) and
[sanitized evidence](docs/evidence/nm5-validation-2026-10-07.json).

---

## 🏗️ Architecture

```text
GNOME Quick Settings / desktop tray / optional nm-applet menu / Settings
                                │
                     Polkit-protected system D-Bus
                                │
                  Python daemon (systemd, runs as root)
                     status, recovery, resource cleanup
                                │
                 ┌──────────────┴────────────────┐
                 │                               │
          create_ap backend             NetworkManager backend
          virtual AP interface          service-owned virtual AP interface
          hostapd + dnsmasq              volatile WPA2 AP profile
          iptables / firewalld           shared IPv4 (DHCP/DNS/forwarding)
```

Desktop applications run as the logged-in user. The daemon performs privileged
network operations after Polkit authorization. Both backends expose the same
Relay controls and status; the NetworkManager path owns only its recorded resources.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
Contributions, bug reports, and feature requests are warmly welcomed!
