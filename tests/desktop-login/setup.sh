#!/bin/bash
set -euo pipefail
mkdir -p /etc/lightdm/lightdm.conf.d /etc/systemd/user/org.gnome.Shell@.service.d /results
# Virtual displays have no kernel VT or physical seat. Keep PAM/logind session
# registration, while clearing LightDM's physical-VT hints before pam_systemd.
cat > /etc/security/relay-virtual-display.env <<'PAMENV'
XDG_VTNR OVERRIDE=0
XDG_SEAT OVERRIDE=""
PAMENV
sed -i '/pam_systemd.so/i session required pam_env.so conffile=/etc/security/relay-virtual-display.env' /etc/pam.d/common-session
cat > /etc/lightdm/lightdm.conf.d/90-relay-test.conf <<'CONF'
[LightDM]
logind-check-graphical=false
[Seat:*]
xserver-command=/usr/local/bin/relay-xvfb -screen 0 1280x800x24 -nolisten tcp
xserver-allow-tcp=false
autologin-user=relaytest
autologin-user-timeout=0
autologin-session=relay-gnome
user-session=relay-gnome
greeter-session=lightdm-gtk-greeter
allow-guest=false
CONF
cat > /usr/local/bin/relay-xvfb <<'XVFB'
#!/usr/bin/python3
import os,re,sys
args=[a for a in sys.argv[1:] if not re.fullmatch(r'vt[0-9]+',a) and a not in ('-novtswitch','-sharevts')]
os.execv('/usr/bin/Xvfb',['Xvfb']+args)
XVFB
chmod 755 /usr/local/bin/relay-xvfb
cat > /usr/local/bin/relay-gnome-session <<'SESSION'
#!/bin/sh
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=GNOME
export LIBGL_ALWAYS_SOFTWARE=1
exec /usr/bin/gnome-session --session=gnome
SESSION
chmod 755 /usr/local/bin/relay-gnome-session
cat > /usr/share/xsessions/relay-gnome.desktop <<'DESKTOP'
[Desktop Entry]
Name=Relay GNOME virtual display test
Exec=/usr/local/bin/relay-gnome-session
Type=Application
DesktopNames=GNOME;
DESKTOP
cat > /etc/systemd/user/org.gnome.Shell@.service.d/virtual-display.conf <<'UNIT'
[Service]
ExecStart=
ExecStart=/usr/bin/gnome-shell --headless --virtual-monitor 1280x800 --wayland --no-x11 --mode=%i
Environment=LIBGL_ALWAYS_SOFTWARE=1
OOMScoreAdjust=0
UNIT
systemctl unmask lightdm.service
systemctl daemon-reload
systemctl reset-failed lightdm.service || true
systemctl start lightdm.service
