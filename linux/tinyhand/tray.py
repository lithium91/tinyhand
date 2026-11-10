"""Status icon with the TinyHand menu (AppIndicator / StatusNotifierItem).

On GNOME this needs the "AppIndicator and KStatusNotifierItem Support"
extension, which Ubuntu ships enabled. Without it TinyHand still works:
the shortcuts toggle the pointer and launching TinyHand again opens Settings.
"""
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from . import styles  # noqa: E402
from .prefs import prefs, shortcut_label  # noqa: E402

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
except (ValueError, ImportError):
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3 as AppIndicator  # noqa: E402
    except (ValueError, ImportError):
        AppIndicator = None


class Tray:
    def __init__(self, app):
        self.app = app
        self.indicator = None
        if AppIndicator is None:
            print("tinyhand: AppIndicator library not found; no tray icon")
            return
        self.indicator = AppIndicator.Indicator.new(
            "tinyhand", "tinyhand-off-symbolic", AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        icon_dir = styles.data_root() / "linux" / "data" / "icons" / "hicolor" / "symbolic" / "apps"
        if not icon_dir.exists():
            icon_dir = styles.data_root() / "data" / "icons" / "hicolor" / "symbolic" / "apps"
        if icon_dir.exists():
            self.indicator.set_icon_theme_path(str(icon_dir))
        self.indicator.set_title("TinyHand")
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()
        self.toggle_item = Gtk.MenuItem(label="")
        self.toggle_item.connect("activate", lambda *_: app.overlay.toggle(Gtk.get_current_event_time()))
        self.clear_item = Gtk.MenuItem(label="")
        self.clear_item.connect("activate", lambda *_: app.overlay.clear_ink())
        self.sound_item = Gtk.CheckMenuItem(label="Tap Sound")
        self._sound_handler = self.sound_item.connect("toggled", self._sound_toggled)
        settings = Gtk.MenuItem(label="Settings…")
        settings.connect("activate", lambda *_: app.show_settings())
        quit_item = Gtk.MenuItem(label="Quit TinyHand")
        quit_item.connect("activate", lambda *_: app.quit_app())
        for item in (self.toggle_item, self.clear_item, self.sound_item, Gtk.SeparatorMenuItem(),
                     settings, Gtk.SeparatorMenuItem(), quit_item):
            menu.append(item)
        menu.show_all()
        self.indicator.set_menu(menu)
        # middle-click on the icon toggles the pointer
        self.indicator.set_secondary_activate_target(self.toggle_item)
        self.refresh()

    def _sound_toggled(self, item):
        self.app.overlay.sound_on = item.get_active()

    def refresh(self):
        if not self.indicator:
            return
        on = self.app.overlay.active
        self.indicator.set_icon_full("tinyhand-on-symbolic" if on else "tinyhand-off-symbolic",
                                     "TinyHand is on" if on else "TinyHand")
        self.toggle_item.set_label(
            f"{'Turn Pointer Off' if on else 'Turn Pointer On'}    {shortcut_label(prefs.get('shortcut.toggle'))}")
        self.clear_item.set_label(f"Clear Drawing    {shortcut_label(prefs.get('shortcut.clear'))}")
        self.sound_item.handler_block(self._sound_handler)
        self.sound_item.set_active(bool(self.app.overlay.sound_on))
        self.sound_item.handler_unblock(self._sound_handler)
