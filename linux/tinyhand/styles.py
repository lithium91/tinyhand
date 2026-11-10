"""Pointer styles, ink colours and where their files live."""
import json
import os
from functools import lru_cache
from pathlib import Path


def hexrgb(v):
    return (((v >> 16) & 0xFF) / 255, ((v >> 8) & 0xFF) / 255, (v & 0xFF) / 255)


PURPLE = (0.53, 0.33, 0.95)
RED = (1.0, 0.16, 0.12)

BUILT_IN = [
    ("lavender", "Lavender toy", PURPLE),
    ("glove", "Cursor glove", PURPLE),
    ("coral", "Coral vinyl", RED),
    ("plush", "Plush", hexrgb(0x2F86F0)),
    ("robot", "Robot", hexrgb(0x16A87A)),
    ("pink", "Bubblegum", hexrgb(0xEE4F98)),
    ("blue", "Sky", hexrgb(0x2F86F0)),
    ("mint", "Mint", hexrgb(0x16A87A)),
    ("lemon", "Lemon", hexrgb(0xF2B705)),
    ("black", "Midnight", hexrgb(0x1D1D21)),
    ("chrome", "Chrome", hexrgb(0x6B7380)),
    ("holo", "Holo", PURPLE),
    ("fuzzy", "Fuzzy", PURPLE),
    ("wood", "Wood", hexrgb(0x9A5E2C)),
    ("marble", "Marble", hexrgb(0x6B7380)),
    ("terrazzo", "Terrazzo", hexrgb(0xF0561D)),
    ("glass", "Glass", hexrgb(0x1597E5)),
    ("jelly", "Jelly", hexrgb(0xA33FE6)),
    ("pastel", "Pastel", hexrgb(0xEE4F98)),
    ("pixel", "Pixel", hexrgb(0x1D1D21)),
    ("lowpoly", "Low poly", PURPLE),
    ("knit", "Knit", PURPLE),
    ("skeleton", "Skeleton", hexrgb(0x9A5E2C)),
    ("astro", "Astronaut", hexrgb(0x2F86F0)),
    ("space", "Space", RED),
    ("monster", "Monster", hexrgb(0x3E9E2E)),
    ("water", "Water", hexrgb(0x1597E5)),
    ("lava", "Lava", hexrgb(0xF0561D)),
    ("grass", "Grass", hexrgb(0x3E9E2E)),
    ("cactus", "Cactus", hexrgb(0x3E9E2E)),
    ("choco", "Chocolate", hexrgb(0x9A5E2C)),
    ("cloud", "Cloud", hexrgb(0x2F86F0)),
    ("mech", "Mech", hexrgb(0xF0561D)),
    ("neon", "Neon", hexrgb(0xE0309A)),
    ("leaf", "Leaf", hexrgb(0x3E9E2E)),
    ("cookie", "Gingerbread", hexrgb(0x9A5E2C)),
]

LASER = "laser"
ALL = [s[0] for s in BUILT_IN] + [LASER]
DEFAULT_PINNED = ["lavender", "glove", "coral", "plush", "robot", LASER]
MAX_PINNED = 8

_BY_ID = {s[0]: s for s in BUILT_IN}


def title(style):
    if style == LASER:
        return "Laser dot"
    return _BY_ID[style][1] if style in _BY_ID else style


def ink_color(style):
    if style == LASER:
        return RED
    return _BY_ID[style][2] if style in _BY_ID else PURPLE


def valid(style):
    return style in _BY_ID or style == LASER


INK_CHOICES = [
    ("match", "Match the pointer", None),
    ("red", "Red", RED),
    ("orange", "Orange", hexrgb(0xFF8A00)),
    ("yellow", "Yellow", hexrgb(0xFFCC00)),
    ("green", "Green", hexrgb(0x30C25A)),
    ("blue", "Blue", hexrgb(0x0A84FF)),
    ("purple", "Purple", hexrgb(0x8754F2)),
    ("white", "White", hexrgb(0xFFFFFF)),
    ("black", "Black", hexrgb(0x1D1D21)),
]
_INK = {c[0]: c for c in INK_CHOICES}


def ink_choice_color(choice):
    return _INK.get(choice, INK_CHOICES[0])[2]


def ink_choice_title(choice):
    return _INK.get(choice, INK_CHOICES[0])[1]


def resolved_ink(choice, style):
    return ink_choice_color(choice) or ink_color(style)


TAP_SOUNDS = [
    ("thock", "Thock"),
    ("click", "Click"),
    ("pop", "Pop"),
    ("wood", "Wood block"),
    ("boop", "Boop"),
    ("squeak", "Squeak"),
]


# ---------------------------------------------------------------- files

def _candidates():
    env = os.environ.get("TINYHAND_DATA")
    if env:
        yield Path(env)
    here = Path(__file__).resolve().parent
    yield here.parent.parent  # running from the source tree: <repo>/linux/tinyhand
    yield Path("/usr/share/tinyhand")
    yield Path("/usr/local/share/tinyhand")


@lru_cache(maxsize=1)
def data_root():
    for root in _candidates():
        if (root / "assets" / "hand_lavender.png").exists():
            return root
    raise FileNotFoundError("TinyHand assets not found; set TINYHAND_DATA")


def asset(name):
    return data_root() / "assets" / name


def hand_path(style):
    return asset(f"hand_{style}.png")


def sound_path(choice):
    return asset(f"sounds/tap_{choice}.wav")


@lru_cache(maxsize=1)
def metrics():
    root = data_root()
    for p in (root / "linux" / "data" / "hands.json", root / "data" / "hands.json"):
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError("hands.json not found")
