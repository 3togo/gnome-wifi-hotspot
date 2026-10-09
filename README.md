# Wi-Fi Relay

Wi-Fi Relay shares an internet connection through a compatible Wi-Fi adapter.
Use its standalone GTK settings application on any supported desktop, and add
GNOME Shell or tray controls if desired. All controls use the same authorized
D-Bus service. Sharing an upstream Wi-Fi connection through the same adapter
requires simultaneous station/access-point (AP+STA) support from its driver.

## Download and install

**[Wi-Fi Relay 1.0.0](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0)**
is the stable release for **Ubuntu 26.10 (Stonking)**, Debian package version
**1.0.0-18**. The packages contain architecture-independent application code;
APT supplies platform-specific dependencies. Other distribution releases have
not been validated. Older beta binary downloads have been retired.

| Download | Contents |
| :--- | :--- |
| [Standalone app](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0/gnome-wifi-hotspot_1.0.0-18_all.deb) | Service and GTK settings; required |
| [GNOME controls](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0/gnome-wifi-hotspot-gnome_1.0.0-18_all.deb) | Optional GNOME Shell Quick Settings and top-bar controls |
| [Tray controls](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0/gnome-wifi-hotspot-tray_1.0.0-18_all.deb) | Optional StatusNotifier/AppIndicator controls for XFCE and compatible desktops |
| [SHA256SUMS](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0/SHA256SUMS) | Checksums for release downloads |

Download the standalone app and `SHA256SUMS` into one folder. Add the optional
control package for your desktop, using the same version for all packages.

```bash
sha256sum --ignore-missing -c SHA256SUMS
sudo apt install ./gnome-wifi-hotspot_1.0.0-18_all.deb
```

The checksum check must report `OK` for each downloaded package. To install
GNOME controls, use:

```bash
sudo apt install ./gnome-wifi-hotspot_1.0.0-18_all.deb ./gnome-wifi-hotspot-gnome_1.0.0-18_all.deb
```

For XFCE or another desktop with a compatible tray, use:

```bash
sudo apt install ./gnome-wifi-hotspot_1.0.0-18_all.deb ./gnome-wifi-hotspot-tray_1.0.0-18_all.deb
```

Log out and back in after installing desktop controls. GNOME compatibility is
declared for Shell 45–51; the automated Shell check covers version 51. The main
package works without either optional integration. These downloads do not
replace NetworkManager, GNOME Settings, or the distribution's network applet.

## Start sharing

Open **Wi-Fi Relay** from the application launcher, or run
`wifi-hotspot-settings` as your normal user. In **General**, choose the actual
Wi-Fi adapter, hotspot name, and a strong password. Keep the default **create_ap**
backend for ordinary use. Choose the internet sharing interface, then enable
**Hotspot Status → Service Status**. Connect a client using the configured name
and password, or scan the locally generated Wi-Fi QR image.

The **NetworkManager (Experimental)** backend uses NetworkManager's public
D-Bus API. It requires the selected adapter to be connected to upstream Wi-Fi
on a permitted channel, and shares the host default route. AP+STA support and
channel restrictions vary by hardware. Its recovery behavior and supported
options are described in the [user guide](docs/user-guide.md).

Closing Settings leaves sharing running. Turning sharing off cancels recovery
requests. **Start desktop controls at login** shows controls; it does not start
broadcasting. A reboot or daemon restart clears the sharing request.

## Upgrade and remove

Stop sharing before an upgrade, especially when upgrading an older beta that
used shared `/tmp` backend state. Upgrade the main package and every installed
optional package together. Configuration and per-user preferences are retained;
sharing must be enabled again afterward. Older bundled installations must
explicitly select an optional control package. Fresh installs generate a random
password; upgrades preserve your existing password.

```bash
sudo apt remove gnome-wifi-hotspot-gnome gnome-wifi-hotspot-tray gnome-wifi-hotspot
```

Remove only the packages you installed. Use `apt purge` to remove their system
configuration as well. Per-user preferences are retained. Removing just an
optional integration leaves the standalone app and service available.

## Reliability and validation

The service uses private runtime files, checks ownership before stopping
processes, bounds worker output and shutdown, and authorizes privileged changes
through Polkit. Firewall rules are scoped to the hotspot interface; Relay leaves
permanent firewalld configuration and AppArmor enforcement intact.

Native Ubuntu 26.10 validation includes 261 unit tests with no skips, real GTK
settings/tray checks, 17 sanitized applet cases, GNOME Shell 51 extension loading,
private-bus service authorization checks, and Debian source/binary builds.
GitHub CI additionally checks isolated install, upgrade, removal, and purge.
See the release's validation report for exact source and environment provenance.

Live multi-adapter traffic, suspend/resume, extended operation, and enforced
firewall/AppArmor fault testing are not certified by this release. Earlier
single-driver hardware results are [historical evidence](docs/networkmanager-live-validation.md),
not validation of the final build. The native NetworkManager backend and
version-specific downstream integration patches remain experimental. RPM builds
are not part of the validated release.

## Build and contribute

Build without installing packages or changing host services:

```bash
./packaging/build-deb.sh
python3 packaging/build-source.py --binary
```

The source builder runs unit and real-widget tests and writes unsigned Debian
source/binary artifacts into `dist/`. See [build requirements and checks](docs/production-readiness.md).
Use `/usr/bin/python3` on Ubuntu when a separate Python environment lacks GI.
Headless widget tests require Xvfb. Package lifecycle tests belong in disposable
CI environments because they remove and purge packages.

Desktop integration entry points use the shared Relay service. Optional
[network applet](integration/nm-applet/README.md) and
[GNOME Settings](integration/gnome-settings/README.md) downstream patches are
maintainer experiments, separate from the stable package downloads. They are
version-specific and are not upstream GNOME or NetworkManager features.

## Documentation and support

- [User guide](docs/user-guide.md): setup, controls, recovery, and troubleshooting.
- [Release notes](RELEASE_NOTES.md): changes, scope, and downloads.
- [Release maintenance and rollback](docs/releases/1.0.0-18.md).
- [Architecture and production checks](docs/production-readiness.md).
- [NetworkManager development](docs/networkmanager-development.md).
- [Report a problem](https://github.com/3togo/gnome-wifi-hotspot/issues): include package version, desktop, backend, adapter/driver, and relevant errors. Remove passwords and personal network details from reports.

## License and attribution

Wi-Fi Relay is MIT licensed; see [LICENSE](LICENSE) and
[Debian copyright notices](packaging/debian/copyright). The create_ap backend
retains its upstream copyright notices. Wi-Fi QR encoding uses the bundled
MIT-licensed Nayuki encoder; see [QR encoder attribution](settings/QR-ENCODER.md).
