# Installed NetworkManager integration validation

Date: 7 October 2026. These results describe one development machine, not a
cross-driver certification or an upstream merge.

## Installed environment

- Wi-Fi Relay initially `1.0.0-11+nm3`; the discovered restart cleanup fix is
  installed as `1.0.0-11+nm4`.
- NetworkManager Applet, connection editor, and compatibility package
  `1.36.0-4ubuntu1+relay2`.
- NetworkManager 1.58.1, wpa_supplicant 2.11, `iwlwifi`.
- XFCE with the patched `nm-applet`; concurrent station and AP on 2.4 GHz.
- Android 14 tablet as the hotspot client.

The packages were installed together, preserving the existing configuration.
The service was active after installation and successfully started the hotspot.
The applet was restarted to load the updated binary.

## Results

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Python regression suite | Pass | 150 unit tests, including four delayed-recovery regressions |
| Tray state suite | Pass | Failed startup, stale replies, and disable checks |
| Applet isolation suite | Pass | 14 private-bus tests, also with ASan/UBSan |
| Installed menu Stop/Start | Pass | Exported menu events stopped and restarted a client-free hotspot; toggle and summary converged to service status |
| Real client association | Pass | Tablet connected; service observed one client |
| DHCP configuration | Pass | Address on `192.168.12.0/24`; Android DHCP diagnostics reported gateway and DNS configuration |
| Hostname resolution / fresh DNS | Pass | A unique generated name was queried through the hotspot gateway; captures showed forwarding over upstream Wi-Fi and the answer returning to the client |
| External client routing | Pass | Route to the tested external IP used the client's Wi-Fi interface and hotspot source address |
| External ICMP | Pass | Client received a reply from `1.1.1.1` through the hotspot |
| HTTPS | Pass | ADB probe received HTTP 200 from `example.com` and `www.kernel.org` over TLS 1.3, with platform certificate trust and HTTPS hostname checks enabled |
| HTTPS client path | Pass | Probe socket bound to the tablet's hotspot IPv4 address; client remained associated and its route used Wi-Fi |
| Certificate validation negative check | Pass | `wrong.host.badssl.com` failed at the TLS stage with `SSLHandshakeException` |
| Earlier plain HTTP / TCP endpoint probes | Unresolved | Plain HTTP and the TCP-only probe to `1.1.1.1:443` failed on both networks; successful HTTPS tests supersede the earlier general web-access uncertainty |
| Client restoration | Pass | Tablet reconnected to its original saved Wi-Fi; final service/menu client count returned to zero |
| Wi-Fi-only egress | Pass | Ethernet disconnected; host route used `wlo2`; both HTTPS endpoints passed and matching outbound/return traffic was captured on Wi-Fi |
| Repeated Start/Stop | Pass | Five cycles; no remaining owned interfaces, profiles, workers, DHCP processes, journal, or firewall references |
| Worker crash | Pass | Forced worker exit reported an error and removed owned resources without changing upstream Wi-Fi |
| Service crash | Pass | Forced daemon exit restarted the service and removed owned resources without changing upstream Wi-Fi |
| Upstream disconnect | Pass | Sharing stopped with a reason and removed owned resources; original station connection and hotspot were restored explicitly |
| NetworkManager restart | Pass after fix | nm3 left a journal when NM was unavailable during cleanup; nm4 retries through polling and removed it automatically after NM returned |
| Controlled band/channel switch | Pass | Switching to a saved 5 GHz station profile stopped sharing and cleaned up; original 2.4 GHz profile and hotspot were restored |
| Suspend/resume | Pass for safe stop | Systemd suspend with NVIDIA hooks and RTC wake completed; station reconnected and owned hotspot resources were removed; an explicit Start succeeded afterward |
| Debian lifecycle | Pass | Disposable Ubuntu 24.04 container verified upgrade, remove, purge, and fresh installation of nm4 |

The first HTTPS run used the host's Ethernet default route. A later run with
Ethernet disconnected verified Wi-Fi-only HTTPS and fresh DNS through `wlo2`.
Packet captures showed the unique DNS request and response on both interfaces,
as well as HTTPS destinations and return traffic on upstream Wi-Fi. Raw captures
were stopped and removed after extracting sanitized evidence. VPN traversal
remains unverified. Station connection and channel snapshots were unchanged
during the client requests.

The tablet has no `curl`, so the follow-up used the
[Android TLS probe](../tools/android/README.md), launched through ADB without an
app installation. The same probe first passed on the tablet's original Wi-Fi.
Through the hotspot it received 589 bytes in the response body section from
`example.com` and 19,137 from `www.kernel.org`. It then rejected the hostname-mismatch
endpoint during the TLS handshake. The temporary Android JAR was removed and
the tablet's original connection was restored. Sanitized results are recorded in
[the HTTPS evidence file](evidence/adb-https-2026-10-07.json).

The later fault and routing checks are recorded in
[the production-check evidence](evidence/production-checks-2026-10-07.json).
The initial service-crash harness held a stale D-Bus owner; constructing a fresh
proxy for each call corrected the test. NetworkManager restart then exposed the
actual journal-retry defect. The fix retains identity validation and retries
owned-resource recovery after a failed attempt; successful recovery stops retries.
Four new unit cases cover initialization, worker exit, Stop, and live-worker
exclusion. The fixed package was installed and the restart test passed.

