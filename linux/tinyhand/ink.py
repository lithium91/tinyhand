"""Strokes drawn on the screen. Port of Ink.swift."""
import math
import time

from .prefs import prefs

FADE_DURATION = 0.6
SHADOW_OFFSET = (1.0, 1.5)  # y-down
SHADOW_ALPHA = 0.18


class Stroke:
    __slots__ = ("points", "color", "width", "fade_at", "box")

    def __init__(self, point, color, width):
        self.points = [point]
        self.color = color
        self.width = width
        self.fade_at = None
        self.box = None
        self._grow(point)

    def _grow(self, p):
        pad = self.width / 2 + 4
        x0, y0 = p[0] - pad, p[1] - pad
        x1, y1 = p[0] + pad + SHADOW_OFFSET[0], p[1] + pad + SHADOW_OFFSET[1]
        if self.box is None:
            self.box = [x0, y0, x1, y1]
        else:
            b = self.box
            b[0], b[1], b[2], b[3] = min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)

    def rect(self):
        b = self.box
        return (b[0], b[1], b[2] - b[0], b[3] - b[1])

    def opacity(self, now):
        if self.fade_at is None or now < self.fade_at:
            return 1.0
        t = min(1.0, (now - self.fade_at) / FADE_DURATION)
        return 1.0 - t * t  # ease in

    def path(self, cr):
        pts = self.points
        cr.move_to(*pts[0])
        if len(pts) == 1:
            cr.line_to(*pts[0])
            return
        # quadratic smoothing through midpoints, as in the original
        x, y = pts[0]
        for i in range(1, len(pts)):
            px, py = pts[i - 1]
            p = pts[i]
            mx, my = (px + p[0]) / 2, (py + p[1]) / 2
            # quad (px,py) -> mid, expressed as a cubic from the current point
            cx0, cy0 = cr.get_current_point()
            cr.curve_to(cx0 + 2 / 3 * (px - cx0), cy0 + 2 / 3 * (py - cy0),
                        mx + 2 / 3 * (px - mx), my + 2 / 3 * (py - my), mx, my)
        cr.line_to(*pts[-1])


class Ink:
    def __init__(self):
        self.color = (0.53, 0.33, 0.95)
        self.strokes = []
        self.current = None

    @property
    def keep(self):
        return float(prefs.get("fadeSeconds")) <= 0

    @property
    def drawing(self):
        return self.current is not None

    def begin(self, point, width):
        self.current = Stroke(point, self.color, width)
        self.strokes.append(self.current)
        return self.current.rect()

    def extend(self, point):
        """Add a point; returns the damaged rect or None."""
        s = self.current
        if s is None:
            return None
        last = s.points[-1]
        if math.hypot(point[0] - last[0], point[1] - last[1]) < 1.5:
            return None
        s.points.append(point)
        s._grow(point)
        pad = s.width / 2 + 4
        x0, y0 = min(last[0], point[0]) - pad, min(last[1], point[1]) - pad
        x1, y1 = max(last[0], point[0]) + pad + 2, max(last[1], point[1]) + pad + 2
        # the smoothed curve can bow toward the previous point; include it
        if len(s.points) > 2:
            pp = s.points[-3]
            x0, y0 = min(x0, pp[0] - pad), min(y0, pp[1] - pad)
            x1, y1 = max(x1, pp[0] + pad), max(y1, pp[1] + pad)
        return (x0, y0, x1 - x0, y1 - y0)

    def end(self):
        s = self.current
        if s is None:
            return
        self.current = None
        if not self.keep:
            s.fade_at = time.monotonic() + max(0.5, float(prefs.get("fadeSeconds")))

    def clear(self):
        """Remove everything; returns the rects that need repainting."""
        rects = [s.rect() for s in self.strokes]
        self.strokes = []
        self.current = None
        return rects

    def fading(self, now):
        """Rects of strokes whose opacity is changing now; drops finished ones."""
        rects, alive = [], []
        for s in self.strokes:
            if s.fade_at is not None and now >= s.fade_at:
                rects.append(s.rect())
                if now >= s.fade_at + FADE_DURATION:
                    continue
            alive.append(s)
        self.strokes = alive
        return rects

    def next_fade(self):
        times = [s.fade_at for s in self.strokes if s.fade_at is not None]
        return min(times) if times else None

    def draw(self, cr, now):
        cr.save()
        cr.set_line_cap(1)  # ROUND
        cr.set_line_join(1)
        for s in self.strokes:
            a = s.opacity(now)
            if a <= 0:
                continue
            cr.set_line_width(s.width)
            cr.save()
            cr.translate(*SHADOW_OFFSET)
            s.path(cr)
            cr.restore()
            cr.set_source_rgba(0, 0, 0, SHADOW_ALPHA * a)
            cr.stroke()
            s.path(cr)
            cr.set_source_rgba(s.color[0], s.color[1], s.color[2], a)
            cr.stroke()
        cr.restore()
