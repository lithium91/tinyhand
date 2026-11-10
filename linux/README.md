# TinyHand for Linux

A port of [TinyHand](../README.md) to Linux: a tiny hand on a stick that points at
things on your screen. Python 3 + GTK 3 + Cairo, no build step.

Target: **Ubuntu 26.04 LTS** (GNOME on Wayland). Also runs on any X11 desktop and
on KDE Plasma / other Wayland desktops through XWayland.

## Install

```bash
sudo apt install ./tinyhand_1.0.2_all.deb      # Ubuntu / Debian
sudo dnf install ./tinyhand-1.0.2-1.noarch.rpm # Fedora
```

Then open **TinyHand** from the app grid. It starts at login from then on
(Settings → General → Startup).

## Use

| | |
|---|---|
| **Ctrl+Alt+H** (or tray icon → Turn Pointer On) | Turn the pointer on or off |
| Tray icon menu, or launch TinyHand again | Settings |
| Click | Tap (nothing underneath gets clicked) |
| Hold and drag | Draw on the screen |
| Hold **Alt** and click | Click the app underneath for real |
| **Ctrl+Alt+X** | Clear the drawing |
| **Esc** | Clear everything and turn the pointer off |

While the pointer is on, a small toolbar at the bottom of the screen lets you pick one of
36 hands or a laser dot, change the ink colour, mute the tap sound, or exit.

Command line (talks to the running instance):

```bash
tinyhand --toggle | --on | --off | --clear | --settings | --quit
```

## How it differs from the macOS app

The macOS app keeps a click-through overlay and steals clicks with a system event
tap. Wayland doesn't allow that, so on Linux the overlay is a transparent,
always-on-top window on every monitor that takes the mouse itself. The same code
runs on X11 and under XWayland. The trade-offs:

* **Top bar and dock stay usable.** The overlay covers the work area, not the whole
  monitor, so the top bar and the dock stay visible. Over them you get the normal
  cursor and real clicks, like the menu bar and Dock in the Mac app; the hand
  can't point at them.

* **Keyboard focus.** While the pointer is on, the overlay has the keyboard
  focus (that is how Esc and "hold Alt to click for real" work), so you can't
  type into other apps until you turn it off.
* **Hold Alt to click for real.** On X11 you can click as many times as you like
  while Alt is held. On Wayland, once a real click moves focus to another app,
  TinyHand takes the mouse back right after that click: one real click (or
  drag) per Alt press. Scrolling also works only while Alt is held.
* **Shortcuts.** On X11 TinyHand grabs them itself. On GNOME Wayland they are
  saved as GNOME custom shortcuts (Settings → Keyboard → Custom Shortcuts) that
  run `tinyhand --toggle` / `tinyhand --clear`. On other Wayland desktops, bind
  those commands in your compositor's shortcut settings.
* **Tray icon.** GNOME needs the "AppIndicator and KStatusNotifierItem Support"
  extension (enabled by default on Ubuntu). Without it, use the shortcuts and
  launch TinyHand again to open Settings.
* **Not ported:** the "make your own hand" wizard and Sparkle self-updates
  (updates come with new packages).

## Develop

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  gir1.2-ayatanaappindicator3-0.1 gir1.2-gst-plugins-base-1.0 \
  gstreamer1.0-plugins-good python3-xlib
make run      # run from the source tree
make check    # byte-compile and render /tmp/tinyhand-render.png offscreen
make deb rpm  # packages in dist/ (rpm needs rpmbuild)
make hands    # re-measure the hand images into data/hands.json
```

Code map (each file mirrors its Swift original):

| File | What |
|---|---|
| `tinyhand/app.py` | single instance, command line, tray/shortcut wiring |
| `tinyhand/overlay.py` | overlay windows, input, click-for-real, frame loop |
| `tinyhand/pointer.py` | the hand on a stick and the laser dot |
| `tinyhand/ink.py` | strokes that fade |
| `tinyhand/toolbar.py` | the toolbar, ink tray and first-run hint |
| `tinyhand/hotkeys.py` | X11 grabs / GNOME custom shortcuts |
| `tinyhand/settings.py`, `welcome.py`, `tray.py` | windows and menu |
| `tinyhand/prefs.py` | settings in `~/.config/tinyhand/settings.json` |
