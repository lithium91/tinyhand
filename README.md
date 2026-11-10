<img src="./.github/logo.png" width="80" />

# TinyHand for Linux

[![Linux packages](https://github.com/lithium91/tinyhand/actions/workflows/linux.yml/badge.svg)](https://github.com/lithium91/tinyhand/actions/workflows/linux.yml)
[![Platform: Linux](https://img.shields.io/badge/platform-Linux-lightgrey)](linux/README.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

A tiny hand on a stick that points at things on your screen. A Linux port of
[TinyHand](https://github.com/nilbuild/tinyhand) by [@nilbuild](https://x.com/nilbuild).

<img src="./.github/banner.jpg" alt="TinyHand: a tiny hand on a stick" />

Made for **Ubuntu 26.04 LTS** (GNOME on Wayland). Also runs on Fedora, KDE Plasma and
any X11 desktop.

Looking for the Mac app? Get it from [the original project](https://github.com/nilbuild/tinyhand/releases/latest)
or [tinyhand.app](https://tinyhand.app).

## Install

Download the `.deb` or `.rpm` from [Releases](https://github.com/lithium91/tinyhand/releases), then:

```bash
sudo apt install ./tinyhand_*_all.deb        # Ubuntu, Debian
sudo dnf install ./tinyhand-*.noarch.rpm     # Fedora
```

Open **TinyHand** from the app grid. It starts at login from then on.

On GNOME the tray icon needs the *AppIndicator and KStatusNotifierItem Support* extension
(Ubuntu has it on by default). Without it, use the shortcuts and open TinyHand again from
the app grid to get to Settings.

## Use

| | |
|---|---|
| **Ctrl+Alt+H**, or the tray icon | Turn the pointer on or off |
| Tray icon menu, or open TinyHand again | Settings |
| Click | Tap (nothing underneath gets clicked) |
| Hold and drag | Draw on the screen |
| Hold **Alt** and click | Click the app underneath for real |
| **Ctrl+Alt+X** | Clear the drawing |
| **Esc** | Clear everything and turn the pointer off |

While the pointer is on, a small toolbar at the bottom of the screen lets you pick one of
36 hands or a laser dot, change the ink colour, mute the tap sound, or exit.

While the pointer is on, TinyHand has the keyboard, so you can't type into other apps
until you turn it off. Differences from the Mac app, building from source and the
code layout are in [linux/README.md](linux/README.md).

## Build

```bash
cd linux
make run      # run from the source tree
make deb rpm  # build packages into linux/dist/
```

## License

MIT. See [LICENSE](LICENSE). Hands, sounds and icons come from the original TinyHand.
