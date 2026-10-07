# Proposal: native concurrent Wi-Fi sharing in NetworkManager

Status: local design draft and tested reference implementation. Nothing has been
submitted to, accepted by, or merged into the upstream projects.

## Problem and intended behavior

A laptop connected to Wi-Fi should be able to share its connection through a
hotspot on the same radio when its driver, interface combinations, and regulatory
state permit that operation. Starting sharing must preserve the existing station
connection. Unsupported configurations should produce an actionable error before
creating resources or changing the uplink.

The user-facing control is “Share Wi-Fi connection”: on/off, current state, and a
settings entry. The connection is a wireless AP with IPv4 sharing. It is not a VPN.
NetworkManager already exposes AP settings, activation/deactivation, shared IPv4,
and authorization. The proposed work concerns concurrent interface ownership and
coordination, followed by a desktop control for that capability.

## Decision and project boundaries

Keep Wi-Fi Relay available while contributing the missing functionality in small,
reviewable changes. Do not move the entire application into NetworkManager.

| Component | Proposed upstream responsibility | Current reference implementation |
| --- | --- | --- |
| NetworkManager core / supplicant integration | Create and own concurrent AP interfaces, preserve station operation, coordinate channel and lifecycle | `tools/nm_ap_sta_probe.py` and `daemon/nm_backend.py` |
| libnm / D-Bus | Expose supported capability, activation intent, state, and actionable failure reasons | Relay's service currently supplies coordination around existing NM APIs |
| NetworkManager Applet | Generic sharing controls using the agreed native interface | `integration/nm-applet/relay-menu.patch` currently calls Relay's service |
| GNOME Shell / Settings | Their own sharing controls and settings, using the same native capability | Relay's extension and Settings remain usable separately |

The local applet patch is a downstream demonstration, not an upstream-ready generic
feature: it names the Relay D-Bus service. Its asynchronous request handling and
status behavior can inform the eventual native control. Upstream UI should depend
on the native NetworkManager capability rather than introduce a Relay dependency.

## Minimum networking contract

1. Identify an explicit parent Wi-Fi device and its active station connection.
   Do not switch to an unrelated saved SSID or change the station band implicitly.
2. Evaluate the relevant PHY interface combination, supported AP mode, current
   channel, and regulatory/driver restrictions. Never bypass `no IR`, disabled,
   or DFS requirements merely because a station is associated.
3. Realize a separate AP interface and bind its identity to this activation.
   The station interface must remain untouched. Externally created interfaces
   and unrelated connection profiles must never be adopted or deleted.
4. Activate an ordinary WPA2 AP profile with shared IPv4 through NetworkManager.
   NetworkManager continues to own DHCP/DNS and sharing rules. Specify whether
   sharing follows the host default route; do not imply Wi-Fi-only egress or
   guarantee VPN traversal unless that policy is explicitly implemented and tested.
5. Keep the lifetime under NetworkManager's ownership, independent of which UI
   requested activation. Emit state changes so all desktop clients stay consistent.
6. On Stop or failed activation, attempt every cleanup action and report failures.
   Cleanup must be idempotent, preserve upstream connectivity, and resist interface
   name reuse. A transport or notification failure must not skip cleanup.
7. For an initial conservative implementation, stop sharing with a reason if the
   station disconnects or changes channel. Automatic channel migration, roaming
   recovery, suspend recovery, and boot activation need separate capability and
   lifecycle work. Do not promise them in an initial patch.

The final API shape is an upstream design decision. We propose an explicit parent
relationship and concurrent-sharing intent, but do not claim that a particular new
D-Bus method or wireless property already exists or should be standardized unchanged.

## Evidence from the reference implementation

On the tested iwlwifi radio with NetworkManager 1.58.1 and wpa_supplicant 2.11:

- The radio advertises managed+AP concurrency with one shared channel.
- A manually created AP interface can be reset to managed mode during device
  initialization. Restoring AP mode once during an unavailable-device retry allowed
  activation on this machine. This workaround is local evidence to investigate;
  it should not be copied into upstream as an unconditional interface-mode reset.
- A service-owned activation ran for 321 seconds after its requesting client exited.
  Explicit Stop and forced-worker-crash recovery preserved upstream Wi-Fi.
- The downstream applet displayed an active hotspot and one connected client, and
  its Settings launcher was exercised without disconnecting that client.
- A later attempt on the associated 5 GHz channel was blocked by the conservative
  regulatory check. The saved 2.4 GHz connection allowed activation. This does not
  establish general 5 GHz support or justify relaxing that check.

A later [installed-package client test](networkmanager-live-validation.md)
verified a DHCP configuration, hostname resolution, client routing through the
hotspot, and an external ICMP reply. Follow-up ADB probes received HTTPS 200
responses from two external sites over TLS 1.3, with certificate and hostname
verification enabled; the hostname-mismatch check failed during TLS as expected.
The first run used Ethernet; subsequent checks verified Wi-Fi-only HTTPS and a
fresh gateway DNS exchange, including forwarding and return packets on Wi-Fi.
Five Start/Stop cycles, worker/daemon crashes, upstream disconnect, controlled
band change, and systemd suspend/resume exercised cleanup. A discovered journal
retry defect during NetworkManager restart was fixed and retested in nm4.
Sharing stops after upstream loss and needs an explicit restart; these results
do not establish seamless roaming, automatic resumption, or support across drivers.
Association and neighbor observations alone remain insufficient.

## Automated verification before further integration

The reference now has targeted tests for:

