"""Per-user preference for starting the tray extension at desktop login."""
import json
import os
from pathlib import Path

UUID = "wifi-relay@3togo.github.io"
LEGACY_UUID = "wifi-hotspot@erhanzeyrek"


def migrate_extension(settings, sync):
    """Carry forward enabled/disabled choices without re-enabling a disabled tray."""
    changed = False
    for key in ("enabled-extensions", "disabled-extensions"):
        current = settings.get_strv(key)
        if LEGACY_UUID not in current:
            continue
        updated = []
        for uuid in current:
            uuid = UUID if uuid == LEGACY_UUID else uuid
            if uuid not in updated:
                updated.append(uuid)
        if not settings.set_strv(key, updated):
            raise RuntimeError("GNOME extension settings are not writable")
        changed = True
    if changed:
        sync()


def preference_path():
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_dir / "wifi-hotspot" / "startup.json"


def get_auto_start(path=None):
    path = path or preference_path()
    try:
        return json.loads(path.read_text()).get("auto_start", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def is_gnome():
    return "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":")


def launch_tray():
    from gi.repository import Gio
    Gio.Subprocess.new(["/usr/bin/python3", str(Path(__file__).resolve().parent / "tray.py")],
                       Gio.SubprocessFlags.NONE)


def set_auto_start(enabled, settings, sync, path=None):
    path = path or preference_path()
    if settings is not None:
        current = settings.get_strv("enabled-extensions")
        updated = [uuid for uuid in current if uuid not in {UUID, LEGACY_UUID}]
        if enabled:
            updated.append(UUID)
            disabled = settings.get_strv("disabled-extensions")
            if any(uuid in disabled for uuid in (UUID, LEGACY_UUID)) and not settings.set_strv(
                    "disabled-extensions", [uuid for uuid in disabled if uuid not in {UUID, LEGACY_UUID}]):
                raise RuntimeError("GNOME extension settings are not writable")
        if updated != current and not settings.set_strv("enabled-extensions", updated):
            raise RuntimeError("GNOME extension settings are not writable")
        sync()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"auto_start": bool(enabled)}) + "\n")
