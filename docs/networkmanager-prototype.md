# NetworkManager AP+STA prototype

This integration prototype is a developer probe, separate from the installed
daemon and desktop UI. It asks whether NetworkManager can activate an ordinary
AP profile on a manually created virtual interface while preserving the existing
station connection on the same radio. A separate service-owned worker now uses the
same activation path for persistent operation controlled by Relay's desktop UI.

## Persistent desktop operation

Install the `1.0.0-11+nm2` package or newer, open Wi-Fi Relay Settings, and stop the
hotspot before selecting **NetworkManager (Experimental)** as the Hotspot Backend.
Connect the chosen adapter to Wi-Fi, set the SSID and password, and use Settings,
the desktop tray, or Relay's GNOME Quick Settings toggle to turn it on. There is
no five-minute limit in this mode. Closing the settings app does not stop it.

The existing Polkit-protected Start/Stop API launches a privileged service worker.
Saved credentials travel over an anonymous pipe and remain out of command arguments
and runtime journals. The worker owns the private D-Bus activation lifetime and
stops on explicit Stop, service shutdown, or an upstream connection/channel change.
The settings UI displays failures; the Shell extension also notifies on them.

The backend supports WPA2, hidden SSID, client isolation, raw PSK, and the configured
/24 gateway. It shares the host default route, so the interface selector is disabled
for egress selection. IEEE generation overrides, MAC filtering, custom DNS, custom
country, and non-NAT modes are rejected explicitly. Keep unsupported overrides off
when selecting this backend. The current upstream channel/band must match any
explicit preference; this backend does not reconnect Wi-Fi or switch bands.

Systemd gives the worker time to deactivate and remove its virtual interface. A
private `/run/wifi-relay/nm-owned.json` record tracks only interface name, index,
MAC, and profile identity. Startup and ExecStopPost recover resources left by a
crash, with identity checks that refuse to delete a replacement interface/profile.
The runtime record contains no password. Existing installations remain on create_ap
until the new backend is selected; selecting another backend requires stopping first.

This integrates with Relay's extension, not GNOME's built-in Wi-Fi hotspot menu.
Roaming/disconnect stops sharing safely; automatic reconnection, suspend recovery,
boot-time hotspot startup, and broad driver compatibility remain future work.

On the tested iwlwifi adapter with NetworkManager 1.58.1, the installed service
kept the hotspot active for 321 seconds after the requesting client exited.
Explicit Stop removed it and preserved upstream Wi-Fi. A separate test killed
the service worker with SIGKILL: the daemon reported the failure and recovered
the virtual interface while preserving upstream Wi-Fi. Both tests restored the
original backend configuration. No client DHCP, DNS, or internet test was performed.

## Read-only assessment

From the repository root:

```sh
python3 tools/nm_ap_sta_probe.py --station wlo2
```

Replace `wlo2` with your connected Wi-Fi interface. This needs Python with
PyGObject/Gio, `iw`, and `nmcli`; it does not require root. The JSON report includes
NetworkManager version, driver, channel, hardware capabilities, existing sibling
interfaces, and blockers. It excludes the upstream SSID, BSSID, and credentials.
It also checks the running daemon's D-Bus activation method signature, rather than
assuming the installed `nmcli` version identifies the running daemon. API presence
does not prove that the daemon/backend accepts the activation options on this radio.
An assessment exits successfully even when live testing is blocked; inspect
`eligible_for_live_probe` and `blockers` for that decision.

The prototype Debian package installs the same tool as `wifi-relay-nm-probe`.
Use that command in place of `python3 tools/nm_ap_sta_probe.py` for all examples
below. These instructions are also installed in
`/usr/share/doc/gnome-wifi-hotspot/networkmanager-prototype.md`.

## Temporary live test

Use an adapter with a connected NetworkManager Wi-Fi profile and no existing AP
or additional client interface on its PHY. Stop an existing hotspot through its
normal controls before testing. The probe refuses to stop or reuse it.

```sh
sudo python3 tools/nm_ap_sta_probe.py --station wlo2 --run --hold-seconds 15
```

The probe:

