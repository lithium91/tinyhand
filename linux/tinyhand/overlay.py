"""The pointer overlay. Port of OverlayController.swift.

The macOS app keeps a click-through window and steals clicks with an event
tap. That can't work under XWayland, so on Linux the overlay is a
transparent, full-screen, always-on-top window per monitor that takes the
mouse itself: clicks land on it (so nothing underneath is clicked), the
real cursor is hidden by a blank cursor on the window, and keyboard focus
gives us Esc and the "hold a key to click for real" modifier. The same
code runs on plain X11 and on GNOME/KDE Wayland through XWayland.

The window covers the monitor's work area, not the whole monitor: a
full-screen window makes GNOME hide the top bar and the dock. Over those
the real cursor shows and clicks reach them, like the menu bar and Dock
in the macOS app.
"""
import math
import os
import time

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import styles  # noqa: E402
from .ink import Ink  # noqa: E402
from .pointer import Pointer  # noqa: E402
from .prefs import prefs  # noqa: E402
from .sound import TapSound  # noqa: E402
from .toolbar import Toolbar  # noqa: E402

DRAG_THRESHOLD = 4
IDLE_AFTER = 0.5

MODIFIER_KEYS = {
    "alt": {"Alt_L", "Alt_R", "Meta_L", "Meta_R", "ISO_Level3_Shift"},
    "super": {"Super_L", "Super_R", "Hyper_L", "Hyper_R"},
    "control": {"Control_L", "Control_R"},
}
MODIFIER_MASKS = {
    "alt": Gdk.ModifierType.MOD1_MASK,
    "super": Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.MOD4_MASK,
    "control": Gdk.ModifierType.CONTROL_MASK,
}


def is_wayland_session():
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def _union(*rects):
    rects = [r for r in rects if r]
    if not rects:
        return None
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects)
    y1 = max(r[1] + r[3] for r in rects)
    return (x0, y0, x1 - x0, y1 - y0)


