"""Per-user visibility of the separate desktop tray icon."""
import json
import os
from pathlib import Path


def preference_path():
    config_dir = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return config_dir / 'wifi-hotspot' / 'tray.json'


def get_tray_visible(path=None):
    try:
        return json.loads((path or preference_path()).read_text()).get('visible', True) is not False
    except (OSError, ValueError, AttributeError):
        return True
