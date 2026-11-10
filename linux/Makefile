# TinyHand for Linux
#   make run                 run from the source tree
#   make install DESTDIR=…   install under $(PREFIX) (default /usr)
#   make deb / make rpm      build packages into dist/

PREFIX ?= /usr
DESTDIR ?=
VERSION := $(shell cat ../VERSION)
SHARE := $(DESTDIR)$(PREFIX)/share
PY ?= python3

.PHONY: run install hands deb rpm check clean

run:
	PYTHONPATH=$(CURDIR) $(PY) -m tinyhand

hands:
	$(PY) scripts/measure_hands.py

check:
	$(PY) -m py_compile tinyhand/*.py
	PYTHONPATH=$(CURDIR) $(PY) -m tinyhand --render-test /tmp/tinyhand-render.png

install:
	install -d $(SHARE)/tinyhand/tinyhand $(SHARE)/tinyhand/assets/sounds $(SHARE)/tinyhand/data
	install -m 644 tinyhand/*.py $(SHARE)/tinyhand/tinyhand/
	sed -i 's/^__version__ = .*/__version__ = "$(VERSION)"/' $(SHARE)/tinyhand/tinyhand/__init__.py
	install -m 644 ../assets/hand_*.png $(SHARE)/tinyhand/assets/
	install -m 644 ../assets/sounds/*.wav $(SHARE)/tinyhand/assets/sounds/
	install -m 644 data/hands.json $(SHARE)/tinyhand/data/
	install -d $(SHARE)/icons/hicolor/512x512/apps $(SHARE)/icons/hicolor/symbolic/apps
	install -m 644 data/icons/hicolor/512x512/apps/tinyhand.png $(SHARE)/icons/hicolor/512x512/apps/
	install -m 644 data/icons/hicolor/symbolic/apps/*.svg $(SHARE)/icons/hicolor/symbolic/apps/
	install -D -m 644 packaging/app.tinyhand.TinyHand.desktop $(SHARE)/applications/app.tinyhand.TinyHand.desktop
	install -D -m 644 ../LICENSE $(SHARE)/doc/tinyhand/copyright
	install -D -m 755 packaging/tinyhand.sh $(DESTDIR)$(PREFIX)/bin/tinyhand
	sed -i 's|@SHARE@|$(PREFIX)/share/tinyhand|' $(DESTDIR)$(PREFIX)/bin/tinyhand

deb:
	packaging/build-deb.sh

rpm:
	packaging/build-rpm.sh

clean:
	rm -rf build dist
