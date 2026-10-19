# Wi-Fi Relay revision 31: community announcement and PPA assessment

Assessment updated: 19 October 2026; originally assessed on 7 October 2026.
Status: revision 31 is the GitHub release baseline; a community announcement and PPA
upload remain pending decisions.

## Recommendation

Use [revision 1.0.0-31](releases/1.0.0-31.md) for a community call
for testers. The recommended download is the all-in-one `bundle.deb`; matching
separate packages remain available. Ubuntu 26.10 is the validated distribution,
create_ap is the stable default, and native NetworkManager AP+STA and downstream
integration patches remain experimental. State the hardware and desktop limits
alongside the completed checks.

Recommended sequence:

1. Agree the audience, feedback channel, target Ubuntu versions, and maintenance
   commitment.
2. If approved, announce revision 31 with release, user-guide, and rollback links.
3. Use the existing source packaging to prepare signed uploads and validate a
   testing PPA.
4. Keep replacement NetworkManager and desktop packages separately opt-in.

No forum post or PPA upload is authorized by this document.

## Revision-31 evidence supporting a testing announcement

- 383 Python tests, Node tray checks, service integration, real GTK widgets,
  extracted-package checks, sanitized applet and isolated GNOME Shell checks.
- Debian source/binary builds and disposable-container package lifecycle checks,
  including split/bundle transitions, secure defaults and credential preservation.
- Two Android 14 clients on one Intel/iwlwifi AP driver: physical and virtual AP
  traffic, verified HTTPS, invalid-TLS rejection, six startup cancellation timings
  and shell-crash cleanup on the `~fix7` candidate. Final runtime payloads match
  that candidate; final packaging checks identify the release source separately.
- A separate installed `~fix7` cohort verified 2.4 GHz channel 12 with both
  clients and Ethernet egress. One administrator session covered installation,
  retries and audit; device power settings and temporary helpers were restored.

See [release scope and rollback](releases/1.0.0-31.md),
[development trial](releases/1.0.0-31-development.md),
[physical fault evidence](evidence/physical-wifi-daemon-fixes-2026-10-19.json),
[installed 2.4 GHz evidence](evidence/physical-installed-2.4ghz-2026-10-19.json),
and the release's `VALIDATION.json` and `SHA256SUMS`.

## Historical revision-30 evidence

The following results retain their original revision-30 build and environment;
they are not new revision-31 tests.

- Candidate validation ran 344 Python tests with one bench-dependent skip;
  tray, real GTK widgets, service integration, 17 sanitized applet cases, and
  isolated GNOME Shell checks passed.
- Disposable Ubuntu 26.10 package lifecycle checks covered legacy and split
  upgrades, split-to-bundle replacement, bundle upgrade, switching back to
  separate packages, removal, purge, and fresh installation. Credentials survived
  upgrades and layout switches; fresh installs generated secure defaults.
- USB-controlled testing completed four DHCP/DNS/HTTPS and cleanup cycles on one
  Android 15 phone and Intel CNVi/iwlwifi adapter with stock NetworkManager.
  Invalid TLS was rejected. An earlier connection timeout and upstream
  negative-DNS variation remain recorded.
- Six distinct LightDM PAM/logind sessions in a software-rendered container
  verified startup enabled, disabled, and re-enabled on GNOME 51 and XFCE 4.20,
  with the expected extension/tray selection and no duplicate tray controls.
- The release records matching candidate runtime files; final changes promote
  version metadata and release documentation. Downloads include the bundle,
  separate packages, Debian source artifacts, checksums, and validation provenance.

