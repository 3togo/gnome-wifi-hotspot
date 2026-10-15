# Container desktop login validation

Run `make test-desktop-login` with working Docker access. Download sources use
the same country detection and overrides as the package lifecycle suite:

```sh
WIFI_RELAY_COUNTRY=CN make test-desktop-login
```

The runner builds the current bundle, installs it in a desktop image, and starts
systemd and LightDM inside a disposable container. A disposable unprivileged
account logs in through LightDM's PAM autologin service. Six distinct logind
sessions exercise enabled, disabled and re-enabled startup on GNOME and XFCE.
Only the installed preference API prepares the next startup choice; the probe
does not launch Relay controls or enable the extension itself.

GNOME must enable the extension through its packaged XDG autostart entry and
create its first-login marker, without starting the tray. XFCE must register one
tray with the panel when enabled and start none when disabled. Each login is
followed by display-manager shutdown and termination of that test user's session
and user manager before the next login.

Results and logs are saved under `dist/desktop-login/`. Override that directory
with `WIFI_RELAY_DESKTOP_OUTPUT`, or the built image tag with
`WIFI_RELAY_DESKTOP_IMAGE`. The container is removed after results are collected;
the image is retained to make subsequent builds faster.

## Virtual display scope

Xvfb supplies LightDM's virtual X display. GNOME uses its headless Wayland
compositor with software rendering. LightDM's physical-VT arguments are removed
from the Xvfb command, and its physical-seat/VT hints are cleared before
`pam_systemd`; PAM authentication and real logind session registration remain.
Consequently logind describes GNOME's LightDM session as X11 while GNOME itself
runs its headless Wayland compositor. These adaptations are test infrastructure,
not changes to the installed application or extension.

The container uses its private cgroup namespace and additional capabilities for
systemd. No host filesystem, display, device, cgroup tree or Docker socket is
mounted into it. This suite establishes containerized display-manager startup;
it does not establish hardware graphics, a host GDM login, password-prompt
interaction, or Wi-Fi client traffic. Physical traffic has separate evidence.
