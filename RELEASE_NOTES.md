# Wi-Fi Relay 1.0.0 — Debian revision 22

Stable release for Ubuntu 26.10 (Stonking), Debian package version **1.0.0-22**.
[Release downloads](https://github.com/3togo/gnome-wifi-hotspot/releases/tag/v1.0.0-22).
The stable app uses create_ap by default. The optional native NetworkManager
AP+STA backend and downstream integration patches retain their experimental status.

## Downloads

| Download | Contents |
| :--- | :--- |
| [Standalone app](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-22/gnome-wifi-hotspot_1.0.0-22_all.deb) | Service and GTK settings; required |
| [GNOME controls](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-22/gnome-wifi-hotspot-gnome_1.0.0-22_all.deb) | Optional GNOME Shell Quick Settings and top-bar controls |
| [Tray controls](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-22/gnome-wifi-hotspot-tray_1.0.0-22_all.deb) | Optional StatusNotifier/AppIndicator controls for XFCE and compatible desktops |
| [SHA256SUMS](https://github.com/3togo/gnome-wifi-hotspot/releases/download/v1.0.0-22/SHA256SUMS) | Checksums for release downloads |

Install the main package, plus matching GNOME or tray controls if desired.
Follow the [installation and upgrade guide](docs/user-guide.md). No replacement
NetworkManager, GNOME Settings, or network applet binary is required.
Beta `.deb` downloads have been retired; historical source tags remain available.

## Changes since revision 18

- Add About to the desktop tray and GNOME top-bar and Quick Settings menus.
- Make tray Quit stop sharing and cancel recovery before closing. Failed or
  denied Stop keeps controls available.
- Start tray controls in eligible logged-in desktop sessions after APT
  installation, as the desktop user. Respect disabled startup and hidden icons.
- Replace older tray processes during upgrade without stopping sharing.
- Wait for the user service restart and verify process survival through the
  initial polling callbacks; retry once and report failures accurately.
- Extend private-bus startup smoke tests past initial icon registration.

## Stable application features

- Separate the standalone service/settings app from optional GNOME and tray
  controls. Every desktop client shares the same authorized controller.
- Use a shared NetworkManager D-Bus client and asynchronous settings transport;
  serialize saves and reject stale replies across service restarts.
- Generate scannable Wi-Fi QR images locally, with escaped credentials and
  hidden-network support, without additional runtime imaging dependencies.
- Generate individual random passwords on fresh installs; preserve configured
  credentials and preferences on upgrades.
- Keep privileged logs, locks, and backend state in private runtime directories.
  Validate process ownership and target only Relay-owned sessions on Stop.
- Bound worker messages and read budgets; supervise automatic recovery and
  escalate stalled shutdowns without blocking the service loop.
- Scope DHCP/DNS firewall rules to the hotspot interface; preserve permanent
  firewalld configuration and AppArmor enforcement. Avoid blocking reverse DNS.
- Handle malformed deeply nested preferences safely and reduce repeated polling
  error logging.
- Normalize Debian timestamps for reproducible direct builds. Preserve nested
  Debian templates when rebuilding exported sources without Git metadata.

## Verification and limits

Native Ubuntu 26.10 checks cover 283 unit tests with zero skips, real GTK4/GTK3
settings and tray widgets, 17 applet cases with AddressSanitizer and
UndefinedBehaviorSanitizer, sustained private-bus tray handover, Debian
source/binary builds, and syntax and metadata checks. The live XFCE user manager
passed the blocking restart and process-survival check. Earlier stable-release
checks covered GNOME Shell 51 loading and private-bus daemon authorization.
The release validation report records source hashes, build provenance, CI links,
and results. GitHub CI exercises destructive package lifecycle checks separately.

The final build has not undergone privileged live wireless traffic,
suspend/resume, multi-client soak, or enforced firewall/AppArmor fault testing.
Earlier Beta 2 hardware tests covered one driver and XFCE and remain historical.
GNOME Shell 45–51 is declared compatible, with automated loading checked on 51.
Other distributions and RPM installation are outside this validated release.
NetworkManager AP+STA remains hardware-dependent and experimental; regulatory
channel restrictions are respected.

## Upgrade and rollback

Stop sharing before upgrading an older installation. Install all selected split
packages at version 1.0.0-22 together. Existing settings and credentials remain;
restart sharing explicitly after the upgrade. Older bundled installs need an
explicit choice of optional GNOME or tray controls.

See [maintenance and rollback](docs/releases/1.0.0-22.md) for private configuration
backups, downgrade procedure, and local AppArmor policy considerations. Downloads
are unsigned Debian packages accompanied by SHA-256 checksums; this release does
not create a signed APT repository or PPA.