| Invariant | Tests |
| --- | --- |
| Unsupported configurations do not create resources | Probe preflight, worker band/channel mismatch, unsupported overrides |
| Startup failure does not leak a worker | Spawn failure, broken credentials pipe, activation/discovery timeout |
| Shutdown completes despite secondary failures | Deactivation/bus-close failures, observer failure, SIGTERM, closed parent pipe |
| Recovery deletes only owned resources | Interface index/MAC and profile identity mismatch, deletion failure, repeated recovery |
| Credentials stay out of runtime metadata | Anonymous input pipe, ownership field whitelist, private journal permissions |
| Status transport remains usable | Partial reads, malformed events, invalid schema, bounded partial output, worker crash |
| Menu operation preserves the correct state | Start/Stop, duplicate activation, busy controls, denied Start, status signals |
| Async callbacks respect service lifetime | Owner replacement with pending replies, cancellation during status/operation/proxy creation |
| Protocol replies are validated | Malformed/duplicate JSON keys, exact Start/Stop reply types, normalized client counts |

Run `make test` for Python and tray tests. With a display and GTK3/Gio/Jansson
build dependencies, run `make test-nm-menu`; set `SANITIZE=1` to enable AddressSanitizer
and UndefinedBehaviorSanitizer. The CI workflow runs the menu suite under a virtual
display with those sanitizers. The private-bus tests make no host network changes.
These tests validate the reference code; native NetworkManager patches will also
need regression tests in NetworkManager's own test infrastructure.

Local verification on 7 October 2026: 150 Python tests, the tray state tests, and
14 private-bus menu cases passed. The menu cases also passed with address and
undefined-behavior sanitizers. Before the nm4 recovery-retry change, Coverage.py's
combined statement/branch measure was 93% for the service backend and 84% for the
probe/session implementation.
Uncovered paths include hardware/D-Bus wrappers and CLI handling; these numbers
do not certify radio behavior or end-to-end client connectivity.

## Proposed contribution sequence

1. Present this problem statement, driver evidence, and minimal reproducible
   activation sequence to NetworkManager maintainers. Resolve the parent-device
   contract and the cause of the initialization mode conflict first.
2. Prepare a focused NetworkManager change with native tests for interface
   creation, station preservation, failed activation, and ownership cleanup.
   Avoid combining a new desktop UI and broad recovery policy into that patch.
3. Once the native activation contract works, prepare a separate applet change
   using libnm. Keep UI requests asynchronous, validate replies/state, and test
   service restart, authorization failure, and stale callbacks.
4. Add GNOME Shell / Settings integration as separate project changes. Their UI
   and release compatibility need their own testing.
5. Retire the Relay worker only when native support replaces its behavior on the
   supported distributions. Keep the working fallback until then.

## Hardware and client gates still required

Before requesting a production merge, repeat the recorded DHCP, fresh DNS,
Wi-Fi-only HTTPS, Stop, crash, restart, disconnect, channel-switch, and suspend
checks on a second driver and a supported GNOME Shell session. Exercise natural
channel roaming, longer multi-client operation, and partial activation failure.

Test both shared default-route operation and any proposed explicit uplink/VPN
policy. Include denied authorization and regulatory-blocked channels. Capture
versions and sanitized lifecycle evidence, never passwords, raw PSKs, or client
identities in public reports. Unavailable hardware scenarios remain open gates;
unit tests must not be presented as their replacement.

## Submission path

Use the [NetworkManager GitLab issue tracker](https://gitlab.freedesktop.org/NetworkManager/NetworkManager/-/issues)
for the initial design discussion. The project's
[contribution guidelines](https://github.com/NetworkManager/NetworkManager/blob/main/CONTRIBUTING.md)
recommend discussing substantial changes before implementing an upstream patch.
Lead with concurrent AP ownership and the initialization mode conflict; the Relay
menu patch remains reference material for the later desktop work.

Before an upstream merge request, the human contributor must review and understand
the patch, build and test it, write the commit messages and merge request
description, and confirm the contribution can use LGPL-2.1-or-later. Read the
upstream `AGENTS.md` before editing that repository. Passing the reference tests
does not satisfy the native project's test requirements or these author duties.

Installed-package verification on 7 October 2026: Relay `1.0.0-11+nm3` and
the three matching applet packages `1.36.0-4ubuntu1+relay2` were installed.
The exported live applet menu completed Stop/Start on a client-free hotspot and
converged to the service's active state and client count. The check helper now
retries status timeouts while synchronous service operations finish.

## Questions for upstream review

- What existing virtual-device lifecycle mechanism should own a concurrent AP?
- How should a sharing profile identify its parent station device/connection?
- Is the observed AP-to-managed initialization behavior a NetworkManager,
  supplicant, or driver issue, and what is the smallest correct fix?
- Which regulatory concurrency rules can be represented safely across drivers?
- What stable capability and failure information should libnm expose to clients?
- Should the first version stop on roaming/channel changes, with recovery added
  separately after driver evidence?

## Primary references

- [NetworkManager activation and lifetime APIs](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.html)
- [Wireless AP settings](https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html)
- [Shared IPv4 settings](https://networkmanager.dev/docs/api/latest/settings-ipv4.html)
- [NetworkManager 1.58.1 Wi-Fi device implementation](https://github.com/NetworkManager/NetworkManager/blob/1.58.1/src/core/devices/wifi/nm-device-wifi.c)
- [NetworkManager supplicant initialization](https://github.com/NetworkManager/NetworkManager/blob/1.58.1/src/core/supplicant/nm-supplicant-manager.c)
- [NetworkManager Applet implementation](https://github.com/GNOME/network-manager-applet/blob/main/src/applet.c)
