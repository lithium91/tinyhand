#!/bin/sh
# Build dist/tinyhand_<version>_all.deb
set -eu
cd "$(dirname "$0")/.."
VERSION=$(cat ../VERSION)
ROOT=build/deb
rm -rf "$ROOT"
make install DESTDIR="$PWD/$ROOT" PREFIX=/usr >/dev/null
mkdir -p "$ROOT/DEBIAN" dist
SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: tinyhand
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, python3-cairo, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, gir1.2-gst-plugins-base-1.0, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, python3-xlib, xwayland | xserver-xorg-core
Recommends: gnome-shell-extension-appindicator
Maintainer: TinyHand for Linux <noreply@tinyhand.app>
Homepage: https://tinyhand.app
Description: tiny hand on a stick that points at things on your screen
 TinyHand turns your mouse pointer into a toy hand on a stick (or a laser
 dot) for presentations and screen recordings. Click to tap, drag to draw,
 Esc to exit. 36 hands, tap sounds and fading ink.
CONTROL
cat > "$ROOT/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
  command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
  command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
fi
POST
cp "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"
sed -i 's/= configure/= remove/' "$ROOT/DEBIAN/postrm"
chmod 755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"
OUT="dist/tinyhand_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT"
echo "built $OUT"
