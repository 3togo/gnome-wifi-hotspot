# Wi-Fi Relay inside the XFCE network menu

This is a downstream patch for Ubuntu's NetworkManager Applet 1.36.0-4ubuntu1.
It adds a **Wi-Fi Relay** submenu beside VPN Connections in the existing network
indicator. The submenu has a Hotspot checkbox, service status and client count,
and a settings launcher. It controls the backend already selected in Relay Settings.
The hotspot remains a Wi-Fi AP; no VPN profile or plugin is registered.

The applet calls Relay's existing Polkit-protected Start/Stop methods asynchronously
and reads GetStatus without accessing credentials. It disables the checkbox during
Start/Stop and when the service is unavailable, shows failed operations in a dialog,
and refreshes from status signals plus a five-second poll for client counts. Exiting
or restarting the applet does not stop the service-owned hotspot. Adapter selection
and regulatory restrictions remain the responsibility of Relay and NetworkManager.

## Build and install

Enable Ubuntu source repositories and install the build dependencies:

```sh
sudo apt-get build-dep network-manager-applet
bash integration/nm-applet/build-deb.sh
sudo apt install ./dist/network-manager-applet_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./dist/nm-connection-editor_1.36.0-4ubuntu1+relay3_amd64.deb \
  ./dist/network-manager-gnome_1.36.0-4ubuntu1+relay3_amd64.deb
```

Ubuntu requires matching versions of these three packages, so install them together.
Restart `nm-applet` or log out and in to load the new binary. Click the usual network
icon and open **Wi-Fi Relay**. Relay itself must be installed and configured first.
This integration targets XFCE's nm-applet; GNOME Shell uses the repository's separate
Quick Settings extension.

## Verification

With a display, run the isolated GTK/D-Bus test suite:

```sh
make test-nm-menu
SANITIZE=1 make test-nm-menu
```

The test uses a private bus and fake Relay service, and changes no host connections.
Its 16 cases check menu activation, duplicate requests, Start/Stop reply types,
busy state, denied authorization, client counts, malformed status, service
replacement with pending replies, and cancellation during outstanding requests. A separate installed-app live test should exercise
the exported DBusMenu events against the real Relay service.

```sh
python3 integration/nm-applet/check-live-menu.py --open-settings
# Optional: cycles an active hotspot only if no clients are connected.
python3 integration/nm-applet/check-live-menu.py --cycle
```

The installed patch was tested in the XFCE session: its exported menu matched
the real active hotspot and one connected client, and the Settings action opened
the settings application. A subsequent client-free installed-menu Stop/Start cycle passed on relay3.
The additional cases cover waiting-state parsing and cancelling recovery from the menu.

## Maintenance and rollback

The patch is kept here rather than copying the full upstream source into this repo.
The builder first runs Python/tray and menu tests, then downloads the matching Ubuntu source and preserves its existing patches,
build flags, and packaging. This is a local downstream package, not an upstream merge.
A future distribution update may replace it; rebase and retest the patch before
rebuilding against a new source version.

To restore the distribution applet while this base version remains available:

```sh
sudo apt install --allow-downgrades network-manager-applet=1.36.0-4ubuntu1 \
  nm-connection-editor=1.36.0-4ubuntu1 network-manager-gnome=1.36.0-4ubuntu1
```

Restart the applet afterward. This leaves the Relay service and Settings installed.
