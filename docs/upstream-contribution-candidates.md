# Candidate fixes for the original hotspot project

These are investigation candidates, not submitted patches. The original project
is [erhanzeyrek/gnome-wifi-hotspot](https://github.com/erhanzeyrek/gnome-wifi-hotspot).
Use the selective contribution process in [fork maintenance](fork-maintenance.md).
The reviewed upstream baseline is `408b2d1620629d57ecf356ca40632c7da969e6fc`.

Fork commits listed here locate existing implementations. They also contain
other changes, so do not cherry-pick them wholesale into an upstream PR. Adapt
one fix on a branch based on upstream, confirm its applicability there, and
include a minimal reproducer and regression check independent of fork-only code.

| Priority | Candidate | Fork reference and checks | Work before an upstream proposal |
| :--- | :--- | :--- | :--- |
| 1 | Fail-closed authorization for privileged D-Bus methods, including credential reads | `f1cc9a4`, daemon authorization and `tests/test_daemon_security.py` | Compare upstream's method dispatch/Polkit contract; isolate sender validation, denied/unavailable authorization and public status behavior without changing its UI or backend |
| 2 | Private privileged startup logs and refusal of unsafe runtime paths | `6f4f518`, `prepare_startup_log()` and startup-log regressions in `tests/test_daemon_security.py` | Adapt path ownership, mode and safe-open behavior to upstream's install/runtime paths; include unsafe-path and existing-file regressions |
| 3 | Stop only owned create_ap processes; protect unrelated networking during cleanup | `f1cc9a4`, `2dc84e9`, daemon ownership checks and `tests/test_legacy_runtime.py` | Reproduce the upstream cleanup behavior; adapt process identity/runtime ownership without introducing the experimental NetworkManager controller |
| 4 | Restrict return forwarding rules to the hotspot network/interface | `f1cc9a4`, `daemon/create_ap` and `tests/test_nat_rules.py` | Locate the original rule provenance and intended topology; show matching add/remove rules and upstream-compatible routing tests |

These priorities order review effort; they do not establish an unverified
vulnerability or affected-version claim. Check the original implementation and
installation assumptions before contacting maintainers. The daemon's broader
asynchronous settings transport, new backend, split packaging and cross-desktop
features are larger design work and are not bundled into these initial fixes.

For each prepared patch, record the upstream base and head commits, issue
reproducer, files changed, license/attribution, checks run on upstream, limitations,
and a concise maintainer-facing explanation. A validated backport can be kept
locally until submission is authorized. No upstream issue, PR, or maintainer
message has been created as part of this inventory.
