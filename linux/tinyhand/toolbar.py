"""The small toolbar at the bottom of the screen, drawn inside the overlay.
Port of Toolbar.swift."""
import math
import time

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

from . import pointer, styles  # noqa: E402
from .prefs import prefs  # noqa: E402

BUTTON = 40
SWATCH = 30
SPACING = 6
PAD_X, PAD_Y = 10, 8
TRAY_PAD_X, TRAY_PAD_Y, TRAY_SPACING = 6, 5, 2
RADIUS = 16
GLASS = (0.11, 0.11, 0.13, 0.86)
FONT = "Sans"


def _rounded(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def _glass(cr, x, y, w, h, r, alpha):
    # soft drop shadow
    for i, a in ((6, 0.05), (3, 0.08), (1, 0.12)):
        _rounded(cr, x - i, y - i + 2, w + 2 * i, h + 2 * i, r + i)
        cr.set_source_rgba(0, 0, 0, a * alpha)
        cr.fill()
    _rounded(cr, x, y, w, h, r)
    cr.set_source_rgba(GLASS[0], GLASS[1], GLASS[2], GLASS[3] * alpha)
    cr.fill_preserve()
    cr.set_source_rgba(1, 1, 1, 0.10 * alpha)
    cr.set_line_width(1)
    cr.stroke()


def _ink_dot(cr, cx, cy, color, r=13 * 40 / 64):
    cr.set_source_rgba(0, 0, 0, 0.35)
    cr.arc(cx + 0.5, cy + 1, r + 1.2, 0, 2 * math.pi)
    cr.fill()
    if color is None:
        colors = [(1, .23, .19), (1, .58, 0), (1, .8, 0), (.2, .78, .35), (0, .48, 1), (.69, .32, .87)]
        for i, c in enumerate(colors):
            cr.move_to(cx, cy)
            cr.arc(cx, cy, r, math.radians(-90 - i * 60 - 60), math.radians(-90 - i * 60))
            cr.close_path()
            cr.set_source_rgb(*c)
            cr.fill()
        return
    cr.set_source_rgb(*color)
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.35)
    cr.save()
    cr.translate(cx - r * 0.2, cy - r * 0.4)
    cr.scale(r * 0.35, r * 0.25)
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()
    cr.fill()


def _speaker(cr, cx, cy, on, alpha):
    cr.set_source_rgba(1, 1, 1, alpha)
    cr.move_to(cx - 9, cy - 3.5)
    cr.line_to(cx - 5, cy - 3.5)
    cr.line_to(cx, cy - 8)
    cr.line_to(cx, cy + 8)
    cr.line_to(cx - 5, cy + 3.5)
    cr.line_to(cx - 9, cy + 3.5)
    cr.close_path()
    cr.fill()
    cr.set_line_width(1.8)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    if on:
        for r in (4.5, 8.5):
            cr.arc(cx + 1, cy, r, -0.85, 0.85)
            cr.stroke()
    else:
        cr.move_to(cx + 3.5, cy - 4)
        cr.line_to(cx + 10.5, cy + 4)
        cr.move_to(cx + 10.5, cy - 4)
        cr.line_to(cx + 3.5, cy + 4)
        cr.stroke()


def _xmark(cr, cx, cy):
    cr.set_source_rgba(1, 1, 1, 0.85)
    cr.set_line_width(2)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for dx in (-1, 1):
        cr.move_to(cx - 6, cy - 6 * dx)
        cr.line_to(cx + 6, cy + 6 * dx)
    cr.stroke()


def _text_layout(cr, markup, size=10):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription(f"{FONT} {size}"))
    layout.set_markup(markup, -1)
    return layout


