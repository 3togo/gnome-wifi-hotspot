# Wi-Fi Relay fork maintenance

Wi-Fi Relay is maintained in [3togo/gnome-wifi-hotspot](https://github.com/3togo/gnome-wifi-hotspot)
as a derivative of [Erhan Zeyrek's GNOME Wi-Fi Hotspot](https://github.com/erhanzeyrek/gnome-wifi-hotspot).
The original MIT notice remains in [LICENSE](../LICENSE). Bundled components
retain their own notices in [Debian copyright](../packaging/debian/copyright).
The fork relationship and shared history are intentional. An ahead/behind
count describes ancestry; it does not establish compatibility or release quality.

## Supported scope

The published baseline is [Debian revision 1.0.0-22](releases/1.0.0-22.md) for
Ubuntu 26.10. Its default backend is create_ap. Standalone settings are separate
from optional GNOME Shell and StatusNotifier/AppIndicator controls. XFCE and
headless GNOME Shell 51 have recorded checks; declared Shell compatibility
does not mean every interactive desktop or wireless driver has been validated.

Native NetworkManager AP+STA and patches under `integration/` remain experimental.
Stable downloads use the installed distribution networking components and do
not require replacing NetworkManager, GNOME Settings, or nm-applet. Expanding
platform, driver, or backend support requires evidence for that combination.

## Identity and installation compatibility

The current fork is an upgrade/replacement of the original installation, not a
coinstallable second hotspot controller. Existing Debian package names, service
names, configuration paths, D-Bus names, and Polkit actions are retained for
upgrade compatibility. Do not run separately installed upstream and fork daemons
against the same configuration or D-Bus service. A manually installed upstream
copy must be accounted for when moving to Debian packages.

A future repository rename is independent of runtime compatibility. Changing
application or service identifiers requires a planned migration of credentials,
preferences, desktop autostart, extension identifiers, and authorization policy,
with upgrade and rollback tests. Do not make that change merely to remove a
GitHub fork banner. Preserve attribution and old source tags throughout a migration.

## Review upstream changes selectively

Use `origin` for this fork and a fetch-only `upstream` remote for the original
project. The local upstream URL is
`https://github.com/erhanzeyrek/gnome-wifi-hotspot.git`. On 10 October 2026 the
reviewed upstream `main` was `408b2d1620629d57ecf356ca40632c7da969e6fc`.
This is a recorded baseline, not a promise that upstream will remain unchanged.

Configure a checkout once if it does not already have an upstream remote:

```bash
git remote add upstream https://github.com/erhanzeyrek/gnome-wifi-hotspot.git
git remote set-url --push upstream disabled://upstream
```

The disabled push URL prevents accidental pushes to the original repository;
prepared contribution branches are published through the contributor's fork.

For a review, with a clean worktree or isolated checkout:

```bash
git fetch upstream
git rev-list --left-right --count main...upstream/main
git log --oneline main..upstream/main
git diff main...upstream/main
```

The count prints fork-only commits first and upstream-only commits second.
Review upstream changes when preparing a release or investigating a relevant
fix; no automatic merge or background watcher is configured. Classify each
change as applicable, already addressed, or incompatible with the fork's scope.
Record the upstream commit, decision, affected behavior, and validation result
in the adopting PR. Never reset fork `main` to upstream or bulk-sync to reduce
the ahead count. For a suitable independent change, use `git cherry-pick -x`
on a task branch and run the affected checks before merging.

Use descriptive branches such as `docs/`, `fix/`, `gui/`, `feature/`, or `pr/`.
Keep `main` releasable, merge focused PRs after their checks pass, and preserve
unrelated workspace files. Remote configuration is local to each checkout;
contributors must configure their own upstream remote.

## Contributions back to the original project

Start with small fixes that also make sense on the upstream implementation.
The [candidate inventory](upstream-contribution-candidates.md) identifies source
areas and regressions to adapt. It is not a list of submitted or accepted patches.
Use a branch based on current `upstream/main`, adapt only the necessary changes,
and demonstrate a reproducer and passing checks on that upstream baseline.
Do not submit the fork's entire main branch as one PR.

Retain original copyright notices. Changes for NetworkManager, nm-applet, or
GNOME Settings are separate contributions with their own guidelines and license
requirements; they are not contributions to the original hotspot repository.
Prepare a concrete patch and validation before contacting maintainers. Upstream
submission is a separate action from publishing a release in this fork.

## Releases and validation

Published tags and release assets are immutable baselines. A newer binary gets
a newer Debian revision; install the main and selected optional packages at the
same version. Main may contain prospective maintenance documentation without
changing the source or assets attached to an existing tag. Use an explicit new
release tag and mark the intended stable release as GitHub Latest.

Documentation changes need link and content checks. Runtime and packaging
changes need the relevant unit, widget, source-export, package, and CI lifecycle
checks described in [production readiness](production-readiness.md). Networking
lifecycle changes also need affected physical-device checks from the
[hardware checklist](release-hardware-validation.md). Headless or mocked checks
cannot substitute for physical driver and client evidence.

Record every pass, failure, blocked case, and untested scenario for the exact
build. Block a release on a demonstrated regression in supported behavior.
Keep untested combinations and experimental backends explicitly limited; do
not extend compatibility claims from historical evidence. Promoting the native
backend requires its separate hardware matrix, recovery, cancellation, and soak
results, followed by a deliberate support-scope decision.

Before publication, verify the tag's source tree matches the tested build and
upload matching packages, source artifacts, checksums, and provenance. Re-download
assets and check their hashes. Do not overwrite historical evidence with results
from a different build. Package lifecycle tests run in disposable CI; local
Ubuntu builds do not require Docker.
