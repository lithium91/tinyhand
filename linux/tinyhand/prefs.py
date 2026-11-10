"""User settings, kept as JSON in ~/.config/tinyhand/settings.json."""
import json
import os
from pathlib import Path

from . import styles

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "tinyhand"
FILE = CONFIG_DIR / "settings.json"

DEFAULTS = {
    "shortcut.toggle": "<Control><Alt>h",
    "shortcut.clear": "<Control><Alt>x",
    "pointerSize": 0.13,
    "showShadow": True,
    "fadeSeconds": 3.0,
    "sound.hands": True,
    "sound.laser": False,
    "tapSound": "thock",
    "interactKey": "alt",
    "interactKeepsHand": False,
    "inkChoice": "match",
    "showInkButton": True,
    "pinnedStyles": list(styles.DEFAULT_PINNED),
    "pointerStyle": "lavender",
    # one-time flags
    "welcomeShown": False,
    "firstRunHintShown": False,
    "loginItemSetUp": False,
}

# Keys removed by "Reset all settings…" (same list as the macOS app).
RESETTABLE = [
    "shortcut.toggle", "shortcut.clear", "pointerSize", "showShadow", "fadeSeconds",
    "sound.hands", "sound.laser", "interactKey", "interactKeepsHand", "pinnedStyles",
    "pointerStyle", "inkChoice", "showInkButton", "tapSound",
]

POINTER_SIZE_RANGE = (0.08, 0.20)

INTERACT_KEYS = [
    # id, title, symbol shown in hints
    ("alt", "Alt", "Alt"),
    ("super", "Super", "Super"),
    ("control", "Ctrl", "Ctrl"),
    ("off", "Off", ""),
]


class _Prefs:
    def __init__(self):
        self._values = {}
        self._listeners = []
        self._load()

    def _load(self):
        try:
            data = json.loads(FILE.read_text())
            if isinstance(data, dict):
                self._values = data
        except (OSError, ValueError):
            self._values = {}

    def _save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            tmp = FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._values, indent=1, sort_keys=True))
            tmp.replace(FILE)
        except OSError:
            pass

    def get(self, key):
        v = self._values.get(key, DEFAULTS.get(key))
        return v

    def set(self, key, value, notify=True):
        if self._values.get(key, DEFAULTS.get(key)) == value and key in self._values:
            return
        self._values[key] = value
        self._save()
        if notify:
            self.changed()

    def changed(self):
        for fn in list(self._listeners):
            fn()

    def connect(self, fn):
        self._listeners.append(fn)

    def reset_all(self):
        for k in RESETTABLE:
            self._values.pop(k, None)
        self._save()
        self.changed()

    # ---- typed helpers

    @property
    def pointer_style(self):
        s = self.get("pointerStyle")
        if s == "dot":
            return styles.LASER
        if s == "sunny":
            return "coral"
        return s if styles.valid(s) else "lavender"

    @pointer_style.setter
    def pointer_style(self, value):
        self.set("pointerStyle", value)

    @property
    def pinned(self):
        raw = self.get("pinnedStyles") or []
        seen, out = set(), []
        for s in raw:
            if styles.valid(s) and s not in seen:
                seen.add(s)
                out.append(s)
        return out or list(styles.DEFAULT_PINNED)

    @pinned.setter
    def pinned(self, value):
        self.set("pinnedStyles", list(value)[: styles.MAX_PINNED])

    @property
    def pointer_size(self):
        lo, hi = POINTER_SIZE_RANGE
        return min(hi, max(lo, float(self.get("pointerSize"))))

    @property
    def interact_key(self):
        k = self.get("interactKey")
        return k if k in [i[0] for i in INTERACT_KEYS] else "alt"

    def interact_symbol(self):
        return next(i[2] for i in INTERACT_KEYS if i[0] == self.interact_key)

    def sound_on(self, style):
        return self.get("sound.laser" if style == styles.LASER else "sound.hands")

    def set_sound_on(self, style, on):
        self.set("sound.laser" if style == styles.LASER else "sound.hands", bool(on))


prefs = _Prefs()


def shortcut_label(accel):
    """'<Control><Alt>h' -> 'Ctrl+Alt+H'."""
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    key, mods = Gtk.accelerator_parse(accel or "")
    if not key:
        return "—"
    return Gtk.accelerator_get_label(key, mods)
