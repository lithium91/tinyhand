"""Settings window. Same sections as the macOS app: General, Pointers,
Appearance, Drawing, Sound, About."""
import math

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import __version__, autostart, pointer, styles  # noqa: E402
from .hotkeys import launcher_command  # noqa: E402
from .prefs import INTERACT_KEYS, POINTER_SIZE_RANGE, prefs, shortcut_label  # noqa: E402

CSS = b"""
.th-card { border-radius: 10px; }
.th-card row { padding: 10px 14px; }
.th-section { font-weight: bold; opacity: 0.6; margin: 0 4px 6px 4px; }
.th-detail { opacity: 0.6; font-size: smaller; }
.th-tile { border-radius: 12px; padding: 12px 6px; }
.th-thumb { border-radius: 10px; padding: 4px; min-width: 52px; min-height: 52px; }
.th-thumb:checked { background-color: alpha(@theme_selected_bg_color, 0.25); }
.th-error { color: #e01b24; }
"""

SECTIONS = [
    ("general", "General", "preferences-system-symbolic"),
    ("pointers", "Pointers", "tinyhand-on-symbolic"),
    ("appearance", "Appearance", "applications-graphics-symbolic"),
    ("drawing", "Drawing", "document-edit-symbolic"),
    ("sound", "Sound", "audio-volume-high-symbolic"),
    ("about", "About", "help-about-symbolic"),
]

FADE_CHOICES = [("After 3 seconds", 3.0), ("After 6 seconds", 6.0), ("After 10 seconds", 10.0),
                ("Keep until cleared", 0.0)]


def _card(title, rows):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    if title:
        lbl = Gtk.Label(label=title, xalign=0)
        lbl.get_style_context().add_class("th-section")
        box.pack_start(lbl, False, False, 0)
    lb = Gtk.ListBox()
    lb.set_selection_mode(Gtk.SelectionMode.NONE)
    lb.get_style_context().add_class("frame")
    lb.get_style_context().add_class("th-card")
    for r in rows:
        row = Gtk.ListBoxRow(activatable=False, selectable=False)
        row.add(r)
        lb.add(row)
    box.pack_start(lb, False, False, 0)
    return box


def _row(title, trailing, detail=None):
    h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
    t = Gtk.Label(label=title, xalign=0)
    v.pack_start(t, False, False, 0)
    d = None
    if detail is not None:
        d = Gtk.Label(label=detail, xalign=0)
        d.set_line_wrap(True)
        d.get_style_context().add_class("th-detail")
        v.pack_start(d, False, False, 0)
    h.pack_start(v, True, True, 0)
    if trailing is not None:
        trailing.set_valign(Gtk.Align.CENTER)
        h.pack_end(trailing, False, False, 0)
    h.detail_label = d
    return h


def _switch(get, set_):
    s = Gtk.Switch(active=bool(get()))
    s.connect("notify::active", lambda w, _p: set_(w.get_active()))
    return s


def _combo(options, get, set_):
    """options: list of (label, value)."""
    c = Gtk.ComboBoxText()
    for label, _ in options:
        c.append_text(label)
    values = [v for _, v in options]
    cur = get()
    c.set_active(values.index(cur) if cur in values else 0)
    c.connect("changed", lambda w: set_(values[w.get_active()]))
    return c


def _page(*children):
    sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22, margin=24)
    for c in children:
        box.pack_start(c, False, False, 0)
    sw.add(box)
    return sw


