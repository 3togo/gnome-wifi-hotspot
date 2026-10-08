# GNOME Settings Wi-Fi device tab cleanup

GNOME Control Center 51.0 uses `NMDevice.Udi` as the Wi-Fi stack page ID.
NetworkManager clears Udi when a virtual Relay interface unrealizes. The
device-removed callback consequently cannot find its old page, leaving another
Intel AX200 tab after every start/stop cycle despite the interface being removed.

The downstream patch uses each NMObject's stable D-Bus path for both stacks,
device membership checks, removal, visible-device bindings, and command-line
device selection. Real hardware UDI changes no longer create duplicate pages.
One physical station and one active Relay child can still appear as two devices.

Build directly on Ubuntu Stonking:

```sh
sudo apt-get build-dep gnome-control-center=1:51.0-1ubuntu1
bash integration/gnome-settings/build-deb.sh
```

The builder preserves Ubuntu packaging, runs its normal tests, and writes the
packages to `dist/`. It does not install them. GNOME Settings must be restarted
after installation. To verify, keep Settings open across repeated Relay Start /
Disconnect cycles: only the current physical adapter and current Relay interface
should have tabs, and removing a visible Relay tab should select a remaining
device without leaving an empty page or a GTK assertion.

The source baseline is Ubuntu `1:51.0-1ubuntu1`; the downstream version is
`1:51.0-1ubuntu1+relay1`. GNOME's GPL-2.0-or-later license applies to the patch.
The Ubuntu build passed all four upstream test targets. With the built binary
open against the installed native Relay stack, two client-free Stop/Start cycles
removed the old tab and restored exactly the two current tabs, verified through
the accessibility tree. No GTK assertions occurred. The package awaits sudo
installation; the open window currently runs the tested binary directly.
