"""Offscreen render check: `python3 -m tinyhand --render-test out.png [style]`."""
import time

import cairo


def render_test(args):
    from . import styles
    from .ink import Ink
    from .pointer import Pointer
    from .prefs import prefs
    from .toolbar import Toolbar

    out = args[0] if args else "/tmp/tinyhand-render.png"
    style = args[1] if len(args) > 1 else prefs.pointer_style
    W, H = 1600, 900
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    cr.set_source_rgb(0.93, 0.94, 0.96)
    cr.paint()
    cr.set_source_rgba(0, 0, 0, 0.06)
    for x in range(0, W, 40):
        cr.rectangle(x, 0, 1, H)
    for y in range(0, H, 40):
        cr.rectangle(0, y, W, 1)
    cr.fill()

    ink = Ink()
    ink.color = styles.resolved_ink(prefs.get("inkChoice"), style)
    p = Pointer()
    p.resize(W, H, 1)
    ink.begin((300, 300), p.ink_width)
    for i in range(60):
        ink.extend((300 + i * 6, 300 + 60 * __import__("math").sin(i / 6)))
    ink.end()
    ink.draw(cr, time.monotonic())

    bar = Toolbar()
    bar.select(style)
    bar.place(W / 2, H)
    bar.set_revealed(True, 0)
    bar.show_hint([("Click", "to tap"), ("Drag", "to draw"), ("Hold Alt", "to click for real"), ("Esc", "to exit")])
    bar.draw(cr, time.monotonic() + 1)

    for st, cursor in ((style, (700, 380)), (styles.LASER, (1200, 200)), ("robot", (1400, 500))):
        p.set_style(st)
        p.grip_x = None
        for _ in range(200):
            p.step(cursor, 1 / 120)
        p.draw(cr)
        cr.set_source_rgb(1, 0, 0)
        cr.arc(cursor[0], cursor[1], 2, 0, 6.3)
        cr.fill()
    surf.write_to_png(out)
    print("rendered", out)
    return 0