class Toolbar:
    def __init__(self):
        self.on_pick = None
        self.on_toggle_sound = None
        self.on_exit = None
        self.current = prefs.pointer_style
        self.sound_on = True
        self.ink_open = False
        self.revealed = False
        self._alpha = 0.0
        self._alpha_from = 0.0
        self._alpha_to = 0.0
        self._alpha_t0 = 0.0
        self._alpha_dur = 0.15
        self.hover = None
        self.items = []  # (kind, value, (x, y, w, h))
        self.tray_items = []
        self.rect = (0, 0, 0, 0)
        self.tray_rect = None
        self.hint = None  # (parts, shown_at, hide_at)
        self._thumbs = {}
        self._anchor = (0, 0)

    # ---- state

    def styles(self):
        shown = prefs.pinned
        if self.current not in shown:
            shown = shown + [self.current]
        return shown

    def _thumb(self, style):
        if style not in self._thumbs:
            try:
                self._thumbs[style] = pointer.thumbnail(style, 64)
            except Exception:
                self._thumbs[style] = None
        return self._thumbs[style]

    def place(self, center_x, bottom_y):
        """Center horizontally at center_x, sitting 14 px above bottom_y."""
        self._anchor = (center_x, bottom_y)
        self.layout()

    def layout(self):
        kinds = [("style", s) for s in self.styles()]
        kinds.append(("divider", None))
        if prefs.get("showInkButton"):
            kinds.append(("ink", None))
        else:
            self.ink_open = False
        kinds += [("sound", None), ("exit", None)]
        width = PAD_X * 2
        for i, (k, _) in enumerate(kinds):
            width += (1 if k == "divider" else BUTTON) + (SPACING if i else 0)
        height = BUTTON + 2 * PAD_Y
        x = round(self._anchor[0] - width / 2)
        y = round(self._anchor[1] - 14 - height)
        self.rect = (x, y, width, height)
        self.items = []
        cx = x + PAD_X
        for i, (k, v) in enumerate(kinds):
            if i:
                cx += SPACING
            w = 1 if k == "divider" else BUTTON
            self.items.append((k, v, (cx, y + PAD_Y, w, BUTTON)))
            cx += w
        self._layout_tray()

    def _layout_tray(self):
        self.tray_items = []
        self.tray_rect = None
        if not self.ink_open:
            return
        ink = next((r for k, _, r in self.items if k == "ink"), None)
        if ink is None:
            return
        n = len(styles.INK_CHOICES)
        w = TRAY_PAD_X * 2 + n * SWATCH + (n - 1) * TRAY_SPACING
        h = SWATCH + 2 * TRAY_PAD_Y
        x = round(ink[0] + ink[2] / 2 - w / 2)
        y = self.rect[1] - 8 - h
        self.tray_rect = (x, y, w, h)
        cx = x + TRAY_PAD_X
        for choice in styles.INK_CHOICES:
            self.tray_items.append((choice[0], (cx, y + TRAY_PAD_Y, SWATCH, SWATCH)))
            cx += SWATCH + TRAY_SPACING

    def select(self, style):
        self.current = style
        self.layout()

    def set_ink_open(self, value):
        if value != self.ink_open:
            self.ink_open = value
            self._layout_tray()

    @property
    def frame(self):
        """Area the toolbar occupies, including the ink tray."""
        r = self.rect
        if self.tray_rect:
            t = self.tray_rect
            x0, y0 = min(r[0], t[0]), min(r[1], t[1])
            x1, y1 = max(r[0] + r[2], t[0] + t[2]), max(r[1] + r[3], t[1] + t[3])
            return (x0, y0, x1 - x0, y1 - y0)
        return r

    def damage(self):
        """Everything the toolbar may paint, with room for shadow, tray and hint."""
        x, y, w, h = self.rect
        return (x - 200, y - 120, w + 400, h + 140)

    # ---- reveal animation

    def set_revealed(self, value, now=None):
        if value == self.revealed:
            return False
        now = now or time.monotonic()
        self._alpha_from = self.alpha(now)
        self._alpha_to = 1.0 if value else 0.0
        self._alpha_t0 = now
        self._alpha_dur = 0.15 if value else 0.35
        self.revealed = value
        if not value:
            self.set_ink_open(False)
            self.hover = None
        return True

    def alpha(self, now=None):
        now = now or time.monotonic()
        t = min(1.0, (now - self._alpha_t0) / self._alpha_dur) if self._alpha_dur else 1.0
        return self._alpha_from + (self._alpha_to - self._alpha_from) * t

    def animating(self, now):
        if now - self._alpha_t0 < self._alpha_dur:
            return True
        if self.hint:
            _, shown, hide = self.hint
            if now - shown < 0.25 or (hide and now < hide + 0.35):
                return True
        return False

    def hide_now(self):
        self.revealed = False
        self._alpha_from = self._alpha_to = 0.0
        self.set_ink_open(False)
        self.hint = None
        self.hover = None

    # ---- hint

    def show_hint(self, parts):
        self.hint = (parts, time.monotonic(), None)

    def hide_hint(self):
        if self.hint and self.hint[2] is None:
            self.hint = (self.hint[0], self.hint[1], time.monotonic())

    # ---- input

    @staticmethod
    def _inside(r, x, y):
        return r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]

    def hit(self, x, y):
        """Return (kind, value) under the point, or None."""
        if not self.revealed:
            return None
        for choice, r in self.tray_items:
            if self._inside(r, x, y):
                return ("swatch", choice)
        for k, v, r in self.items:
            if k != "divider" and self._inside(r, x, y):
                return (k, v)
        if self._inside(self.rect, x, y) or (self.tray_rect and self._inside(self.tray_rect, x, y)):
            return ("bar", None)
        return None

    def click(self, x, y):
        hit = self.hit(x, y)
        if hit is None:
            return False
        kind, value = hit
        if kind == "style":
            self.set_ink_open(False)
            if self.on_pick:
                self.on_pick(value)
        elif kind == "ink":
            self.set_ink_open(not self.ink_open)
        elif kind == "swatch":
            prefs.set("inkChoice", value)
            self.set_ink_open(False)
        elif kind == "sound":
            if self.on_toggle_sound:
                self.on_toggle_sound()
        elif kind == "exit":
            if self.on_exit:
                self.on_exit()
        return True

    def tooltip(self, hit):
        if not hit:
            return None
        kind, value = hit
        if kind == "style":
            return styles.title(value)
        if kind == "ink":
            return "Ink colour"
        if kind == "swatch":
            return styles.ink_choice_title(value)
        if kind == "sound":
            return "Tap sound on — click to mute" if self.sound_on else "Tap sound off — click to unmute"
        if kind == "exit":
            return "Exit  (Esc)"
        return None

    # ---- drawing

    def draw(self, cr, now):
        a = self.alpha(now)
        if a > 0.01:
            cr.push_group()
            self._draw_bar(cr)
            cr.pop_group_to_source()
            cr.paint_with_alpha(a)
        self._draw_hint(cr, now)

    def _draw_bar(self, cr):
        x, y, w, h = self.rect
        _glass(cr, x, y, w, h, RADIUS, 1)
        for kind, value, (bx, by, bw, bh) in self.items:
            cx, cy = bx + bw / 2, by + bh / 2
            active = (kind == "style" and value == self.current) or (kind == "ink" and self.ink_open)
            hovered = self.hover is not None and self.hover == (kind, value)
            if active or hovered:
                _rounded(cr, bx, by, bw, bh, 10)
                cr.set_source_rgba(1, 1, 1, 0.18 if active else 0.08)
                cr.fill()
            if kind == "divider":
                cr.set_source_rgba(1, 1, 1, 0.18)
                cr.rectangle(bx, cy - 12, 1, 24)
                cr.fill()
            elif kind == "style":
                thumb = self._thumb(value)
                if thumb:
                    cr.save()
                    s = bw / thumb.get_width()
                    cr.translate(bx, by)
                    cr.scale(s, s)
                    cr.set_source_surface(thumb, 0, 0)
                    cr.get_source().set_filter(cairo.FILTER_GOOD)
                    cr.paint()
                    cr.restore()
            elif kind == "ink":
                _ink_dot(cr, cx, cy, styles.resolved_ink(prefs.get("inkChoice"), self.current))
            elif kind == "sound":
                _speaker(cr, cx, cy, self.sound_on, 0.85 if self.sound_on else 0.45)
            elif kind == "exit":
                _xmark(cr, cx, cy)
        if self.tray_rect:
            tx, ty, tw, th = self.tray_rect
            _glass(cr, tx, ty, tw, th, 14, 1)
            chosen = prefs.get("inkChoice")
            for choice, (sx, sy, sw, sh) in self.tray_items:
                if choice == chosen or self.hover == ("swatch", choice):
                    _rounded(cr, sx, sy, sw, sh, 15)
                    cr.set_source_rgba(1, 1, 1, 0.2 if choice == chosen else 0.1)
                    cr.fill()
                _ink_dot(cr, sx + sw / 2, sy + sh / 2, styles.ink_choice_color(choice), r=13 * 30 / 64)
        tip = self.tooltip(self.hover)
        if tip and self.hover[0] not in ("bar", "divider"):
            r = next((r for k, v, r in self.items if (k, v) == self.hover), None)
            if r is None:
                r = next((r for c, r in self.tray_items if ("swatch", c) == self.hover), None)
            if r:
                layout = _text_layout(cr, f"<span foreground='white'>{_esc(tip)}</span>", 9)
                tw, th = layout.get_pixel_size()
                top = (self.tray_rect[1] if self.tray_rect and self.hover[0] != "swatch" else r[1]) - 8
                lx = r[0] + r[2] / 2 - tw / 2 - 8
                ly = top - th - 8
                _rounded(cr, lx, ly, tw + 16, th + 8, 6)
                cr.set_source_rgba(0.08, 0.08, 0.1, 0.92)
                cr.fill()
                cr.move_to(lx + 8, ly + 4)
                PangoCairo.show_layout(cr, layout)

    def _draw_hint(self, cr, now):
        if not self.hint:
            return
        parts, shown, hide = self.hint
        a = min(1.0, (now - shown) / 0.2)
        if hide:
            a *= max(0.0, 1 - (now - hide) / 0.3)
            if a <= 0:
                self.hint = None
                return
        markup = "    ".join(
            f"<b>{_esc(k)}</b> <span foreground='#ffffffb3'>{_esc(t)}</span>" for k, t in parts)
        layout = _text_layout(cr, f"<span foreground='white'>{markup}</span>", 10)
        tw, th = layout.get_pixel_size()
        w, h = tw + 32, th + 18
        x = self.rect[0] + self.rect[2] / 2 - w / 2
        y = self.rect[1] - 12 - h
        cr.push_group()
        _glass(cr, x, y, w, h, 12, 1)
        cr.move_to(x + 16, y + 9)
        PangoCairo.show_layout(cr, layout)
        cr.pop_group_to_source()
        cr.paint_with_alpha(a)


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
