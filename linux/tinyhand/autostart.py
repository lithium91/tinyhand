"""Open at login via an XDG autostart entry."""
import os
from pathlib import Path

from .hotkeys import launcher_command

DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart"
FILE = DIR / "tinyhand.desktop"


def enabled():
    try:
        text = FILE.read_text()
    except OSError:
        return False
    return "Hidden=true" not in text and "X-GNOME-Autostart-enabled=false" not in text


def set_enabled(on):
    if not on:
        try:
            FILE.unlink()
        except OSError:
            pass
        return
    DIR.mkdir(parents=True, exist_ok=True)
    FILE.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=TinyHand\n"
        "Comment=A tiny hand on a stick that points at things on your screen\n"
        f"Exec={launcher_command('--background')}\n"
        "Icon=tinyhand\n"
        "X-GNOME-Autostart-enabled=true\n"
        "NoDisplay=true\n"
    )


def installed():
    """True when running from a system install rather than the source tree."""
    here = Path(__file__).resolve()
    return str(here).startswith(("/usr/", "/opt/"))
