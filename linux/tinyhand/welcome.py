"""First-run card. On Linux nothing needs permission, so it just shows the
shortcut and a Start button."""
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from .prefs import prefs, shortcut_label  # noqa: E402


class Welcome(Gtk.Window):
    def __init__(self, on_start, hotkey_kind):
        super().__init__(title="Welcome to TinyHand")
        self.set_default_size(420, -1)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name("tinyhand")
        self.on_start = on_start
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=28)
        icon = Gtk.Image.new_from_icon_name("tinyhand", Gtk.IconSize.DIALOG)
        icon.set_pixel_size(96)
        box.pack_start(icon, False, False, 0)
        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>You're all set</span>")
        box.pack_start(title, False, False, 0)
        key = shortcut_label(prefs.get("shortcut.toggle"))
        if hotkey_kind == "manual":
            text = ("Bind <tt>tinyhand --toggle</tt> to a key in your desktop's shortcut settings, "
                    "or use the tray icon.")
        else:
            text = f"Press <b>{key}</b> any time to start."
        sub = Gtk.Label()
        sub.set_markup(text)
        sub.set_line_wrap(True)
        sub.set_justify(Gtk.Justification.CENTER)
        box.pack_start(sub, False, False, 0)
        tips = Gtk.Label()
        tips.set_markup("<small>Click to tap · Drag to draw · Esc to exit</small>")
        tips.get_style_context().add_class("dim-label")
        box.pack_start(tips, False, False, 0)
        button = Gtk.Button(label="Start")
        button.get_style_context().add_class("suggested-action")
        button.set_halign(Gtk.Align.CENTER)
        button.set_size_request(140, -1)
        button.connect("clicked", self._start)
        box.pack_start(button, False, False, 8)
        self.add(box)
        self.connect("key-press-event", self._key)

    def _start(self, *_):
        self.destroy()
        self.on_start()

    def _key(self, _w, event):
        if event.keyval == 0xFF1B:  # Escape
            self.destroy()
            return True
        return False