class OverlayWindow(Gtk.Window):
    def __init__(self, controller, monitor_index):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.controller = controller
        self.monitor_index = monitor_index
        display = Gdk.Display.get_default()
        self.monitor = display.get_monitor(monitor_index)
        self.geometry = self.monitor.get_geometry()
        self.workarea = self.monitor.get_workarea()
        self.area = self._overlay_area()

        self.set_title("TinyHand")
        self.set_wmclass("tinyhand-overlay", "TinyHand")
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_accept_focus(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.KEY_RELEASE_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK | Gdk.EventMask.FOCUS_CHANGE_MASK
            | Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        a = self.area
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
        self.move(a.x, a.y)
        self.set_default_size(a.width, a.height)
        self.set_size_request(a.width, a.height)
        self.resize(a.width, a.height)

        self.connect("draw", controller._on_draw)
        self.connect("motion-notify-event", controller._on_motion)
        self.connect("button-press-event", controller._on_press)
        self.connect("button-release-event", controller._on_release)
        self.connect("key-press-event", controller._on_key_press)
        self.connect("key-release-event", controller._on_key_release)
        self.connect("enter-notify-event", controller._on_enter)
        self.connect("leave-notify-event", controller._on_leave)
        self.connect("focus-out-event", controller._on_focus_out)
        self.connect("scroll-event", lambda *_: True)
        self.connect("delete-event", lambda *_: True)

    def open(self):
        self.realize()
        gdkwin = self.get_window()
        gdkwin.set_cursor(Gdk.Cursor.new_for_display(self.get_display(), Gdk.CursorType.BLANK_CURSOR))
        self.show()
        a = self.area
        self.move(a.x, a.y)
        self.set_keep_above(True)

    def _overlay_area(self):
        a = Gdk.Rectangle()
        wa, g = self.workarea, self.geometry
        a.x, a.y, a.width, a.height = wa.x, wa.y, wa.width, wa.height
        if a.width <= 0 or a.height <= 0:
            a.x, a.y, a.width, a.height = g.x, g.y, g.width, g.height
        if (a.x, a.y, a.width, a.height) == (g.x, g.y, g.width, g.height):
            # An undecorated window exactly the size of a monitor counts as
            # full-screen for mutter (and hides the panel and dock); one
            # pixel short does not.
            a.height -= 1
        return a

    def local(self, x_root, y_root):
        return (x_root - self.area.x, y_root - self.area.y)

    def size(self):
        return (self.area.width, self.area.height)

    def queue(self, rect):
        if not rect:
            return
        x, y, w, h = rect
        x0, y0 = int(math.floor(x)), int(math.floor(y))
        x1, y1 = int(math.ceil(x + w)), int(math.ceil(y + h))
        if x1 > x0 and y1 > y0:
            self.queue_draw_area(x0, y0, x1 - x0, y1 - y0)


class Overlay:
    def __init__(self):
        self.pointer = Pointer()
        self.ink = Ink()
        self.toolbar = Toolbar()
        self.sound = TapSound(prefs.get("tapSound"))
        self.windows = []
        self.win = None  # the window under the mouse
        self.active = False
        self.cursor = None
        self.down_point = None
        self.drag_events = 0
        self.reveal_until = 0.0
        self.interacting = False
        self.outside = False
        self._interact_poll = None
        self._focus_lost_at = None
        self._tick_id = None
        self._last_frame = None
        self._still_since = time.monotonic()
        self._fade_timer = None
        self.wayland = is_wayland_session()

        self.on_active_changed = None
        self.on_sound_changed = None

        self.toolbar.on_pick = self.pick
        self.toolbar.on_toggle_sound = self.toggle_sound
        self.toolbar.on_exit = self.exit
        self.toolbar.select(self.pointer.style)
        self._sync_sound()
        self._sync_ink()
        prefs.connect(self._prefs_changed)
        screen = Gdk.Screen.get_default()
        screen.connect("monitors-changed", self._monitors_changed)

    # ------------------------------------------------------------ public

    def toggle(self, timestamp=None):
        if self.active:
            self.deactivate()
        else:
            self.activate(timestamp)

    def exit(self):
        self.clear_ink()
        self.deactivate()

    def clear_ink(self):
        rects = self.ink.clear()
        if self.win:
            for r in rects:
                self.win.queue(r)

    @property
    def sound_on(self):
        return prefs.sound_on(self.pointer.style)

    @sound_on.setter
    def sound_on(self, value):
        prefs.set_sound_on(self.pointer.style, value)

    def toggle_sound(self):
        self.sound_on = not self.sound_on

    def pick(self, style):
        old = self.pointer.predicted_bbox()
        self.pointer.set_style(style)
        prefs.pointer_style = self.pointer.style
        self.toolbar.select(self.pointer.style)
        self._sync_sound()
        self._sync_ink()
        if self.win:
            self.win.queue(old)
            self.win.queue(self.toolbar.damage())
        self._kick()

    def activate(self, timestamp=None):
        if self.active:
            return
        display = Gdk.Display.get_default()
        screen = Gdk.Screen.get_default()
        if not screen.is_composited():
            print("tinyhand: no compositor running; the overlay can't be transparent")
        self.active = True
        self.sound.warm()
        self.windows = [OverlayWindow(self, i) for i in range(display.get_n_monitors())]
        for w in self.windows:
            w.open()
        # start on the monitor the mouse is on, if we can tell
        seat = display.get_default_seat()
        _, x, y = seat.get_pointer().get_position()
        mon = display.get_monitor_at_point(x, y)
        start = next((w for w in self.windows if w.monitor == mon), self.windows[0])
        self._set_win(start, start.local(x, y), moving=False)
        lx, ly = start.local(x, y)
        aw, ah = start.size()
        self.outside = not (0 <= lx < aw and 0 <= ly < ah)
        self._present(timestamp)

        now = time.monotonic()
        self.reveal_until = now + 3
        if not prefs.get("firstRunHintShown"):
            prefs.set("firstRunHintShown", True, notify=False)
            parts = [("Click", "to tap"), ("Drag", "to draw")]
            if prefs.interact_key != "off":
                parts.append((f"Hold {prefs.interact_symbol()}", "to click for real"))
            parts.append(("Esc", "to exit"))
            self.toolbar.show_hint(parts)
            self.reveal_until = now + 10
            GLib.timeout_add_seconds(10, self._end_hint)
        self._kick()
        if self.on_active_changed:
            self.on_active_changed()

    def deactivate(self):
        if not self.active:
            return
        self.active = False
        self._stop_tick()
        self._leave_interact(restore=False)
        if self._fade_timer:
            GLib.source_remove(self._fade_timer)
            self._fade_timer = None
        self.pointer.held = False
        self.down_point = None
        self.ink.clear()
        self.toolbar.hide_now()
        for w in self.windows:
            w.destroy()
        self.windows = []
        self.win = None
        self.cursor = None
        self.outside = False
        if self.on_active_changed:
            self.on_active_changed()

    # ------------------------------------------------------------ helpers

    def _present(self, timestamp=None):
        if not self.win:
            return
        if timestamp:
            self.win.present_with_time(timestamp)
        else:
            self.win.present()

    def _set_win(self, win, local, moving=True):
        if win is not self.win:
            old = self.win
            if old is not None:
                self._release()
                old.queue_draw()
            self.ink.clear()
            self.win = win
            w, h = win.size()
            self.pointer.resize(w, h, win.get_scale_factor())
            self.toolbar.place(w / 2, h)
            if moving:
                self.reveal_until = time.monotonic() + 1.5
            win.queue_draw()
        self.cursor = local

    def _end_hint(self):
        self.toolbar.hide_hint()
        self._kick()
        return False

    def _sync_sound(self):
        self.sound.enabled = self.sound_on
        self.toolbar.sound_on = self.sound_on
        if self.win:
            self.win.queue(self.toolbar.damage())
        if self.on_sound_changed:
            self.on_sound_changed()

    def _sync_ink(self):
        self.ink.color = styles.resolved_ink(prefs.get("inkChoice"), self.pointer.style)

    def _prefs_changed(self):
        self.sound.load(prefs.get("tapSound"))
        self._sync_sound()
        self._sync_ink()
        if self.pointer.style != prefs.pointer_style:
            self.pick(prefs.pointer_style)
        self.toolbar.layout()
        if self.win:
            self.win.queue_draw()
            self._kick()

    def _monitors_changed(self, *_):
        if self.active:
            self.deactivate()
            GLib.idle_add(lambda: (self.activate(), False)[1])

    # ------------------------------------------------------------ ticking

    def _kick(self):
        self._still_since = time.monotonic()
        if self._tick_id is None and self.win is not None and self.active:
            self._last_frame = None
            self._tick_id = self.win.add_tick_callback(self._tick)
            self._tick_win = self.win

    def _stop_tick(self):
        if self._tick_id is not None:
            try:
                self._tick_win.remove_tick_callback(self._tick_id)
            except Exception:
                pass
            self._tick_id = None

    def _tick(self, widget, clock):
        if widget is not self.win or not self.active:
            self._tick_id = None
            if self.active:
                GLib.idle_add(lambda: (self._kick(), False)[1])
            return GLib.SOURCE_REMOVE
        now = time.monotonic()
        dt = 1 / 60 if self._last_frame is None else min(0.1, now - self._last_frame)
        self._last_frame = now
        win = self.win

        # pointer
        if self.cursor is not None:
            before = self.pointer.bbox
            prev_cursor = self.pointer.cursor
            self.pointer.step(self.cursor, dt)
            after = self.pointer.predicted_bbox()
            if after != before or prev_cursor != self.cursor:
                win.queue(_union(before, after))

        # toolbar
        if self.cursor is not None:
            fx, fy, fw, fh = self.toolbar.frame
            near_box = (fx - 80, fy - 90 - 10, fw + 160, fh + 90 + 20)
            cx, cy = self.cursor
            near = near_box[0] <= cx < near_box[0] + near_box[2] and near_box[1] <= cy < near_box[1] + near_box[3]
            want = not self.ink.drawing and not self.interacting and (near or now < self.reveal_until)
            if self.toolbar.set_revealed(want, now):
                win.queue(self.toolbar.damage())
            hover = self.toolbar.hit(cx, cy) if self.toolbar.revealed else None
            if hover != self.toolbar.hover:
                self.toolbar.hover = hover
                win.queue(self.toolbar.damage())
        if self.toolbar.animating(now):
            win.queue(self.toolbar.damage())

        # ink fading
        for r in self.ink.fading(now):
            win.queue(r)

        # go idle when nothing moves
        busy = (self.pointer.held or self.pointer.settling or self.ink.drawing
                or self.toolbar.animating(now) or now < self.reveal_until
                or any(s.fade_at is not None and s.fade_at <= now for s in self.ink.strokes)
                or now - self._still_since < IDLE_AFTER)
        if not busy:
            self._tick_id = None
            self._arm_fade_timer()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _arm_fade_timer(self):
        nxt = self.ink.next_fade()
        if self._fade_timer:
            GLib.source_remove(self._fade_timer)
            self._fade_timer = None
        if nxt is None:
            return
        delay = max(0, int((nxt - time.monotonic()) * 1000))

        def fire():
            self._fade_timer = None
            self._kick()
            return False

        self._fade_timer = GLib.timeout_add(delay, fire)

    # ------------------------------------------------------------ drawing

    def _on_draw(self, win, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if win is not self.win or not self.active:
            return True
        now = time.monotonic()
        self.ink.draw(cr, now)
        self.toolbar.draw(cr, now)
        self.pointer.hidden = (self.interacting and not prefs.get("interactKeepsHand")) \
            or (self.outside and self.down_point is None)
        box = self.pointer.draw(cr)
        if box:
            x0, y0, x1, y1 = cr.clip_extents()
            if box[0] < x0 or box[1] < y0 or box[0] + box[2] > x1 or box[1] + box[3] > y1:
                win.queue(box)
        return True

    # ------------------------------------------------------------ input

    def _on_enter(self, win, event):
        if self.outside:
            self.outside = False
            win.queue_draw()
        self._set_win(win, (event.x, event.y))
        if not win.has_toplevel_focus() and not self.interacting:
            win.present_with_time(event.time)
        self._kick()
        return False

    def _on_leave(self, win, event):
        """The mouse went to the top bar, the dock or past the edge: the real
        cursor is there, so put the hand away until it comes back."""
        if win is not self.win or event.mode != Gdk.CrossingMode.NORMAL \
                or event.detail == Gdk.NotifyType.INFERIOR:
            return False
        self.outside = True
        win.queue(self.pointer.bbox)
        self.toolbar.hover = None
        self._kick()
        return False

    def _on_motion(self, win, event):
        if self.outside:
            self.outside = False
        if win is not self.win:
            self._set_win(win, (event.x, event.y))
        self.cursor = (event.x, event.y)
        if self.down_point is not None:
            self.drag_events += 1
            self._drag()
        self._kick()
        return True

    def _on_press(self, win, event):
        if event.type != Gdk.EventType.BUTTON_PRESS:
            return True  # ignore synthesized double/triple-click events
        if win is not self.win:
            self._set_win(win, (event.x, event.y))
        self.cursor = (event.x, event.y)
        if event.button == 1 and self.toolbar.click(event.x, event.y):
            self.win.queue(self.toolbar.damage())
            self._kick()
            return True
        if self.down_point is not None:
            return True  # a second button while one is held
        self.pointer.press()
        self.pointer.held = True
        self.sound.play()
        self.toolbar.hide_hint()
        self.down_point = (event.x, event.y)
        self.drag_events = 0
        self._kick()
        return True

    def _on_release(self, win, event):
        self._release()
        self._kick()
        return True

    def _release(self):
        self.pointer.held = False
        self.down_point = None
        self.ink.end()

    def _drag(self):
        start, p = self.down_point, self.cursor
        if start is None or p is None or not self.win:
            return
        if not self.ink.drawing:
            if math.hypot(p[0] - start[0], p[1] - start[1]) < DRAG_THRESHOLD:
                return
            self.win.queue(self.ink.begin(start, self.pointer.ink_width))
        self.win.queue(self.ink.extend(p))

    def _on_key_press(self, win, event):
        name = Gdk.keyval_name(event.keyval) or ""
        if name == "Escape":
            self.exit()
            return True
        key = prefs.interact_key
        if key != "off" and name in MODIFIER_KEYS[key]:
            self._enter_interact()
            return True
        return False

    def _on_key_release(self, win, event):
        name = Gdk.keyval_name(event.keyval) or ""
        key = prefs.interact_key
        if key != "off" and name in MODIFIER_KEYS[key]:
            self._leave_interact()
            return True
        return False

    def _on_focus_out(self, win, event):
        if self.interacting:
            self._focus_lost_at = time.monotonic()
        return False

    # ------------------------------------------------------------ click for real

    def _enter_interact(self):
        if self.interacting or not self.active:
            return
        self.interacting = True
        self._focus_lost_at = None
        self._release()
        empty = cairo.Region()
        for w in self.windows:
            w.input_shape_combine_region(empty)
            gdkwin = w.get_window()
            if gdkwin:
                gdkwin.set_cursor(None)
        if self.win:
            self.win.queue_draw()
        if self._interact_poll is None:
            self._interact_poll = GLib.timeout_add(40, self._poll_interact)
        self._kick()

    def _leave_interact(self, restore=True):
        if not self.interacting:
            return
        self.interacting = False
        if self._interact_poll is not None:
            GLib.source_remove(self._interact_poll)
            self._interact_poll = None
        if not restore:
            return
        blank = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.BLANK_CURSOR)
        for w in self.windows:
            w.input_shape_combine_region(None)
            gdkwin = w.get_window()
            if gdkwin:
                gdkwin.set_cursor(blank)
        if self.win:
            if not self.win.has_toplevel_focus():
                self.win.present()
            self.win.queue_draw()
        self._kick()

    def _poll_interact(self):
        """While the overlay lets clicks through, watch for the key to come up.

        On X11 the server reports the global pointer and modifier state, so
        we follow both. Under XWayland we only learn about the keyboard while
        we have focus: once a real click moved focus to another window, we
        take the pointer back shortly after (one real click per key hold)."""
        if not self.interacting:
            self._interact_poll = None
            return False
        display = Gdk.Display.get_default()
        device = display.get_default_seat().get_pointer()
        root = Gdk.get_default_root_window()
        _, x, y, mask = root.get_device_position(device)
        if not self.wayland:
            if not mask & MODIFIER_MASKS.get(prefs.interact_key, 0):
                self._leave_interact()
                self._interact_poll = None
                return False
            if prefs.get("interactKeepsHand") and self.win:
                mon = display.get_monitor_at_point(x, y)
                win = next((w for w in self.windows if w.monitor == mon), self.win)
                self._set_win(win, win.local(x, y))
                self._kick()
        elif self._focus_lost_at is not None and time.monotonic() - self._focus_lost_at > 0.3:
            # Pointer grabs stay with the app until the button comes up, so
            # taking the input region back now can't break a drag in progress.
            self._leave_interact()
            self._interact_poll = None
            return False
        return True