def _surface_image(surf, size):
    def draw(widget, cr):
        a = widget.get_allocation()
        s = min(a.width, a.height) / surf.get_width()
        cr.translate((a.width - surf.get_width() * s) / 2, (a.height - surf.get_height() * s) / 2)
        cr.scale(s, s)
        cr.set_source_surface(surf, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.paint()
        return True

    area = Gtk.DrawingArea()
    area.set_size_request(size, size)
    area.connect("draw", draw)
    return area


_thumbs = {}


def _thumb(style):
    if style not in _thumbs:
        _thumbs[style] = pointer.thumbnail(style, 96)
    return _thumbs[style]


class ShortcutButton(Gtk.Button):
    """Click, then press a key combination."""

    def __init__(self, key, apply, on_recording):
        super().__init__()
        self.key = key
        self.apply = apply
        self.on_recording = on_recording
        self.recording = False
        self.set_size_request(150, -1)
        self.connect("clicked", self._start)
        self.connect("key-press-event", self._key)
        self.connect("focus-out-event", lambda *_: self._stop())
        self.refresh()

    def refresh(self):
        self.set_label("Type a shortcut…" if self.recording else shortcut_label(prefs.get(self.key)))

    def _start(self, *_):
        if self.recording:
            return
        self.recording = True
        self.on_recording(True)
        self.refresh()

    def _stop(self):
        if self.recording:
            self.recording = False
            self.on_recording(False)
            self.refresh()
        return False

    def _key(self, _w, event):
        if not self.recording:
            return False
        keyval = Gdk.keyval_to_lower(event.keyval)
        name = Gdk.keyval_name(keyval) or ""
        if name == "Escape":
            self._stop()
            return True
        if name.endswith(("_L", "_R")) or name in ("ISO_Level3_Shift", "Caps_Lock", "Num_Lock"):
            return True  # wait for a real key
        mods = event.state & Gtk.accelerator_get_default_mod_mask()
        if not mods & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK
                       | Gdk.ModifierType.SUPER_MASK):
            return True  # needs Ctrl, Alt or Super
        accel = Gtk.accelerator_name(keyval, mods)
        self.recording = False
        self.apply(self.key, accel)
        self.on_recording(False)
        self.refresh()
        return True


class SettingsWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(title="TinyHand Settings")
        self.app = app
        self.set_default_size(760, 560)
        self.set_icon_name("tinyhand")
        self.set_position(Gtk.WindowPosition.CENTER)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        header = Gtk.HeaderBar(title="TinyHand Settings", show_close_button=True)
        self.set_titlebar(header)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.sidebar = Gtk.StackSidebar(stack=self.stack)
        self.sidebar.set_size_request(170, -1)
        paned = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        paned.pack_start(self.sidebar, False, False, 0)
        paned.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        paned.pack_start(self.stack, True, True, 0)
        self.add(paned)
        self._building = False
        self._quiet = False
        self._pending = None
        self.rebuild()
        self._listener = self._prefs_changed
        prefs.connect(self._listener)
        self.connect("delete-event", self._hide)

    def _hide(self, *_):
        self.hide()
        return True

    def show_section(self, name=None):
        if name:
            self.stack.set_visible_child_name(name)
        self.show_all()
        self.present()

    def _prefs_changed(self):
        if self._quiet or self._building:
            return
        self._schedule()

    def _schedule(self):
        if not self._pending:
            self._pending = GLib.idle_add(self._deferred_rebuild)

    def _deferred_rebuild(self):
        self._pending = None
        self.rebuild()
        return False

    def quiet(self, key):
        """Setter for widgets that already show the new value: no page rebuild."""
        def set_(value):
            self._quiet = True
            try:
                prefs.set(key, value)
            finally:
                self._quiet = False
        return set_

    def rebuild(self):
        self._building = True
        current = self.stack.get_visible_child_name()
        for child in self.stack.get_children():
            self.stack.remove(child)
        builders = {
            "general": self._general, "pointers": self._pointers, "appearance": self._appearance,
            "drawing": self._drawing, "sound": self._sound, "about": self._about,
        }
        for name, title, icon in SECTIONS:
            page = builders[name]()
            self.stack.add_titled(page, name, title)
            self.stack.child_set_property(page, "icon-name", icon)
        self.stack.show_all()
        if current:
            self.stack.set_visible_child_name(current)
        self._building = False

    # ------------------------------------------------------------ pages

    def _general(self):
        kind = self.app.hotkeys.kind
        rows = [
            _row("Turn the pointer on or off", ShortcutButton("shortcut.toggle", self._apply_shortcut,
                                                              self.app.set_recording)),
            _row("Clear the drawing", ShortcutButton("shortcut.clear", self._apply_shortcut,
                                                     self.app.set_recording)),
        ]
        shortcuts = [_card("Shortcuts", rows)]
        if getattr(self, "shortcut_error", None):
            err = Gtk.Label(label=self.shortcut_error, xalign=0)
            err.get_style_context().add_class("th-error")
            shortcuts.append(err)
        if kind == "gnome":
            note = Gtk.Label(xalign=0)
            note.set_markup("<small>Saved as GNOME keyboard shortcuts "
                            "(Settings → Keyboard → Custom Shortcuts).</small>")
            note.get_style_context().add_class("dim-label")
            shortcuts.append(note)
        elif kind == "manual":
            note = Gtk.Label(xalign=0, selectable=True)
            note.set_line_wrap(True)
            note.set_markup(
                "<small>This desktop doesn't let apps register global shortcuts. Bind these commands "
                "in your compositor instead:\n"
                f"<tt>{_esc(launcher_command('--toggle'))}</tt>\n<tt>{_esc(launcher_command('--clear'))}</tt></small>")
            shortcuts.append(note)

        interact = prefs.interact_key
        keep = prefs.get("interactKeepsHand")
        click_rows = [_row("Hold to use the app",
                           _combo([(t, k) for k, t, _ in INTERACT_KEYS], lambda: prefs.interact_key,
                                  lambda v: prefs.set("interactKey", v)),
                           detail="Clicks, drags and scrolls reach the app.")]
        if interact != "off":
            click_rows.append(_row("While holding",
                                   _combo([("Show the cursor", False), ("Keep the hand", True)],
                                          lambda: keep, self.quiet("interactKeepsHand")),
                                   detail="The hand stays." if keep else "The normal cursor comes back."))
        startup = _card("Startup", [_row("Open TinyHand when you log in",
                                         _switch(autostart.enabled, autostart.set_enabled))])
        sbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for w in shortcuts:
            sbox.pack_start(w, False, False, 0)
        return _page(sbox, _card("Clicking for real", click_rows), startup)

    def _apply_shortcut(self, key, accel):
        ok = self.app.apply_shortcut(key, accel)
        self.shortcut_error = None if ok else f"{shortcut_label(accel)} is taken by another app. Try another."
        self._schedule()

    def _pointers(self):
        pinned = prefs.pinned
        current = prefs.pointer_style

        # toolbar row
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for i, s in enumerate(pinned):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            b = Gtk.ToggleButton(active=(s == current), relief=Gtk.ReliefStyle.NONE)
            b.get_style_context().add_class("th-thumb")
            b.add(_surface_image(_thumb(s), 44))
            b.set_tooltip_text(f"{styles.title(s)} — click to use it")
            b.connect("clicked", lambda _b, s=s: self._use(s))
            col.pack_start(b, False, False, 0)
            arrows = Gtk.Box(spacing=0, halign=Gtk.Align.CENTER)
            for icon, delta, tip in (("go-previous-symbolic", -1, "Move left"),
                                     ("list-remove-symbolic", 0, "Remove from the toolbar"),
                                     ("go-next-symbolic", 1, "Move right")):
                a = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.MENU)
                a.set_relief(Gtk.ReliefStyle.NONE)
                a.set_tooltip_text(tip)
                if (delta == -1 and i == 0) or (delta == 1 and i == len(pinned) - 1) or \
                        (delta == 0 and len(pinned) <= 1):
                    a.set_sensitive(False)
                a.connect("clicked", lambda _a, s=s, d=delta: self._move(s, d))
                arrows.pack_start(a, False, False, 0)
            col.pack_start(arrows, False, False, 0)
            bar.pack_start(col, False, False, 0)
        reset = Gtk.Button(label="Reset toolbar")
        reset.connect("clicked", lambda *_: prefs.set("pinnedStyles", list(styles.DEFAULT_PINNED)))
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        top.pack_start(_card(f"In the toolbar ({len(pinned)} of {styles.MAX_PINNED})", [bar]), False, False, 0)
        hb = Gtk.Box()
        hb.pack_end(reset, False, False, 0)
        top.pack_start(hb, False, False, 0)

        # all pointers
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=12,
                           min_children_per_line=4, column_spacing=6, row_spacing=6, homogeneous=True)
        for s in styles.ALL:
            b = Gtk.ToggleButton(active=(s in pinned), relief=Gtk.ReliefStyle.NONE)
            b.get_style_context().add_class("th-thumb")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            v.pack_start(_surface_image(_thumb(s), 52), False, False, 0)
            lbl = Gtk.Label(label=styles.title(s))
            lbl.get_style_context().add_class("th-detail")
            lbl.set_ellipsize(3)
            lbl.set_max_width_chars(10)
            v.pack_start(lbl, False, False, 0)
            b.add(v)
            b.set_tooltip_text("In the toolbar — click to remove" if s in pinned else "Click to add to the toolbar")
            b.connect("toggled", lambda _b, s=s: self._pin(s))
            flow.add(b)
        msg = getattr(self, "pin_message", None)
        parts = [top, _card("All pointers", [flow])]
        if msg:
            m = Gtk.Label(label=msg, xalign=0)
            m.get_style_context().add_class("th-error")
            parts.insert(1, m)
        self.pin_message = None
        return _page(*parts)

    def _use(self, style):
        prefs.pointer_style = style

    def _move(self, style, delta):
        p = prefs.pinned
        i = p.index(style)
        if delta == 0:
            if len(p) > 1:
                p.remove(style)
        else:
            j = i + delta
            if 0 <= j < len(p):
                p[i], p[j] = p[j], p[i]
        prefs.pinned = p

    def _pin(self, style):
        p = prefs.pinned
        if style in p:
            if len(p) <= 1:
                self.pin_message = "Keep at least one pointer in the toolbar."
                self._schedule()
                return
            p.remove(style)
        else:
            if len(p) >= styles.MAX_PINNED:
                self.pin_message = f"The toolbar holds {styles.MAX_PINNED} pointers. Remove one first."
                self._schedule()
                return
            p.append(style)
        prefs.pinned = p

    def _appearance(self):
        lo, hi = POINTER_SIZE_RANGE
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 0.005)
        scale.set_draw_value(False)
        scale.set_value(prefs.pointer_size)
        scale.set_size_request(220, -1)
        set_size = self.quiet("pointerSize")
        scale.connect("value-changed", lambda w: set_size(round(w.get_value(), 3)))
        size = Gtk.Box(spacing=8)
        small = Gtk.Image.new_from_icon_name("tinyhand-on-symbolic", Gtk.IconSize.MENU)
        small.set_pixel_size(12)
        big = Gtk.Image.new_from_icon_name("tinyhand-on-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        big.set_pixel_size(20)
        size.pack_start(small, False, False, 0)
        size.pack_start(scale, False, False, 0)
        size.pack_start(big, False, False, 0)
        return _page(_card("Pointer", [
            _row("Size", size),
            _row("Shadow under the pointer", _switch(lambda: prefs.get("showShadow"), self.quiet("showShadow"))),
        ]))

    def _drawing(self):
        choice = prefs.get("inkChoice")
        swatches = Gtk.Box(spacing=6)
        for cid, title, color in styles.INK_CHOICES:
            b = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
            b.set_tooltip_text(title)
            b.add(_swatch(color, cid == choice))
            b.connect("clicked", lambda _b, cid=cid: prefs.set("inkChoice", cid))
            swatches.pack_start(b, False, False, 0)
        detail = "Matches each pointer." if choice == "match" else \
            f"All pointers draw in {styles.ink_choice_title(choice).lower()}."
        clear = shortcut_label(prefs.get("shortcut.clear"))
        return _page(_card("Ink", [
            _row("Ink colour", swatches, detail=detail),
            _row("Lines fade", _combo(FADE_CHOICES, lambda: float(prefs.get("fadeSeconds")),
                                      self.quiet("fadeSeconds")),
                 detail=f"Clear them any time with {clear}."),
            _row("Ink button in the toolbar", _switch(lambda: prefs.get("showInkButton"), self.quiet("showInkButton")),
                 detail="Change the colour while you present."),
        ]))

    def _sound(self):
        on = prefs.get("sound.hands")
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=3,
                           max_children_per_line=7, column_spacing=8, row_spacing=8, homogeneous=True)
        tiles = [("off", "Off", "audio-volume-muted-symbolic")] + \
                [(cid, title, "audio-x-generic-symbolic") for cid, title in styles.TAP_SOUNDS]
        for cid, title, icon in tiles:
            selected = (not on) if cid == "off" else (on and prefs.get("tapSound") == cid)
            b = Gtk.ToggleButton(active=selected)
            b.get_style_context().add_class("th-tile")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            v.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
            v.pack_start(Gtk.Label(label=title), False, False, 0)
            b.add(v)
            b.connect("clicked", lambda _b, cid=cid: self._pick_sound(cid))
            flow.add(b)
        head = Gtk.Label(label="Tap sound", xalign=0)
        head.get_style_context().add_class("th-section")
        note = Gtk.Label(label="Click a sound to hear it. It plays each time the hand taps.", xalign=0)
        note.get_style_context().add_class("th-detail")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.pack_start(head, False, False, 0)
        box.pack_start(flow, False, False, 0)
        box.pack_start(note, False, False, 0)
        sw = _switch(lambda: prefs.get("sound.laser"), self.quiet("sound.laser"))
        sw.set_sensitive(on)
        laser = _card(None, [_row("Laser dot taps too", sw, detail="Off by default, for quiet pointing.")])
        laser.set_opacity(1 if on else 0.5)
        return _page(box, laser)

    def _pick_sound(self, cid):
        if cid == "off":
            prefs.set("sound.hands", False)
            return
        prefs.set("tapSound", cid, notify=False)
        prefs.set("sound.hands", True, notify=False)
        prefs.changed()
        self.app.overlay.sound.preview(cid)

    def _about(self):
        head = Gtk.Box(spacing=16)
        icon = Gtk.Image.new_from_icon_name("tinyhand", Gtk.IconSize.DIALOG)
        icon.set_pixel_size(72)
        head.pack_start(icon, False, False, 0)
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        t = Gtk.Label(xalign=0)
        t.set_markup("<span size='large' weight='bold'>TinyHand</span>")
        v.pack_start(t, False, False, 0)
        for text in (f"Version {__version__}", "A tiny hand for your screen. Free and open source."):
            lbl = Gtk.Label(label=text, xalign=0)
            lbl.get_style_context().add_class("th-detail")
            v.pack_start(lbl, False, False, 0)
        head.pack_start(v, True, True, 0)

        def link(title, detail, url):
            b = Gtk.LinkButton(uri=url, label=detail)
            return _row(title, b)

        links = _card(None, [
            link("Website", "tinyhand.app", "https://tinyhand.app"),
            link("Source code", "github.com/nilbuild/tinyhand", "https://github.com/nilbuild/tinyhand"),
            link("Made by", "@nilbuild on X", "https://x.com/nilbuild"),
            link("License", "MIT", "https://github.com/nilbuild/tinyhand/blob/main/LICENSE"),
        ])
        reset = Gtk.Button(label="Reset all settings…", relief=Gtk.ReliefStyle.NONE)
        reset.connect("clicked", self._reset)
        hb = Gtk.Box()
        hb.pack_end(reset, False, False, 0)
        return _page(head, links, hb)

    def _reset(self, *_):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.NONE, text="Reset all settings?")
        d.format_secondary_text("Shortcuts, pointers, sounds and drawing go back to how they were "
                                "when you first opened TinyHand.")
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Reset", Gtk.ResponseType.OK)
        d.get_widget_for_response(Gtk.ResponseType.OK).get_style_context().add_class("destructive-action")
        if d.run() == Gtk.ResponseType.OK:
            prefs.reset_all()
            self.app.reregister_hotkeys()
        d.destroy()


def _swatch(color, selected):
    area = Gtk.DrawingArea()
    area.set_size_request(28, 28)

    def draw(widget, cr):
        a = widget.get_allocation()
        cx, cy, r = a.width / 2, a.height / 2, 10
        if selected:
            rgba = widget.get_style_context().lookup_color("theme_selected_bg_color")
            c = rgba[1] if rgba[0] else Gdk.RGBA(0.2, 0.5, 1, 1)
            cr.set_source_rgba(c.red, c.green, c.blue, 1)
            cr.set_line_width(2)
            cr.arc(cx, cy, r + 3, 0, 2 * math.pi)
            cr.stroke()
        if color is None:
            colors = [(1, .23, .19), (1, .8, 0), (.2, .78, .35), (0, .48, 1), (.69, .32, .87), (1, .23, .19)]
            for i in range(6):
                cr.move_to(cx, cy)
                cr.arc(cx, cy, r, i * math.pi / 3, (i + 1) * math.pi / 3)
                cr.close_path()
                cr.set_source_rgb(*colors[i])
                cr.fill()
        else:
            cr.set_source_rgb(*color)
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.fill_preserve()
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.4)
            cr.set_line_width(1)
            cr.stroke()
        return True

    area.connect("draw", draw)
    return area


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
