#!/bin/sh
# Build dist/tinyhand-<version>-1.noarch.rpm (needs rpmbuild)
set -eu
cd "$(dirname "$0")/.."
VERSION=$(cat ../VERSION)
TOP="$PWD/build/rpm"
rm -rf "$TOP"
mkdir -p "$TOP/SOURCES" "$TOP/SPECS" dist
STAGE="$TOP/tinyhand-$VERSION"
mkdir -p "$STAGE/assets"
cp ../VERSION ../LICENSE "$STAGE/"
cp -r ../assets/sounds "$STAGE/assets/"
cp ../assets/hand_*.png "$STAGE/assets/"
mkdir -p "$STAGE/linux"
cp -r Makefile tinyhand data packaging "$STAGE/linux/"
find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
tar -C "$TOP" -czf "$TOP/SOURCES/tinyhand-$VERSION.tar.gz" "tinyhand-$VERSION"
rpmbuild --define "_topdir $TOP" --define "th_version $VERSION" \
  --define "__brp_python_bytecompile %{nil}" -bb packaging/tinyhand.spec
cp "$TOP"/RPMS/noarch/*.rpm dist/
echo "built dist/$(ls "$TOP"/RPMS/noarch/)"