1. Rechecks eligibility and records the upstream profile, BSSID, SSID, and frequency
   internally to detect disconnects or roaming.
2. Creates a uniquely named virtual AP interface with a random locally administered
   MAC address. NetworkManager is allowed to manage this interface.
3. Requests a WPA2/CCMP AP on the current upstream channel, with `ipv4.method=shared`
   and IPv6 disabled. NetworkManager owns AP activation and IPv4 sharing; the probe
   does not launch `create_ap`, `hostapd`, or its own DHCP/firewall setup.
4. Uses `AddAndActivateConnection2` with `persist=volatile` and
   `bind-activation=dbus-client` on a private D-Bus connection. The profile is not
   saved to disk, and activation is tied to that bus connection's lifetime.
5. Observes the active AP and upstream connection for the requested time, then
   deactivates the AP, closes the bus connection, and deletes the interface it
   created. Cleanup is also attempted on errors, Ctrl-C, and SIGTERM.

The password is generated for each run and is neither printed nor passed on a
command line. By default no credentials are exported. The live probe observes
authorized stations and correlates their MAC addresses with IPv4 neighbors in the
AP subnet, reporting aggregate counts and gateway addresses. It does not publish
client MAC addresses or IP addresses. A neighbor entry is not proof of a DHCP
lease, DNS resolution, or internet access; those verification flags remain false.

## Connecting a test client

For a longer test with a phone or a second computer:

```sh
sudo python3 tools/nm_ap_sta_probe.py --station wlo2 --run \
    --hold-seconds 180 --credentials-file /tmp/relay-nm-client.json --require-client
```

In a second terminal, after the probe prints that activation has completed:

```sh
sudo cat /tmp/relay-nm-client.json
```

Connect the client using the SSID and password in that file. The file is created
exclusively with mode 0600, is root-owned when run through sudo, and is removed
at cleanup. An existing file or symlink is never overwritten. A crash/SIGKILL can
leave it behind along with the interface; remove the credentials file after such
a run. Client-test options require `--run`, so read-only assessment creates no file.

`--require-client` fails unless an authorized station with a usable IPv4 neighbor
in the AP subnet appears during the observation period. Generate traffic from the
client toward the hotspot gateway to populate that neighbor entry. A successful
run satisfies only this client link/address observation, not end-to-end connectivity.

On a Linux client, collect separate evidence while the probe remains active:

```sh
ip -4 address show dev CLIENT_INTERFACE
ip -4 route show dev CLIENT_INTERFACE
nslookup example.com GATEWAY_IPV4
curl --interface CLIENT_INTERFACE --noproxy '*' --max-time 15 https://example.com/
```

Replace `CLIENT_INTERFACE` and `GATEWAY_IPV4` with the client's Wi-Fi interface and
the gateway supplied by the hotspot. Configure the client for automatic DHCP;
inspect a DHCP exchange or client lease record to verify address acquisition.
The DNS check targets the hotspot gateway explicitly. For the HTTPS check, verify
that the route uses the client Wi-Fi connection. Disable other client uplinks if
the platform cannot bind traffic reliably. Record these client-side results beside
the host JSON; the host does not automatically import or certify them. Internet
egress can follow an Ethernet or VPN default route on the hotspot host.

A live-test error exits nonzero. Cleanup failures are printed to stderr and cause
a nonzero exit even if activation succeeded. Process crashes or SIGKILL can leave
the manually created interface behind; the bus binding protects activation, not
kernel interface lifetime. Inspect `iw dev` and remove only the leftover `wrnm…`
probe interface if needed. Any orphaned probe interface blocks a subsequent test.

## Lifecycle and repeated cycles

Each live result includes timed lifecycle stages: preparing, interface-created,
waiting-for-device, activating, active, stopping, and passed/failed. The probe waits
up to 15 seconds for NetworkManager's device to reach disconnected/ready state;
merely appearing on D-Bus does not establish availability. It records the device
state and reason and preserves the failure stage and observations. A failure preserves the stage at
which it occurred and any client observations gathered before stopping. Cleanup
checks verify the kernel interface is absent, the owned volatile profile is absent
from NetworkManager's connection list, and the exported credentials file is gone.
The profile check allows up to five seconds for asynchronous removal. A cleanup
error makes the result fail even if activation and observation succeeded.

