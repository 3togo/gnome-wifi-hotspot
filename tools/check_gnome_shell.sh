#!/bin/bash
# Smoke-test the extension on a private session bus and headless GNOME display.
# The desktop's extension preferences and system network are not modified.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
relay_test_root=$(mktemp -d)
trap 'rm -rf -- "$relay_test_root"' EXIT
export XDG_CONFIG_HOME="$relay_test_root/config" XDG_DATA_HOME="$relay_test_root/data"
export XDG_CACHE_HOME="$relay_test_root/cache" XDG_RUNTIME_DIR="$relay_test_root/runtime"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME/gnome-shell/extensions/wifi-relay@3togo.github.io" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
cp -R "$repo_dir/extension/." "$XDG_DATA_HOME/gnome-shell/extensions/wifi-relay@3togo.github.io/"
export RELAY_TEST_ROOT="$relay_test_root"
env -u LD_PRELOAD dbus-run-session -- bash -eu -c '
    export LIBGL_ALWAYS_SOFTWARE=1
    gsettings set org.gnome.shell enabled-extensions "[\"wifi-relay@3togo.github.io\"]"
    gsettings set org.gnome.shell welcome-dialog-last-shown-version "51"
    gnome-shell --headless --virtual-monitor 1280x720 --wayland --no-x11 > "$RELAY_TEST_ROOT/shell.log" 2>&1 &
    relay_shell_pid=$!
    trap "kill $relay_shell_pid 2>/dev/null || true; wait $relay_shell_pid 2>/dev/null || true" EXIT
    python3 - <<"PY"
import json, time
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
uuid = "wifi-relay@3togo.github.io"
def call(method):
    return bus.call_sync("org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell.Extensions",
                         method, GLib.Variant("(s)", (uuid,)), None, 0, 5000, None).unpack()[0]
def ready():
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        try:
            info = call("GetExtensionInfo")
            if info.get("error"):
                raise RuntimeError(info["error"])
            if info.get("enabled") and info.get("state") == 1:
                return
        except GLib.Error:
            pass
        time.sleep(1)
    raise RuntimeError("GNOME extension did not become active")
ready()
assert call("DisableExtension"), "Disable failed"
assert call("EnableExtension"), "Enable failed"
ready()
print(json.dumps({"headless_gnome": True, "extension_loaded": True,
                  "disable_enable_passed": True, "extension_error": ""}))
PY
' > "$relay_test_root/result.log" 2> "$relay_test_root/session.log" || {
    cat "$relay_test_root/shell.log" "$relay_test_root/session.log" >&2
    exit 1
}

# Activated session services may print their own messages; return the result line.
rg '^\{"headless_gnome"' "$relay_test_root/result.log"
