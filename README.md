# GNOME Wi-Fi Hotspot 🌐

[![GNOME Shell](https://img.shields.io/badge/GNOME-45%20|%2046%20|%2047%20|%2048-blue?logo=gnome&logoColor=white)](https://www.gnome.org/)
[![GTK4 & Libadwaita](https://img.shields.io/badge/UI-GTK4%20%2F%20Libadwaita-purple)](https://gnome.pages.gitlab.gnome.org/libadwaita/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Immutable Linux Ready](https://img.shields.io/badge/Fedora%20Atomic-Bluefin%20%7C%20Bazzite%20%7C%20Silverblue-success)](https://projectbluefin.io/)

Native, seamless, and modern **Wi-Fi Hotspot & Repeater (AP+STA)** integration for GNOME Shell. Share your Wi-Fi internet connection from the same wireless card (just like Windows 10/11) directly from the GNOME Quick Settings Command Center.

---

## 🎯 Overview

Most Linux hotspot tools are either legacy GTK3 applications, CLI-only scripts, or simple wrappers around NetworkManager that disable your active Wi-Fi connection when creating an Access Point.

**GNOME Wi-Fi Hotspot** bridges this gap by providing a deep, native GNOME Shell integration powered by a secure system D-Bus daemon. It enables true **concurrent Wi-Fi reception and broadcasting (AP+STA mode)** on supported wireless cards without interrupting your existing connection.

---

## 🚀 Key Advantages Over Traditional Tools (`linux-wifi-hotspot` / `wihotspot`)

| Feature | Legacy `linux-wifi-hotspot` | **GNOME Wi-Fi Hotspot** (This Project) |
| :--- | :--- | :--- |
| **Desktop Integration** | Separate, standalone GTK3 window | **Native GNOME Quick Settings toggle & top-bar indicator** |
| **User Experience** | Manual app launch required every time | **1-Click toggle directly in GNOME Command Center** |
| **Connected Clients** | Basic terminal/table display | **Integrated Quick Menu submenu** showing device names and IPs |
| **Security & Permissions** | Prompts for `sudo` password on every start | **Secure D-Bus daemon with Polkit rules** (passwordless for wheel/sudo) |
| **Immutable / Atomic OS** | Hardcoded to `/usr`, breaks on Ostree systems | **First-class Bluefin, Bazzite & Fedora Silverblue support** (`/usr/local` & `/etc`) |
| **Channel Synchronization** | Frequent `EBUSY` crashes on channel changes | **Automatic dynamic channel syncing** with active Wi-Fi connection |
| **Modern Standards** | Legacy GTK3 UI | **Modern GTK4 & Libadwaita** application matching GNOME HIG |
| **Band Compatibility** | Fails silently on unsupported 5GHz AP mode | **Smart hardware check** with 1-click notification to switch bands |
| **QR Code Sharing** | Not available or external | **Built-in QR connection modal** for instant phone/tablet pairing |
| **Device Naming** | Shows raw, cryptic MAC addresses | **Intelligent hostname resolution** (shows device name & IP) |
| **Default Naming** | Generic hardcoded SSID | **Dynamic `<hostname>-Hotspot`** naming tailored to your machine |

---

## ✨ Features

- ⚡ **1-Click Quick Settings Toggle:** Turn your hotspot on and off right from the GNOME status menu.
- 📱 **Expandable Submenu:** View active SSID, real-time frequency band (2.4/5 GHz), connected device count, and individual device names & IP addresses.
- 🔄 **True AP+STA Concurrent Mode:** Receive Wi-Fi internet and broadcast a hotspot simultaneously from a single Wi-Fi adapter.
- 🛡️ **Zero-Friction Firewall Setup:** Automatically configures `firewalld` policies for DHCP/DNS and handles `dnsmasq` lifecycle cleanly.
- 📶 **Wi-Fi Standards Control:** Configurable support for **IEEE 802.11n (Wi-Fi 4)**, **IEEE 802.11ac (Wi-Fi 5)**, and **IEEE 802.11ax (Wi-Fi 6)**.
- 🎛️ **Libadwaita Preferences App:** Beautiful native GNOME preferences window for configuring credentials, interfaces, hidden SSIDs, client isolation, and gateways.
- 📷 **Instant QR Code Sharing:** Display a Wi-Fi connection code to let mobile devices scan and join in seconds.

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

### 1. Clone the Repository
```bash
git clone https://github.com/erhanzeyrek/gnome-wifi-hotspot.git
cd gnome-wifi-hotspot
```

### 2. Install System Components
```bash
sudo make install
```
*This installs the daemon to `/usr/local/libexec/wifi-hotspot-daemon`, configuration and D-Bus policies to `/etc`, and registers the systemd service to start automatically on boot.*

### 3. Activate the GNOME Extension
Log out of your desktop session and log back in (**Logout → Login**), then enable the extension:
```bash
gnome-extensions enable wifi-hotspot@erhanzeyrek
```

---

## 🗑️ Uninstallation

To completely remove the extension, daemon, systemd services, and D-Bus policies:

```bash
sudo make uninstall
```

*(Note: Your custom settings in `/etc/wifi-hotspot.conf` are preserved. To wipe them completely, run `sudo rm -f /etc/wifi-hotspot.conf`)*

---

## 💻 Developer & Live Hacking Workflow

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
