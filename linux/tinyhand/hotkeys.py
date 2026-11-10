"""Global shortcuts.

* X11: XGrabKey on the root window, read from the GLib main loop.
* GNOME on Wayland: X11 grabs only fire while an X11 window has focus, so
  we register GNOME custom shortcuts that run `tinyhand --toggle` /
  `tinyhand --clear` instead. The running instance receives them over D-Bus.
* Other Wayland desktops: no API for us; the user binds the same commands
  in their compositor (Settings shows how).
"""
import os
import shlex
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from .overlay import is_wayland_session  # noqa: E402

GNOME_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
GNOME_BINDING_SCHEMA = GNOME_SCHEMA + ".custom-keybinding"
GNOME_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/tinyhand-{}/"


def launcher_command(arg):
    """Command line that reaches the running TinyHand with one option."""
    exe = Path(sys.argv[0]).resolve()
    if exe.name == "tinyhand" and os.access(exe, os.X_OK):
        return f"{shlex.quote(str(exe))} {arg}"
    if Path("/usr/bin/tinyhand").exists():
        return f"/usr/bin/tinyhand {arg}"
    pkg_parent = Path(__file__).resolve().parent.parent
    return (f"env PYTHONPATH={shlex.quote(str(pkg_parent))} "
            f"{shlex.quote(sys.executable)} -m tinyhand {arg}")


def is_gnome():
    return "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":") or \
        "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper()


def backend_name():
    if not is_wayland_session():
        return "x11"
    if is_gnome() and _gnome_schema_available():
        return "gnome"
    return "manual"


def _gnome_schema_available():
    src = Gio.SettingsSchemaSource.get_default()
    return src is not None and src.lookup(GNOME_SCHEMA, True) is not None \
        and src.lookup(GNOME_BINDING_SCHEMA, True) is not None


class _X11Backend:
    def __init__(self):
        from Xlib import X, XK, display  # noqa: F401

        self.X = X
        self.XK = XK
        self.dpy = display.Display()
        self.root = self.dpy.screen().root
        self.grabs = {}  # name -> (keycode, mods, callback)
        GLib.io_add_watch(self.dpy.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN, self._pump)
        self._ignored = self._ignored_masks()

    def _ignored_masks(self):
        X = self.X
        numlock = 0
        mapping = self.dpy.get_modifier_mapping()
        nl = self.dpy.keysym_to_keycode(self.XK.string_to_keysym("Num_Lock"))
        for i, codes in enumerate(mapping):
            if nl and nl in codes:
                numlock = 1 << i
        return [0, X.LockMask, numlock, X.LockMask | numlock]

    def _mods(self, gdk_mods):
        X = self.X
        out = 0
        if gdk_mods & 1:  # SHIFT
            out |= X.ShiftMask
        if gdk_mods & (1 << 2):  # CONTROL
            out |= X.ControlMask
        if gdk_mods & (1 << 3):  # MOD1 / Alt
            out |= X.Mod1Mask
        if gdk_mods & ((1 << 26) | (1 << 6)):  # SUPER / MOD4
            out |= X.Mod4Mask
        return out

    def register(self, name, accel, callback):
        from Xlib import error

        key, mods = Gtk.accelerator_parse(accel)
        if not key:
            return False
        code = self.dpy.keysym_to_keycode(key)
        if not code:
            return False
        xmods = self._mods(int(mods))
        catcher = error.CatchError(error.BadAccess)
        for extra in self._ignored:
            self.root.grab_key(code, xmods | extra, True, self.X.GrabModeAsync, self.X.GrabModeAsync,
                               onerror=catcher)
        self.dpy.sync()
        if catcher.get_error():
            for extra in self._ignored:
                self.root.ungrab_key(code, xmods | extra)
            self.dpy.sync()
            return False
        self.grabs[name] = (code, xmods, callback)
        return True

    def unregister(self, name):
        g = self.grabs.pop(name, None)
        if g:
            for extra in self._ignored:
                self.root.ungrab_key(g[0], g[1] | extra)
            self.dpy.sync()

    def _pump(self, *_):
        X = self.X
        while self.dpy.pending_events():
            ev = self.dpy.next_event()
            if ev.type != X.KeyPress:
                continue
            state = ev.state & ~(self._ignored[3])
            for code, mods, cb in list(self.grabs.values()):
                if ev.detail == code and state == mods:
                    GLib.idle_add(lambda cb=cb: (cb(), False)[1])
        return True


class _GnomeBackend:
    def __init__(self):
        self.media = Gio.Settings.new(GNOME_SCHEMA)

    def register(self, name, accel, callback):
        path = GNOME_PATH.format(name)
        s = Gio.Settings.new_with_path(GNOME_BINDING_SCHEMA, path)
        s.set_string("name", f"TinyHand: {'turn the pointer on or off' if name == 'toggle' else 'clear the drawing'}")
        s.set_string("command", launcher_command(f"--{name}"))
        s.set_string("binding", accel)
        paths = list(self.media.get_strv("custom-keybindings"))
        if path not in paths:
            paths.append(path)
            self.media.set_strv("custom-keybindings", paths)
        Gio.Settings.sync()
        return True

    def unregister(self, name):
        # Keep the entry (so `tinyhand --toggle` still starts the app), just disable the key.
        s = Gio.Settings.new_with_path(GNOME_BINDING_SCHEMA, GNOME_PATH.format(name))
        s.set_string("binding", "")
        Gio.Settings.sync()


class _ManualBackend:
    def register(self, name, accel, callback):
        return True

    def unregister(self, name):
        pass


class Hotkeys:
    def __init__(self):
        self.kind = backend_name()
        try:
            self.backend = {"x11": _X11Backend, "gnome": _GnomeBackend}.get(self.kind, _ManualBackend)()
        except Exception as e:  # no python-xlib, no X display...
            print("tinyhand: global shortcuts unavailable:", e)
            self.kind = "manual"
            self.backend = _ManualBackend()

    def register(self, name, accel, callback):
        try:
            return self.backend.register(name, accel, callback)
        except Exception as e:
            print("tinyhand: cannot register shortcut", accel, e)
            return False

    def unregister(self, name):
        try:
            self.backend.unregister(name)
        except Exception as e:
            print("tinyhand: cannot unregister shortcut", name, e)