A direct `rtcwake` suspend bypassed the enabled NVIDIA hooks and was rejected by
the driver. The corrected test programmed an RTC alarm and started systemd's
suspend service, including those hooks. It completed suspend/resume successfully.
The ADB server needed restarting afterward to rediscover the two authorized
devices. Sharing deliberately stops on upstream loss and requires an explicit
Start; these checks do not certify automatic resumption or seamless roaming.

The package lifecycle assertion was corrected to compare fresh installation
against the new package's defaults rather than defaults from version 1.0.0-7.
The complete corrected lifecycle check passed for nm4. No host uninstall or purge
was performed. NetworkManager restart automatically reconnected Ethernet; it was
disconnected again to restore its initial state.

Post-stress HTTPS on nm4 passed again through Wi-Fi-only egress. One early random
DNS query returned NOERROR instead of the expected NXDOMAIN; a subsequent host
query for the same name returned NXDOMAIN. Follow-up client queries after a short
settling delay returned the expected negative answers. This single response
anomaly remains recorded for investigation; the earlier packet capture establishes
fresh forwarding, but does not guarantee every startup-time DNS response.

The first client check ran immediately after association, before DHCP completed.
Waiting for the assigned address corrected that check. The live menu helper also
needed to retry status timeouts while the service completed synchronous Start/Stop
operations; the corrected helper passed the installed-package cycle.

The hotspot was left active. Passwords and client identities are excluded from
this report. Detailed local test output is under ignored `dist/` files.

## Remaining integration gates

Repeat on another physical driver and a full GNOME desktop session. The isolated
GNOME Shell 51 load and disable/re-enable smoke test now passes. Test natural
same-band roaming, longer operation with multiple clients, and distribution
applet updates, and retain multi-client and distribution-update coverage.
Automatic recovery is implemented in nm5; the additional validation below records
its results and limits. Native NetworkManager interface lifecycle regression tests and
maintainer design review remain required before an upstream merge. See the
[contribution proposal](networkmanager-upstream-proposal.md) for the staged scope.


## nm5 recovery and GNOME checks

The service retains a successful Start request in memory and pins it to the
original upstream connection UUID. After temporary upstream loss it cleans up its
owned resources, waits for four seconds of stable association, repeats regulatory
and interface-combination checks, and retries with backoff. The worker independently
checks the expected upstream UUID before creating an interface. Stop cancels pending
and connecting recovery; radio-off cancels it as well. Configuration changes require
a new explicit Start. Intent is deliberately not retained across a daemon restart
or reboot, and credentials are not written into the ownership journal or status.

There are 170 Python regression tests, Node menu-state checks, and 16 private-bus
applet cases passing with address and undefined-behavior sanitizers. Coverage includes
cancelling while waiting, changed profiles/channels, regulatory refusal, cleanup
retry exclusion, sleep inhibition, and a profile change immediately before activation.

GNOME Shell 51 loaded the actual extension on a headless software-rendered display,
then disabled and re-enabled it without an extension error. Metadata now advertises
51 support. `bash tools/check_gnome_shell.sh` repeats this check on a private bus
and disposable configuration directories. It does not certify full physical-display
interaction or another physical Wi-Fi driver.

Ten new Android DNS queries were compared with direct gateway and upstream-resolver
queries for the same unique names. All ten returned matching result codes. Seven
were NOERROR with no answers and one authority record; three were NXDOMAIN. Both
HTTPS endpoints still returned 200 with verified TLS 1.3, and the invalid-hostname
endpoint failed at the TLS handshake. The evidence locates the earlier apparent
DNS anomaly upstream rather than in Relay startup or forwarding. The strict probe
still reports failure when its assumed NXDOMAIN result is absent; these results
must be interpreted with the upstream comparison, not silently relabelled.
[RFC 2308 section 2.2](https://www.rfc-editor.org/rfc/rfc2308.html#section-2.2)
describes NOERROR negative responses (NODATA); authority record count alone does not
establish the record type or the upstream resolver's reason for responding this way.

The installed nm5 combined hardware sequence passed upstream disconnect/reconnect,
complete removal of the old session, Stop while waiting, and NetworkManager restart
with automatic recovery. An isolated restart also passed. Earlier combined trials
lost intent while desktop controls still ran older code; restarting those clients
preceded the passing combined run. The cancellation source was not conclusively
identified, so this remains a compatibility observation requiring further repeated
upgrade testing rather than a claimed proven root-cause fix.

Logind/systemd suspend with the RTC alarm and NVIDIA hooks also passed: the system
returned from the documented suspend operation, sharing recovered automatically,
and the original upstream profile remained selected. Elapsed boot time through
recovery was 55.7 seconds. The hotspot was left active with Wi-Fi-only egress; the
Android client's original network was restored and its temporary probes removed.
The new validation evidence is in
[the nm5 evidence record](evidence/nm5-validation-2026-10-07.json).

The final nm5 package was reinstalled after the host restarted. Its daemon,
GNOME extension, and tray match the final source byte for byte. A fresh 170-test
Python run, 16 sanitizer applet cases, GNOME 51 smoke test, and installed NetworkManager
menu Start/Stop cycle passed. Sharing was left active with recovery armed.
