ARG BASE_IMAGE=ubuntu:26.10
FROM ${BASE_IMAGE}
ARG APT_MIRROR=
ENV DEBIAN_FRONTEND=noninteractive container=docker
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod 755 /usr/sbin/policy-rc.d && \
    if [ -n "$APT_MIRROR" ]; then sed -i -E "s#https?://(archive|security).ubuntu.com/ubuntu/?#${APT_MIRROR%/}/#g" /etc/apt/sources.list.d/ubuntu.sources; fi && \
    printf 'Acquire::Retries "2";\nAcquire::http::Timeout "30";\n' > /etc/apt/apt.conf.d/80-relay-test && \
    apt-get update --error-on=any && apt-get install -y --no-install-recommends \
    systemd-sysv dbus-user-session libpam-systemd gnome-session gnome-shell gnome-settings-daemon \
    lightdm lightdm-gtk-greeter xvfb xauth x11-utils xdotool accountsservice locales \
    xfce4-session xfce4-panel xfdesktop4 xfwm4 fonts-dejavu-core python3-gi
COPY candidate.deb /tmp/candidate.deb
RUN apt-get install -y --no-install-recommends /tmp/candidate.deb && \
    useradd --create-home --shell /bin/bash relaytest && passwd -d relaytest && \
    locale-gen en_US.UTF-8 && rm /usr/sbin/policy-rc.d && \
    systemctl set-default multi-user.target && systemctl mask lightdm.service && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
ENV LANG=en_US.UTF-8
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
