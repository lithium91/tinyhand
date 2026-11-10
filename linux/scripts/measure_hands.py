#!/usr/bin/env python3
"""Measure the built-in hand images once and write data/hands.json.

Port of HandAsset.measure() from the macOS app. All values are fractions
of the image size, rows counted from the top.
"""
import json
import sys
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "linux"))
from tinyhand.styles import BUILT_IN  # noqa: E402


def measure(path):
    pb = GdkPixbuf.Pixbuf.new_from_file(str(path))
    w, h, stride = pb.get_width(), pb.get_height(), pb.get_rowstride()
    assert pb.get_n_channels() == 4
    data = pb.get_pixels()
    solid = bytes(1 if a > 128 else 0 for a in range(256))
    rows = [data[y * stride + 3:y * stride + 4 * w:4].translate(solid) for y in range(h)]
    counts = [r.count(1) for r in rows]

    def center(y):
        r = rows[y]
        lo = r.find(1)
        if lo < 0:
            return 0.5
        return (lo + r.rfind(1)) / 2 / w

    top = next(y for y, c in enumerate(counts) if c > 0)
    search_end = min(h, top + int(0.45 * h))
    max_w = max(counts[top:search_end])
    fist = next(y for y in range(top, h) if counts[y] > 0.6 * max_w)
    wrist = next(y for y in range(fist, h) if counts[y] < 0.35 * max_w)
    rod_w = counts[min(h - 1, wrist + h // 50)]
    last_row = max(y for y, c in enumerate(counts) if c > 0)
    start = min(h - 1, wrist + h // 33)
    handle = next((y for y in range(start, h) if counts[y] > 1.8 * rod_w), None)
    rod_end = handle if handle is not None else last_row

    min_x, max_x = w, 0
    for y in range(top, wrist):
        r = rows[y]
        lo = r.find(1)
        if lo >= 0:
            min_x = min(min_x, lo)
            max_x = max(max_x, r.rfind(1))

    return {
        "aspect": w / h,
        "handTop": max(0.0, top - 0.004 * h) / h,
        "tip": top / h,
        "wrist": wrist / h,
        "rodEnd": rod_end / h,
        "tipX": center(min(h - 1, top + h // 200)),
        "rodX": center((wrist + rod_end) // 2),
        "handMinX": min_x / w,
        "handMaxX": max_x / w,
    }


def main():
    out = {}
    for sid, _title, _ink in BUILT_IN:
        out[sid] = {k: round(v, 5) for k, v in measure(ROOT / "assets" / f"hand_{sid}.png").items()}
        print(sid, out[sid])
    target = ROOT / "linux" / "data" / "hands.json"
    target.write_text(json.dumps(out, indent=1) + "\n")
    print("wrote", target)


if __name__ == "__main__":
    main()
