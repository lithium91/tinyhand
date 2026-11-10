Name:           tinyhand
Version:        %{th_version}
Release:        1%{?dist}
Summary:        A tiny hand on a stick that points at things on your screen
License:        MIT
URL:            https://tinyhand.app
BuildArch:      noarch
Source0:        tinyhand-%{version}.tar.gz

Requires:       python3 >= 3.10
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk3
Requires:       libayatana-appindicator-gtk3
Requires:       gstreamer1-plugins-base
Requires:       gstreamer1-plugins-good
Requires:       python3-xlib
Requires:       (xorg-x11-server-Xwayland or xorg-x11-server-Xorg)
Recommends:     gnome-shell-extension-appindicator

%description
TinyHand turns your mouse pointer into a toy hand on a stick (or a laser
dot) for presentations and screen recordings. Click to tap, drag to draw,
Esc to exit. 36 hands, tap sounds and fading ink.

%prep
%setup -q

%build

%install
make -C linux install DESTDIR=%{buildroot} PREFIX=/usr

%files
/usr/bin/tinyhand
/usr/share/tinyhand
/usr/share/applications/app.tinyhand.TinyHand.desktop
/usr/share/icons/hicolor/512x512/apps/tinyhand.png
/usr/share/icons/hicolor/symbolic/apps/tinyhand-on-symbolic.svg
/usr/share/icons/hicolor/symbolic/apps/tinyhand-off-symbolic.svg
%doc /usr/share/doc/tinyhand/copyright
