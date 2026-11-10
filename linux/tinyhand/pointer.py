"""The hand on a stick (and the laser dot). Port of ArmView.swift.

Geometry follows the macOS code, which works in a y-up space with the
grip below the bottom edge of the screen. We keep that math and convert
to GTK's y-down space only when drawing.
"""
import math

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf  # noqa: E402

from . import styles  # noqa: E402
from .prefs import prefs  # noqa: E402

MIN_ROD_FRAC = 0.05
GRIP_LEAN_FRAC = 0.30
GRIP_DEPTH_FRAC = 0.12
GRIP_FOLLOW = 0.08  # per 1/120 s tick in the original
LIFT_FRAC = 0.06
PRESS_DECAY = 0.18  # per 1/120 s tick
LASER_CORE = (1.0, 0.86, 0.82, 0.95)


def _per_tick(rate, dt):
    """Turn a per-120Hz-tick easing rate into one for a frame of dt seconds."""
    return 1 - (1 - rate) ** max(0.0, dt * 120)


class HandImage:
    """A hand PNG, its measurements and display-sized copies."""

    _cache = {}

    def __init__(self, style):
        m = styles.metrics()[style]
        self.__dict__.update(m)
        self.full = GdkPixbuf.Pixbuf.new_from_file(str(styles.hand_path(style)))
        self._display = {}
        self._shadow = {}

    @classmethod
    def load(cls, style):
        if style not in cls._cache:
            if len(cls._cache) >= 3:
                cls._cache.pop(next(iter(cls._cache)))
            cls._cache[style] = cls(style)
        return cls._cache[style]

    def display(self, px_height):
        """Image scaled to about px_height device pixels (stepped by 64 like the original)."""
        step = 64
        full_h = self.full.get_height()
        needed = (int(math.ceil(px_height)) + step - 1) // step * step
        h = full_h if needed >= full_h * 9 // 10 else max(step, needed)
        if h not in self._display:
            w = max(1, round(self.full.get_width() * h / full_h))
            pb = self.full if h == full_h else self.full.scale_simple(w, h, GdkPixbuf.InterpType.HYPER)
            self._display = {h: Gdk.cairo_surface_create_from_pixbuf(pb, 1, None)}
        return self._display[h]

    def shadow(self, small_h):
        """A small, soft silhouette; drawn upscaled with a bilinear filter it reads as a blur.

        small_h is the silhouette height in pixels: the fewer pixels, the softer.
        """
        key = max(12, int(small_h) // 4 * 4)
        if key not in self._shadow:
            full_h = self.full.get_height()
            h = key
            w = max(4, round(self.full.get_width() * h / full_h))
            pad = 2
            small = self.full.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w + 2 * pad, h + 2 * pad)
            cr = cairo.Context(surf)
            Gdk.cairo_set_source_pixbuf(cr, small, pad, pad)
            cr.paint()
            # second, softer pass
            w2, h2 = max(2, (w + 2 * pad) // 2), max(2, (h + 2 * pad) // 2)
            soft = cairo.ImageSurface(cairo.FORMAT_ARGB32, w2, h2)
            c2 = cairo.Context(soft)
            c2.scale(w2 / (w + 2 * pad), h2 / (h + 2 * pad))
            c2.set_source_surface(surf, 0, 0)
            c2.get_source().set_filter(cairo.FILTER_GOOD)
            c2.paint()
            self._shadow = {key: (soft, pad / (w + 2 * pad), pad / (h + 2 * pad))}
        return self._shadow[key]


class Pointer:
    def __init__(self):
        self.style = prefs.pointer_style
        self.image = None
        self.width = 1
        self.height = 1
        self.scale = 1
        self.held = False
        self.hidden = False
        self.press_amount = 0.0
        self.grip_x = None
        self.grip_target = None
        self.cursor = None
        self.bbox = None  # damage box from the last draw, in window coords
        self.set_style(self.style)

    # ---- state

    def set_style(self, style):
        self.style = style if styles.valid(style) else "lavender"
        self.image = None
        if self.style != styles.LASER:
            try:
                self.image = HandImage.load(self.style)
            except Exception as e:  # missing file: fall back like the original
                print("tinyhand: cannot load hand", style, e)
                self.style = styles.LASER

    def resize(self, width, height, scale):
        self.width, self.height, self.scale = width, height, scale
        self.grip_x = None

    def press(self):
        self.press_amount = 1.0

    @property
    def settling(self):
        if self.press_amount > 0.002:
            return True
        if self.grip_x is None or self.grip_target is None:
            return False
        return abs(self.grip_target - self.grip_x) > 0.5

    @property
    def ink_width(self):
        return max(3.0, self.height * 0.0055)

    def step(self, cursor, dt):
        """Advance the animation toward the cursor (window coords, y-down)."""
        self.cursor = cursor
        w = self.width
        target = min(max(cursor[0] + GRIP_LEAN_FRAC * w, w * 0.15), w * 1.05)
        if self.grip_x is None:
            self.grip_x = target
        else:
            self.grip_x += (target - self.grip_x) * _per_tick(GRIP_FOLLOW, dt)
        self.grip_target = target
        if not self.held:
            self.press_amount += (0 - self.press_amount) * _per_tick(PRESS_DECAY, dt)
            if self.press_amount < 0.001:
                self.press_amount = 0.0

    # ---- drawing

    def draw(self, cr):
        """Draw and return the damage box (x, y, w, h) or None."""
        if self.hidden or self.cursor is None:
            self.bbox = None
            return None
        if self.style == styles.LASER:
            self.bbox = self._draw_laser(cr)
        else:
            self.bbox = self._draw_hand(cr)
        return self.bbox

    def predicted_bbox(self):
        """Box the next draw will cover; used to queue damage before drawing."""
        if self.hidden or self.cursor is None:
            return None
        if self.style == styles.LASER:
            return self._laser_geometry()[1]
        return self._hand_geometry()["bbox"]

    def _laser_geometry(self):
        size = prefs.pointer_size
        r = max(4.0, self.height * 0.0038 * size / 0.13) * (1 + 0.2 * self.press_amount)
        glow = r * (2.2 + 1.0 * self.press_amount)
        x, y = self.cursor
        e = r + glow * 1.6 + 2
        return r, (x - e, y - e, 2 * e, 2 * e), glow

    def _draw_laser(self, cr):
        r, box, glow = self._laser_geometry()
        x, y = self.cursor
        red = styles.RED
        g = cairo.RadialGradient(x, y, r * 0.6, x, y, r + glow * 1.6)
        g.add_color_stop_rgba(0, red[0], red[1], red[2], 0.75)
        g.add_color_stop_rgba(0.35, red[0], red[1], red[2], 0.3)
        g.add_color_stop_rgba(1, red[0], red[1], red[2], 0)
        cr.set_source(g)
        cr.arc(x, y, r + glow * 1.6, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*red)
        cr.arc(x, y, r, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(*LASER_CORE)
        cr.arc(x, y, r * 0.45, 0, 2 * math.pi)
        cr.fill()
        return box

    def _hand_geometry(self):
        a = self.image
        H = self.height
        cx, cy_down = self.cursor
        cy = H - cy_down  # y-up
        gx = self.grip_x if self.grip_x is not None else cx
        grip = (gx, -GRIP_DEPTH_FRAC * H)

        dx, dy = cx - grip[0], cy - grip[1]
        reach = math.hypot(dx, dy)
        aim_angle = math.atan2(dy, dx)

        size = prefs.pointer_size
        hand_pts = size * H * (1 - 0.06 * self.press_amount)
        s = hand_pts / (a.wrist - a.handTop)
        width_pts = s * a.aspect
        hand_tip_pts = (a.wrist - a.tip) * s
        tip_off_x = (a.tipX - a.rodX) * width_pts

        along = math.sqrt(max(0.0, reach * reach - tip_off_x * tip_off_x))
        rod_len = max(MIN_ROD_FRAC * H, along - hand_tip_pts)
        tip_angle = math.atan2(rod_len + hand_tip_pts, tip_off_x)
        rotation = aim_angle - tip_angle

        lift = LIFT_FRAC * H * (1 - 0.8 * self.press_amount)
        shadow_off = (lift * 0.6, lift)  # y-down screen offset
        blur = max(1.0, lift * 0.35) + 5 * self.press_amount

        grip_down = (grip[0], H - grip[1])
        # bounding box of the rotated group (+ shadow)
        x0, x1 = -a.rodX * width_pts, (1 - a.rodX) * width_pts
        top = -(rod_len + hand_pts)
        c, sn = math.cos(-rotation), math.sin(-rotation)
        xs, ys = [], []
        for px, py in ((x0, 0), (x1, 0), (x0, top), (x1, top)):
            xs.append(grip_down[0] + px * c - py * sn)
            ys.append(grip_down[1] + px * sn + py * c)
        pad = blur * 2 + 4
        bx0 = min(xs) - pad
        by0 = min(ys) - pad
        bx1 = max(xs) + max(0, shadow_off[0]) + pad
        by1 = max(ys) + max(0, shadow_off[1]) + pad
        return {
            "grip": grip_down, "rotation": rotation, "rod_len": rod_len, "hand_pts": hand_pts,
            "width_pts": width_pts, "shadow_off": shadow_off, "blur": blur,
            "bbox": (bx0, by0, bx1 - bx0, by1 - by0),
        }

    def _draw_hand(self, cr):
        a = self.image
        g = self._hand_geometry()
        hand_pts, rod_len, width_pts = g["hand_pts"], g["rod_len"], g["width_pts"]
        rest_pts = prefs.pointer_size * self.height / (a.wrist - a.handTop)
        img = a.display(rest_pts * self.scale)

        if prefs.get("showShadow"):
            # one silhouette pixel spans about `blur` screen points once stretched
            shadow, padx, pady = a.shadow(rest_pts / max(1.0, g["blur"] * 0.8))
            opacity = 0.26 + 0.02 * self.press_amount
            cr.save()
            cr.translate(g["grip"][0] + g["shadow_off"][0], g["grip"][1] + g["shadow_off"][1])
            cr.rotate(-g["rotation"])
            self._paint_parts(cr, shadow, a, rod_len, hand_pts, width_pts, padx, pady,
                              mask_alpha=opacity)
            cr.restore()

        cr.save()
        cr.translate(*g["grip"])
        cr.rotate(-g["rotation"])
        self._paint_parts(cr, img, a, rod_len, hand_pts, width_pts, 0, 0)
        cr.restore()
        return g["bbox"]

    @staticmethod
    def _paint_parts(cr, surf, a, rod_len, hand_pts, width_pts, padx, pady, mask_alpha=None):
        """Paint the rod (stretched) and the hand from one image.

        padx/pady are the transparent margins (as fractions) around a shadow image.
        """
        sw, sh = surf.get_width(), surf.get_height()
        inner_w = sw * (1 - 2 * padx)
        inner_h = sh * (1 - 2 * pady)
        x0 = -a.rodX * width_pts
        sx = width_pts / inner_w
        parts = (
            # (src top, src bottom, dest top, dest height)
            (a.wrist, a.rodEnd, -rod_len, rod_len),
            (a.handTop, a.wrist, -(rod_len + hand_pts), hand_pts),
        )
        for src0, src1, dst_top, dst_h in parts:
            src_h = (src1 - src0) * inner_h
            if src_h <= 0 or dst_h <= 0:
                continue
            sy = dst_h / src_h
            cr.save()
            if mask_alpha is None:
                # overlap the seam by a hair so the rod and hand meet cleanly
                cr.rectangle(x0 - 1, dst_top - 0.5, width_pts + 2, dst_h + 1)
            else:
                # a shadow must not double up on the seam
                cr.rectangle(x0 - width_pts, dst_top, width_pts * 3, dst_h)
            cr.clip()
            cr.translate(x0, dst_top)
            cr.scale(sx, sy)
            src_x = -padx * sw
            src_y = -(pady * sh + src0 * inner_h)
            if mask_alpha is None:
                cr.set_source_surface(surf, src_x, src_y)
                pat = cr.get_source()
                pat.set_extend(cairo.EXTEND_PAD)
                pat.set_filter(cairo.FILTER_GOOD)
                cr.paint()
            else:
                cr.set_source_rgba(0, 0, 0, mask_alpha)
                pat = cairo.SurfacePattern(surf)
                m = cairo.Matrix(x0=-src_x, y0=-src_y)
                pat.set_matrix(m)
                pat.set_filter(cairo.FILTER_BILINEAR)
                pat.set_extend(cairo.EXTEND_PAD)
                cr.mask(pat)
            cr.restore()


def thumbnail(style, px=64):
    """Square thumbnail of the hand (no stick), or a laser dot."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, px, px)
    cr = cairo.Context(surf)
    if style == styles.LASER:
        c = px / 2
        red = styles.RED
        g = cairo.RadialGradient(c, c, 0, c, c, px * 0.28)
        g.add_color_stop_rgba(0, red[0], red[1], red[2], 0.55)
        g.add_color_stop_rgba(1, red[0], red[1], red[2], 0)
        cr.set_source(g)
        cr.arc(c, c, px * 0.28, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*red)
        cr.arc(c, c, px * 7 / 64, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(*LASER_CORE)
        cr.arc(c, c, px * 3 / 64, 0, 2 * math.pi)
        cr.fill()
        return surf
    a = HandImage.load(style) if style in HandImage._cache else None
    m = styles.metrics()[style]
    full = a.full if a else GdkPixbuf.Pixbuf.new_from_file(str(styles.hand_path(style)))
    w, h = full.get_width(), full.get_height()
    hand_w = (m["handMaxX"] - m["handMinX"]) * w
    hand_h = (m["wrist"] - m["handTop"]) * h
    side = max(hand_w, hand_h) * 1.06
    cx = (m["handMinX"] + m["handMaxX"]) / 2 * w
    cy = (m["handTop"] + m["wrist"]) / 2 * h
    k = px / side
    small = full.scale_simple(max(1, round(w * k)), max(1, round(h * k)), GdkPixbuf.InterpType.HYPER)
    Gdk.cairo_set_source_pixbuf(cr, small, px / 2 - cx * k, px / 2 - cy * k)
    cr.paint()
    return surf
