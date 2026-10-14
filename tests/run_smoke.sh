#!/bin/sh
# Run each GTK version in its own process with private buses and preferences.
set -eu
cd "$(dirname "$0")/.."
PYTHON=${PYTHON:-python3}
for command in "$PYTHON" dbus-run-session timeout; do
    command -v "$command" >/dev/null || { echo "Missing smoke-test dependency: $command" >&2; exit 1; }
done
if command -v xvfb-run >/dev/null; then
    display_mode=xvfb
elif [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    display_mode=session
else
    echo 'Smoke tests need xvfb-run or a graphical display.' >&2
    exit 1
fi
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT HUP INT TERM
export HOME="$fixture/home" XDG_CONFIG_HOME="$fixture/config"
export XDG_CACHE_HOME="$fixture/cache" XDG_DATA_HOME="$fixture/data"
# Preserve access to an existing Wayland socket while isolating runtime files.
if [ "$display_mode" = session ] && [ -n "${WAYLAND_DISPLAY:-}" ]; then
    case "$WAYLAND_DISPLAY" in
        /*) ;;
        *) export WAYLAND_DISPLAY="${XDG_RUNTIME_DIR:?}/$WAYLAND_DISPLAY" ;;
    esac
fi
export XDG_RUNTIME_DIR="$fixture/runtime"
mkdir -m 700 "$XDG_RUNTIME_DIR"
export GTK_A11Y=none PYTHONOPTIMIZE=0 GIO_USE_VFS=local
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME"
for script in check_settings_window.py check_settings_service.py check_desktop_tray.py check_tray_startup.py; do
    echo "Running $script ($display_mode display)"
    # Mapping the system bus to the private session bus prevents host activation.
    if [ "$display_mode" = xvfb ]; then
        timeout --kill-after=5s 60s dbus-run-session -- sh -c \
            'export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; exec xvfb-run -a "$1" "$2"' \
            sh "$PYTHON" "tests/$script"
    else
        timeout --kill-after=5s 60s dbus-run-session -- sh -c \
            'export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; exec "$1" "$2"' \
            sh "$PYTHON" "tests/$script"
    fi
done
