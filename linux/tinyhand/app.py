"""Application: single instance, tray, shortcuts, and the command line.

    tinyhand              start (or open Settings if already running)
    tinyhand --toggle     turn the pointer on or off
    tinyhand --on/--off   turn it on / off
    tinyhand --clear      clear the drawing
    tinyhand --settings   open Settings
    tinyhand --quit       quit the running instance
"""
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import __version__, autostart, styles  # noqa: E402
from .prefs import prefs  # noqa: E402

APP_ID = "app.tinyhand.TinyHand"


class TinyHandApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.overlay = None
        self.tray = None
        self.hotkeys = None
        self.settings = None
        self._started = False
        for name, desc in (("toggle", "Turn the pointer on or off"), ("on", "Turn the pointer on"),
                           ("off", "Turn the pointer off"), ("clear", "Clear the drawing"),
                           ("settings", "Open Settings"), ("background", "Start without any window"),
                           ("quit", "Quit TinyHand"), ("version", "Print the version")):
            self.add_main_option(name, 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE, desc, None)

    def do_handle_local_options(self, options):
        if options.contains("version"):
            print(f"TinyHand {__version__}")
            return 0
        return -1

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.Window.set_default_icon_name("tinyhand")
        self._add_icon_path()

    def _add_icon_path(self):
        theme = Gtk.IconTheme.get_default()
        for base in (styles.data_root() / "linux" / "data" / "icons", styles.data_root() / "data" / "icons"):
            if base.exists():
                theme.prepend_search_path(str(base))

    def _start(self):
        if self._started:
            return
        self._started = True
        from .hotkeys import Hotkeys
        from .overlay import Overlay
        from .tray import Tray

        self.hold()
        self.overlay = Overlay()
        self.hotkeys = Hotkeys()
        self.tray = Tray(self)
        self.overlay.on_active_changed = self._refresh
        self.overlay.on_sound_changed = self._refresh
        prefs.connect(self._refresh)
        self.reregister_hotkeys()
        if not prefs.get("loginItemSetUp") and autostart.installed():
            prefs.set("loginItemSetUp", True, notify=False)
            autostart.set_enabled(True)

    def _refresh(self):
        if self.tray:
            self.tray.refresh()

    def do_command_line(self, command_line):
        opts = command_line.get_options_dict().end().unpack()
        first = not self._started
        self._start()
        if opts.get("quit"):
            self.quit_app()
            return 0
        if opts.get("toggle"):
            self.overlay.toggle()
        elif opts.get("on"):
            self.overlay.activate()
        elif opts.get("off"):
            self.overlay.deactivate()
        elif opts.get("clear"):
            self.overlay.clear_ink()
        elif opts.get("settings"):
            self.show_settings()
        elif opts.get("background"):
            pass
        elif first:
            if not prefs.get("welcomeShown"):
                self.show_welcome()
        else:
            # launched again from the app grid: there may be no tray, so open Settings
            self.show_settings()
        return 0

    # ------------------------------------------------------------ actions

    def show_welcome(self):
        from .welcome import Welcome

        prefs.set("welcomeShown", True, notify=False)
        w = Welcome(lambda: self.overlay.activate(), self.hotkeys.kind)
        self.add_window(w)
        w.show_all()
        w.present()

    def show_settings(self, section=None):
        from .settings import SettingsWindow

        if self.overlay.active:
            self.overlay.exit()
        if self.settings is None:
            self.settings = SettingsWindow(self)
            self.add_window(self.settings)
        self.settings.show_section(section)

    def quit_app(self):
        if self.overlay:
            self.overlay.deactivate()
        self.release()
        self.quit()

    # ------------------------------------------------------------ shortcuts

    def reregister_hotkeys(self):
        self.hotkeys.unregister("toggle")
        self.hotkeys.unregister("clear")
        ok1 = self.hotkeys.register("toggle", prefs.get("shortcut.toggle"), self.overlay.toggle)
        ok2 = self.hotkeys.register("clear", prefs.get("shortcut.clear"), self.overlay.clear_ink)
        return ok1 and ok2

    def apply_shortcut(self, key, accel):
        old = prefs.get(key)
        prefs.set(key, accel)
        if self.reregister_hotkeys():
            return True
        prefs.set(key, old)
        self.reregister_hotkeys()
        return False

    def set_recording(self, recording):
        """Free the shortcuts while the user records a new one."""
        if recording:
            self.hotkeys.unregister("toggle")
            self.hotkeys.unregister("clear")
        else:
            self.reregister_hotkeys()


def main(argv=None):
    app = TinyHandApp()
    return app.run(argv if argv is not None else sys.argv)