Upstream preservation is checked after cleanup on both success and failure. The
probe does not reconnect or modify the upstream profile to repair a detected
change. These checks verify resource removal, not restoration of every firewall
rule or host routing detail; that still needs real network testing.

For start/stop repetition after a basic live test succeeds:

```sh
sudo python3 tools/nm_ap_sta_probe.py --station wlo2 --run \
    --hold-seconds 15 --cycles 3 > /tmp/relay-nm-cycles.json
```

Each cycle reinspects the radio, creates a fresh interface/profile, observes it,
then cleans up. Repetition stops at the first activation, observation, preflight,
or cleanup failure. One to ten cycles are supported. If credentials are exported,
each cycle gets a new password; reconnect the test client with that cycle's
credentials. Repeated cycles without `--require-client` exercise lifecycle only.

Stdout contains one JSON document on success or failure, suitable for saving as
above. Stderr carries progress and diagnostic messages. Failed CLI reports contain
`error` and `report`; `report.cycles` preserves completed and failed live cycles.
A preflight failure may have no live-cycle result because nothing was created.
The exit status remains nonzero for failure; check both exit status and saved JSON.

## Current evidence and limits

Inspection of the development machine found NetworkManager 1.58.1, the `iwlwifi`
driver, and an advertised managed+AP combination restricted to one channel. The
generated profile passed local libnm validation. After connecting the station to
the permitted 2.4 GHz channel, two live attempts failed: NetworkManager detected
the virtual AP, but the supplicant could not initialize it (`Device or resource
busy`, followed by `wpa_supplicant couldn't grab this interface`).

The first attempt requested activation before readiness and was rejected as
unavailable. A retry with the readiness wait confirmed the device stayed in state
20 (unavailable), reason 2 (now managed), until timeout. Both attempts removed the
temporary interface and preserved the upstream station connection; no client test
was possible in those attempts. No conclusion about other drivers follows from this result.

Tracing NetworkManager 1.58.1's Wi-Fi `deactivate()` path found that it resets a
non-infrastructure interface to infrastructure/station mode. The supplicant's
nl80211 initialization preserves a statically created AP when it is still in AP
mode. This suggests why an AP+STA-capable PHY advertising only one managed slot
fails during initial handover: the extra interface becomes another station.

An opt-in diagnostic workaround, `--restore-ap-mode`, checks the owned interface
while it is unavailable. If its type has become `managed`, the probe takes only
that interface down and restores `__ap` once, then waits up to 30 seconds for NM's
supplicant reacquisition. It never changes the upstream interface. Normal probe
behavior is unchanged unless this option is supplied.

The first live workaround test passed: NetworkManager reached activated state,
the AP broadcast on the upstream channel, a shared address of `10.42.0.1` appeared,
the upstream connection was preserved, and both the interface and profile were
removed. No client joined that run, so DHCP/DNS/internet access remains unverified.
This is evidence of a working initialization workaround on this machine, not a
general fix for NetworkManager or all drivers.

Three subsequent start/observe/stop cycles also passed, each preserving the
upstream connection and removing its owned interface and profile. The host thus
completed four successful live runs with the opt-in workaround. These observations
do not yet cover connected clients, suspend/resume, or upstream roaming.

To reproduce the diagnostic test with the updated prototype:

```sh
sudo wifi-relay-nm-probe --station wlo2 --run --restore-ap-mode --hold-seconds 15
```

The option also works with `--cycles`, `--credentials-file`, and `--require-client`.
Keep it experimental: it relies on an unavailable-device retry and is sensitive
to NetworkManager/supplicant behavior. A service backend still needs explicit
ownership, crash cleanup, roaming handling, and client validation. The upstream
direction is to preserve an intended AP role during initialization and shutdown,
rather than exposing this timing workaround as the final GNOME user flow.

