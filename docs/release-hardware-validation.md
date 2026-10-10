# Hardware validation for the next release

This is a procedure and blank evidence checklist, not completed validation.
The latest published baseline is [revision 1.0.0-22](releases/1.0.0-22.md).
Earlier [hardware results](networkmanager-live-validation.md) describe their
recorded development builds; do not copy their passes into a new candidate.

## Candidate and test bench

Record the exact candidate before testing. If runtime code or installed package
contents change, repeat affected cases and record the new hashes. A successful
test of a worktree does not certify a differently built release binary.

| Field | Value to record |
| :--- | :--- |
| Candidate | App version, Debian revision, Git commit/tree, package SHA-256 hashes |
| Platform | Distribution/version, kernel, NetworkManager and supplicant versions |
| Desktop | Desktop/version, X11 or Wayland, selected optional control package |
| Radio | Adapter chipset, driver/firmware, AP+STA combination and regulatory domain |
| Backend | create_ap or NetworkManager (experimental); never combine results |
| Upstream | Wi-Fi or wired egress, permitted band/channel, VPN state; redact SSIDs |
| Clients | Device/OS families and count; redact device identities |
| Timing | Date in UTC, duration, cycle counts, recovery/cleanup deadlines |
| Evidence | Sanitized logs, observations, case results, and artifact location |

Use a dedicated bench or an agreed maintenance window. Suspend, radio changes,
NetworkManager/daemon restarts, package removal, and injected crashes interrupt
connectivity. Arrange an independent way to restore the machine and client
network settings before those cases. Do not run destructive package lifecycle
tests on an everyday workstation. Back up credentials privately using the
[rollback procedure](releases/1.0.0-22.md).

Keep raw evidence in an ignored, owner-only local directory. Public reports must
exclude passwords, credential-bearing configuration, SSIDs, MAC addresses,
connection UUIDs, and identifying client details. Record chipset and software
versions, which are needed to understand driver coverage. Avoid capturing
unrelated traffic. Use the public controller through Settings/tray/GNOME menus;
do not bypass Polkit or kernel restrictions to obtain a pass.

## Coverage matrix

Run applicable cases for each claimed combination. Start with create_ap on the
currently exercised XFCE/driver combination, then add an interactive GNOME
session and a second physical driver family. A second adapter using the same
driver does not establish cross-driver coverage. Include X11 and Wayland where
those combinations are claimed. Other desktops remain unverified until tested.

Run the native NetworkManager backend as a separate experimental cohort on
adapters that pass preflight. A regulatory or hardware refusal must leave the
station and unrelated connections intact; it is not successful sharing coverage.
Stable-package controls must first be tested with stock desktop/network packages.
Any downstream integration patch gets a separate record of its exact versions.

Use these result labels: **Pass**, **Fail**, **Blocked**, **Not run**, or
**Not applicable**. Explain Blocked and Not applicable. Leave no ambiguous blank
results in a published report. All cases below initially have status **Not run**.

## Install and desktop lifecycle

| ID | Procedure | Required observation |
| :--- | :--- | :--- |
| D1 | Install matching candidate packages on a fresh test system | Fresh credentials are generated; no unsolicited sharing starts; optional controls match the selected desktop |
| D2 | Upgrade from revision 22 three times, returning to the previous packages using the documented rollback between trials | Credentials/preferences remain; versions match; active-session tray startup is verified; one tray process and one icon appear without checkbox toggling or nm-applet restart |
| D3 | Repeat D2 with a hidden icon and with startup disabled | Hidden icons stay hidden; disabled startup is not overridden; a manually opened tray is not forcibly replaced when startup is disabled |
| D4 | Log out/in and reboot, three cycles each | Desktop controls follow preferences; no duplicates; reboot clears the sharing request |
| D5 | Exercise About, Settings close, Start, Stop, and tray Quit | About is accurate; closing Settings leaves sharing running; Quit stops sharing before closing; GNOME extension lifecycle remains Shell-managed |
| D6 | Exercise denied/failed Stop and unavailable service on the bench | Controls report the error and remain available; they do not claim sharing stopped without acknowledgement |
| D7 | Remove/reinstall optional controls on a disposable test system | The standalone service/settings remain available; reinstall respects preferences; removed controls do not keep running |

Document how each version was installed and whether old desktop processes were
present. Store timing and user-service journal evidence for D2, including whether
the first startup attempt failed and a retry was needed. User service restarts
refresh controls; they do not themselves stop or start hotspot broadcasting.

## Client connectivity and cleanup

