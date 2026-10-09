# Dependency review and minimal Stonking packages

## Findings and changes

1. The Relay package declared `procps` and `psmisc` although the shipped Python
   code and create_ap do not call their tools. create_ap's `pidof` comes from
   the Essential `sysvinit-utils` package on Stonking. Both unused declarations
   were removed. Its external `which` calls were replaced by Bash `command -v`.
2. Three GI dependencies were redundant: python3-gi already requires GLib GI,
   adwaita GI requires GTK4 GI, and Ayatana AppIndicator GI requires GTK3 GI.
   Removing their duplicate declarations changes neither toolkit availability
   nor the supported desktop features. Mandatory direct dependencies drop from
   17 to 12. An empty-status APT simulation with `--no-install-recommends` drops
   the complete mandatory package closure from 281 to 280: only psmisc disappears,
   because procps remains a dependency of another package. This is a package-set
   comparison, not a prediction of downloads on an existing desktop.
3. The patched applet forced an exact matching nm-connection-editor package,
   although the Relay patches affect the applet, not the editor. The applet and
   transitional package now accept editors from Ubuntu's reviewed 1.36 family,
   starting at 1.36.0-4ubuntu1 and stopping before 1.37. The transition package
   still requires its matching patched applet. Builds export only the applet and
   transition package by default. Existing or archive editors can satisfy the
   requirement without a custom editor .deb.
4. The GNOME Settings patch changes device identity comparisons without changing
   schemas, UI resources, or other shared data. Its minimum data version now
   remains Ubuntu's 1:51.0-1ubuntu1 baseline; the upstream next-version upper
   bound remains. Builds export only gnome-control-center by default. Stock or
   previously installed compatible data is sufficient.
5. The NetworkManager patch changes shared connection validation in libnm.
   Its exact libnm0 dependency is required and remains intact. Core builds now
   export only network-manager and libnm0 by default. Headers, introspection,
   text UI, translations, alternate backends, and debug output are not part
   of the minimal custom runtime bundle. `--all` retains full export support.

Dependency relaxation is guarded by exact supported upstream source versions
and expected control templates. New upstream versions need review before these
rules can be reused. No dependency checks are disabled in the build scripts.

## Minimum custom .deb files

These counts exclude normal Ubuntu archive dependencies, which APT resolves.
They also exclude unrelated packages already installed on a particular machine.
Use APT with explicit filenames rather than dpkg or a wildcard over dist.

| Requested behavior | Custom packages | Count |
| --- | --- | --- |
| Relay with stock NetworkManager and helper-owned AP lifecycle | gnome-wifi-hotspot | 1 |
| Native NetworkManager-owned AP lifecycle | gnome-wifi-hotspot, network-manager, libnm0 | 3 |
| Native Relay plus nm-applet controls; no transition package installed | above plus network-manager-applet | 4 |
| Native Relay plus nm-applet controls; existing network-manager-gnome transition package retained | above plus compatible network-manager-gnome | 5 |
| Above plus GNOME Settings duplicate-tab correction | above plus gnome-control-center | 6 |

A transition package is metadata, not the NetworkManager daemon. An installed
older transition package may pin old applet/editor versions, so simply omitting
it can break upgrades. The compatible rebuilt transition package avoids removing
existing desktop packages. Do not automatically remove it on a user's machine.

If an installed libnm-dev or network-manager-tui pins a different libnm version,
a core upgrade also needs its matching package. libnm-dev additionally pins the
matching gir1.2-nm-1.0. The Relay app itself imports Gio, not NM introspection.
Those extras are required by the target machine's installed packages, not by
Relay's runtime. Use the core builder's `--all` output in that situation and
simulate the exact install first. Never force past a libnm dependency failure.

## Builds and installation review

Local builds are native Stonking builds and never install their output:

```
./packaging/build-deb.sh
./integration/nm-core/build-deb.sh
./integration/nm-applet/build-deb.sh
./integration/gnome-settings/build-deb.sh
```

Each integration builder accepts `[version] [--all]`. The optional flag exports
unchanged companions as well; the upstream builds still generate all their
binary outputs internally. Export minimization reduces release files, not build
dependencies or upstream test coverage.

The reviewed six-file bundle is under `dist/minimal-relay-stonking/`. Verify its
SHA256SUMS and run its printed explicit APT simulation before installing. APT
will fetch ordinary archive dependencies if needed. The machine reviewed here
already has the matching native core/libnm pair, so its update needs only four
new files in `dist/minimal-update-stonking/`: Relay, applet, transition metadata,
and GNOME Settings. Both exact install simulations succeed without removals,
including a separate simulation explicitly selecting stock editor/data versions. This operation is a review,
not permission to alter the running network stack.

## Remaining limits

GTK4/adwaita supplies Settings and GTK3/AppIndicator supplies the standalone tray.
Starting with development version 1.0.0-16, GTK3/AppIndicator belongs to the
optional `gnome-wifi-hotspot-tray` package. GNOME Shell controls belong to
`gnome-wifi-hotspot-gnome`. The main package requires only GTK4/adwaita for its UI;
startup controls are unavailable when the session's integration is absent.
Both optional packages depend on the matching main-package version. The older
bundles reviewed above predate this split. hostapd and
iptables remain necessary for the create_ap backend; removing them from the
common package without changing defaults or checking backend availability would
break fresh installations. dnsmasq-base is used for hotspot address service and
avoids installing a second system dnsmasq daemon.

The native core remains a hardware-dependent prototype with the release gates
in production-readiness.md. Dependency simulation cannot validate AP+STA driver
behavior. The Show QR issue identified by this review is fixed in 1.0.0-15+qr1:
Settings renders a scannable image using the bundled MIT-licensed Nayuki encoder,
without adding QR or imaging packages to the runtime dependencies.