Source references:
[NetworkManager 1.58.1 Wi-Fi device implementation](https://github.com/NetworkManager/NetworkManager/blob/1.58.1/src/core/devices/wifi/nm-device-wifi.c),
[NetworkManager supplicant initialization](https://github.com/NetworkManager/NetworkManager/blob/1.58.1/src/core/supplicant/nm-supplicant-manager.c),
and [hostap 2.11 nl80211 driver initialization](https://chromium.googlesource.com/external/w1.fi/cgit/hostap/+/refs/tags/hostap_2_11/src/drivers/driver_nl80211.c).

The probe reuses the production daemon's conservative regulatory parser: disabled,
`no IR`, and radar/DFS channels are excluded. It never switches the upstream band
or reconnects the station. Roaming or a changed channel causes it to stop. It checks
the connection at intervals, so a short interruption between samples may be missed.
It does not yet automatically verify client DHCP/DNS/internet access, roaming recovery, suspend,
multiple adapters, VPN routing, or different drivers. NetworkManager's shared
connection follows host routing; this is not a test of Wi-Fi-specific egress.

After a successful live activation, the next milestone is client connectivity and
failure recovery on representative hardware. Evidence from those tests should
determine whether the missing upstream work belongs in NetworkManager interface
creation/lifecycle, channel coordination, or GNOME's hotspot UI.

## GNOME integration: now and later

XFCE's NetworkManager Applet has a separate downstream integration in
[integration/nm-applet](../integration/nm-applet/README.md). Its network menu now
includes a Wi-Fi Relay submenu that uses the same service API. The installed
applet's live status and Settings action were verified without interrupting its
connected hotspot client. This does not change GNOME Shell's built-in menu.

The intended control is a VPN-like on/off toggle in the network controls, while
the connection remains a Wi-Fi AP. The repository already has a GNOME Shell Quick
Settings toggle with Start/Stop methods and status notifications. That UI currently
controls the selected Relay backend, including the new persistent NM worker.

The implemented extension path is:

```text
Wi-Fi Relay Quick Settings toggle
              |
     Relay service: Start / Stop / status
              |
     interface creation and channel coordination
              |
     NetworkManager AP profile + IPv4 sharing
```

| Layer | Available now | Work needed before shipping |
| --- | --- | --- |
| GNOME controls | Existing extension toggle controls the selected backend | Test a real GNOME Shell session and propose built-in integration separately |
| AP activation and sharing | Standard wireless AP and shared-IPv4 settings | Prove activation, DHCP, DNS, routing, and cleanup on real hardware |
| Virtual AP interface | Service worker owns it; journal and systemd hooks recover leftovers | Wider driver testing and suspend recovery |
| Concurrent channel handling | Prototype pins the AP to the station channel | Event handling and recovery for roaming/regulatory changes |
| Built-in GNOME controls | Documented hotspot flow disconnects the Wi-Fi station | Separate upstream GNOME design and implementation proposal |

This uses today's NetworkManager APIs. Activation works on the tested driver with
the AP-mode workaround, and the optional Relay backend provides desktop control
without waiting for an upstream GNOME merge. Other drivers need their own live
tests. If those fail, retain the working `create_ap` backend and use the failure evidence
to scope NetworkManager/supplicant/driver work. Unsupported hardware needs a second
adapter; a future software merge cannot remove radio restrictions.

An actual VPN plugin is a different connection type with its own D-Bus plugin
service and tunnel configuration. Registering the hotspot as VPN would add that
contract while still requiring AP creation, DHCP sharing, and channel coordination.
It is not needed to get a similar toggle. Keep actual VPN connections independent
so sharing and an existing VPN can coexist according to the host's routing policy.

The UI integration reuses Relay's current toggle and service methods. A service
worker owns the lifetime and existing Polkit checks authorize client requests.
The bounded developer probe remains a separate testing command.
Extending GNOME's built-in menu is a later upstream change; the extension is the
available path to the desired control today.

Official references: [wireless AP settings](https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html),
[IPv4 sharing](https://networkmanager.dev/docs/api/latest/settings-ipv4.html), and
[AddAndActivateConnection2 options](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.html).
Also see [VPN settings](https://networkmanager.dev/docs/api/latest/settings-vpn.html)
and [GNOME's documented hotspot flow](https://help.gnome.org/gnome-help/net-wireless-adhoc.html).