| ID | Procedure | Required observation |
| :--- | :--- | :--- |
| N1 | Start from each supported upstream path and connect one real client | Station association remains when AP+STA is claimed; client obtains a valid DHCP lease, gateway and DNS configuration |
| N2 | Perform a fresh DNS query and verified HTTPS request from the client | Requests use hotspot Wi-Fi, not cellular or another saved network; DNS outcomes agree with the upstream resolver; TLS verification remains enabled |
| N3 | Where a suitable TLS probe is available, exercise an invalid certificate/hostname endpoint | The TLS check rejects it; no certificate validation bypass is introduced |
| N4 | Repeat Start/Stop ten times, including client disconnect/reconnect | Status converges; Relay-owned interfaces, profiles, DHCP processes, workers and firewall rules are cleaned up; unrelated resources remain |
| N5 | Remove and restore the upstream connection, then change its band/channel on the bench | State reflects the actual backend behavior; a permitted session can be restored; station selection and unrelated profiles are preserved; unsupported channels are refused |
| N6 | Reboot or restart the daemon during a controlled active session | No sharing request survives the daemon restart; owned state is recovered/cleaned up; an explicit new Start works |
| N7 | Inject a backend worker failure and unavailable networking service in a controlled trial | Failure is reported; only owned resources are cleaned up; unrelated networking and security policy remain intact |
| N8 | Run with the deployment firewall/AppArmor policy enforced | DHCP/DNS/HTTPS succeed where intended; denials are investigated without disabling enforcement or globally relaxing rules |

For N2, wait for DHCP completion and check the client's egress route. If the
host has multiple uplinks, record which default route carries traffic. Explicitly
test Wi-Fi-only egress for a Wi-Fi relay claim. VPN traversal requires its own
case; ordinary internet access does not establish it. DNS NODATA and NXDOMAIN
are different outcomes; compare upstream results rather than assuming a random
name must return NXDOMAIN. The [Android probe guide](../tools/android/README.md)
describes an existing option for client-path evidence.

For create_ap, do not assume automatic recovery after upstream loss; record what
happens and confirm explicit Stop/Start restores a valid session. For the native
backend, use the recovery contract below. Set and record a bounded cleanup and
recovery deadline before each fault trial; a timeout is a failure or blocked
investigation, never an unbounded wait relabelled as a pass.

## Native NetworkManager recovery and cancellation

These cases apply only to the experimental backend. Repeat each applicable
case five times on each physical driver cohort; use permitted channels.

| ID | Procedure | Required observation |
| :--- | :--- | :--- |
| R1 | Temporarily lose and restore the original upstream Wi-Fi connection | The request remains pending, old resources are cleaned up, and sharing recovers after association is stable and preflight permits it |
| R2 | Press Stop while waiting and while connecting | Pending recovery is cancelled; restoring upstream does not restart sharing |
| R3 | Switch to another saved upstream profile or an unsupported channel | Relay does not silently use the new profile; status explains refusal/waiting; a new explicit request is needed where required |
| R4 | Turn Wi-Fi radio off/on, and separately change Relay configuration while waiting | Recovery is cancelled; radio-on or restoring upstream alone does not request sharing |
| R5 | Restart NetworkManager on the bench | Recovery uses the original requested profile when available; cleanup retries settle; no unrelated profiles/interfaces are removed |
| R6 | Suspend/resume using the machine's normal systemd/logind path | Station and a permitted requested hotspot recover within the declared deadline; driver hooks run; cancellation during the recovery window remains effective |

Recovery intent does not persist across Relay daemon restart or reboot. A passing
R5 or R6 must not be described as seamless roaming or support for arbitrary
channels. Use the documented machine suspend path; a driver-rejected bypass of
platform hooks is not evidence that the supported path failed or passed.

## Multiple clients and extended operation

For a new driver or promoted backend, run at least two clients from different
OS families for eight hours with periodic fresh DNS and verified HTTPS requests.
Include sustained bidirectional transfer, one client's disconnect/rejoin, and
one upstream interruption. Record traffic totals, latency/error observations,
resource usage at the beginning and end, recovery times, and stale client entries.
Record thermal or driver resets and investigate unexplained growth or loss.
A longer 24-hour run can add evidence; it does not replace coverage on another
driver or desktop. Set performance acceptance thresholds for the bench before
testing, rather than inventing a throughput claim from one favorable result.

## Result record and release decision

Copy this record per case/cohort into a candidate-specific report:

```text
Candidate version / commit / package hashes:
Desktop / backend / adapter-driver cohort:
Case ID and status (Pass / Fail / Blocked / Not run / Not applicable):
Start/end UTC and cycle count or duration:
Preconditions and declared deadlines/acceptance thresholds:
Steps performed:
Expected behavior and actual observation:
Sanitized evidence location:
Resources/preferences restored and remaining issues:
Issue or follow-up reference:
```

A reproduced regression in supported behavior blocks publication until fixed
and rechecked. State untested cases and unsupported combinations in release
notes; do not turn Blocked into Pass. Documentation-only changes do not require
another radio soak. Promote the experimental backend only after its matrix,
client path, recovery/cancellation, cleanup, enforcement and extended-operation
evidence is reviewed. Keep that decision separate from a stable create_ap update.

This checklist supplements [automated production checks](production-readiness.md)
and [release maintenance](fork-maintenance.md); none of the new physical cases
are claimed as completed by adding this document.