The [revision-30 source CI](https://github.com/3togo/gnome-wifi-hotspot/actions/runs/38684574384)
passed on 15 October 2026.

Detailed local references:
[candidate validation record](releases/1.0.0-30-rc1.md),
[USB traffic evidence](evidence/physical-usb-1.0.0-30-rc1.json),
[container desktop-login evidence](evidence/desktop-login-container-1.0.0-30-rc1.json), and
[user guide](user-guide.md).

## Limits to disclose

Revision-31 physical traffic used two Android 14 clients and one AP driver on a
host with downstream NetworkManager `1.58.1-1ubuntu3+relay1+dev3`; stock networking
is exercised in automated Ubuntu 26.10 CI, not this physical cohort. Strict
NXDOMAIN failures and same-query upstream NOERROR/NODATA comparisons remain
separate. Channel 12 requires compatible clients and local regulatory permission.

The ten-cycle matrix, other AP drivers and client OS families, natural roaming,
multi-adapter failover, reboot/suspend fault trials, native-backend physical
recovery and extended soaks remain incomplete. Administrator fault injection
does not establish physical desktop-user authorization. Host GDM, physical
seats, hardware graphics, RPM installation and other distributions need coverage.

Earlier desktop-login, recovery, transfer and suspend results apply to their
recorded builds; they do not fill gaps in the current matrix. Keep native
NetworkManager and integration patches experimental. GitHub distribution does
not establish Ubuntu endorsement, an upstream merge, or signed APT delivery.

## Historical Beta-2 evidence, 7 October 2026

The original assessment recorded 170 Python tests, Node state checks, and 16
applet cases under address and undefined-behavior sanitizers; Ubuntu 26.10 CI and
an isolated Beta-1 upgrade passed with configuration preserved and `dpkg --audit`
clean. Its live checks covered upstream loss/reconnection, Stop while waiting,
NetworkManager restart, suspend/resume, installed-menu Start/Stop, Android
certificate/hostname verification, and gateway/upstream DNS comparisons.
The [original CI run](https://github.com/3togo/gnome-wifi-hotspot/actions/runs/37675244790),
[live validation report](networkmanager-live-validation.md), and
[sanitized evidence](evidence/nm5-validation-2026-10-07.json) retain that scope.

Earlier combined upgrade/restart trials lost sharing intent. A later combined run
passed after desktop controls were restarted, but the cancellation source was not
conclusively identified. This remains a historical compatibility observation,
not a proven root-cause fix or a revision-30 recovery result. Beta 2 was marked
Latest at the time; revision 31 now supersedes that distribution baseline.

## Community announcement

Suggested venue: Ubuntu Discourse's
[Project Discussion category](https://discourse.ubuntu.com/c/project/307).
Confirm the category's posting guidance before submitting.

Frame the post as an introduction and call for testers. Include:

- The purpose: concurrent Wi-Fi hotspot sharing through supported adapters.
- Revision-31 bundle and separate downloads, the user guide, and setup/rollback
  instructions.
- The distinction between Relay's GNOME extension, standalone desktop tray,
  optional XFCE applet patch, and experimental NetworkManager backend.
- Tested Ubuntu version, desktop, hardware scope, and known limitations.
- Requested feedback: adapter/driver, Ubuntu version, desktop, backend, observed
  behavior, and relevant diagnostic output without passwords.

Use the existing GitHub downloads initially. A PPA is not a prerequisite for a
community testing announcement.

## PPA preparation: completed work

- `packaging/build-source.py` generates unsigned Debian quilt source artifacts
  with declared build dependencies; `--binary` also builds packages and runs
  package build tests. Revision-31 source artifacts accompany the release.
- Source and direct binary builds share payload templates for the standalone app,
  GNOME controls, tray controls, and all-in-one bundle. Source exports rebuild
  without Git metadata; archive timestamp normalization and reproducibility
  checks are documented in [production readiness](production-readiness.md).
- GNOME Shell is optional for the standalone app and bundle. The separate layout
  keeps GTK3/AppIndicator dependencies in the tray package; the bundle includes
  those dependencies for its tray controls.
- Debian copyright metadata records the application and bundled components,
  including Nayuki and both create_ap notices; retained notices accompany the source.
- Ubuntu 26.10 CI covers source/binary builds and disposable package lifecycle
  checks. This is not a Launchpad build result.

## Remaining PPA preparation

Before uploading:

- Choose supported Ubuntu target series, use suitable changelog distributions
  and PPA versioning, and validate build/install behavior for each claimed series.
  Current source packaging targets Stonking; other series need explicit review.
- Confirm the Launchpad account/PPA and upload-signing key, review maintainer
  and source metadata for the intended uploader, then produce signed source uploads.
- Confirm Launchpad builds, installation, upgrade, removal, and rollback before
  distributing the PPA installation command.

Start with a clearly identified testing PPA for Relay. Treat the downstream
NetworkManager Applet replacements as a separate opt-in distribution decision:
they replace Ubuntu packages and need ongoing rebasing and testing when the
distribution updates them. The [dependency review](dependency-review.md) records
the reduced custom package set and version constraints; a custom connection
editor is no longer required for the reviewed applet version.

Primary references:

- [Launchpad PPA requirements](https://ubuntu.com/docs/launchpad/user/reference/packaging/ppas/ppa/)
- [Building a source package](https://ubuntu.com/docs/launchpad/user/reference/packaging/ppas/building-a-source-package/)
- [Ubuntu PPA upload guide](https://ubuntu.com/project/docs/contributors/new-package/upload-packages-to-a-ppa/)

## Decisions for the next review

- Announce for testing now, or gather more hardware/GNOME feedback first?
- Which Ubuntu series and architectures should the initial PPA support?
- Who will maintain uploads, respond to reports, and handle dependency updates?
- Keep patched applet distribution limited to separate GitHub downloads, or plan
  a separately opt-in testing archive?

Until these decisions are made, retain the current GitHub revision-31 distribution
and leave the community announcement and PPA unpublished.
