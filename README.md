# Wi-Fi Relay 🌐

## Download Beta 1

**Ready-to-install packages are available — no source build required.**

- **[Download Ubuntu 26.10 Stonking package (.deb)](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.1/gnome-wifi-hotspot_1.0.0-10%2Bubuntu26.10.1_all.deb)**
- **[Download Debian/Ubuntu package (.deb)](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.1/gnome-wifi-hotspot_1.0.0-10_all.deb)**
- [Release notes and all downloads](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0-beta.1) · [SHA256 checksums](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-beta.1/SHA256SUMS)

Install the downloaded package, then **open settings before starting the hotspot**:

```bash
sudo apt install ./gnome-wifi-hotspot_*.deb
wifi-hotspot-settings
```

Download either package, then run these commands from its download folder. In
settings, select your Wi-Fi adapter and internet sharing interface, and set the
network name and password. Log out and back in to start the tray automatically.

**Beta scope:** This release focuses on the Debian/Ubuntu package and XFCE tray.
GNOME desktop integration and RPM installation remain experimental and unverified.
The GNOME extension declares versions 45–50; GNOME 51 is not supported by this beta.

[![GNOME Shell](https://img.shields.io/badge/GNOME-45%20|%2046%20|%2047%20|%2048-blue?logo=gnome&logoColor=white)](https://www.gnome.org/)
[![GTK4 & Libadwaita](https://img.shields.io/badge/UI-GTK4%20%2F%20Libadwaita-purple)](https://gnome.pages.gitlab.gnome.org/libadwaita/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Immutable Linux Ready](https://img.shields.io/badge/Fedora%20Atomic-Bluefin%20%7C%20Bazzite%20%7C%20Silverblue-success)](https://projectbluefin.io/)

Native, seamless, and modern **Wi-Fi Hotspot & Repeater (AP+STA)** integration for GNOME Shell. Share your Wi-Fi internet connection from the same wireless card (just like Windows 10/11) directly from the GNOME Quick Settings Command Center.

---

## 🎯 Overview

Most Linux hotspot tools are either legacy GTK3 applications, CLI-only scripts, or simple wrappers around NetworkManager that disable your active Wi-Fi connection when creating an Access Point.

**Wi-Fi Relay** bridges this gap by providing a deep, native GNOME Shell integration powered by a secure system D-Bus daemon. It enables true **concurrent Wi-Fi reception and broadcasting (AP+STA mode)** on supported wireless cards without interrupting your existing connection.

---

## 🚀 Key Advantages Over Traditional Tools (`linux-wifi-hotspot` / `wihotspot`)

| Feature | Legacy `linux-wifi-hotspot` | **Wi-Fi Relay** (This Project) |
| :--- | :--- | :--- |
| **Desktop Integration** | Separate, standalone GTK3 window | **Native GNOME Quick Settings toggle & top-bar indicator** |
| **User Experience** | Manual app launch required every time | **1-Click toggle directly in GNOME Command Center** |
| **Connected Clients** | Basic terminal/table display | **Integrated Quick Menu submenu** showing device names and IPs |
| **Security & Permissions** | Prompts for `sudo` password on every start | **Secure D-Bus daemon with Polkit rules** (passwordless for wheel/sudo) |
| **Immutable / Atomic OS** | Hardcoded to `/usr`, breaks on Ostree systems | **First-class Bluefin, Bazzite & Fedora Silverblue support** (`/usr/local` & `/etc`) |
| **Channel Synchronization** | Frequent `EBUSY` crashes on channel changes | **Automatic dynamic channel syncing** with active Wi-Fi connection |
| **Modern Standards** | Legacy GTK3 UI | **Modern GTK4 & Libadwaita** application matching GNOME HIG |
| **Band Compatibility** | Fails silently on unsupported 5GHz AP mode | **Channel-aware hardware check** with automatic 2.4 GHz fallback |
| **Connection Sharing** | Not available or external | **Connection details dialog** showing Wi-Fi connection text; QR image rendering is planned |
| **Device Naming** | Shows raw, cryptic MAC addresses | **Intelligent hostname resolution** (shows device name & IP) |
| **Default Naming** | Generic hardcoded SSID | **Dynamic `<hostname>-Hotspot`** naming tailored to your machine |

---

## ✨ Features

- 🚦 **Persistent Tray Icon:** A clickable top-bar hotspot icon stays visible: gray when off, amber while connecting or stopping, and green when on. Its menu provides the hotspot switch, connected devices, and settings; changes from the settings app update the icon too.
- ⚡ **1-Click Quick Settings Toggle:** Turn your hotspot on and off right from the GNOME status menu.
- 📱 **Expandable Submenu:** View active SSID, real-time frequency band (2.4/5 GHz), connected device count, and individual device names & IP addresses.
- 🔄 **True AP+STA Concurrent Mode:** Receive Wi-Fi internet and broadcast a hotspot simultaneously from a single Wi-Fi adapter.
- 🛡️ **Zero-Friction Firewall Setup:** Automatically configures `firewalld` policies for DHCP/DNS and handles `dnsmasq` lifecycle cleanly.
- 📶 **Wi-Fi Standards Control:** Configurable support for **IEEE 802.11n (Wi-Fi 4)**, **IEEE 802.11ac (Wi-Fi 5)**, and **IEEE 802.11ax (Wi-Fi 6)**.
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

### Automatic band fallback

The hotspot checks the selected adapter's AP+STA support and permitted channels.
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

Before installing, ensure the core networking packages are present on your system:

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
The workflow checks installation and GTK widgets; it does not test an actual
desktop login or GNOME Shell session.

Build the package from this checkout without root:

```bash
./packaging/build-deb.sh
sudo apt install ./dist/gnome-wifi-hotspot_1.0.0-11+nm5_all.deb
```

The package includes the current working-tree changes. An optional first argument
sets the package version.

**Required first-run setup:** Launch the settings app as your normal user:

```bash
wifi-hotspot-settings
```

You can also open **Wi-Fi Relay** from your application launcher. In **General**,
select your actual **Wi-Fi Adapter** and **Internet Sharing Interface**; the
default `wlan0` may not exist on your machine. To share an existing Wi-Fi
connection using one adapter, choose that adapter for both fields. Set the
hotspot name and a password of at least eight characters. Settings save
automatically. Keep **Start tray at login** enabled if you want automatic startup.

Then log out and back in. The tray extension is enabled automatically at your first
desktop login after installation and starts on subsequent logins. GNOME uses the
Shell extension; XFCE and other desktops use a StatusNotifier tray.

### 1. Clone the Repository
```bash
git clone https://github.com/3togo/gnome-wifi-hotspot.git
cd gnome-wifi-hotspot
```

### 2. Install System Components
```bash
sudo make install
```
*This installs the daemon to `/usr/local/libexec/wifi-hotspot-daemon`, configuration and D-Bus policies to `/etc`, and registers the systemd service to start automatically on boot.*

### 3. Configure Before First Use

**Run the settings app as your normal user before starting the hotspot:**

```bash
wifi-hotspot-settings
```

Select the Wi-Fi adapter and internet sharing interface in **General**, then set
the hotspot name and password. For sharing Wi-Fi from a single adapter, select
the same adapter for both interfaces. Settings save automatically.

### 4. Start the Tray
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

To completely remove the extension, daemon, systemd services, and D-Bus policies:

```bash
sudo make uninstall
```

*(Note: Your custom settings in `/etc/wifi-hotspot.conf` are preserved. To wipe them completely, run `sudo rm -f /etc/wifi-hotspot.conf`)*

---

## 💻 Developer & Live Hacking Workflow

An experimental persistent **NetworkManager backend** is available in Settings →
General → **Hotspot Backend**. Connect the selected adapter to Wi-Fi, stop any
existing hotspot, and select **NetworkManager (Experimental)**. Configure the
SSID/password, then use the existing GNOME Quick Settings toggle, desktop tray,
or Settings switch. It runs until switched off; closing Settings does not stop it.
It shares the host default route and requires WPA2 and the current upstream channel.
Upstream disconnects or roaming stop the hotspot with an error; automatic recovery
and GNOME's built-in hotspot menu integration are not implemented.

On XFCE, an optional [patched NetworkManager Applet](integration/nm-applet/README.md)
adds **Wi-Fi Relay** directly to the existing network icon menu, with a Hotspot
checkbox, status/client count, and Settings launcher. This is a separate downstream
applet package; the normal Relay package also keeps its existing tray controls.

The [native NetworkManager integration proposal](docs/networkmanager-upstream-proposal.md)
defines upstream responsibilities, tested invariants, and the hardware checks still
needed before a production merge. Run `make test` and `make test-nm-menu` to verify
the reference implementation; CI also runs the menu tests with memory/UB sanitizers.

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

## 🏗️ Architecture

```
 ┌────────────────────────────────────────────────────────┐
 │                   GNOME Shell UI                       │
 │  Quick Settings Toggle ── QuickMenu Submenu ── Prefs   │
 └───────────────────────────┬────────────────────────────┘
                             │ D-Bus System Bus
                             │ (io.github.erhanzeyrek.WifiHotspot)
 ┌───────────────────────────▼────────────────────────────┐
 │             Python D-Bus Daemon (Systemd)              │
 │  - Polkit security checks & non-root user execution    │
 │  - Dynamic station & client IP/hostname resolution     │
 │  - Real-time NetworkManager Wi-Fi state monitor        │
 └───────────────────────────┬────────────────────────────┘
                             │
 ┌───────────────────────────▼────────────────────────────┐
 │               Backend Network Engine                   │
 │  - nl80211 virtual interface management (ap1)          │
 │  - hostapd (AP broadcast & IEEE 802.11n/ac/ax)         │
 │  - dnsmasq (DHCP lease allocation & DNS)               │
 │  - iptables / firewalld NAT packet forwarding          │
 └────────────────────────────────────────────────────────┘
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
Contributions, bug reports, and feature requests are warmly welcomed!
